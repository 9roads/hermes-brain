from __future__ import annotations

import importlib.util
import sys
import types
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackSurfaceTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if (
                name.startswith("phoenix_slack_surface_test_")
                or name == "gateway"
                or name.startswith("gateway.")
            ):
                sys.modules.pop(name, None)

    def test_rewrites_phoenix_slash_command(self) -> None:
        plugin = load_plugin_module()
        ctx = FakePluginContext()

        plugin.register(ctx)

        result = ctx.hooks["pre_gateway_dispatch"](
            event=types.SimpleNamespace(
                text="/phoenix check this",
                source=types.SimpleNamespace(platform=types.SimpleNamespace(value="slack")),
            )
        )

        self.assertEqual(result, {"action": "rewrite", "text": "check this"})

    def test_routes_slack_archive_command_handler(self) -> None:
        plugin = load_plugin_module()
        plugin.load_slack_archive_command_module = lambda: types.SimpleNamespace(
            handle_command=lambda raw_args: f"archive:{raw_args}"
        )
        ctx = FakePluginContext()

        plugin.register(ctx)

        response = ctx.commands["phoenix"]["handler"]("slack-archive status")

        self.assertEqual(response, "archive:slack-archive status")

    def test_preserves_regular_phoenix_command_handler_response(self) -> None:
        plugin = load_plugin_module()
        ctx = FakePluginContext()

        plugin.register(ctx)

        response = ctx.commands["phoenix"]["handler"]("hello")

        self.assertEqual(response, "Phoenix is available from Slack with `/phoenix <message>`.")

    def test_suppresses_routine_slack_compression_status(self) -> None:
        gateway_run = install_gateway_run_stub()
        plugin = load_plugin_module()

        plugin.patch_gateway_status_messages()

        self.assertIsNone(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="slack"),
                "lifecycle",
                "Preflight compression: ~131,982 tokens >= 128,000 threshold.\n"
                "This may take a moment.",
            )
        )
        self.assertIsNone(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="slack"),
                "lifecycle",
                "Compacting context - summarizing earlier conversation so I can continue...",
            )
        )
        self.assertIsNone(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="slack"),
                "lifecycle",
                "Context: 88% to compaction (threshold: 50% of window).",
            )
        )

    def test_preserves_non_compression_and_non_slack_status(self) -> None:
        gateway_run = install_gateway_run_stub()
        plugin = load_plugin_module()

        plugin.patch_gateway_status_messages()

        self.assertEqual(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="slack"),
                "lifecycle",
                "Switching to fallback model.",
            ),
            "slack:lifecycle:Switching to fallback model.",
        )
        self.assertEqual(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="telegram"),
                "lifecycle",
                "Preflight compression: ~131,982 tokens >= 128,000 threshold.",
            ),
            "telegram:lifecycle:Preflight compression: ~131,982 tokens >= 128,000 threshold.",
        )
        self.assertEqual(
            gateway_run._prepare_gateway_status_message(
                types.SimpleNamespace(value="slack"),
                "warn",
                "Compression summary failed.",
            ),
            "slack:warn:Compression summary failed.",
        )


class FakePluginContext:
    def __init__(self) -> None:
        self.commands: dict[str, Any] = {}
        self.hooks: dict[str, Any] = {}

    def register_command(
        self,
        name: str,
        *,
        handler: Any,
        description: str,
        args_hint: str,
    ) -> None:
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "args_hint": args_hint,
        }

    def register_hook(self, name: str, handler: Any) -> None:
        self.hooks[name] = handler


def install_gateway_run_stub() -> types.ModuleType:
    gateway_module = types.ModuleType("gateway")
    gateway_run = types.ModuleType("gateway.run")

    def prepare_gateway_status_message(platform: Any, event_type: str, message: str) -> str:
        value = getattr(platform, "value", platform)
        return f"{value}:{event_type}:{message}"

    gateway_run._prepare_gateway_status_message = prepare_gateway_status_message
    sys.modules["gateway"] = gateway_module
    sys.modules["gateway.run"] = gateway_run
    return gateway_run


def load_plugin_module():
    module_name = f"phoenix_slack_surface_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
