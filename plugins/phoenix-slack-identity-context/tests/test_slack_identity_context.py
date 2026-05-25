from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
import uuid
from enum import Enum
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackIdentityContextTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if (
                name.startswith("phoenix_slack_identity_context_test_")
                or name == "gateway"
                or name.startswith("gateway.")
            ):
                sys.modules.pop(name, None)

    def test_shared_slack_inbound_prefix_includes_slack_id(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        runner = modules.run.GatewayRunner()
        source = slack_source()
        event = types.SimpleNamespace(text="can you mention me again?")

        result = asyncio.run(
            modules.run.GatewayRunner._prepare_inbound_message_text(
                runner,
                event=event,
                source=source,
                history=[],
            )
        )

        self.assertEqual(
            result,
            "[Predrag (Slack ID: <@U123>)] can you mention me again?",
        )

    def test_channel_context_keeps_new_message_sender_prefix_decorated(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        runner = modules.run.GatewayRunner()
        source = slack_source()
        event = types.SimpleNamespace(
            text="new context",
            channel_context="[Thread context]\nAlice: earlier",
        )

        result = asyncio.run(
            modules.run.GatewayRunner._prepare_inbound_message_text(
                runner,
                event=event,
                source=source,
                history=[],
            )
        )

        self.assertEqual(
            result,
            (
                "[Thread context]\nAlice: earlier\n\n[New message]\n"
                "[Predrag (Slack ID: <@U123>)] new context"
            ),
        )

    def test_missing_slack_user_id_leaves_existing_prefix_unchanged(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        runner = modules.run.GatewayRunner()
        source = slack_source(user_id=None)
        event = types.SimpleNamespace(text="hello")

        result = asyncio.run(
            modules.run.GatewayRunner._prepare_inbound_message_text(
                runner,
                event=event,
                source=source,
                history=[],
            )
        )

        self.assertEqual(result, "[Predrag] hello")

    def test_already_decorated_name_is_not_double_decorated(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        runner = modules.run.GatewayRunner()
        source = slack_source(user_name="Predrag (Slack ID: <@U123>)")
        event = types.SimpleNamespace(text="hello")

        result = asyncio.run(
            modules.run.GatewayRunner._prepare_inbound_message_text(
                runner,
                event=event,
                source=source,
                history=[],
            )
        )

        self.assertEqual(result, "[Predrag (Slack ID: <@U123>)] hello")

    def test_thread_context_decorates_names_only_during_thread_fetch(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        adapter = modules.slack.SlackAdapter()

        context = asyncio.run(
            modules.slack.SlackAdapter._fetch_thread_context(
                adapter,
                "C123",
                "1700000000.000100",
                "1700000001.000200",
                team_id="T123",
            )
        )
        normal_name = asyncio.run(modules.slack.SlackAdapter._resolve_user_name(adapter, "U123"))

        self.assertEqual(
            context,
            (
                "Predrag (Slack ID: <@U123>): hello\n"
                "Loisa (Slack ID: <@UBOT>, you: true): previous assistant context"
            ),
        )
        self.assertEqual(normal_name, "Predrag")

    def test_bot_identity_uses_you_true_only_for_bot_user_id(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())

        self.assertEqual(
            plugin.format_slack_identity(
                "Loisa",
                "UBOT",
                is_self=plugin.is_bot_user_id(modules.slack.SlackAdapter(), "UBOT"),
            ),
            "Loisa (Slack ID: <@UBOT>, you: true)",
        )
        self.assertEqual(
            plugin.format_slack_identity(
                "Predrag",
                "U123",
                is_self=plugin.is_bot_user_id(modules.slack.SlackAdapter(), "U123"),
            ),
            "Predrag (Slack ID: <@U123>)",
        )

    def test_register_is_idempotent(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())
        plugin.register(types.SimpleNamespace())
        runner = modules.run.GatewayRunner()
        source = slack_source()
        event = types.SimpleNamespace(text="hello")

        result = asyncio.run(
            modules.run.GatewayRunner._prepare_inbound_message_text(
                runner,
                event=event,
                source=source,
                history=[],
            )
        )

        self.assertEqual(result, "[Predrag (Slack ID: <@U123>)] hello")

    def test_shared_slack_session_prompt_adds_identity_note(self) -> None:
        modules = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.register(types.SimpleNamespace())

        prompt = modules.session.build_session_context_prompt(
            types.SimpleNamespace(
                source=slack_source(),
                shared_multi_user_session=True,
            )
        )

        self.assertIn("Slack identity note", prompt)
        self.assertIn("only verified mention targets", prompt)
        self.assertIn("do not guess", prompt)


class FakeGatewayRunner:
    def __init__(self) -> None:
        self.config = types.SimpleNamespace(
            group_sessions_per_user=True,
            thread_sessions_per_user=False,
        )
        self.adapters = {Platform.SLACK: FakeSlackAdapter()}

    async def _prepare_inbound_message_text(
        self,
        *,
        event: Any,
        source: Any,
        history: list[dict[str, Any]],
    ) -> str:
        message_text = event.text or ""
        if is_shared_multi_user_session(
            source,
            group_sessions_per_user=self.config.group_sessions_per_user,
            thread_sessions_per_user=self.config.thread_sessions_per_user,
        ) and getattr(source, "user_name", None):
            message_text = f"[{source.user_name}] {message_text}"

        if getattr(event, "channel_context", None):
            message_text = f"{event.channel_context}\n\n[New message]\n{message_text}"

        return message_text


class FakeSlackAdapter:
    def __init__(self) -> None:
        self._bot_user_id = "UBOT"
        self._team_bot_user_ids = {"T123": "UBOT"}

    async def _resolve_user_name(self, user_id: str, chat_id: str = "") -> str:
        return {
            "U123": "Predrag",
            "UBOT": "Loisa",
        }.get(user_id, user_id)

    async def _fetch_thread_context(
        self,
        channel_id: str,
        thread_ts: str,
        current_ts: str,
        team_id: str = "",
        limit: int = 30,
    ) -> str:
        human_name = await self._resolve_user_name("U123", chat_id=channel_id)
        bot_name = await self._resolve_user_name("UBOT", chat_id=channel_id)
        return f"{human_name}: hello\n{bot_name}: previous assistant context"


class Platform(Enum):
    SLACK = "slack"
    TELEGRAM = "telegram"


def is_shared_multi_user_session(
    source: Any,
    *,
    group_sessions_per_user: bool,
    thread_sessions_per_user: bool,
) -> bool:
    if getattr(source, "thread_id", None) and not thread_sessions_per_user:
        return True

    return getattr(source, "chat_type", None) in {"group", "channel"} and not group_sessions_per_user


def build_session_context_prompt(context: Any) -> str:
    source = getattr(context, "source", None)
    return (
        "## Current Session Context\n\n"
        f"**Source:** {getattr(getattr(source, 'platform', None), 'value', 'unknown')}\n"
        "**Session type:** Multi-user thread - messages are prefixed with [sender name]."
    )


def slack_source(
    *,
    user_id: str | None = "U123",
    user_name: str = "Predrag",
    thread_id: str | None = "1700000000.000100",
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        platform=Platform.SLACK,
        chat_id="C123",
        chat_type="group",
        user_id=user_id,
        user_name=user_name,
        thread_id=thread_id,
    )


def install_hermes_stubs() -> types.SimpleNamespace:
    gateway_module = types.ModuleType("gateway")
    run_module = types.ModuleType("gateway.run")
    session_module = types.ModuleType("gateway.session")
    platforms_module = types.ModuleType("gateway.platforms")
    slack_module = types.ModuleType("gateway.platforms.slack")

    run_module.GatewayRunner = FakeGatewayRunner
    session_module.is_shared_multi_user_session = is_shared_multi_user_session
    session_module.build_session_context_prompt = build_session_context_prompt
    slack_module.SlackAdapter = FakeSlackAdapter

    sys.modules["gateway"] = gateway_module
    sys.modules["gateway.run"] = run_module
    sys.modules["gateway.session"] = session_module
    sys.modules["gateway.platforms"] = platforms_module
    sys.modules["gateway.platforms.slack"] = slack_module

    return types.SimpleNamespace(
        run=run_module,
        session=session_module,
        slack=slack_module,
    )


def load_plugin_module():
    module_name = f"phoenix_slack_identity_context_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
