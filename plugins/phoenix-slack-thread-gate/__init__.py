from __future__ import annotations

import importlib
import inspect
import json
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)

PLUGIN_ID = "phoenix-slack-thread-gate"
DEFAULT_THREAD_GATE_MODEL = "gpt-5.4-mini"
PATCH_MARKER = "__phoenix_slack_thread_gate_patched__"
ORIGINAL_HANDLE_ATTR = "_phoenix_slack_thread_gate_original_handle_message"
CONTEXT_ATTR = "_phoenix_slack_thread_gate_context"

THREAD_GATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "should_respond": {
            "type": "boolean",
            "description": "False only when the Slack reply is clearly unrelated human conversation.",
        },
        "reason": {
            "type": "string",
            "description": "Brief reason for the decision.",
        },
    },
    "required": ["should_respond", "reason"],
}

THREAD_GATE_INSTRUCTIONS = (
    "Decide whether the Slack assistant Phoenix/Hermes/Loisa should respond to "
    "this unmentioned Slack thread reply. Prefer should_respond=true whenever "
    "the latest message plausibly belongs in the assistant thread, follows up "
    "on previous assistant output, asks a question, asks for agent action, asks "
    "for clarification, acknowledges the assistant, or keeps an assistant-led "
    "exchange going. Acknowledgements, thanks, casual replies, and short "
    "follow-ups can still be relevant and should usually return true when they "
    "appear connected to Phoenix/Hermes/Loisa. Return should_respond=false only "
    "when the latest message is clearly unrelated human-to-human conversation, "
    "side chatter between people, a status update not meant for the assistant, "
    "or a message addressed to someone else. When uncertain, choose true."
)


def register(ctx: Any) -> None:
    patch_slack_adapter(ctx)


def patch_slack_adapter(ctx: Any) -> bool:
    try:
        slack_module = importlib.import_module("gateway.platforms.slack")
    except Exception as exc:
        LOGGER.info("Slack thread gate unavailable: %s", exc)
        return False

    slack_adapter = getattr(slack_module, "SlackAdapter", None)
    if slack_adapter is None:
        LOGGER.info("Slack thread gate unavailable: missing SlackAdapter")
        return False

    current_handle = getattr(slack_adapter, "handle_message", None)
    if current_handle is None:
        LOGGER.info("Slack thread gate unavailable: missing handle_message")
        return False

    setattr(slack_adapter, CONTEXT_ATTR, ctx)

    if getattr(current_handle, PATCH_MARKER, False):
        return True

    original_handle = getattr(slack_adapter, ORIGINAL_HANDLE_ATTR, current_handle)
    setattr(slack_adapter, ORIGINAL_HANDLE_ATTR, original_handle)

    async def handle_message(self: Any, event: Any) -> Any:
        gate_ctx = getattr(type(self), CONTEXT_ATTR, ctx)
        if await should_allow_message(self, event, gate_ctx):
            return await original_handle(self, event)
        return None

    setattr(handle_message, PATCH_MARKER, True)
    slack_adapter.handle_message = handle_message
    return True


async def should_allow_message(adapter: Any, event: Any, ctx: Any) -> bool:
    if not is_gate_candidate(adapter, event):
        return True

    decision = await classify_thread_reply(event, ctx)
    if decision.get("should_respond") is True:
        LOGGER.debug(
            "Slack thread gate allowed reply: reason=%s channel=%s thread=%s",
            decision.get("reason"),
            chat_id(event),
            thread_id(event),
        )
        return True

    LOGGER.info(
        "Slack thread gate skipped unmentioned reply: reason=%s channel=%s thread=%s",
        decision.get("reason") or "not directed at assistant",
        chat_id(event),
        thread_id(event),
    )
    return False


def is_gate_candidate(adapter: Any, event: Any) -> bool:
    if bool(getattr(event, "internal", False)):
        return False

    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", None)
    if platform != "slack":
        return False

    if is_command_event(event):
        return False

    if is_slack_dm(event):
        return False

    if is_directly_mentioned(adapter, event):
        return False

    return is_thread_reply(event)


def is_command_event(event: Any) -> bool:
    get_command = getattr(event, "get_command", None)
    if callable(get_command):
        try:
            if get_command():
                return True
        except Exception:
            pass

    text = getattr(event, "text", "")
    if isinstance(text, str) and text.lstrip().startswith("/"):
        return True

    message_type = getattr(event, "message_type", None)
    message_type_value = getattr(message_type, "value", message_type)
    return str(message_type_value or "").lower() == "command"


def is_slack_dm(event: Any) -> bool:
    source = getattr(event, "source", None)
    if getattr(source, "chat_type", None) == "dm":
        return True

    raw = raw_message(event)
    channel_type = raw.get("channel_type")
    return channel_type in {"im", "mpim"}


def is_thread_reply(event: Any) -> bool:
    raw = raw_message(event)
    raw_thread_ts = clean_text(raw.get("thread_ts"))
    raw_ts = clean_text(raw.get("ts") or getattr(event, "message_id", None))
    if raw_thread_ts and raw_ts:
        return raw_thread_ts != raw_ts

    return bool(getattr(event, "reply_to_message_id", None))


def is_directly_mentioned(adapter: Any, event: Any) -> bool:
    raw = raw_message(event)
    if raw.get("type") == "app_mention":
        return True

    bot_uid = bot_user_id(adapter, raw)
    if not bot_uid:
        return False

    text = raw_text(event)
    return f"<@{bot_uid}>" in text


def bot_user_id(adapter: Any, raw: dict[str, Any]) -> str:
    team_id = clean_text(raw.get("team") or raw.get("team_id"))
    team_bot_ids = getattr(adapter, "_team_bot_user_ids", None)
    if isinstance(team_bot_ids, dict) and team_id:
        team_bot_uid = clean_text(team_bot_ids.get(team_id))
        if team_bot_uid:
            return team_bot_uid
    return clean_text(getattr(adapter, "_bot_user_id", None))


async def classify_thread_reply(event: Any, ctx: Any) -> dict[str, Any]:
    llm = getattr(ctx, "llm", None)
    complete_structured = getattr(llm, "acomplete_structured", None) or getattr(
        llm, "complete_structured", None
    )
    if not callable(complete_structured):
        return {
            "should_respond": False,
            "reason": "thread gate LLM unavailable",
        }

    prompt = build_prompt(event)
    model = configured_thread_gate_model()
    try:
        result = complete_structured(
            instructions=THREAD_GATE_INSTRUCTIONS,
            input=[{"type": "text", "text": prompt}],
            json_schema=THREAD_GATE_SCHEMA,
            json_mode=True,
            schema_name="slack_thread_gate_decision",
            model=model,
            purpose="slack_thread_gate",
        )
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        LOGGER.info("Slack thread gate classifier failed: %s", exc)
        return {
            "should_respond": False,
            "reason": "classifier error",
        }

    parsed = parse_structured_result(result)
    if isinstance(parsed, dict) and isinstance(parsed.get("should_respond"), bool):
        return {
            "should_respond": parsed["should_respond"],
            "reason": clean_text(parsed.get("reason"), max_length=300) or "model decision",
        }

    return {
        "should_respond": False,
        "reason": "classifier returned an invalid decision",
    }


def build_prompt(event: Any) -> str:
    source = getattr(event, "source", None)
    payload = {
        "channel_id": clean_text(getattr(source, "chat_id", None)),
        "channel_name": clean_text(getattr(source, "chat_name", None), max_length=200),
        "thread_ts": thread_id(event),
        "user_id": clean_text(getattr(source, "user_id", None)),
        "user_name": clean_text(getattr(source, "user_name", None), max_length=200),
        "reply_to_text": clean_text(getattr(event, "reply_to_text", None), max_length=3000),
        "message_text": clean_text(getattr(event, "text", None), max_length=10000),
        "raw_message_text": clean_text(raw_text(event), max_length=3000),
    }

    return f"Slack event JSON:\n{json.dumps(payload, ensure_ascii=True)}"


def configured_thread_gate_model() -> str:
    try:
        from hermes_cli.config import load_config

        config = load_config() or {}
        plugins = config.get("plugins")
        entries = plugins.get("entries") if isinstance(plugins, dict) else None
        entry = entries.get(PLUGIN_ID) if isinstance(entries, dict) else None
        model = entry.get("model") if isinstance(entry, dict) else None
        configured = clean_text(model)
        if configured:
            return configured
    except Exception as exc:
        LOGGER.debug("Slack thread gate model config unavailable: %s", exc)

    return DEFAULT_THREAD_GATE_MODEL


def parse_structured_result(result: Any) -> Any:
    if isinstance(result, dict):
        return result

    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()

    text = result if isinstance(result, str) else getattr(result, "text", None)
    if isinstance(text, str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    return {}


def raw_message(event: Any) -> dict[str, Any]:
    raw = getattr(event, "raw_message", None)
    return raw if isinstance(raw, dict) else {}


def raw_text(event: Any) -> str:
    raw = raw_message(event)
    text = raw.get("text")
    if isinstance(text, str):
        return text
    return clean_text(getattr(event, "text", None), max_length=20000)


def chat_id(event: Any) -> str:
    source = getattr(event, "source", None)
    return clean_text(getattr(source, "chat_id", None))


def thread_id(event: Any) -> str:
    raw = raw_message(event)
    return clean_text(
        raw.get("thread_ts")
        or getattr(getattr(event, "source", None), "thread_id", None)
        or getattr(event, "reply_to_message_id", None)
    )


def clean_text(value: Any, max_length: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > max_length:
        return text[: max_length - 1] + "..."
    return text
