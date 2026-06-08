from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


_current_context: ContextVar["SlackActorContext | None"] = ContextVar(
    "loisa_composio_slack_context",
    default=None,
)
_contexts_by_session: dict[str, "SlackActorContext"] = {}


@dataclass(frozen=True)
class SlackActorContext:
    slack_team_id: str | None = None
    slack_user_id: str | None = None
    slack_user_name: str | None = None
    slack_channel_id: str | None = None
    slack_thread_id: str | None = None

    def request_fields(self) -> dict[str, str | None]:
        return {
            "slack_team_id": self.slack_team_id,
            "slack_user_id": self.slack_user_id,
            "slack_channel_id": self.slack_channel_id,
            "slack_thread_id": self.slack_thread_id,
        }


def extract_slack_context(event: Any) -> SlackActorContext | None:
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", None)

    if clean_text(platform).lower() != "slack":
        return None

    raw = raw_message(event)
    metadata = platform_metadata(event, source)
    channel_id = first_text(
        getattr(source, "chat_id", None),
        getattr(source, "channel_id", None),
        raw.get("channel"),
        raw.get("channel_id"),
        metadata.get("channel_id"),
    )

    return SlackActorContext(
        slack_team_id=first_text(
            getattr(source, "team_id", None),
            getattr(source, "slack_team_id", None),
            raw.get("team"),
            raw.get("team_id"),
            metadata.get("team"),
            metadata.get("team_id"),
        ),
        slack_user_id=first_text(
            getattr(source, "user_id", None),
            getattr(source, "slack_user_id", None),
            raw.get("user"),
            raw.get("user_id"),
            metadata.get("user_id"),
        ),
        slack_user_name=first_text(
            getattr(source, "user_name", None),
            getattr(source, "username", None),
            raw.get("user_name"),
            raw.get("username"),
            metadata.get("user_name"),
        ),
        slack_channel_id=channel_id,
        slack_thread_id=first_text(
            getattr(source, "thread_id", None),
            getattr(event, "thread_id", None),
            getattr(event, "reply_to_message_id", None),
            raw.get("thread_ts"),
            raw.get("ts"),
            metadata.get("thread_id"),
        ),
    )


def remember_slack_context(context: SlackActorContext, session_id: str | None = None) -> None:
    _current_context.set(context)

    if session_id:
        _contexts_by_session[session_id] = context


def get_slack_context(session_id: str | None = None) -> SlackActorContext | None:
    if session_id and session_id in _contexts_by_session:
        return _contexts_by_session[session_id]

    return _current_context.get()


def read_session_id(kwargs: dict[str, Any]) -> str | None:
    for value in (
        kwargs.get("session_id"),
        kwargs.get("conversation_id"),
        kwargs.get("task_id"),
        getattr(kwargs.get("event"), "session_id", None),
        getattr(kwargs.get("event"), "conversation_id", None),
    ):
        text = clean_text(value, max_length=200)

        if text:
            return text

    return None


def raw_message(event: Any) -> dict[str, Any]:
    for name in ("raw_message", "raw", "message"):
        value = getattr(event, name, None)

        if isinstance(value, dict):
            return value

    return {}


def platform_metadata(event: Any, source: Any) -> dict[str, Any]:
    for value in (
        getattr(source, "platform_metadata", None),
        getattr(source, "metadata", None),
        getattr(event, "platform_metadata", None),
        getattr(event, "metadata", None),
    ):
        if isinstance(value, dict):
            return value

    return {}


def first_text(*values: Any) -> str | None:
    for value in values:
        text = clean_text(value)

        if text:
            return text

    return None


def clean_text(value: Any, *, max_length: int = 500) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    return text[:max_length]
