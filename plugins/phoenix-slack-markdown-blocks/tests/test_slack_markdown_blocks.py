from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import types
import unittest
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackMarkdownBlocksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_hermes_home = os.environ.get("HERMES_HOME")
        os.environ.pop("HERMES_HOME", None)
        install_hermes_stubs()
        self.plugin = load_plugin_module()
        self.plugin.register(types.SimpleNamespace())

    def tearDown(self) -> None:
        if self._original_hermes_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._original_hermes_home
        for name in list(sys.modules):
            if (
                name == self.plugin.__name__
                or name == "gateway"
                or name.startswith("gateway.")
                or name == "tools"
                or name.startswith("tools.")
                or name == "aiohttp"
            ):
                sys.modules.pop(name, None)

    def test_send_uses_markdown_blocks_and_fallback_text(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        adapter = FakeSlackAdapter()
        content = "| Name | Value |\n| --- | --- |\n| **bold** | [link](https://example.com) |"

        result = asyncio.run(slack_module.SlackAdapter.send(adapter, "C123", content))

        self.assertTrue(result.success)
        payload = adapter.client.posted[0]
        self.assertEqual(payload["channel"], "C123")
        self.assertEqual(payload["blocks"], [{"type": "markdown", "text": content}])
        self.assertNotIn("mrkdwn", payload)
        self.assertIn("*bold*", payload["text"])
        self.assertNotEqual(payload["text"], content)

    def test_edit_message_uses_markdown_blocks(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        adapter = FakeSlackAdapter()
        content = "| A | B |\n| --- | --- |\n| **x** | y |"

        result = asyncio.run(
            slack_module.SlackAdapter.edit_message(adapter, "C123", "1700000000.000100", content)
        )

        self.assertTrue(result.success)
        payload = adapter.client.updated[0]
        self.assertEqual(payload["channel"], "C123")
        self.assertEqual(payload["ts"], "1700000000.000100")
        self.assertEqual(payload["blocks"], [{"type": "markdown", "text": content}])
        self.assertNotIn("mrkdwn", payload)

    def test_send_message_tool_slack_branch_preserves_raw_markdown(self) -> None:
        tool_module = sys.modules["tools.send_message_tool"]
        config_module = sys.modules["gateway.config"]
        sent: list[str] = []

        async def fake_send_slack(_token: str, _chat_id: str, message: str) -> dict[str, Any]:
            sent.append(message)
            return {"success": True, "platform": "slack", "chat_id": _chat_id, "message_id": "1"}

        tool_module._send_slack = fake_send_slack
        content = "| A | B |\n| --- | --- |\n| **raw** | value |"

        result = asyncio.run(
            tool_module._send_to_platform(
                config_module.Platform.SLACK,
                types.SimpleNamespace(token="xoxb-test"),
                "C123",
                content,
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(sent, [content])

    def test_send_slack_uses_blocks_without_mrkdwn(self) -> None:
        tool_module = sys.modules["tools.send_message_tool"]
        aiohttp_stub = install_aiohttp_stub()
        content = "| A | B |\n| --- | --- |\n| **raw** | value |"

        result = asyncio.run(tool_module._send_slack("xoxb-test", "C123", content))

        self.assertTrue(result["success"])
        payload = aiohttp_stub.payloads[0]
        self.assertEqual(payload["channel"], "C123")
        self.assertEqual(payload["text"], content)
        self.assertEqual(payload["blocks"], [{"type": "markdown", "text": content}])
        self.assertNotIn("mrkdwn", payload)

    def test_status_only_mode_keeps_status_without_loading_messages(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        self.plugin.load_profile_config = lambda: {
            "display": {"platforms": {"slack": {"assistant_status": "status_only"}}}
        }
        self.assertTrue(self.plugin.patch_slack_assistant_status())

        adapter = slack_module.SlackAdapter()
        asyncio.run(slack_module.SlackAdapter.send_typing(adapter, "C123", {"thread_ts": "T123"}))

        self.assertEqual(
            adapter.client.statuses,
            [
                {
                    "channel_id": "C123",
                    "thread_ts": "T123",
                    "status": "is thinking...",
                }
            ],
        )

    def test_quiet_loading_mode_uses_blank_loading_message(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        self.plugin.load_profile_config = lambda: {
            "display": {"platforms": {"slack": {"assistant_status": "quiet_loading"}}}
        }
        self.assertTrue(self.plugin.patch_slack_assistant_status())

        adapter = slack_module.SlackAdapter()
        asyncio.run(slack_module.SlackAdapter.send_typing(adapter, "C123", {"thread_ts": "T123"}))

        self.assertEqual(
            adapter.client.statuses,
            [
                {
                    "channel_id": "C123",
                    "thread_ts": "T123",
                    "status": "is thinking...",
                    "loading_messages": ["\u200b"],
                }
            ],
        )

    def test_loading_message_failure_falls_back_to_status_only(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        self.plugin.load_profile_config = lambda: {
            "display": {"platforms": {"slack": {"assistant_status": "quiet_loading"}}}
        }
        self.assertTrue(self.plugin.patch_slack_assistant_status())

        adapter = slack_module.SlackAdapter()
        adapter.client.fail_status_with_loading = True
        asyncio.run(slack_module.SlackAdapter.send_typing(adapter, "C123", {"thread_ts": "T123"}))

        self.assertEqual(
            adapter.client.statuses,
            [
                {
                    "channel_id": "C123",
                    "thread_ts": "T123",
                    "status": "is thinking...",
                    "loading_messages": ["\u200b"],
                },
                {
                    "channel_id": "C123",
                    "thread_ts": "T123",
                    "status": "is thinking...",
                },
            ],
        )

    def test_assistant_status_off_suppresses_status(self) -> None:
        slack_module = sys.modules["gateway.platforms.slack"]
        self.plugin.load_profile_config = lambda: {
            "display": {"platforms": {"slack": {"assistant_status": "off"}}}
        }
        self.assertTrue(self.plugin.patch_slack_assistant_status())

        adapter = slack_module.SlackAdapter()
        asyncio.run(slack_module.SlackAdapter.send_typing(adapter, "C123", {"thread_ts": "T123"}))

        self.assertEqual(adapter.client.statuses, [])


class FakeClient:
    def __init__(self) -> None:
        self.posted: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.statuses: list[dict[str, Any]] = []
        self.fail_status_with_loading = False

    async def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        self.posted.append(kwargs)
        return {"ts": "1700000000.000100"}

    async def chat_update(self, **kwargs: Any) -> dict[str, Any]:
        self.updated.append(kwargs)
        return {"ok": True}

    async def assistant_threads_setStatus(self, **kwargs: Any) -> dict[str, Any]:
        self.statuses.append(kwargs)
        if self.fail_status_with_loading and "loading_messages" in kwargs:
            raise RuntimeError("invalid_arguments")
        return {"ok": True}


class FakeSlackAdapter:
    MAX_MESSAGE_LENGTH = 40000
    _BOT_TS_MAX = 100

    def __init__(self) -> None:
        self.client = FakeClient()
        self._app = types.SimpleNamespace(client=self.client)
        self._channel_team: dict[str, str] = {}
        self._team_clients: dict[str, Any] = {}
        self.config = types.SimpleNamespace(extra={})
        self._bot_message_ts: set[str] = set()
        self._active_status_threads: dict[str, str] = {}
        self.stopped_typing = False

    def _get_client(self, _chat_id: str) -> FakeClient:
        return self.client

    def _pop_slash_context(self, _chat_id: str) -> None:
        return None

    def _resolve_thread_ts(self, reply_to: str | None, metadata: dict[str, Any] | None) -> str | None:
        return reply_to or (metadata or {}).get("thread_ts")

    async def stop_typing(self, _chat_id: str) -> None:
        self.stopped_typing = True

    async def send_typing(self, _chat_id: str, _metadata: dict[str, Any] | None = None) -> None:
        return None

    def format_message(self, content: str) -> str:
        return content.replace("**bold**", "*bold*").replace("**x**", "*x*")

    def truncate_message(self, content: str, _max_length: int) -> list[str]:
        return [content]

    async def send(self, *_args: Any, **_kwargs: Any) -> SendResult:
        return SendResult(success=True)

    async def edit_message(self, *_args: Any, **_kwargs: Any) -> SendResult:
        return SendResult(success=True)


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    raw_response: dict[str, Any] | None = None
    error: str | None = None


def load_plugin_module():
    module_name = f"phoenix_slack_markdown_blocks_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def install_hermes_stubs() -> None:
    gateway_module = types.ModuleType("gateway")
    config_module = types.ModuleType("gateway.config")
    platforms_module = types.ModuleType("gateway.platforms")
    base_module = types.ModuleType("gateway.platforms.base")
    slack_module = types.ModuleType("gateway.platforms.slack")
    tools_module = types.ModuleType("tools")
    send_message_tool_module = types.ModuleType("tools.send_message_tool")

    class Platform(Enum):
        SLACK = "slack"
        DISCORD = "discord"

    class BasePlatformAdapter:
        @staticmethod
        def truncate_message(content: str, _max_length: int) -> list[str]:
            return [content]

    class SlackAdapter(FakeSlackAdapter):
        pass

    async def original_send_to_platform(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        return {"delegated": "true"}

    async def original_send_slack(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        return {"original": "true"}

    config_module.Platform = Platform
    base_module.BasePlatformAdapter = BasePlatformAdapter
    base_module.resolve_proxy_url = lambda: None
    base_module.proxy_kwargs_for_aiohttp = lambda _proxy: ({}, {})
    slack_module.SlackAdapter = SlackAdapter
    slack_module.SendResult = SendResult
    slack_module.logger = types.SimpleNamespace(
        error=lambda *_args, **_kwargs: None,
        info=lambda *_args, **_kwargs: None,
    )
    send_message_tool_module._send_to_platform = original_send_to_platform
    send_message_tool_module._send_slack = original_send_slack
    send_message_tool_module._error = lambda message: {"error": message}

    sys.modules["gateway"] = gateway_module
    sys.modules["gateway.config"] = config_module
    sys.modules["gateway.platforms"] = platforms_module
    sys.modules["gateway.platforms.base"] = base_module
    sys.modules["gateway.platforms.slack"] = slack_module
    sys.modules["tools"] = tools_module
    sys.modules["tools.send_message_tool"] = send_message_tool_module


def install_aiohttp_stub():
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.payloads = []

    class ClientTimeout:
        def __init__(self, total: int) -> None:
            self.total = total

    class Response:
        async def __aenter__(self) -> "Response":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def json(self) -> dict[str, Any]:
            return {"ok": True, "ts": "1700000000.000100"}

    class ClientSession:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "ClientSession":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        def post(self, _url: str, *, json: dict[str, Any], **_kwargs: Any) -> Response:
            aiohttp_module.payloads.append(json)
            return Response()

    aiohttp_module.ClientTimeout = ClientTimeout
    aiohttp_module.ClientSession = ClientSession
    sys.modules["aiohttp"] = aiohttp_module
    return aiohttp_module


if __name__ == "__main__":
    unittest.main()
