"""Session synchronization for the OpenViking memory provider."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .client import OpenVikingClient
from .config import ProviderConfig
from .prompting import build_capture_message, compact_text

logger = logging.getLogger(__name__)


class SessionSyncManager:
    def __init__(self, client: OpenVikingClient, config: ProviderConfig):
        self.client = client
        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="openviking-memory-sync")
        self._futures: list[Future[Any]] = []
        self._lock = threading.RLock()
        self._turn_counts: dict[str, int] = {}
        self._committed_counts: dict[str, int] = {}
        self._ensured_sessions: set[str] = set()
        self._closed = False

    def ensure_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._ensured_sessions:
                return
        self.client.ensure_session(session_id)
        with self._lock:
            self._ensured_sessions.add(session_id)

    def _trim_message(self, content: str) -> str:
        return compact_text(content, self.config.max_message_chars)

    def _storage_role_id(self) -> str:
        return self.config.user_space

    def _user_message_content(self, content: str) -> str:
        actor = self.config.user_role_id.strip()

        if not actor or actor == self._storage_role_id():
            return content

        return f"Source metadata:\n- actor: {actor}\n\nMessage:\n{content}"

    def _write_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        self.ensure_session(session_id)
        self.client.add_message(
            session_id,
            "user",
            content=self._trim_message(self._user_message_content(user_content)),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.client.add_message(
            session_id,
            "assistant",
            content=self._trim_message(assistant_content),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def enqueue_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        if not session_id or not user_content or not assistant_content:
            return
        with self._lock:
            if self._closed:
                return
            self._turn_counts[session_id] = self._turn_counts.get(session_id, 0) + 1
            future = self._executor.submit(self._write_turn, session_id, user_content, assistant_content)
            self._futures.append(future)

    def flush(self, timeout: float | None = None) -> bool:
        timeout = self.config.sync_flush_timeout if timeout is None else timeout
        deadline = time.monotonic() + timeout
        ok = True
        while True:
            with self._lock:
                pending = [future for future in self._futures if not future.done()]
                self._futures = pending
            if not pending:
                return ok
            for future in pending:
                remaining = max(0.0, deadline - time.monotonic())
                if remaining <= 0:
                    return False
                try:
                    future.result(timeout=remaining)
                except TimeoutError:
                    ok = False
                except Exception as exc:
                    logger.warning("OpenViking memory sync failed: %s", exc)
                    ok = False

    def commit_session(
        self,
        session_id: str,
        *,
        wait: bool | None = None,
        timeout: float | None = None,
        keep_recent_count: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        if not session_id:
            return {"status": "skipped", "reason": "missing_session_id"}

        self.flush()
        with self._lock:
            turn_count = self._turn_counts.get(session_id, 0)
            committed_count = self._committed_counts.get(session_id, -1)
        if not force and turn_count == 0:
            return {"status": "skipped", "reason": "no_synced_turns", "session_id": session_id}
        if not force and committed_count == turn_count:
            return {"status": "skipped", "reason": "already_committed", "session_id": session_id}

        keep_recent = self.config.commit_keep_recent_count if keep_recent_count is None else keep_recent_count
        response = self.client.commit_session(session_id, keep_recent_count=keep_recent)
        result = self.client.unwrap_result(response)
        if not isinstance(result, dict):
            result = {}
        task_id = str(result.get("task_id") or "")
        should_wait = self.config.commit_wait if wait is None else wait
        if task_id and should_wait:
            result["task"] = self.client.poll_task(
                task_id,
                timeout=timeout or self.config.task_poll_timeout,
                interval=self.config.task_poll_interval,
            )
        with self._lock:
            self._committed_counts[session_id] = turn_count
        return result

    def capture(
        self,
        active_session_id: str,
        hermes_session_id: str,
        content: str,
        *,
        source: str = "",
        actor: str = "",
        wait: bool | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        capture_session_id = f"{active_session_id}__capture__{uuid4().hex[:10]}"
        message = build_capture_message(
            content,
            hermes_session_id=hermes_session_id,
            actor=actor or self.config.user_role_id or self.config.agent_id,
            source=source,
        )
        self.ensure_session(capture_session_id)
        self.client.add_message(
            capture_session_id,
            "user",
            content=message,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._turn_counts[capture_session_id] = 1
        result = self.commit_session(
            capture_session_id,
            wait=self.config.capture_wait if wait is None else wait,
            timeout=timeout,
            keep_recent_count=0,
            force=True,
        )
        result["capture_session_id"] = capture_session_id
        return result

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        self.flush(timeout=self.config.sync_flush_timeout)
        self._executor.shutdown(wait=False, cancel_futures=False)
