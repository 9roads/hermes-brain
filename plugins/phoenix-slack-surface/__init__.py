from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

PHOENIX_COMMAND = "phoenix"
PHOENIX_USAGE = "Use `/phoenix <message>` to ask Phoenix about this workspace."
SLACK_ARCHIVE_COMMAND_PREFIX = "slack-archive"
SLACK_ARCHIVE_COMMAND_MODULE = "phoenix_slack_viking_archive_command"
STATUS_PATCH_MARKER = "__phoenix_slack_surface_status_patch__"
SLACK_COMPRESSION_STATUS_MARKERS = (
    "Preflight compression",
    "Compacting context",
    "to compaction",
)


def register(ctx: Any) -> None:
    patch_gateway_status_messages()

    def handle_phoenix(raw_args: str = "") -> str:
        raw_args = str(raw_args or "")
        archive_response = handle_slack_archive_command(raw_args)
        if archive_response is not None:
            return archive_response

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


def handle_slack_archive_command(raw_args: str) -> str | None:
    stripped = str(raw_args or "").strip()
    if not stripped:
        return None

    first_token = stripped.split(None, 1)[0].lower()
    if first_token != SLACK_ARCHIVE_COMMAND_PREFIX:
        return None

    command_module = load_slack_archive_command_module()
    if command_module is None:
        return "Slack archive command is not available in this Hermes profile."

    try:
        return command_module.handle_command(stripped)
    except Exception as exc:
        LOGGER.warning("Slack archive command failed: %s", exc)
        return "Slack archive command failed before it could start. Check Hermes logs."


def load_slack_archive_command_module() -> Any | None:
    existing = sys.modules.get(SLACK_ARCHIVE_COMMAND_MODULE)
    if existing is not None:
        return existing

    plugin_path = Path(__file__).resolve().parents[1] / "phoenix-slack-viking-archive" / "command.py"
    if not plugin_path.exists():
        LOGGER.info("Slack archive command module is unavailable: missing %s", plugin_path)
        return None

    spec = importlib.util.spec_from_file_location(SLACK_ARCHIVE_COMMAND_MODULE, plugin_path)
    if spec is None or spec.loader is None:
        LOGGER.info("Slack archive command module is unavailable: could not load %s", plugin_path)
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[SLACK_ARCHIVE_COMMAND_MODULE] = module
    spec.loader.exec_module(module)
    return module


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
        if is_slack_compression_status(platform, event_type, message):
            return None

        return original_prepare(platform, event_type, message)

    setattr(prepare_gateway_status_message, STATUS_PATCH_MARKER, True)

    if not hasattr(gateway_run, "_phoenix_original_prepare_gateway_status_message"):
        gateway_run._phoenix_original_prepare_gateway_status_message = original_prepare

    gateway_run._prepare_gateway_status_message = prepare_gateway_status_message
    return True


def is_slack_compression_status(platform: Any, event_type: str, message: str) -> bool:
    if platform_value(platform) != "slack" or str(event_type or "").lower() != "lifecycle":
        return False

    text = str(message or "")
    return any(marker in text for marker in SLACK_COMPRESSION_STATUS_MARKERS)


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
