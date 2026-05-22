from __future__ import annotations

import logging
import os
import sys
from types import ModuleType
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)

PATCH_MARKER = "__phoenix_tool_gateway_managed_nous_patch__"
ORIGINAL_ATTR = "_phoenix_original_managed_nous_tools_enabled"
DIRECT_IMPORT_MODULES = (
    "tools.web_tools",
    "tools.browser_providers.browser_use",
    "tools.image_generation_tool",
    "tools.transcription_tools",
    "tools.tts_tool",
    "tools.terminal_tool",
)


def register(ctx: Any) -> None:
    patch_managed_gateway_auth()


def explicit_tool_gateway_token_configured() -> bool:
    value = os.environ.get("TOOL_GATEWAY_USER_TOKEN")
    return bool(value and value.strip() and value.strip().lower() != "undefined")


def patch_managed_gateway_auth() -> bool:
    try:
        helper_module = __import__("tools.tool_backend_helpers", fromlist=["*"])
    except Exception as exc:
        LOGGER.info("Phoenix Tool Gateway auth patch unavailable: %s", exc)
        return False

    original = getattr(helper_module, "managed_nous_tools_enabled", None)
    if original is None:
        LOGGER.info("Phoenix Tool Gateway auth patch unavailable: missing helper")
        return False

    if getattr(original, PATCH_MARKER, False):
        patched = original
    else:
        patched = build_managed_nous_tools_enabled(original)
        setattr(helper_module, ORIGINAL_ATTR, original)
        helper_module.managed_nous_tools_enabled = patched

    patch_loaded_module("tools.managed_tool_gateway", patched)
    for module_name in DIRECT_IMPORT_MODULES:
        module = sys.modules.get(module_name)
        if module is not None:
            patch_loaded_module(module, patched)

    return True


def build_managed_nous_tools_enabled(original: Callable[[], bool]) -> Callable[[], bool]:
    def managed_nous_tools_enabled() -> bool:
        if explicit_tool_gateway_token_configured():
            return True

        try:
            return bool(original())
        except Exception:
            return False

    setattr(managed_nous_tools_enabled, PATCH_MARKER, True)
    setattr(managed_nous_tools_enabled, ORIGINAL_ATTR, original)
    return managed_nous_tools_enabled


def patch_loaded_module(module_or_name: ModuleType | str, patched: Callable[[], bool]) -> None:
    if isinstance(module_or_name, str):
        module = sys.modules.get(module_or_name)
        if module is None:
            return
    else:
        module = module_or_name

    if hasattr(module, "managed_nous_tools_enabled"):
        if not hasattr(module, ORIGINAL_ATTR):
            setattr(module, ORIGINAL_ATTR, getattr(module, "managed_nous_tools_enabled"))
        setattr(module, "managed_nous_tools_enabled", patched)
