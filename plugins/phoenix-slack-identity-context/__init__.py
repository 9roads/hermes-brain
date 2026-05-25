from __future__ import annotations

import contextvars
import importlib
import logging
import re
from typing import Any


LOGGER = logging.getLogger(__name__)

GATEWAY_PATCH_MARKER = "__phoenix_slack_identity_context_gateway_patched__"
SESSION_PATCH_MARKER = "__phoenix_slack_identity_context_session_patched__"
SLACK_PATCH_MARKER = "__phoenix_slack_identity_context_slack_patched__"
ORIGINAL_PREPARE_ATTR = "_phoenix_slack_identity_context_original_prepare"
ORIGINAL_SESSION_PROMPT_ATTR = "_phoenix_slack_identity_context_original_prompt"
ORIGINAL_FETCH_THREAD_CONTEXT_ATTR = "_phoenix_slack_identity_context_original_fetch_thread_context"
ORIGINAL_RESOLVE_USER_NAME_ATTR = "_phoenix_slack_identity_context_original_resolve_user_name"

SLACK_ID_MARKER = "(Slack ID:"
SLACK_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]+$")
SLACK_MENTION_RE = re.compile(r"<@[UW][A-Z0-9]+>")
THREAD_CONTEXT_ADAPTER: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "phoenix_slack_identity_context_thread_adapter",
    default=None,
)


def register(ctx: Any) -> None:
    patch_gateway_runner()
    patch_session_prompt()
    patch_slack_adapter()


def patch_gateway_runner() -> bool:
    try:
        gateway_run = importlib.import_module("gateway.run")
    except Exception as exc:
        LOGGER.info("Slack identity context gateway patch unavailable: %s", exc)
        return False

    gateway_runner = getattr(gateway_run, "GatewayRunner", None)
    if gateway_runner is None:
        LOGGER.info("Slack identity context gateway patch unavailable: missing GatewayRunner")
        return False

    current_prepare = getattr(gateway_runner, "_prepare_inbound_message_text", None)
    if current_prepare is None:
        LOGGER.info(
            "Slack identity context gateway patch unavailable: missing _prepare_inbound_message_text"
        )
        return False

    if getattr(current_prepare, GATEWAY_PATCH_MARKER, False):
        return True

    original_prepare = getattr(gateway_runner, ORIGINAL_PREPARE_ATTR, current_prepare)
    setattr(gateway_runner, ORIGINAL_PREPARE_ATTR, original_prepare)

    async def prepare_inbound_message_text(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = await original_prepare(self, *args, **kwargs)
        if not isinstance(result, str):
            return result

        source = kwargs.get("source")
        if source is None and len(args) >= 2:
            source = args[1]

        if not should_decorate_inbound_source(self, source):
            return result

        return decorate_inbound_sender_prefix(result, source, owner=self)

    setattr(prepare_inbound_message_text, GATEWAY_PATCH_MARKER, True)
    gateway_runner._prepare_inbound_message_text = prepare_inbound_message_text
    return True


def patch_session_prompt() -> bool:
    try:
        gateway_session = importlib.import_module("gateway.session")
    except Exception as exc:
        LOGGER.info("Slack identity context session prompt patch unavailable: %s", exc)
        return False

    current_prompt = getattr(gateway_session, "build_session_context_prompt", None)
    if current_prompt is None:
        LOGGER.info(
            "Slack identity context session prompt patch unavailable: "
            "missing build_session_context_prompt"
        )
        return False

    if getattr(current_prompt, SESSION_PATCH_MARKER, False):
        return True

    original_prompt = getattr(gateway_session, ORIGINAL_SESSION_PROMPT_ATTR, current_prompt)
    setattr(gateway_session, ORIGINAL_SESSION_PROMPT_ATTR, original_prompt)

    def build_session_context_prompt(context: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_prompt(context, *args, **kwargs)
        if not isinstance(result, str) or not is_shared_slack_context(context):
            return result

        note = slack_identity_prompt_note()
        if note in result:
            return result

        return f"{result}\n\n{note}"

    setattr(build_session_context_prompt, SESSION_PATCH_MARKER, True)
    gateway_session.build_session_context_prompt = build_session_context_prompt
    return True


def patch_slack_adapter() -> bool:
    try:
        slack_module = importlib.import_module("gateway.platforms.slack")
    except Exception as exc:
        LOGGER.info("Slack identity context adapter patch unavailable: %s", exc)
        return False

    slack_adapter = getattr(slack_module, "SlackAdapter", None)
    if slack_adapter is None:
        LOGGER.info("Slack identity context adapter patch unavailable: missing SlackAdapter")
        return False

    current_fetch = getattr(slack_adapter, "_fetch_thread_context", None)
    current_resolve = getattr(slack_adapter, "_resolve_user_name", None)
    if current_fetch is None or current_resolve is None:
        LOGGER.info(
            "Slack identity context adapter patch unavailable: missing thread context methods"
        )
        return False

    fetch_patched = getattr(current_fetch, SLACK_PATCH_MARKER, False)
    resolve_patched = getattr(current_resolve, SLACK_PATCH_MARKER, False)
    if fetch_patched and resolve_patched:
        return True

    original_fetch = getattr(slack_adapter, ORIGINAL_FETCH_THREAD_CONTEXT_ATTR, current_fetch)
    original_resolve = getattr(slack_adapter, ORIGINAL_RESOLVE_USER_NAME_ATTR, current_resolve)
    setattr(slack_adapter, ORIGINAL_FETCH_THREAD_CONTEXT_ATTR, original_fetch)
    setattr(slack_adapter, ORIGINAL_RESOLVE_USER_NAME_ATTR, original_resolve)

    async def fetch_thread_context(self: Any, *args: Any, **kwargs: Any) -> Any:
        token = THREAD_CONTEXT_ADAPTER.set(self)
        try:
            return await original_fetch(self, *args, **kwargs)
        finally:
            THREAD_CONTEXT_ADAPTER.reset(token)

    async def resolve_user_name(
        self: Any,
        user_id: str,
        chat_id: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> str:
        name = await original_resolve(self, user_id, chat_id, *args, **kwargs)
        if THREAD_CONTEXT_ADAPTER.get() is not self:
            return name

        return format_slack_identity(
            name,
            user_id,
            is_self=is_bot_user_id(self, user_id),
        )

    setattr(fetch_thread_context, SLACK_PATCH_MARKER, True)
    setattr(resolve_user_name, SLACK_PATCH_MARKER, True)
    slack_adapter._fetch_thread_context = fetch_thread_context
    slack_adapter._resolve_user_name = resolve_user_name
    return True


def should_decorate_inbound_source(owner: Any, source: Any) -> bool:
    if not is_slack_source(source):
        return False

    user_name = clean_text(getattr(source, "user_name", None), max_length=240)
    if not user_name:
        return False

    if not slack_mention(getattr(source, "user_id", None)):
        return False

    return is_shared_multi_user_source(owner, source)


def is_shared_multi_user_source(owner: Any, source: Any) -> bool:
    try:
        gateway_session = importlib.import_module("gateway.session")
        is_shared = getattr(gateway_session, "is_shared_multi_user_session", None)
        if callable(is_shared):
            config = getattr(owner, "config", None)
            return bool(
                is_shared(
                    source,
                    group_sessions_per_user=getattr(config, "group_sessions_per_user", True),
                    thread_sessions_per_user=getattr(config, "thread_sessions_per_user", False),
                )
            )
    except Exception as exc:
        LOGGER.debug("Slack shared-session detection unavailable: %s", exc)

    return bool(getattr(source, "thread_id", None))


def decorate_inbound_sender_prefix(message_text: str, source: Any, *, owner: Any) -> str:
    user_name = clean_text(getattr(source, "user_name", None), max_length=240)
    user_id = clean_text(getattr(source, "user_id", None), max_length=120)
    decorated_name = format_slack_identity(
        user_name,
        user_id,
        is_self=is_bot_user_id(owner, user_id, source=source),
    )

    if not user_name or decorated_name == user_name:
        return message_text

    prefix = f"[{user_name}]"
    decorated_prefix = f"[{decorated_name}]"

    if message_text.startswith(prefix):
        return decorated_prefix + message_text[len(prefix) :]

    new_message_prefix = f"\n[New message]\n{prefix}"
    index = message_text.find(new_message_prefix)
    if index == -1:
        return message_text

    start = index + len("\n[New message]\n")
    return (
        message_text[:start]
        + decorated_prefix
        + message_text[start + len(prefix) :]
    )


def format_slack_identity(name: Any, user_id: Any, *, is_self: bool = False) -> str:
    label = clean_text(name, max_length=240)
    if not label or is_already_decorated(label):
        return label

    mention = slack_mention(user_id)
    if not mention:
        return label

    suffix = f"Slack ID: {mention}"
    if is_self:
        suffix += ", you: true"

    return f"{label} ({suffix})"


def is_already_decorated(name: str) -> bool:
    return SLACK_ID_MARKER in name or bool(SLACK_MENTION_RE.search(name))


def slack_mention(user_id: Any) -> str:
    value = clean_text(user_id, max_length=120)
    if not value or value.lower() == "unknown":
        return ""

    if value.startswith("<@") and value.endswith(">"):
        raw = value[2:-1]
        return value if SLACK_USER_ID_RE.match(raw) else ""

    if not SLACK_USER_ID_RE.match(value):
        return ""

    return f"<@{value}>"


def is_bot_user_id(owner: Any, user_id: Any, *, source: Any | None = None) -> bool:
    value = clean_slack_user_id(user_id)
    if not value:
        return False

    return value in bot_user_ids(owner, source=source)


def bot_user_ids(owner: Any, *, source: Any | None = None) -> set[str]:
    candidates: list[Any] = [owner]

    adapters = getattr(owner, "adapters", None)
    if isinstance(adapters, dict):
        platform = getattr(source, "platform", None) if source is not None else None
        for key in (platform, "slack"):
            adapter = adapters.get(key)
            if adapter is not None:
                candidates.append(adapter)

        for key, adapter in adapters.items():
            if platform_value(key) == "slack":
                candidates.append(adapter)

    ids: set[str] = set()
    for candidate in candidates:
        ids.update(read_bot_ids_from_adapter(candidate))

    return ids


def read_bot_ids_from_adapter(adapter: Any) -> set[str]:
    ids: set[str] = set()
    bot_user_id = clean_slack_user_id(getattr(adapter, "_bot_user_id", None))
    if bot_user_id:
        ids.add(bot_user_id)

    team_bot_ids = getattr(adapter, "_team_bot_user_ids", None)
    if isinstance(team_bot_ids, dict):
        for value in team_bot_ids.values():
            team_bot_id = clean_slack_user_id(value)
            if team_bot_id:
                ids.add(team_bot_id)

    return ids


def clean_slack_user_id(value: Any) -> str:
    text = clean_text(value, max_length=120)
    if text.startswith("<@") and text.endswith(">"):
        text = text[2:-1]

    return text if SLACK_USER_ID_RE.match(text) else ""


def is_shared_slack_context(context: Any) -> bool:
    source = getattr(context, "source", None)
    return is_slack_source(source) and bool(getattr(context, "shared_multi_user_session", False))


def is_slack_source(source: Any) -> bool:
    return platform_value(getattr(source, "platform", None)) == "slack"


def platform_value(platform: Any) -> str:
    value = getattr(platform, "value", platform)
    return str(value or "").strip().lower()


def slack_identity_prompt_note() -> str:
    return (
        "**Slack identity note:** In shared Slack conversations, sender and thread-context "
        "names may include `(Slack ID: <@U...>)`. Use those IDs as the only verified "
        "mention targets for those people. If a name has no Slack ID, do not guess a "
        "`<@U...>` mention from names, memory, or prior history."
    )


def clean_text(value: Any, *, max_length: int = 500) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    return text[:max_length]
