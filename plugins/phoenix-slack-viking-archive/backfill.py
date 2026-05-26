from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


LOGGER = logging.getLogger(__name__)

DEFAULT_DAYS = 60
DEFAULT_CHANNEL_LIMIT = 200
DEFAULT_HISTORY_LIMIT = 200
DEFAULT_REPLY_LIMIT = 200
DEFAULT_CHANNEL_TYPES = "public_channel,private_channel"
DEFAULT_TOKEN_ENVS = ("SLACK_BOT_TOKEN", "SLACK_TOKEN")


archive = None


class BackfillError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackfillOptions:
    token: str
    token_env: str
    oldest: str
    latest: str
    channel_ids: tuple[str, ...]
    exclude_archived: bool
    channel_types: str = DEFAULT_CHANNEL_TYPES
    channel_limit: int = DEFAULT_CHANNEL_LIMIT
    history_limit: int = DEFAULT_HISTORY_LIMIT
    reply_limit: int = DEFAULT_REPLY_LIMIT


@dataclass
class BackfillSummary:
    channels_seen: int = 0
    channels_archived: int = 0
    messages_seen: int = 0
    messages_written: int = 0
    messages_skipped: int = 0
    threads_read: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "channels_seen": self.channels_seen,
            "channels_archived": self.channels_archived,
            "messages_seen": self.messages_seen,
            "messages_written": self.messages_written,
            "messages_skipped": self.messages_skipped,
            "threads_read": self.threads_read,
            "errors": self.errors,
        }


class ExistingContentGuard:
    def __init__(self, writer: Any) -> None:
        self.writer = writer
        self._content_by_uri: dict[str, str] = {}
        self.read_count = 0

    def should_skip(self, snapshot: Any) -> bool:
        content = self._thread_content(snapshot.thread_uri)
        return archive.content_contains_message_marker(content, snapshot)

    def remember(self, snapshot: Any) -> None:
        content = self._content_by_uri.get(snapshot.thread_uri)
        if content is None:
            return

        marker = archive.render_source(
            {
                "message_ts": snapshot.message_ts,
                "event_kind": snapshot.event_kind,
            }
        )
        self._content_by_uri[snapshot.thread_uri] = f"{content}\n{marker}\n"

    def _thread_content(self, uri: str) -> str:
        if uri in self._content_by_uri:
            return self._content_by_uri[uri]

        if not hasattr(self.writer, "read"):
            self._content_by_uri[uri] = ""
            return ""

        try:
            content = self.writer.read(uri)
            self.read_count += 1
        except archive.OpenVikingReadError as exc:
            self.read_count += 1
            if not exc.is_not_found:
                LOGGER.warning("OpenViking read failed before backfill write: uri=%s error=%s", uri, exc)
            content = ""

        self._content_by_uri[uri] = content or ""
        return self._content_by_uri[uri]


class SlackBackfill:
    def __init__(self, *, client: Any, archive_writer: Any, options: BackfillOptions) -> None:
        self.client = client
        self.writer = archive_writer
        self.archive = archive.SlackVikingArchive(writer=archive_writer, max_workers=1)
        self.options = options
        self.guard = ExistingContentGuard(archive_writer)
        self.summary = BackfillSummary()
        self._seen_messages: set[tuple[str, str, str]] = set()

    def run(self) -> BackfillSummary:
        try:
            for channel in self.iter_channels():
                self.summary.channels_seen += 1
                try:
                    archived = self.backfill_channel(channel)
                    if archived:
                        self.summary.channels_archived += 1
                except Exception as exc:
                    self.summary.errors += 1
                    LOGGER.warning("Slack backfill failed for channel=%s error=%s", channel.get("id"), exc)
        finally:
            self.archive.shutdown()

        self.summary.threads_read = self.guard.read_count
        return self.summary

    def iter_channels(self) -> Iterable[dict[str, Any]]:
        explicit_channels = self.options.channel_ids
        if explicit_channels:
            for channel_id in explicit_channels:
                if archive.is_slack_channel_id(channel_id):
                    yield {"id": channel_id, "name": channel_id}
            return

        for channel in paginate(
            self.client.conversations_list,
            "channels",
            limit=self.options.channel_limit,
            types=self.options.channel_types,
            exclude_archived=self.options.exclude_archived,
        ):
            channel_id = clean_str(channel.get("id"))
            if archive.is_slack_channel_id(channel_id):
                yield channel

    def backfill_channel(self, channel: dict[str, Any]) -> bool:
        wrote_any = False
        history = sorted(
            paginate(
                self.client.conversations_history,
                "messages",
                channel=channel["id"],
                oldest=self.options.oldest,
                latest=self.options.latest,
                inclusive=True,
                limit=self.options.history_limit,
            ),
            key=message_sort_key,
        )

        for message in history:
            wrote_any = self.backfill_message_tree(channel, message) or wrote_any

        return wrote_any

    def backfill_message_tree(self, channel: dict[str, Any], message: dict[str, Any]) -> bool:
        sequence = [message]
        message_ts = clean_str(message.get("ts"))

        if int_value(message.get("reply_count")) > 0 and is_thread_root(message):
            replies = sorted(
                paginate(
                    self.client.conversations_replies,
                    "messages",
                    channel=channel["id"],
                    ts=message_ts,
                    oldest=self.options.oldest,
                    latest=self.options.latest,
                    inclusive=True,
                    limit=self.options.reply_limit,
                ),
                key=message_sort_key,
            )
            sequence.extend(reply for reply in replies if clean_str(reply.get("ts")) != message_ts)

        wrote_any = False
        for item in sequence:
            self.summary.messages_seen += 1
            wrote_any = self.write_message(channel, item, root_ts=message_ts) or wrote_any
        return wrote_any

    def write_message(self, channel: dict[str, Any], message: dict[str, Any], *, root_ts: str) -> bool:
        event = slack_event(channel, message, root_ts=root_ts)
        snapshot = archive.snapshot_from_event(event)
        if snapshot is None:
            self.summary.messages_skipped += 1
            return False

        seen_key = (snapshot.channel_id, snapshot.message_ts, snapshot.event_kind)
        if seen_key in self._seen_messages:
            self.summary.messages_skipped += 1
            return False
        self._seen_messages.add(seen_key)

        if self.guard.should_skip(snapshot):
            self.summary.messages_skipped += 1
            return False

        if not self.archive.write_snapshot(snapshot):
            self.summary.errors += 1
            return False

        self.guard.remember(snapshot)
        self.summary.messages_written += 1
        return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill bot-visible Slack channel messages into OpenViking thread resources."
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--history-limit", type=page_limit, default=DEFAULT_HISTORY_LIMIT)
    parser.add_argument("--reply-limit", type=page_limit, default=DEFAULT_REPLY_LIMIT)
    parser.add_argument("--channel", action="append", default=[])
    parser.add_argument("--latest-ts")
    parser.add_argument("--oldest-ts")
    parser.add_argument("--token-env")
    parser.add_argument("--exclude-archived", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def options_from_args(
    args: argparse.Namespace,
    *,
    env: dict[str, str] | os._Environ[str] = os.environ,
    now: datetime | None = None,
) -> BackfillOptions:
    token, token_env = resolve_slack_token(args.token_env, env=env)
    base_time = now or datetime.now(timezone.utc)
    latest = clean_str(args.latest_ts) or slack_ts(base_time)
    oldest = clean_str(args.oldest_ts) or slack_ts(base_time - timedelta(days=args.days))
    channel_ids = tuple(clean_str(channel_id) for channel_id in args.channel if archive.is_slack_channel_id(channel_id))

    return BackfillOptions(
        token=token,
        token_env=token_env,
        oldest=oldest,
        latest=latest,
        channel_ids=channel_ids,
        exclude_archived=bool(args.exclude_archived),
        history_limit=args.history_limit,
        reply_limit=args.reply_limit,
    )


def resolve_slack_token(
    token_env: str | None = None,
    *,
    env: dict[str, str] | os._Environ[str] = os.environ,
) -> tuple[str, str]:
    names = (token_env,) if token_env else DEFAULT_TOKEN_ENVS
    for name in names:
        if not name:
            continue
        token = clean_str(env.get(name))
        if token:
            return token, name

    expected = token_env or " or ".join(DEFAULT_TOKEN_ENVS)
    raise BackfillError(f"missing Slack token env: {expected}")


def create_slack_client(token: str) -> Any:
    from slack_sdk import WebClient
    from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

    client = WebClient(token=token)
    client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=3))
    return client


def paginate(method: Any, item_key: str, **params: Any) -> Iterable[dict[str, Any]]:
    cursor = ""
    while True:
        call_params = dict(params)
        if cursor:
            call_params["cursor"] = cursor
        response = method(**call_params)
        items = response.get(item_key) or []
        for item in items:
            if isinstance(item, dict):
                yield item
        cursor = clean_str((response.get("response_metadata") or {}).get("next_cursor"))
        if not cursor:
            break


def slack_event(channel: dict[str, Any], message: dict[str, Any], *, root_ts: str) -> Any:
    channel_id = clean_str(channel.get("id"))
    channel_name = clean_str(channel.get("name") or channel.get("name_normalized") or channel_id)
    message_ts = clean_str(message.get("ts"))
    thread_ts = clean_str(message.get("thread_ts")) or root_ts or message_ts
    raw = dict(message)
    raw["channel"] = channel_id
    raw["channel_name"] = channel_name
    raw.setdefault("channel_type", channel_type(channel))
    if thread_ts:
        raw["thread_ts"] = thread_ts

    return types.SimpleNamespace(
        raw_message=raw,
        text=raw.get("text"),
        message_id=message_ts,
        source=types.SimpleNamespace(
            platform=types.SimpleNamespace(value="slack"),
            chat_id=channel_id,
            chat_type=raw["channel_type"],
            chat_name=channel_name,
            user_id=clean_str(raw.get("user") or raw.get("bot_id")),
            user_name=clean_str(raw.get("user_name") or raw.get("username")),
            slack_team_id=clean_str(raw.get("team") or raw.get("team_id") or channel.get("context_team_id")),
        ),
    )


def is_thread_root(message: dict[str, Any]) -> bool:
    message_ts = clean_str(message.get("ts"))
    thread_ts = clean_str(message.get("thread_ts"))
    return not thread_ts or thread_ts == message_ts


def channel_type(channel: dict[str, Any]) -> str:
    channel_id = clean_str(channel.get("id"))
    if channel_id.startswith("G") or bool(channel.get("is_private")):
        return "group"
    return "channel"


def message_sort_key(message: dict[str, Any]) -> float:
    try:
        return float(message.get("ts"))
    except (TypeError, ValueError):
        return 0.0


def slack_ts(value: datetime) -> str:
    dt = value.astimezone(timezone.utc)
    return f"{int(dt.timestamp())}.{dt.microsecond:06d}"


def page_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > 999:
        raise argparse.ArgumentTypeError("limit must be between 1 and 999")
    return parsed


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_archive_module() -> Any:
    module_name = "phoenix_slack_viking_archive_runtime"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing

    plugin_path = Path(__file__).resolve().with_name("__init__.py")
    spec = importlib.util.spec_from_file_location(module_name, plugin_path)
    if spec is None or spec.loader is None:
        raise BackfillError(f"could not load archive plugin from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, clean_str(args.log_level).upper(), logging.INFO))

    try:
        options = options_from_args(args)
        client = create_slack_client(options.token)
        writer = archive.OpenVikingContentWriter()
        summary = SlackBackfill(client=client, archive_writer=writer, options=options).run()
    except Exception as exc:
        LOGGER.error("Slack OpenViking backfill failed: %s", exc)
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", **summary.as_dict()}, sort_keys=True))
    return 0


archive = load_archive_module()


if __name__ == "__main__":
    raise SystemExit(main())
