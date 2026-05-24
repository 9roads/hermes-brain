"""Phoenix OpenViking memory provider."""

from __future__ import annotations

import atexit
import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional

from .client import OpenVikingClient, get_httpx
from .config import DEFAULT_ENDPOINT, ProviderConfig
from .prompting import SYSTEM_PROMPT, collect_context_entries, compact_text, format_prefetch
from .resource_upload import add_resource_from_source
from .schemas import tool_schemas
from .session_sync import SessionSyncManager

try:
    from agent.memory_provider import MemoryProvider
except Exception:  # pragma: no cover - only used in standalone import tests

    class MemoryProvider:  # type: ignore[no-redef]
        pass

try:
    from tools.registry import tool_error
except Exception:  # pragma: no cover - only used in standalone import tests

    def tool_error(message: str) -> str:
        return json.dumps({"error": message}, ensure_ascii=False)


logger = logging.getLogger(__name__)
_last_active_provider: Optional["OpenVikingMemoryProvider"] = None


def _bool_arg(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_arg(
    value: Any,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _atexit_shutdown() -> None:
    global _last_active_provider
    provider = _last_active_provider
    if provider is None:
        return
    _last_active_provider = None
    try:
        provider.shutdown()
    except Exception:
        pass


atexit.register(_atexit_shutdown)


class OpenVikingMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._config: ProviderConfig | None = None
        self._client: OpenVikingClient | None = None
        self._sync: SessionSyncManager | None = None
        self._active_hermes_session_id = ""
        self._active_openviking_session_id = ""
        self._prefetch_lock = threading.RLock()
        self._prefetch_thread: threading.Thread | None = None
        self._prefetch_results: dict[str, str] = {}
        self._shutdown = False

    @property
    def name(self) -> str:
        return "openviking_memory"

    def is_available(self) -> bool:
        if get_httpx() is None:
            return False
        return bool(ProviderConfig.from_env().endpoint.strip())

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._config = ProviderConfig.from_env(**kwargs)
        self._client = OpenVikingClient(self._config)
        self._sync = SessionSyncManager(self._client, self._config)
        self._active_hermes_session_id = session_id
        self._active_openviking_session_id = self._config.openviking_session_id(session_id)
        self._shutdown = False

        if self._config.healthcheck_on_initialize and not self._client.health():
            logger.warning("OpenViking memory endpoint is not healthy: %s", self._config.endpoint)
        try:
            self._sync.ensure_session(self._active_openviking_session_id)
        except Exception as exc:
            logger.warning(
                "OpenViking memory could not ensure session %s: %s",
                self._active_openviking_session_id,
                exc,
            )

        global _last_active_provider
        _last_active_provider = self

    def system_prompt_block(self) -> str:
        return SYSTEM_PROMPT if self._client else ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        openviking_session_id = self._session_id_for(session_id)
        with self._prefetch_lock:
            return self._prefetch_results.pop(openviking_session_id, "")

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not self._client or not self._config or not query.strip():
            return
        openviking_session_id = self._session_id_for(session_id)

        def _run() -> None:
            try:
                assert self._client is not None
                assert self._config is not None
                payload = {
                    "query": query,
                    "session_id": openviking_session_id,
                    "target_uri": self._config.search_target_uri,
                    "limit": self._config.prefetch_limit,
                    "include_provenance": False,
                    "level": "0,1",
                }
                if self._sync:
                    self._sync.ensure_session(openviking_session_id)
                response = self._client.search(payload)
                result = self._client.unwrap_result(response)
                formatted = format_prefetch(result, max_chars=self._config.max_prefetch_chars)
                if formatted:
                    self._record_used(openviking_session_id, result)
                    with self._prefetch_lock:
                        self._prefetch_results[openviking_session_id] = formatted
            except Exception as exc:
                logger.debug("OpenViking memory prefetch failed: %s", exc)

        with self._prefetch_lock:
            if self._prefetch_thread and self._prefetch_thread.is_alive():
                return
            self._prefetch_thread = threading.Thread(
                target=_run,
                daemon=True,
                name="openviking-memory-prefetch",
            )
            self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self._sync:
            return
        openviking_session_id = self._session_id_for(session_id)
        self._sync.enqueue_turn(openviking_session_id, user_content, assistant_content)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        config = self._config or ProviderConfig.from_env()
        return tool_schemas(config.enabled_tools)

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        if not self._client or not self._config or not self._sync:
            return tool_error("OpenViking memory is not initialized")

        try:
            if tool_name == "loisa_memory_search":
                return self._tool_search(args)
            if tool_name == "loisa_memory_read":
                return self._tool_read(args)
            if tool_name == "loisa_memory_list":
                return self._tool_list(args)
            if tool_name == "loisa_memory_grep":
                return self._tool_grep(args)
            if tool_name == "loisa_memory_add_resource":
                return self._tool_add_resource(args)
            if tool_name == "loisa_memory_capture":
                return self._tool_capture(args)
            return tool_error(f"Unknown OpenViking memory tool: {tool_name}")
        except Exception as exc:
            logger.warning("OpenViking memory tool %s failed: %s", tool_name, exc)
            return tool_error(str(exc))

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs: Any,
    ) -> None:
        if not self._config or not self._sync or not new_session_id:
            return
        old_openviking_session_id = self._session_id_for(parent_session_id or self._active_hermes_session_id)
        self._sync.flush()
        if reset and old_openviking_session_id:
            self._commit(old_openviking_session_id, wait=False)
        self._active_hermes_session_id = new_session_id
        self._active_openviking_session_id = self._config.openviking_session_id(new_session_id)
        try:
            self._sync.ensure_session(self._active_openviking_session_id)
        except Exception as exc:
            logger.debug("OpenViking memory session switch ensure failed: %s", exc)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        if not self._active_openviking_session_id:
            return ""
        result = self._commit(self._active_openviking_session_id, wait=False, keep_recent_count=0)
        task_id = result.get("task_id") if isinstance(result, dict) else None
        if task_id:
            return f"OpenViking memory checkpoint queued for task {task_id}."
        return ""

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._active_openviking_session_id:
            return
        self._commit(self._active_openviking_session_id, wait=None)

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if action not in {"add", "replace"} or not content or not self._sync:
            return
        source = f"Hermes built-in memory write target={target}"
        if metadata:
            task_id = metadata.get("task_id") or metadata.get("tool_call_id")
            if task_id:
                source = f"{source}; task={task_id}"
        try:
            self._sync.capture(
                self._active_openviking_session_id,
                self._active_hermes_session_id,
                content,
                source=source,
                actor=self._config.agent_id if self._config else "",
                wait=False,
            )
        except Exception as exc:
            logger.debug("OpenViking memory built-in write mirror failed: %s", exc)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        try:
            self.on_session_end([])
        finally:
            if self._prefetch_thread and self._prefetch_thread.is_alive():
                self._prefetch_thread.join(timeout=3.0)
            if self._sync:
                self._sync.shutdown()
            global _last_active_provider
            if _last_active_provider is self:
                _last_active_provider = None

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "OPENVIKING_ENDPOINT",
                "description": "OpenViking server endpoint for memory.",
                "secret": False,
                "required": False,
                "default": DEFAULT_ENDPOINT,
                "env_var": "OPENVIKING_ENDPOINT",
            },
            {
                "key": "OPENVIKING_API_KEY",
                "description": "OpenViking API key. OPENVIKING_ROOT_API_KEY is also accepted.",
                "secret": True,
                "required": False,
                "env_var": "OPENVIKING_API_KEY",
            },
            {
                "key": "OPENVIKING_ACCOUNT",
                "description": "OpenViking tenant account. Defaults to default.",
                "secret": False,
                "required": False,
                "default": "default",
                "env_var": "OPENVIKING_ACCOUNT",
            },
            {
                "key": "OPENVIKING_USER_SPACE",
                "description": "OpenViking user namespace. Defaults to default.",
                "secret": False,
                "required": False,
                "default": "default",
                "env_var": "OPENVIKING_USER_SPACE",
            },
        ]

    def _session_id_for(self, hermes_session_id: str = "") -> str:
        if not self._config:
            return ""
        if hermes_session_id:
            openviking_session_id = self._config.openviking_session_id(hermes_session_id)
            self._active_hermes_session_id = hermes_session_id
            self._active_openviking_session_id = openviking_session_id
            return openviking_session_id
        return self._active_openviking_session_id

    def _commit(
        self,
        openviking_session_id: str,
        *,
        wait: bool | None,
        keep_recent_count: int | None = None,
    ) -> dict[str, Any]:
        if not self._sync:
            return {"status": "skipped", "reason": "not_initialized"}
        try:
            result = self._sync.commit_session(
                openviking_session_id,
                wait=wait,
                keep_recent_count=keep_recent_count,
            )
            task_id = result.get("task_id") if isinstance(result, dict) else None
            archive_uri = result.get("archive_uri") if isinstance(result, dict) else None
            if task_id or archive_uri:
                logger.info(
                    "OpenViking memory commit session=%s task_id=%s archive_uri=%s",
                    openviking_session_id,
                    task_id,
                    archive_uri,
                )
            return result
        except Exception as exc:
            logger.warning("OpenViking memory commit failed for %s: %s", openviking_session_id, exc)
            return {"status": "error", "error": str(exc), "session_id": openviking_session_id}

    def _record_used(self, openviking_session_id: str, result: Any) -> None:
        if not self._client or not openviking_session_id:
            return
        entries = collect_context_entries(result, include_provenance=False, max_abstract_chars=200)
        uris = [entry["uri"] for entry in entries if entry.get("uri")][:10]
        if not uris:
            return
        try:
            self._client.record_used(openviking_session_id, uris)
        except Exception as exc:
            logger.debug("OpenViking memory used-context record failed: %s", exc)

    def _tool_search(self, args: Dict[str, Any]) -> str:
        assert self._client is not None
        assert self._config is not None
        query = str(args.get("query") or "").strip()
        if not query:
            return tool_error("query is required")
        limit = int(args.get("limit") or self._config.search_limit)
        limit = max(1, min(25, limit))
        openviking_session_id = self._active_openviking_session_id
        payload: dict[str, Any] = {
            "query": query,
            "session_id": openviking_session_id,
            "target_uri": self._config.search_target_uri,
            "limit": limit,
            "include_provenance": bool(args.get("include_provenance", False)),
        }
        for key in ("since", "until"):
            if args.get(key):
                payload[key] = args[key]
        if self._sync:
            self._sync.ensure_session(openviking_session_id)
        response = self._client.search(payload)
        result = self._client.unwrap_result(response)
        self._record_used(openviking_session_id, result)
        entries = collect_context_entries(
            result,
            include_provenance=bool(args.get("include_provenance", False)),
            max_abstract_chars=900,
        )[:limit]
        total = result.get("total", len(entries)) if isinstance(result, dict) else len(entries)
        output = {
            "results": entries,
            "total": total,
            "session_id": openviking_session_id,
            "target_uri": payload["target_uri"],
        }
        return compact_text(json.dumps(output, ensure_ascii=False), self._config.max_tool_chars)

    @staticmethod
    def _normalize_summary_uri(uri: str) -> str:
        for suffix in ("/.abstract.md", "/.overview.md", "/.read.md", "/.full.md"):
            if uri.endswith(suffix):
                return uri[: -len(suffix)] or "viking://"
        return uri

    def _is_directory_uri(self, uri: str) -> bool | None:
        assert self._client is not None
        try:
            result = self._client.unwrap_result(self._client.stat(uri))
        except Exception:
            return None
        if isinstance(result, dict):
            if "isDir" in result:
                return bool(result.get("isDir"))
            if "is_dir" in result:
                return bool(result.get("is_dir"))
            if result.get("type") == "dir":
                return True
            if result.get("type") == "file":
                return False
        return None

    def _tool_read(self, args: Dict[str, Any]) -> str:
        assert self._client is not None
        assert self._config is not None
        uri = str(args.get("uri") or "").strip()
        if not uri:
            return tool_error("uri is required")
        self._config.validate_public_uris([self._normalize_summary_uri(uri)])
        level = str(args.get("level") or "overview").lower()
        if level not in {"abstract", "overview", "full"}:
            return tool_error("level must be abstract, overview, or full")

        summary_level = level in {"abstract", "overview"}
        resolved_uri = self._normalize_summary_uri(uri) if summary_level else uri
        used_fallback = False
        if summary_level and resolved_uri == uri and self._is_directory_uri(uri) is False:
            used_fallback = True

        try:
            response = self._client.read_content(resolved_uri, "full" if used_fallback else level)
        except Exception:
            if not summary_level or resolved_uri != uri or used_fallback:
                raise
            response = self._client.read_content(uri, "full")
            used_fallback = True
        result = self._client.unwrap_result(response)
        if isinstance(result, str):
            content = result
        elif isinstance(result, dict):
            content = result.get("content") or result.get("text") or ""
        else:
            content = ""

        default_cap = {
            "abstract": self._config.max_read_abstract_chars,
            "overview": self._config.max_read_overview_chars,
            "full": self._config.max_read_full_chars,
        }[level]
        max_chars = int(args.get("max_chars") or default_cap)
        max_chars = max(300, min(20000, max_chars))
        payload = {
            "uri": uri,
            "resolved_uri": resolved_uri,
            "level": level,
            "content": compact_text(content, max_chars),
        }
        if used_fallback:
            payload["fallback"] = "content/read"
        self._record_used(self._active_openviking_session_id, {"memories": [{"uri": uri, "abstract": ""}]})
        return json.dumps(payload, ensure_ascii=False)

    def _tool_list(self, args: Dict[str, Any]) -> str:
        assert self._client is not None
        assert self._config is not None
        uri = str(args.get("uri") or "").strip()
        if not uri:
            return tool_error("uri is required")
        uri = self._config.validate_public_uris([uri], allow_root=True)[0]
        limit = _int_arg(args.get("limit"), 100, minimum=1, maximum=1000)
        recursive = _bool_arg(args.get("recursive"), False)
        include_hidden = _bool_arg(args.get("include_hidden"), False)

        response = self._client.list_directory(
            uri,
            recursive=recursive,
            node_limit=limit,
            show_all_hidden=include_hidden,
            output="agent",
            abs_limit=500,
        )
        result = self._client.unwrap_result(response)
        raw_entries: Any = result
        total = 0
        if isinstance(result, dict):
            raw_entries = result.get("entries") or result.get("items") or result.get("children") or []
            total = int(result.get("count") or result.get("total") or 0)
        if not isinstance(raw_entries, list):
            raw_entries = []

        entries: list[dict[str, Any]] = []
        for item in raw_entries[:limit]:
            if isinstance(item, dict):
                entry_uri = str(item.get("uri") or "")
                name = str(
                    item.get("rel_path")
                    or item.get("name")
                    or (entry_uri.rstrip("/").rsplit("/", 1)[-1] if entry_uri else "")
                )
                is_dir = bool(item.get("isDir") or item.get("is_dir") or item.get("type") == "dir")
                entry: dict[str, Any] = {
                    "name": name,
                    "uri": entry_uri,
                    "type": "dir" if is_dir else "file",
                }
                abstract = item.get("abstract")
                if abstract:
                    entry["abstract"] = compact_text(abstract, 500)
                entries.append(entry)
            elif isinstance(item, str):
                entries.append(
                    {
                        "name": item.rstrip("/").rsplit("/", 1)[-1],
                        "uri": item,
                        "type": "file",
                    }
                )

        output = {
            "uri": uri,
            "recursive": recursive,
            "entries": entries,
            "count": total or len(raw_entries),
            "truncated": len(raw_entries) > len(entries),
        }
        return compact_text(json.dumps(output, ensure_ascii=False), self._config.max_tool_chars)

    def _tool_grep(self, args: Dict[str, Any]) -> str:
        assert self._client is not None
        assert self._config is not None
        uri = str(args.get("uri") or "").strip()
        if not uri:
            return tool_error("uri is required")
        pattern = str(args.get("pattern") or "")
        if not pattern:
            return tool_error("pattern is required")

        uri = self._config.validate_public_uris([uri], allow_root=True)[0]
        literal = _bool_arg(args.get("literal"), False)
        regex_pattern = re.escape(pattern) if literal else pattern
        limit = _int_arg(args.get("limit"), 10, minimum=1, maximum=100)
        level_limit = _int_arg(args.get("level_limit"), 5, minimum=1, maximum=25)
        payload: dict[str, Any] = {
            "uri": uri,
            "pattern": regex_pattern,
            "case_insensitive": _bool_arg(args.get("case_insensitive"), False),
            "node_limit": limit,
            "level_limit": level_limit,
        }
        if args.get("exclude_uri"):
            payload["exclude_uri"] = self._config.validate_public_uris(
                [str(args["exclude_uri"])],
                allow_root=True,
            )[0]

        response = self._client.grep(payload)
        result = self._client.unwrap_result(response)
        raw_matches: Any = []
        total = 0
        if isinstance(result, dict):
            raw_matches = result.get("matches") or []
            total = int(result.get("count") or result.get("total") or 0)
        elif isinstance(result, list):
            raw_matches = result
        if not isinstance(raw_matches, list):
            raw_matches = []

        matches: list[dict[str, Any]] = []
        for item in raw_matches[:limit]:
            if isinstance(item, dict):
                match: dict[str, Any] = {
                    "uri": item.get("uri", ""),
                    "line": item.get("line"),
                    "content": compact_text(item.get("content") or item.get("text") or "", 700),
                }
                if item.get("column") is not None:
                    match["column"] = item.get("column")
                matches.append(match)

        output = {
            "uri": uri,
            "pattern": pattern,
            "literal": literal,
            "case_insensitive": payload["case_insensitive"],
            "matches": matches,
            "count": total or len(raw_matches),
            "truncated": len(raw_matches) > len(matches),
        }
        return compact_text(json.dumps(output, ensure_ascii=False), self._config.max_tool_chars)

    def _tool_add_resource(self, args: Dict[str, Any]) -> str:
        assert self._client is not None
        assert self._config is not None
        data = add_resource_from_source(self._client, self._config, args)
        result = data.get("result") or {}
        payload = data.get("payload") or {}
        response = {
            "status": result.get("status", "added"),
            "root_uri": result.get("root_uri") or result.get("uri", ""),
            "temp_uri": result.get("temp_uri", ""),
            "errors": result.get("errors", []),
            "queued": True,
            "message": "Resource submitted to OpenViking resources.",
        }
        if self._config.diagnostics:
            response["request"] = {key: value for key, value in payload.items() if key not in {"temp_file_id"}}
        return json.dumps(response, ensure_ascii=False)

    def _tool_capture(self, args: Dict[str, Any]) -> str:
        assert self._config is not None
        assert self._sync is not None
        content = str(args.get("content") or "").strip()
        if not content:
            return tool_error("content is required")
        result = self._sync.capture(
            self._active_openviking_session_id,
            self._active_hermes_session_id,
            content,
            source=str(args.get("source") or "").strip(),
            actor=str(args.get("actor") or "").strip(),
            wait=False,
        )
        return json.dumps(
            {
                "status": result.get("status", "accepted"),
                "task_id": result.get("task_id"),
                "task": result.get("task"),
                "archive_uri": result.get("archive_uri"),
                "capture_session_id": result.get("capture_session_id"),
            },
            ensure_ascii=False,
        )


def register(ctx) -> None:
    ctx.register_memory_provider(OpenVikingMemoryProvider())
