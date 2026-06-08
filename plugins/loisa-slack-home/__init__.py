from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


LOGGER = logging.getLogger(__name__)

SLACK_HOME_CHANNEL_ENV = "SLACK_HOME_CHANNEL"
SLACK_BOT_TOKEN_ENV = "SLACK_BOT_TOKEN"
SLACK_API_BASE_URL = "https://slack.com/api"
SLACK_API_TIMEOUT_SECONDS = 8
SLACK_DISCOVERY_PAGE_LIMIT = 200
SLACK_DISCOVERY_MAX_PAGES = 5
LLM_CANDIDATE_LIMIT = 30
TOOLSET = "loisa_slack_home"

_current_slack_source: ContextVar[dict[str, str | None] | None] = ContextVar(
    "loisa_slack_home_source",
    default=None,
)
_last_slack_source: dict[str, str | None] | None = None
_last_gateway: Any = None


@dataclass(frozen=True)
class SlackChannelCandidate:
    channel_id: str
    name: str
    is_private: bool = False
    is_member: bool = False
    is_general: bool = False
    num_members: int = 0
    topic: str = ""
    purpose: str = ""

    def compact(self) -> dict[str, Any]:
        return {
            "id": self.channel_id,
            "name": self.name,
            "is_private": self.is_private,
            "is_member": self.is_member,
            "is_general": self.is_general,
            "num_members": self.num_members,
            "topic": self.topic[:180],
            "purpose": self.purpose[:180],
        }


@dataclass(frozen=True)
class HomeChannelSelection:
    channel_id: str
    name: str = ""
    thread_id: str | None = None


SET_SLACK_HOME_CHANNEL_SCHEMA = {
    "name": "set_slack_home_channel",
    "description": (
        "Persist and immediately apply the Slack channel/chat ID where Loisa Hermes "
        "should deliver cron results and cross-platform messages. Use this when a user "
        "asks to route future output to the current Slack conversation, for example "
        "'output messages here'."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "channel_id": {
                "type": "string",
                "description": "Slack channel/chat ID such as C..., G..., or D....",
            },
            "channel_name": {
                "type": "string",
                "description": "Optional human-readable Slack channel name.",
            },
            "thread_id": {
                "type": "string",
                "description": "Optional Slack thread timestamp to route output into.",
            },
        },
    },
}


def register(ctx: Any) -> None:
    def pre_gateway_dispatch(*args: Any, **kwargs: Any) -> None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        event = kwargs.get("event")
        source = getattr(event, "source", None)
        platform = getattr(getattr(source, "platform", None), "value", None)

        if platform != "slack":
            return None

        remember_slack_source(source)
        gateway = kwargs.get("gateway")
        remember_gateway(gateway)

        try:
            ensure_slack_home_channel(ctx=ctx, gateway=gateway, source=source)
        except Exception as exc:
            LOGGER.warning("Loisa Slack home selection failed; using current Slack source: %s", exc)
            fallback = selection_from_source(source)
            if fallback:
                apply_home_channel(
                    fallback.channel_id,
                    name=fallback.name,
                    thread_id=fallback.thread_id,
                    gateway=gateway,
                )

        return None

    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)
    ctx.register_tool(
        name="set_slack_home_channel",
        toolset=TOOLSET,
        schema=SET_SLACK_HOME_CHANNEL_SCHEMA,
        handler=set_slack_home_channel,
    )


def ensure_slack_home_channel(ctx: Any, gateway: Any, source: Any) -> dict[str, Any] | None:
    existing = clean_text(os.getenv(SLACK_HOME_CHANNEL_ENV), max_length=120)

    if existing:
        return {
            "ok": True,
            "channel_id": existing,
            "persisted": False,
            "runtime_synced": sync_gateway_home_channel(gateway, existing, "", None),
        }

    selection = choose_home_channel(ctx, source)
    if not selection:
        return None

    return apply_home_channel(
        selection.channel_id,
        name=selection.name,
        thread_id=selection.thread_id,
        gateway=gateway,
    )


def choose_home_channel(ctx: Any, source: Any) -> HomeChannelSelection | None:
    fallback = selection_from_source(source)
    token = clean_text(os.getenv(SLACK_BOT_TOKEN_ENV), max_length=5000)

    if not token:
        return fallback

    candidates = discover_slack_channels(token)
    if not candidates:
        return fallback

    candidates = sorted(candidates, key=score_candidate, reverse=True)
    llm_selection = choose_channel_with_llm(
        getattr(ctx, "llm", None),
        candidates[:LLM_CANDIDATE_LIMIT],
    )
    if llm_selection:
        return llm_selection

    selected = candidates[0]
    return HomeChannelSelection(channel_id=selected.channel_id, name=selected.name)


def discover_slack_channels(token: str) -> list[SlackChannelCandidate]:
    candidates: list[SlackChannelCandidate] = []
    cursor = ""

    for _ in range(SLACK_DISCOVERY_MAX_PAGES):
        payload = slack_api_get(
            token,
            "conversations.list",
            {
                "exclude_archived": "true",
                "limit": str(SLACK_DISCOVERY_PAGE_LIMIT),
                "types": "public_channel,private_channel",
                **({"cursor": cursor} if cursor else {}),
            },
        )

        if not payload.get("ok"):
            LOGGER.info("Slack conversations.list failed: %s", payload.get("error") or "unknown")
            break

        for raw_channel in payload.get("channels") or []:
            candidate = candidate_from_slack_channel(raw_channel)
            if candidate:
                candidates.append(candidate)

        metadata = payload.get("response_metadata") or {}
        cursor = clean_text(metadata.get("next_cursor"), max_length=500)
        if not cursor:
            break

    member_channels = [candidate for candidate in candidates if candidate.is_member]
    return member_channels or candidates


def candidate_from_slack_channel(raw_channel: Any) -> SlackChannelCandidate | None:
    if not isinstance(raw_channel, dict) or raw_channel.get("is_archived") is True:
        return None

    channel_id = clean_text(raw_channel.get("id"), max_length=120)
    if not channel_id:
        return None

    return SlackChannelCandidate(
        channel_id=channel_id,
        name=clean_text(
            raw_channel.get("name") or raw_channel.get("name_normalized") or channel_id,
            max_length=180,
        ),
        is_private=raw_channel.get("is_private") is True,
        is_member=raw_channel.get("is_member") is True,
        is_general=raw_channel.get("is_general") is True,
        num_members=read_int(raw_channel.get("num_members")),
        topic=read_slack_text(raw_channel.get("topic")),
        purpose=read_slack_text(raw_channel.get("purpose")),
    )


def slack_api_get(token: str, method: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{SLACK_API_BASE_URL}/{method}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=SLACK_API_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_response"}


def choose_channel_with_llm(
    llm: Any,
    candidates: list[SlackChannelCandidate],
) -> HomeChannelSelection | None:
    if not llm or not hasattr(llm, "complete_structured") or not candidates:
        return None

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"channel_id": {"type": "string"}},
        "required": ["channel_id"],
    }
    prompt = (
        "Choose the best Slack home channel for Loisa Hermes proactive messages.\n"
        "Prefer channels about Loisa, Hermes, agents, alerts, updates, ops, "
        "or the main general/team channel. Avoid narrow private channels unless "
        "their name or purpose clearly fits Loisa agent output.\n"
        "Return a channel_id from this JSON only:\n"
        f"{json.dumps({'channels': [c.compact() for c in candidates]}, ensure_ascii=True)}"
    )

    try:
        result = llm.complete_structured(prompt=prompt, schema=schema)
    except Exception as exc:
        LOGGER.info("Slack home LLM selection failed: %s", exc)
        return None

    parsed = parse_structured_result(result)
    selected_id = clean_text(parsed.get("channel_id") if isinstance(parsed, dict) else None)
    selected = {candidate.channel_id: candidate for candidate in candidates}.get(selected_id)

    if not selected:
        return None

    return HomeChannelSelection(channel_id=selected.channel_id, name=selected.name)


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


def score_candidate(candidate: SlackChannelCandidate) -> tuple[int, int, int, str]:
    name = candidate.name.lower().replace("_", "-")
    score = 0

    if candidate.is_member:
        score += 1000
    if candidate.is_general:
        score += 120
    if not candidate.is_private:
        score += 80

    exact_scores = {
        "loisa": 500,
        "loisa-ai": 480,
        "loisa-agent": 470,
        "hermes": 460,
        "hermes-alerts": 450,
        "agent-alerts": 430,
        "ai-agents": 420,
        "company-memory": 410,
        "general": 250,
        "updates": 220,
        "announcements": 210,
    }
    part_scores = {
        "loisa": 520,
        "hermes": 480,
        "agent": 160,
        "ai": 130,
        "alert": 120,
        "ops": 110,
        "update": 100,
        "announce": 90,
        "general": 80,
    }

    score += exact_scores.get(name, 0)
    for part, value in part_scores.items():
        if part in name:
            score += value

    searchable_text = f"{candidate.topic} {candidate.purpose}".lower()
    for part, value in part_scores.items():
        if part in searchable_text:
            score += value // 2

    score += min(candidate.num_members, 500)
    return (score, candidate.num_members, 0 if candidate.is_private else 1, candidate.name)


def set_slack_home_channel(args: dict[str, Any] | None = None, **_: Any) -> str:
    args = args if isinstance(args, dict) else {}
    source = _current_slack_source.get() or _last_slack_source or {}
    channel_id = clean_text(args.get("channel_id"), max_length=120) or clean_text(
        source.get("chat_id"),
        max_length=120,
    )
    channel_name = clean_text(args.get("channel_name"), max_length=180) or clean_text(
        source.get("chat_name"),
        max_length=180,
    )
    thread_id = clean_text(args.get("thread_id"), max_length=80) or clean_text(
        source.get("thread_id"),
        max_length=80,
    )

    result = apply_home_channel(
        channel_id,
        name=channel_name,
        thread_id=thread_id or None,
        gateway=_last_gateway,
    )
    return json.dumps(result, ensure_ascii=True)


def apply_home_channel(
    channel_id: str,
    *,
    name: str = "",
    thread_id: str | None = None,
    gateway: Any = None,
) -> dict[str, Any]:
    channel_id = clean_text(channel_id, max_length=120)
    name = clean_text(name, max_length=180)
    thread_id = clean_text(thread_id, max_length=80) or None

    if not channel_id:
        return {
            "ok": False,
            "error": "channel_id_required",
            "message": "No Slack channel_id was provided and no current Slack source was available.",
        }

    os.environ[SLACK_HOME_CHANNEL_ENV] = channel_id
    persisted, persist_error = persist_home_channel(channel_id)
    runtime_synced = sync_gateway_home_channel(gateway, channel_id, name, thread_id)

    return {
        "ok": True,
        "channel_id": channel_id,
        "channel_name": name,
        "thread_id": thread_id,
        "persisted": persisted,
        "runtime_synced": runtime_synced,
        "error": persist_error,
    }


def persist_home_channel(channel_id: str) -> tuple[bool, str | None]:
    try:
        from hermes_cli.config import is_managed, save_env_value
    except Exception as exc:
        return False, f"hermes_env_writer_unavailable: {exc}"

    try:
        if is_managed():
            return False, "hermes_managed_mode"

        save_env_value(SLACK_HOME_CHANNEL_ENV, channel_id)
        return True, None
    except Exception as exc:
        return False, str(exc)


def sync_gateway_home_channel(
    gateway: Any,
    channel_id: str,
    name: str,
    thread_id: str | None,
) -> bool:
    if gateway is None:
        return False

    try:
        from gateway.config import HomeChannel, Platform, PlatformConfig
    except Exception:
        return False

    config = getattr(gateway, "config", None)
    platforms = getattr(config, "platforms", None)
    if not isinstance(platforms, dict):
        return False

    platform_config = platforms.setdefault(Platform.SLACK, PlatformConfig(enabled=True))
    platform_config.home_channel = HomeChannel(
        platform=Platform.SLACK,
        chat_id=channel_id,
        name=name,
        thread_id=thread_id,
    )
    return True


def selection_from_source(source: Any) -> HomeChannelSelection | None:
    channel_id = clean_text(getattr(source, "chat_id", None), max_length=120)
    if not channel_id:
        return None

    return HomeChannelSelection(
        channel_id=channel_id,
        name=clean_text(getattr(source, "chat_name", None), max_length=180),
        thread_id=clean_text(getattr(source, "thread_id", None), max_length=80) or None,
    )


def remember_slack_source(source: Any) -> None:
    global _last_slack_source

    snapshot = {
        "chat_id": clean_text(getattr(source, "chat_id", None), max_length=120),
        "chat_name": clean_text(getattr(source, "chat_name", None), max_length=180),
        "thread_id": clean_text(getattr(source, "thread_id", None), max_length=80) or None,
    }
    _current_slack_source.set(snapshot)
    _last_slack_source = snapshot


def remember_gateway(gateway: Any) -> None:
    global _last_gateway

    if gateway is not None:
        _last_gateway = gateway


def read_slack_text(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("value"), max_length=500)

    return clean_text(value, max_length=500)


def read_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean_text(value: Any, *, max_length: int = 1000) -> str:
    if value is None:
        return ""

    cleaned = str(value).replace("\n", " ").replace("\r", " ").strip()
    return cleaned[:max_length]


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
