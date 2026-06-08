from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackThreadGateTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if (
                name.startswith("loisa_slack_thread_gate_test_")
                or name == "gateway"
                or name.startswith("gateway.")
            ):
                sys.modules.pop(name, None)

    def test_explicit_slack_mention_calls_original_handler(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(False))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(
            slack_module.SlackAdapter.handle_message(
                adapter,
                slack_event(text="<@UBOT> can you check this?"),
            )
        )

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(ctx.llm.calls, [])

    def test_slack_dm_calls_original_handler(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(False))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(
            slack_module.SlackAdapter.handle_message(
                adapter,
                slack_event(chat_type="dm", channel_type="im"),
            )
        )

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(ctx.llm.calls, [])

    def test_non_slack_event_calls_original_handler(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(False))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(
            slack_module.SlackAdapter.handle_message(
                adapter,
                slack_event(platform="telegram"),
            )
        )

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(ctx.llm.calls, [])

    def test_unmentioned_slack_thread_reply_can_be_skipped(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(False))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(adapter.handled, [])
        self.assertEqual(len(ctx.llm.calls), 1)
        self.assertEqual(ctx.llm.calls[0]["provider"], "openrouter")
        self.assertEqual(ctx.llm.calls[0]["model"], "deepseek/deepseek-v4-pro")
        self.assertNotIn("reasoning_effort", ctx.llm.calls[0])
        self.assertIsNone(ctx.llm.calls[0]["json_schema"])
        self.assertIn("json", ctx.llm.calls[0]["instructions"].lower())
        self.assertIn("Do not return an empty response", ctx.llm.calls[0]["instructions"])

    def test_unmentioned_slack_thread_reply_can_be_allowed(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(True))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(len(ctx.llm.calls), 1)
        self.assertEqual(ctx.llm.calls[0]["provider"], "openrouter")
        self.assertEqual(ctx.llm.calls[0]["model"], "deepseek/deepseek-v4-pro")

    def test_classifier_failure_allows_unmentioned_thread_reply(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLlm(True, error=RuntimeError("boom")))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(len(ctx.llm.calls), 2)

    def test_empty_classifier_response_retries_then_allows(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeSequenceLlm(["", ""]))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(len(ctx.llm.calls), 2)

    def test_empty_classifier_response_retries_then_uses_decision(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeSequenceLlm(["", {"should_respond": False, "reason": "side chat"}]))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(adapter.handled, [])
        self.assertEqual(len(ctx.llm.calls), 2)

    def test_legacy_llm_still_handles_gate(self) -> None:
        slack_module = install_hermes_stubs()
        ctx = FakePluginContext(FakeLegacyLlm(True))
        plugin = load_plugin_module()
        plugin.register(ctx)
        adapter = slack_module.SlackAdapter()

        asyncio.run(slack_module.SlackAdapter.handle_message(adapter, slack_event()))

        self.assertEqual(len(adapter.handled), 1)
        self.assertEqual(len(ctx.llm.calls), 1)
        self.assertEqual(ctx.llm.calls[0]["provider"], "openrouter")
        self.assertEqual(ctx.llm.calls[0]["model"], "deepseek/deepseek-v4-pro")


class FakePluginContext:
    def __init__(self, llm: "FakeLlm") -> None:
        self.llm = llm


class FakeLlm:
    def __init__(self, should_respond: bool, error: Exception | None = None) -> None:
        self.should_respond = should_respond
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def complete_structured(
        self,
        *,
        instructions: str,
        input: list[dict[str, Any]],
        json_schema: dict[str, Any] | None = None,
        json_mode: bool,
        schema_name: str,
        provider: str,
        model: str,
        max_tokens: int,
        timeout: int,
        purpose: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "instructions": instructions,
                "input": input,
                "json_schema": json_schema,
                "json_mode": json_mode,
                "schema_name": schema_name,
                "provider": provider,
                "model": model,
                "max_tokens": max_tokens,
                "timeout": timeout,
                "purpose": purpose,
            }
        )
        if self.error:
            raise self.error
        return {
            "should_respond": self.should_respond,
            "reason": "test decision",
        }


class FakeLegacyLlm(FakeLlm):
    def complete_structured(
        self,
        *,
        instructions: str,
        input: list[dict[str, Any]],
        json_schema: dict[str, Any] | None = None,
        json_mode: bool,
        schema_name: str,
        provider: str,
        model: str,
        max_tokens: int,
        timeout: int,
        purpose: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "instructions": instructions,
                "input": input,
                "json_schema": json_schema,
                "json_mode": json_mode,
                "schema_name": schema_name,
                "provider": provider,
                "model": model,
                "max_tokens": max_tokens,
                "timeout": timeout,
                "purpose": purpose,
            }
        )
        return {
            "should_respond": self.should_respond,
            "reason": "test decision",
        }


class FakeSequenceLlm(FakeLlm):
    def __init__(self, responses: list[Any]) -> None:
        super().__init__(True)
        self.responses = list(responses)

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return ""


class FakeSlackAdapter:
    def __init__(self) -> None:
        self._bot_user_id = "UBOT"
        self._team_bot_user_ids = {"T123": "UBOT"}
        self.handled: list[Any] = []

    async def handle_message(self, event: Any) -> None:
        self.handled.append(event)


def slack_event(
    *,
    platform: str = "slack",
    chat_type: str = "group",
    channel_type: str = "channel",
    text: str = "I think that sounds good",
) -> types.SimpleNamespace:
    platform_obj = types.SimpleNamespace(value=platform)
    source = types.SimpleNamespace(
        platform=platform_obj,
        chat_id="C123",
        chat_name="test",
        chat_type=chat_type,
        user_id="U123",
        user_name="Predrag",
        thread_id="1700000000.000100",
    )
    return types.SimpleNamespace(
        text=text,
        source=source,
        raw_message={
            "type": "message",
            "team": "T123",
            "channel": "C123",
            "channel_type": channel_type,
            "text": text,
            "thread_ts": "1700000000.000100",
            "ts": "1700000001.000200",
        },
        message_id="1700000001.000200",
        reply_to_message_id="1700000000.000100",
        internal=False,
    )


def install_hermes_stubs():
    gateway_module = types.ModuleType("gateway")
    platforms_module = types.ModuleType("gateway.platforms")
    slack_module = types.ModuleType("gateway.platforms.slack")
    slack_module.SlackAdapter = FakeSlackAdapter
    sys.modules["gateway"] = gateway_module
    sys.modules["gateway.platforms"] = platforms_module
    sys.modules["gateway.platforms.slack"] = slack_module
    return slack_module


def load_plugin_module():
    module_name = f"loisa_slack_thread_gate_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
