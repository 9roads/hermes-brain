from __future__ import annotations

import importlib.util
import sys
import types
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class OpenAiTextVerbosityTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if (
                name.startswith("loisa_openai_text_verbosity_test_")
                or name == "agent"
                or name.startswith("agent.")
            ):
                sys.modules.pop(name, None)

    def test_parse_text_verbosity_accepts_only_supported_values(self) -> None:
        plugin = load_plugin_module()

        self.assertIsNone(plugin.parse_text_verbosity(""))
        self.assertEqual(plugin.parse_text_verbosity(" LOW "), "low")
        self.assertEqual(plugin.parse_text_verbosity("medium"), "medium")
        self.assertEqual(plugin.parse_text_verbosity("HIGH"), "high")
        self.assertIsNone(plugin.parse_text_verbosity("verbose"))

    def test_register_injects_text_verbosity_for_codex_responses_transport(self) -> None:
        codex_module, _adapter_module = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.load_profile_config = lambda: {"agent": {"text_verbosity": "low"}}

        plugin.register(types.SimpleNamespace())

        transport = codex_module.ResponsesApiTransport()
        kwargs = transport.build_kwargs(
            model="gpt-5.5",
            messages=[{"role": "user", "content": "hi"}],
            provider="custom",
            base_url="https://llm-gateway.example.test/v1",
            request_overrides={"text": {"format": {"type": "text"}}},
        )

        self.assertEqual(
            kwargs["text"],
            {"format": {"type": "text"}, "verbosity": "low"},
        )

    def test_invalid_config_value_is_noop(self) -> None:
        codex_module, _adapter_module = install_hermes_stubs()
        plugin = load_plugin_module()
        plugin.load_profile_config = lambda: {"agent": {"text_verbosity": "verbose"}}

        plugin.register(types.SimpleNamespace())

        transport = codex_module.ResponsesApiTransport()
        kwargs = transport.build_kwargs(
            model="gpt-5.5",
            messages=[{"role": "user", "content": "hi"}],
        )

        self.assertNotIn("text", kwargs)

    def test_codex_preflight_accepts_and_normalizes_text_verbosity(self) -> None:
        _codex_module, adapter_module = install_hermes_stubs()
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())

        payload = adapter_module._preflight_codex_api_kwargs(
            {
                "model": "gpt-5.5",
                "store": False,
                "text": {
                    "verbosity": "HIGH",
                    "format": {"type": "text"},
                    "ignored": None,
                },
            }
        )

        self.assertEqual(
            payload["text"],
            {"verbosity": "high", "format": {"type": "text"}},
        )

    def test_codex_preflight_rejects_invalid_text_verbosity(self) -> None:
        _codex_module, adapter_module = install_hermes_stubs()
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())

        with self.assertRaisesRegex(ValueError, "text.verbosity"):
            adapter_module._preflight_codex_api_kwargs(
                {
                    "model": "gpt-5.5",
                    "store": False,
                    "text": {"verbosity": "verbose"},
                }
            )

    def test_register_is_idempotent(self) -> None:
        codex_module, adapter_module = install_hermes_stubs()
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())
        first_build_kwargs = codex_module.ResponsesApiTransport.build_kwargs
        first_preflight = adapter_module._preflight_codex_api_kwargs

        plugin.register(types.SimpleNamespace())

        self.assertIs(codex_module.ResponsesApiTransport.build_kwargs, first_build_kwargs)
        self.assertIs(adapter_module._preflight_codex_api_kwargs, first_preflight)


def load_plugin_module():
    module_name = f"loisa_openai_text_verbosity_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def install_hermes_stubs():
    agent_module = types.ModuleType("agent")
    agent_module.__path__ = []
    transports_module = types.ModuleType("agent.transports")
    transports_module.__path__ = []
    codex_module = types.ModuleType("agent.transports.codex")
    adapter_module = types.ModuleType("agent.codex_responses_adapter")

    class ResponsesApiTransport:
        def build_kwargs(
            self,
            model: str,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
            **params: Any,
        ) -> dict[str, Any]:
            kwargs = {"model": model, "input": messages, "tools": tools or []}
            request_overrides = params.get("request_overrides")
            if isinstance(request_overrides, dict):
                kwargs.update(request_overrides)
            return kwargs

    def preflight(api_kwargs: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if not isinstance(api_kwargs, dict):
            raise ValueError("Codex Responses request must be an object.")
        if "text" in api_kwargs:
            raise ValueError("Codex Responses request has unsupported field(s): text.")
        return dict(api_kwargs)

    codex_module.ResponsesApiTransport = ResponsesApiTransport
    adapter_module._preflight_codex_api_kwargs = preflight

    sys.modules["agent"] = agent_module
    sys.modules["agent.transports"] = transports_module
    sys.modules["agent.transports.codex"] = codex_module
    sys.modules["agent.codex_responses_adapter"] = adapter_module
    return codex_module, adapter_module


if __name__ == "__main__":
    unittest.main()
