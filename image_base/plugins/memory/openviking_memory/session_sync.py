"""Session synchronization for the OpenViking memory provider."""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .client import OpenVikingClient
from .config import ProviderConfig
from .prompting import build_capture_message

logger = logging.getLogger(__name__)

_SYSTEM_USER_PREFIXES = (
    "[System: Your previous tool call ",
    "[System: The previous response was cut off ",
    "[System: Your previous response was truncated ",
    "[System: Continue now.",
)
_MAX_BATCH_MESSAGES = 100
_UNKNOWN_CONTENT_JSON_LIMIT = 1000
_IMAGE_PART_TYPES = {"image", "image_url", "input_image"}
_AUDIO_PART_TYPES = {"audio", "input_audio"}
_FILE_PART_TYPES = {"file", "input_file"}


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

    def _storage_role_id(self) -> str:
        return self.config.user_space

    def _user_message_content(self, content: str) -> str:
        actor = self.config.user_role_id.strip()

        if not actor or actor == self._storage_role_id():
            return content

        return f"Source metadata:\n- actor: {actor}\n\nMessage:\n{content}"

    def _unknown_content_text(self, content: Any) -> str:
        try:
            text = json.dumps(content, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(content)
        if len(text) > _UNKNOWN_CONTENT_JSON_LIMIT:
            return "[non-text content omitted]"
        return text

    def _content_part_text(self, part: dict[str, Any]) -> str:
        part_type = str(part.get("type") or "").lower()
        if part_type in _IMAGE_PART_TYPES:
            return "[image attachment]"
        if part_type in _AUDIO_PART_TYPES:
            return "[audio attachment]"
        if part_type in _FILE_PART_TYPES:
            name = part.get("filename") or part.get("name")
            return f"[file attachment: {name}]" if name else "[file attachment]"

        for key in ("text", "content"):
            value = part.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                nested = self._message_text(value).strip()
                if nested:
                    return nested

        if part_type == "context":
            abstract = str(part.get("abstract") or "").strip()
            uri = str(part.get("uri") or "").strip()
            if abstract and uri:
                return f"{abstract} ({uri})"
            return abstract or uri or "[context]"

        if part_type:
            return f"[{part_type} content]"
        return self._unknown_content_text(part)

    def _message_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = self._content_part_text(item).strip()
                    if text:
                        parts.append(text)
                elif item is not None:
                    parts.append(str(item))
            return "\n".join(parts)
        if isinstance(content, dict):
            return self._content_part_text(content)
        return str(content)

    def _text_part(self, content: Any) -> dict[str, str] | None:
        text = self._message_text(content).strip()
        if not text:
            return None
        return {"type": "text", "text": text}

    def _is_synthetic_user_message(self, message: dict[str, Any]) -> bool:
        if message.get("_thinking_prefill") or message.get("_empty_recovery_synthetic"):
            return True
        text = self._message_text(message.get("content")).strip()
        return any(text.startswith(prefix) for prefix in _SYSTEM_USER_PREFIXES)

    def _current_turn_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        start_index = -1
        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if not isinstance(message, dict):
                continue
            if message.get("role") == "user" and not self._is_synthetic_user_message(message):
                start_index = index
                break
        if start_index < 0:
            return []
        return [message for message in messages[start_index:] if isinstance(message, dict)]

    def _decode_tool_input(self, value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, (list, int, float, bool)):
            return {"arguments": value}
        raw = str(value)
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_arguments": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"arguments": parsed}

    def _tool_call_fields(self, tool_call: Any) -> tuple[str, str, Any]:
        if isinstance(tool_call, dict):
            function = tool_call.get("function")
            if not isinstance(function, dict):
                function = {}
            tool_id = str(
                tool_call.get("id")
                or tool_call.get("tool_call_id")
                or tool_call.get("call_id")
                or ""
            )
            tool_name = str(
                function.get("name")
                or tool_call.get("name")
                or tool_call.get("tool_name")
                or "unknown"
            )
            tool_input = (
                function.get("arguments")
                if "arguments" in function
                else tool_call.get("arguments", tool_call.get("input", tool_call.get("tool_input")))
            )
            return tool_id, tool_name, self._decode_tool_input(tool_input)

        function = getattr(tool_call, "function", None)
        tool_id = str(
            getattr(tool_call, "id", None)
            or getattr(tool_call, "tool_call_id", None)
            or getattr(tool_call, "call_id", None)
            or ""
        )
        tool_name = str(
            getattr(function, "name", None)
            or getattr(tool_call, "name", None)
            or getattr(tool_call, "tool_name", None)
            or "unknown"
        )
        tool_input = (
            getattr(function, "arguments", None)
            if function is not None
            else getattr(tool_call, "arguments", None)
        )
        return tool_id, tool_name, self._decode_tool_input(tool_input)

    def _tool_results_by_id(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
        matched: dict[str, list[dict[str, str]]] = {}
        unmatched: list[dict[str, str]] = []
        for message in messages:
            if message.get("role") != "tool":
                continue
            tool_id = str(
                message.get("tool_call_id")
                or message.get("call_id")
                or message.get("tool_use_id")
                or message.get("id")
                or ""
            )
            entry = {
                "name": str(message.get("name") or message.get("tool_name") or "unknown"),
                "content": self._message_text(message.get("content")).strip(),
            }
            if tool_id:
                matched.setdefault(tool_id, []).append(entry)
            else:
                unmatched.append(entry)
        return matched, unmatched

    def _tool_part(
        self,
        *,
        tool_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: str,
        tool_status: str = "",
    ) -> dict[str, Any]:
        status = tool_status
        if not status:
            if tool_output.lstrip().lower().startswith("error"):
                status = "error"
            else:
                status = "completed" if tool_output else "pending"
        return {
            "type": "tool",
            "tool_id": tool_id or "unknown",
            "tool_name": tool_name or "unknown",
            "tool_input": tool_input,
            "tool_output": tool_output.strip(),
            "tool_status": status,
        }

    def _assistant_parts(
        self,
        message: dict[str, Any],
        tool_results: dict[str, list[dict[str, str]]],
        consumed_tool_ids: set[str],
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        text_part = self._text_part(message.get("content"))
        if text_part:
            parts.append(text_part)

        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            tool_calls = [tool_calls]
        for index, tool_call in enumerate(tool_calls):
            tool_id, tool_name, tool_input = self._tool_call_fields(tool_call)
            if not tool_id:
                tool_id = f"unknown_{index + 1}"
            results = tool_results.get(tool_id, [])
            if results:
                consumed_tool_ids.add(tool_id)
            output = "\n\n".join(result["content"] for result in results if result.get("content"))
            if results and (not tool_name or tool_name == "unknown"):
                tool_name = results[0].get("name") or "unknown"
            parts.append(
                self._tool_part(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=output,
                )
            )
        return parts

    def _openviking_messages_for_turn(
        self,
        user_content: str,
        assistant_content: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        turn_messages = self._current_turn_messages(messages)
        if not turn_messages:
            return []

        created_at = datetime.now(timezone.utc).isoformat()
        tool_results, unmatched_tool_results = self._tool_results_by_id(turn_messages)
        consumed_tool_ids: set[str] = set()
        converted: list[dict[str, Any]] = []
        first_user = True

        for message in turn_messages:
            role = message.get("role")
            if role == "tool":
                continue
            if role == "user":
                if self._is_synthetic_user_message(message):
                    continue
                content = self._user_message_content(user_content) if first_user else self._message_text(message.get("content"))
                first_user = False
                text_part = self._text_part(content)
                if text_part:
                    converted.append({"role": "user", "parts": [text_part], "created_at": created_at})
                continue
            if role != "assistant":
                continue

            parts = self._assistant_parts(message, tool_results, consumed_tool_ids)
            if parts:
                converted.append({"role": "assistant", "parts": parts, "created_at": created_at})

        for tool_id, results in tool_results.items():
            if tool_id in consumed_tool_ids:
                continue
            for index, result in enumerate(results):
                converted.append(
                    {
                        "role": "assistant",
                        "parts": [
                            self._tool_part(
                                tool_id=tool_id or f"unmatched_{index + 1}",
                                tool_name=result.get("name") or "unknown",
                                tool_input={},
                                tool_output=result.get("content") or "",
                            )
                        ],
                        "created_at": created_at,
                    }
                )

        for index, result in enumerate(unmatched_tool_results):
            converted.append(
                {
                    "role": "assistant",
                    "parts": [
                        self._tool_part(
                            tool_id=f"unmatched_{index + 1}",
                            tool_name=result.get("name") or "unknown",
                            tool_input={},
                            tool_output=result.get("content") or "",
                        )
                    ],
                    "created_at": created_at,
                }
            )

        text_part = self._text_part(assistant_content)
        if not text_part:
            return converted
        assistant_text = text_part["text"]
        for message in converted:
            if message.get("role") != "assistant":
                continue
            for part in message.get("parts") or []:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text") == assistant_text:
                    return converted
        converted.append({"role": "assistant", "parts": [text_part], "created_at": created_at})
        return converted

    def _write_messages(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        self.ensure_session(session_id)
        for index in range(0, len(messages), _MAX_BATCH_MESSAGES):
            self.client.add_messages(session_id, messages[index : index + _MAX_BATCH_MESSAGES])

    def enqueue_messages(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        messages: list[dict[str, Any]],
    ) -> None:
        if not session_id or not messages:
            return
        converted = self._openviking_messages_for_turn(user_content, assistant_content, messages)
        if not converted:
            return
        with self._lock:
            if self._closed:
                return
            self._turn_counts[session_id] = self._turn_counts.get(session_id, 0) + 1
            future = self._executor.submit(self._write_messages, session_id, converted)
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
