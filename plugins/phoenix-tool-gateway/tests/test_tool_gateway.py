from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class PhoenixToolGatewayTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if (
                name.startswith("phoenix_tool_gateway_test_")
                or name == "tools"
                or name.startswith("tools.")
            ):
                sys.modules.pop(name, None)

    def test_explicit_token_enables_managed_tools(self) -> None:
        helper_module, managed_module = install_tool_stubs(original_enabled=False)
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())

        with patch.dict(os.environ, {"TOOL_GATEWAY_USER_TOKEN": "gateway-token"}, clear=False):
            self.assertTrue(helper_module.managed_nous_tools_enabled())
            self.assertTrue(managed_module.managed_nous_tools_enabled())
            self.assertEqual(
                managed_module.resolve_managed_tool_gateway("firecrawl"),
                {
                    "vendor": "firecrawl",
                    "token": "gateway-token",
                },
            )

    def test_missing_token_falls_back_to_original_helper(self) -> None:
        helper_module, managed_module = install_tool_stubs(original_enabled=True)
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())

        with patch.dict(os.environ, {"TOOL_GATEWAY_USER_TOKEN": ""}, clear=False):
            self.assertTrue(helper_module.managed_nous_tools_enabled())
            self.assertTrue(managed_module.managed_nous_tools_enabled())

    def test_loaded_modules_with_direct_imports_are_patched(self) -> None:
        helper_module, _managed_module = install_tool_stubs(original_enabled=False)
        web_tools = types.ModuleType("tools.web_tools")
        web_tools.managed_nous_tools_enabled = helper_module.managed_nous_tools_enabled
        sys.modules["tools.web_tools"] = web_tools
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())

        with patch.dict(os.environ, {"TOOL_GATEWAY_USER_TOKEN": "gateway-token"}, clear=False):
            self.assertTrue(web_tools.managed_nous_tools_enabled())

    def test_register_is_idempotent(self) -> None:
        helper_module, managed_module = install_tool_stubs(original_enabled=False)
        plugin = load_plugin_module()

        plugin.register(types.SimpleNamespace())
        first_helper = helper_module.managed_nous_tools_enabled
        first_managed = managed_module.managed_nous_tools_enabled

        plugin.register(types.SimpleNamespace())

        self.assertIs(helper_module.managed_nous_tools_enabled, first_helper)
        self.assertIs(managed_module.managed_nous_tools_enabled, first_managed)


def load_plugin_module():
    module_name = f"phoenix_tool_gateway_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def install_tool_stubs(original_enabled: bool):
    tools_module = types.ModuleType("tools")
    tools_module.__path__ = []
    helper_module = types.ModuleType("tools.tool_backend_helpers")
    managed_module = types.ModuleType("tools.managed_tool_gateway")

    def original_managed_nous_tools_enabled() -> bool:
        return original_enabled

    def read_nous_access_token() -> str | None:
        value = os.environ.get("TOOL_GATEWAY_USER_TOKEN")
        return value.strip() if value and value.strip() else None

    def resolve_managed_tool_gateway(vendor: str) -> dict[str, Any] | None:
        if not managed_module.managed_nous_tools_enabled():
            return None
        token = read_nous_access_token()
        if not token:
            return None
        return {"vendor": vendor, "token": token}

    helper_module.managed_nous_tools_enabled = original_managed_nous_tools_enabled
    managed_module.managed_nous_tools_enabled = helper_module.managed_nous_tools_enabled
    managed_module.read_nous_access_token = read_nous_access_token
    managed_module.resolve_managed_tool_gateway = resolve_managed_tool_gateway

    sys.modules["tools"] = tools_module
    sys.modules["tools.tool_backend_helpers"] = helper_module
    sys.modules["tools.managed_tool_gateway"] = managed_module
    return helper_module, managed_module


if __name__ == "__main__":
    unittest.main()
