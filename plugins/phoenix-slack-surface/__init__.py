from __future__ import annotations

import importlib
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)

PHOENIX_COMMAND = "phoenix"
PHOENIX_USAGE = "Use `/phoenix <message>` to ask Phoenix about this workspace."
STATUS_PATCH_MARKER = "__phoenix_slack_surface_status_patch__"
NOISY_SLACK_STATUS_MARKERS = (
    "Preflight compression",
    "Compacting context",
    "No response from provider",
    "to compaction",
)
STATUS_MESSAGES_OFF_VALUES = {"0", "false", "no", "off", "disabled", "none"}


def register(ctx: Any) -> None:
    patch_gateway_status_messages()

    def handle_phoenix(raw_args: str = "") -> str:
        raw_args = str(raw_args or "")
        if raw_args.strip():
            return "Phoenix is available from Slack with `/phoenix <message>`."

        return PHOENIX_USAGE

    def pre_gateway_dispatch(*args: Any, **kwargs: Any) -> dict[str, str] | None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        event = kwargs.get("event")
        text = getattr(event, "text", None)
        source = getattr(event, "source", None)
        platform = getattr(getattr(source, "platform", None), "value", None)

        if platform != "slack" or not isinstance(text, str):
            return None

        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        command_token, _, raw_message = stripped.partition(" ")
        command = command_token.lstrip("/").split("@", 1)[0].lower()

        if command != PHOENIX_COMMAND:
            return None

        message = raw_message.strip()
        if not message:
            return None

        return {"action": "rewrite", "text": message}

    ctx.register_command(
        PHOENIX_COMMAND,
        handler=handle_phoenix,
        description="Ask Phoenix about this workspace",
        args_hint="<message>",
    )
    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)


def patch_gateway_status_messages() -> bool:
    try:
        gateway_run = importlib.import_module("gateway.run")
    except Exception as exc:
        LOGGER.info("Slack status message patch unavailable: %s", exc)
        return False

    original_prepare = getattr(gateway_run, "_prepare_gateway_status_message", None)
    if original_prepare is None:
        LOGGER.info("Slack status message patch unavailable: missing gateway status preparer")
        return False

    if getattr(original_prepare, STATUS_PATCH_MARKER, False):
        return True

    def prepare_gateway_status_message(platform: Any, event_type: str, message: str) -> str | None:
        if is_status_messages_disabled(platform):
            return None

        if is_noisy_slack_status(platform, event_type, message):
            return None

        return original_prepare(platform, event_type, message)

    setattr(prepare_gateway_status_message, STATUS_PATCH_MARKER, True)

    if not hasattr(gateway_run, "_phoenix_original_prepare_gateway_status_message"):
        gateway_run._phoenix_original_prepare_gateway_status_message = original_prepare

    gateway_run._prepare_gateway_status_message = prepare_gateway_status_message
    return True


def is_status_messages_disabled(platform: Any) -> bool:
    value = resolve_display_setting(platform_value(platform), "status_messages")
    return is_disabled_value(value)


def resolve_display_setting(platform: str, setting: str) -> Any:
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:
        return None

    display = config.get("display") if isinstance(config, dict) else None
    if not isinstance(display, dict):
        return None

    platforms = display.get("platforms")
    if isinstance(platforms, dict):
        platform_display = platforms.get(platform)
        if isinstance(platform_display, dict) and setting in platform_display:
            return platform_display.get(setting)

    return display.get(setting)


def is_disabled_value(value: Any) -> bool:
    if value is False:
        return True
    if value is None or value is True:
        return False

    return str(value).strip().lower() in STATUS_MESSAGES_OFF_VALUES


def is_noisy_slack_status(platform: Any, event_type: str, message: str) -> bool:
    if platform_value(platform) != "slack" or str(event_type or "").lower() != "lifecycle":
        return False

    text = str(message or "")
    return any(marker in text for marker in NOISY_SLACK_STATUS_MARKERS)


def platform_value(platform: Any) -> str:
    value = getattr(platform, "value", platform)
    return str(value or "").lower()


def coerce_hook_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    if not args:
        return kwargs

    merged = dict(kwargs)

    for index, arg in enumerate(args):
        if isinstance(arg, dict):
            merged.update(arg)
        else:
            merged[f"arg_{index}"] = arg

    return merged
