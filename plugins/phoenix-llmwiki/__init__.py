from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

try:
    from . import slack_format
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import slack_format


LOGGER = logging.getLogger(__name__)

PLUGIN_ID = "phoenix-llmwiki"
DEFAULT_MAX_WORKERS = 4
DEFAULT_DEDUPE_LIMIT = 4096

SlackMessageSnapshot = slack_format.SlackMessageSnapshot
DEFAULT_LLMWIKI_ROOT = slack_format.DEFAULT_LLMWIKI_ROOT
SLACK_TEXT_MAX_CHARS = slack_format.SLACK_TEXT_MAX_CHARS
SOURCE_VALUE_MAX_CHARS = slack_format.SOURCE_VALUE_MAX_CHARS
clean_text = slack_format.clean_text
content_contains_message_marker = slack_format.content_contains_message_marker
content_contains_source_marker = slack_format.content_contains_source_marker
datetime_from_slack_ts = slack_format.datetime_from_slack_ts
event_kind_from_raw = slack_format.event_kind_from_raw
first_nonempty = slack_format.first_nonempty
is_slack_channel_id = slack_format.is_slack_channel_id
is_slack_channel_message_event = slack_format.is_slack_channel_message_event
llmwiki_root = slack_format.llmwiki_root
markdown_line = slack_format.markdown_line
previous_message_body = slack_format.previous_message_body
raw_message = slack_format.raw_message
redact_text = slack_format.redact_text
render_message_block = slack_format.render_message_block
render_source = slack_format.render_source
render_source_append = slack_format.render_source_append
render_source_file_header = slack_format.render_source_file_header
safe_uri_segment = slack_format.safe_uri_segment
slack_message_body = slack_format.slack_message_body
slack_source_file_name = slack_format.slack_source_file_name
slack_ts_to_iso = slack_format.slack_ts_to_iso
snapshot_from_event = slack_format.snapshot_from_event
source_value = slack_format.source_value
sources_dir = slack_format.sources_dir
text_for_event = slack_format.text_for_event
thread_marker = slack_format.thread_marker


class SourceReadError(RuntimeError):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.is_not_found = not_found


class LlmwikiSourceWriter:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else llmwiki_root()

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    def write_snapshot(self, snapshot: SlackMessageSnapshot) -> dict[str, Any]:
        path = Path(snapshot.source_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = ""

        if content_contains_message_marker(content, snapshot):
            return {"status": "skipped", "reason": "duplicate", "path": str(path)}

        with path.open("a", encoding="utf-8") as source_file:
            source_file.write(render_source_append(snapshot, include_header=not bool(content)))

        return {"status": "written", "path": str(path)}

    def read(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SourceReadError(f"source file not found: {path}", not_found=True) from exc


class SlackLlmwikiArchive:
    def __init__(
        self,
        *,
        writer: Any | None = None,
        max_workers: int | None = None,
        dedupe_limit: int = DEFAULT_DEDUPE_LIMIT,
    ) -> None:
        self.writer = writer or LlmwikiSourceWriter()
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers or env_int("PHOENIX_LLMWIKI_ARCHIVE_WORKERS", DEFAULT_MAX_WORKERS),
            thread_name_prefix="slack-llmwiki-archive",
        )
        self.dedupe_limit = max(1, dedupe_limit)
        self._dedupe: OrderedDict[str, None] = OrderedDict()
        self._dedupe_lock = threading.RLock()
        self._file_locks: dict[str, threading.Lock] = {}
        self._file_locks_lock = threading.RLock()

    def submit_event(self, event: Any) -> bool:
        snapshot = snapshot_from_event(event)
        if snapshot is None:
            return False
        if not self._remember_dedupe(snapshot.dedupe_key):
            return False

        self.executor.submit(self.write_snapshot, snapshot)
        return True

    def write_snapshot(self, snapshot: SlackMessageSnapshot) -> bool:
        lock = self._lock_for_path(snapshot.source_path)
        with lock:
            try:
                self.writer.write_snapshot(snapshot)
                return True
            except Exception as exc:
                LOGGER.warning(
                    "Slack llmwiki source write failed: channel=%s thread=%s ts=%s path=%s error=%s",
                    snapshot.channel_id,
                    snapshot.thread_ts,
                    snapshot.message_ts,
                    snapshot.source_path,
                    exc,
                )
                return False

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _remember_dedupe(self, key: str) -> bool:
        with self._dedupe_lock:
            if key in self._dedupe:
                self._dedupe.move_to_end(key)
                return False
            self._dedupe[key] = None
            while len(self._dedupe) > self.dedupe_limit:
                self._dedupe.popitem(last=False)
            return True

    def _lock_for_path(self, path: str) -> threading.Lock:
        with self._file_locks_lock:
            lock = self._file_locks.get(path)
            if lock is None:
                lock = threading.Lock()
                self._file_locks[path] = lock
            return lock


def register(ctx: Any) -> None:
    def pre_gateway_dispatch(*args: Any, **kwargs: Any) -> None:
        hook_kwargs = coerce_hook_kwargs(args, kwargs)
        event = hook_kwargs.get("event")
        try:
            ARCHIVE.submit_event(event)
        except Exception as exc:
            LOGGER.debug("Slack llmwiki archive scheduling failed: %s", exc)
        return None

    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)


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


def env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, "").strip())
    except ValueError:
        value = default
    return max(1, value)


def _shutdown_archive() -> None:
    try:
        ARCHIVE.shutdown()
    except Exception:
        pass


ARCHIVE = SlackLlmwikiArchive()
atexit.register(_shutdown_archive)
