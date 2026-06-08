from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

BUILD_KWARGS_PATCH_MARKER = "__loisa_openai_text_verbosity_build_kwargs_patched__"
PREFLIGHT_PATCH_MARKER = "__loisa_openai_text_verbosity_preflight_patched__"
VALID_TEXT_VERBOSITIES = {"low", "medium", "high"}


def register(ctx: Any) -> None:
    patch_responses_transport()
    patch_codex_preflight()


def parse_text_verbosity(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    if not value:
        return None
    if value in VALID_TEXT_VERBOSITIES:
        return value
    return None


def configured_text_verbosity() -> str | None:
    config = load_profile_config()
    agent_config = config.get("agent", {})
    if not isinstance(agent_config, dict):
        return None
    return parse_text_verbosity(agent_config.get("text_verbosity"))


def patch_responses_transport() -> bool:
    try:
        codex_module = importlib.import_module("agent.transports.codex")
    except Exception as exc:
        LOGGER.info("Responses text verbosity patch unavailable: %s", exc)
        return False

    transport = getattr(codex_module, "ResponsesApiTransport", None)
    if transport is None:
        LOGGER.info("Responses text verbosity patch unavailable: missing ResponsesApiTransport")
        return False

    original_build_kwargs = getattr(transport, "build_kwargs", None)
    if original_build_kwargs is None:
        LOGGER.info("Responses text verbosity patch unavailable: missing build_kwargs")
        return False

    if getattr(original_build_kwargs, BUILD_KWARGS_PATCH_MARKER, False):
        return True

    def build_kwargs(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        api_kwargs = original_build_kwargs(self, *args, **kwargs)
        verbosity = configured_text_verbosity()
        if not verbosity or not isinstance(api_kwargs, dict):
            return api_kwargs

        text = api_kwargs.get("text")
        if text is not None and not isinstance(text, dict):
            return api_kwargs

        text_obj = dict(text or {})
        text_obj["verbosity"] = verbosity
        api_kwargs["text"] = text_obj
        return api_kwargs

    setattr(build_kwargs, BUILD_KWARGS_PATCH_MARKER, True)
    if not hasattr(transport, "_loisa_original_build_kwargs"):
        transport._loisa_original_build_kwargs = original_build_kwargs
    transport.build_kwargs = build_kwargs
    return True


def patch_codex_preflight() -> bool:
    try:
        adapter_module = importlib.import_module("agent.codex_responses_adapter")
    except Exception as exc:
        LOGGER.info("Codex Responses preflight text verbosity patch unavailable: %s", exc)
        return False

    original_preflight = getattr(adapter_module, "_preflight_codex_api_kwargs", None)
    if original_preflight is None:
        LOGGER.info("Codex Responses preflight text verbosity patch unavailable: missing preflight")
        return False

    if getattr(original_preflight, PREFLIGHT_PATCH_MARKER, False):
        return True

    def preflight(api_kwargs: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if not isinstance(api_kwargs, dict) or "text" not in api_kwargs:
            return original_preflight(api_kwargs, *args, **kwargs)

        normalized_text = normalize_text_object(api_kwargs.get("text"))
        api_kwargs_without_text = dict(api_kwargs)
        api_kwargs_without_text.pop("text", None)
        normalized = original_preflight(api_kwargs_without_text, *args, **kwargs)
        if normalized_text:
            normalized["text"] = normalized_text
        return normalized

    setattr(preflight, PREFLIGHT_PATCH_MARKER, True)
    if not hasattr(adapter_module, "_loisa_original_preflight_codex_api_kwargs"):
        adapter_module._loisa_original_preflight_codex_api_kwargs = original_preflight
    adapter_module._preflight_codex_api_kwargs = preflight
    return True


def normalize_text_object(text: Any) -> dict[str, Any]:
    if text is None:
        return {}
    if not isinstance(text, dict):
        raise ValueError("Codex Responses request 'text' must be an object.")

    normalized: dict[str, Any] = {}
    verbosity = text.get("verbosity")
    if verbosity is not None:
        verbosity_value = parse_text_verbosity(verbosity)
        if not verbosity_value:
            raise ValueError(
                "Codex Responses request 'text.verbosity' must be low, medium, or high."
            )
        normalized["verbosity"] = verbosity_value

    for key, value in text.items():
        if key == "verbosity" or value is None:
            continue
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Codex Responses request 'text' keys must be non-empty strings.")
        normalized[key.strip()] = value

    return normalized


def load_profile_config() -> dict[str, Any]:
    home = os.environ.get("HERMES_HOME")
    if not home:
        return {}

    config_path = Path(home) / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        import yaml

        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        LOGGER.info("Responses text verbosity config unavailable: %s", exc)
        return {}

    return loaded if isinstance(loaded, dict) else {}
