from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import types
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = PLUGIN_ROOT.parents[1]


class PhoenixComposioSessionTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name.startswith("phoenix_composio_session_test_"):
                sys.modules.pop(name, None)

        for name in (
            "COMPOSIO_TOOL_ROUTER_SESSION_ID",
            "COMPOSIO_MISSING_TOOL_URL_TEMPLATE",
        ):
            os.environ.pop(name, None)

    def test_extracts_slack_context_with_and_without_user_id(self) -> None:
        plugin = load_plugin_package()

        context = plugin.slack_context.extract_slack_context(slack_event())

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.slack_team_id, "T123")
        self.assertEqual(context.slack_user_id, "U123")
        self.assertEqual(context.slack_channel_id, "C123")
        self.assertEqual(context.slack_thread_id, "1700000000.000100")

        missing_user_context = plugin.slack_context.extract_slack_context(slack_event(user_id=None))

        self.assertIsNotNone(missing_user_context)
        assert missing_user_context is not None
        self.assertIsNone(missing_user_context.slack_user_id)
        self.assertEqual(missing_user_context.slack_channel_id, "C123")

    def test_backend_bootstrap_request_uses_auth_headers_and_expected_payload(self) -> None:
        plugin = load_plugin_package()
        opener = FakeOpener(
            {
                "composio_session_id": "trs_123",
                "missing_tool_url_template": "https://app.test/tools?toolkit={toolkit_slug}",
            }
        )

        response = plugin.client.create_tool_router_session(
            plugin.client.BootstrapSessionRequest(
                session_id="hermes-session-1",
                slack_team_id="T123",
                slack_user_id="U123",
                slack_channel_id="C123",
                slack_thread_id="1700000000.000100",
            ),
            environ={
                "PHOENIX_BACKEND_URL": "https://backend.test/",
                "PHOENIX_WORKSPACE_ID": "workspace one",
                "PHOENIX_HERMES_PLUGIN_TOKEN": "plugin-token",
                "COMPOSIO_API_KEY": "project-key",
            },
            opener=opener,
        )

        self.assertEqual(response.composio_session_id, "trs_123")
        self.assertEqual(len(opener.requests), 1)

        request = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://backend.test/api/v1/internal/hermes/workspaces/workspace%20one/composio/tool-router-session",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer plugin-token")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("User-agent"), "phoenix-hermes-composio-session/0.1.0")

        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "workspace_id": "workspace one",
                "session_id": "hermes-session-1",
                "slack_team_id": "T123",
                "slack_user_id": "U123",
                "slack_channel_id": "C123",
                "slack_thread_id": "1700000000.000100",
            },
        )

    def test_plugin_injects_session_context_once_before_llm_work(self) -> None:
        plugin = load_plugin_package()
        calls: list[Any] = []

        def fake_create_tool_router_session(request: Any) -> Any:
            calls.append(request)
            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_session",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = fake_create_tool_router_session
        ctx = FakePluginContext()
        plugin.register(ctx)

        ctx.hooks["pre_gateway_dispatch"](session_id="session-1", event=slack_event())
        injected = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
        repeated = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].slack_user_id, "U123")
        self.assertEqual(calls[0].slack_channel_id, "C123")
        self.assertIsNone(repeated)
        self.assertEqual(os.environ["COMPOSIO_TOOL_ROUTER_SESSION_ID"], "trs_session")
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_session", injected["context"])
        self.assertIn("Use the composio-cli skill for non-Slack", injected["context"])
        self.assertIn("Composio Tool Router session:", injected["context"])
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID line", injected["context"])
        self.assertIn("must pass --session-id trs_session", injected["context"])
        self.assertIn("nori-slack-cli skill", injected["context"])
        self.assertIn("SLACK_BOT_TOKEN", injected["context"])
        self.assertNotIn("Composio Slackbot tools are allowed", injected["context"])

    def test_missing_tool_url_slug_replacement_is_url_safe(self) -> None:
        plugin = load_plugin_package()

        url = plugin.prompt_context.missing_tool_url(
            "https://app.test/tools?toolkit={toolkit_slug}&connect=1",
            "Google Calendar",
        )

        self.assertEqual(url, "https://app.test/tools?toolkit=google_calendar&connect=1")

    def test_failed_bootstrap_is_retried_for_same_session(self) -> None:
        plugin = load_plugin_package()
        calls = 0

        def flaky_create_tool_router_session(request: Any) -> Any:
            nonlocal calls
            calls += 1

            if calls == 1:
                raise RuntimeError("temporary failure")

            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_retry",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = flaky_create_tool_router_session
        ctx = FakePluginContext()
        plugin.register(ctx)

        failed = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
        retried = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
        repeated = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)

        self.assertEqual(calls, 2)
        self.assertIn("could not be created", failed["context"])
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_retry", retried["context"])
        self.assertIsNone(repeated)

    def test_composio_cli_skill_examples_always_include_session_id(self) -> None:
        content = (HERMES_ROOT / "skills" / "composio-cli" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        command_blocks = re.findall(r"```bash\n(.*?)```", content, flags=re.S)

        self.assertIn("COMPOSIO_API_KEY", content)
        self.assertIn("Composio Tool Router session:", content)
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID:", content)
        self.assertIn("Slack API work must use the `nori-slack-cli` skill", content)
        self.assertNotIn("--toolkits slackbot", content)
        self.assertIn("Do not use Composio `slack` or `slackbot` toolkits", content)
        self.assertGreaterEqual(len(command_blocks), 3)

        for block in command_blocks:
            if any(command in block for command in ("composio search", "composio execute", "composio proxy")):
                self.assertIn("--session-id", block)

    def test_profile_removes_static_mcp_and_documents_runtime_requirements(self) -> None:
        config = (HERMES_ROOT / "config.yaml").read_text(encoding="utf-8")
        plugin_yaml = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        healthcheck = (HERMES_ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        soul = (HERMES_ROOT / "SOUL.md").read_text(encoding="utf-8")
        mcp = json.loads((HERMES_ROOT / "mcp.json").read_text(encoding="utf-8"))

        self.assertIn("- phoenix-composio-session", config)
        self.assertNotIn("COMPOSIO_MCP_URL", config)
        self.assertNotIn("mcp_servers:\n  composio:", config)
        self.assertNotIn("composio", mcp.get("mcpServers", {}))
        self.assertIn("COMPOSIO_API_KEY", plugin_yaml)
        self.assertIn('shutil.which("composio")', healthcheck)
        self.assertIn('shutil.which("nori-slack")', healthcheck)
        self.assertIn("COMPOSIO_API_KEY", healthcheck)
        self.assertIn("PHOENIX_BACKEND_URL", healthcheck)
        self.assertIn("PHOENIX_HERMES_PLUGIN_TOKEN", healthcheck)
        self.assertIn("nori-slack-cli", soul)
        self.assertIn("SLACK_BOT_TOKEN", soul)
        self.assertNotIn("Composio Slackbot tools are allowed", soul)


class FakePluginContext:
    def __init__(self) -> None:
        self.hooks: dict[str, Any] = {}

    def register_hook(self, name: str, handler: Any) -> None:
        self.hooks[name] = handler


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.requests: list[Any] = []

    def __call__(self, request: Any, *, timeout: int) -> FakeResponse:
        self.requests.append(request)
        self.timeout = timeout
        return FakeResponse(self.payload)


def slack_event(user_id: str | None = "U123") -> types.SimpleNamespace:
    source = types.SimpleNamespace(
        platform=types.SimpleNamespace(value="slack"),
        team_id="T123",
        chat_id="C123",
        user_id=user_id,
        user_name="Predrag",
        thread_id="1700000000.000100",
    )
    return types.SimpleNamespace(
        source=source,
        raw_message={
            "team": "T123",
            "channel": "C123",
            "user": user_id,
            "thread_ts": "1700000000.000100",
            "ts": "1700000001.000200",
        },
    )


def load_plugin_package():
    module_name = f"phoenix_composio_session_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
