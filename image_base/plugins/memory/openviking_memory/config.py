"""Configuration helpers for the Phoenix OpenViking memory provider."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlparse

DEFAULT_ENDPOINT = "http://127.0.0.1:1933"
DEFAULT_ACCOUNT = "default"
DEFAULT_USER_SPACE = "default"
DEFAULT_AGENT_ID = "hermes-memory"
DEFAULT_TOOLS = {"search", "read", "list", "grep", "add_resource", "capture"}
REMOTE_RESOURCE_PREFIXES = ("http://", "https://", "git@", "ssh://", "git://")

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _first_nonempty(*values: Any) -> str:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return ""


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def sanitize_identifier(value: str, default: str = DEFAULT_USER_SPACE, max_len: int = 96) -> str:
    cleaned = _SAFE_ID_RE.sub("-", _clean(value)).strip("-_.:")
    if not cleaned:
        cleaned = default
    if len(cleaned) <= max_len:
        return cleaned
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
    return f"{cleaned[: max_len - 13].rstrip('-_.:')}-{digest}"


def _enabled_tools() -> set[str]:
    raw = os.environ.get("OPENVIKING_MEMORY_TOOLS", "")
    if not raw.strip():
        return set(DEFAULT_TOOLS)
    requested = {part.replace("-", "_") for part in _split_csv(raw)}
    return requested & DEFAULT_TOOLS


@dataclass(frozen=True)
class ProviderConfig:
    endpoint: str = DEFAULT_ENDPOINT
    account: str = DEFAULT_ACCOUNT
    user_space: str = DEFAULT_USER_SPACE
    agent_id: str = DEFAULT_AGENT_ID
    hermes_home: str = ""
    platform: str = "cli"
    agent_identity: str = ""
    user_role_id: str = ""
    enabled_tools: set[str] = field(default_factory=lambda: set(DEFAULT_TOOLS))
    healthcheck_on_initialize: bool = True
    prefetch_limit: int = 5
    search_limit: int = 8
    max_prefetch_chars: int = 3200
    max_tool_chars: int = 8000
    max_message_chars: int = 20000
    max_read_abstract_chars: int = 1200
    max_read_overview_chars: int = 4000
    max_read_full_chars: int = 10000
    commit_keep_recent_count: int = 0
    commit_wait: bool = False
    capture_wait: bool = True
    task_poll_timeout: float = 60.0
    task_poll_interval: float = 2.0
    sync_flush_timeout: float = 10.0
    request_timeout: float = 30.0
    temp_upload_mode: str = "local"
    diagnostics: bool = False

    @classmethod
    def from_env(cls, **runtime: Any) -> "ProviderConfig":
        return cls(
            endpoint=_first_nonempty(os.environ.get("OPENVIKING_ENDPOINT"), DEFAULT_ENDPOINT).rstrip("/"),
            account=sanitize_identifier(_first_nonempty(os.environ.get("OPENVIKING_ACCOUNT"), DEFAULT_ACCOUNT)),
            user_space=sanitize_identifier(
                _first_nonempty(os.environ.get("OPENVIKING_USER_SPACE"), DEFAULT_USER_SPACE)
            ),
            agent_id=sanitize_identifier(_first_nonempty(os.environ.get("OPENVIKING_AGENT_ID"), DEFAULT_AGENT_ID)),
            hermes_home=_clean(runtime.get("hermes_home")),
            platform=_first_nonempty(runtime.get("platform"), "cli"),
            agent_identity=_clean(runtime.get("agent_identity")),
            user_role_id=_first_nonempty(runtime.get("user_id"), runtime.get("user_name")),
            enabled_tools=_enabled_tools(),
            healthcheck_on_initialize=_env_bool("OPENVIKING_HEALTHCHECK_ON_INITIALIZE", True),
            prefetch_limit=_env_int("OPENVIKING_MEMORY_PREFETCH_LIMIT", 5, minimum=1, maximum=20),
            search_limit=_env_int("OPENVIKING_MEMORY_SEARCH_LIMIT", 8, minimum=1, maximum=25),
            max_prefetch_chars=_env_int("OPENVIKING_MEMORY_MAX_PREFETCH_CHARS", 3200, minimum=800),
            max_tool_chars=_env_int("OPENVIKING_MEMORY_MAX_TOOL_CHARS", 8000, minimum=1000),
            max_message_chars=_env_int("OPENVIKING_MEMORY_MAX_MESSAGE_CHARS", 20000, minimum=1000),
            max_read_abstract_chars=_env_int("OPENVIKING_MEMORY_READ_ABSTRACT_CHARS", 1200, minimum=300),
            max_read_overview_chars=_env_int("OPENVIKING_MEMORY_READ_OVERVIEW_CHARS", 4000, minimum=800),
            max_read_full_chars=_env_int("OPENVIKING_MEMORY_READ_FULL_CHARS", 10000, minimum=1000),
            commit_keep_recent_count=_env_int("OPENVIKING_MEMORY_COMMIT_KEEP_RECENT", 0, minimum=0, maximum=100),
            commit_wait=_env_bool("OPENVIKING_MEMORY_COMMIT_WAIT", False),
            capture_wait=_env_bool("OPENVIKING_MEMORY_CAPTURE_WAIT", True),
            task_poll_timeout=_env_float("OPENVIKING_MEMORY_TASK_TIMEOUT", 60.0, minimum=1.0),
            task_poll_interval=_env_float("OPENVIKING_MEMORY_TASK_POLL_INTERVAL", 2.0, minimum=0.25),
            sync_flush_timeout=_env_float("OPENVIKING_MEMORY_SYNC_FLUSH_TIMEOUT", 10.0, minimum=1.0),
            request_timeout=_env_float("OPENVIKING_MEMORY_REQUEST_TIMEOUT", 30.0, minimum=1.0),
            temp_upload_mode=_first_nonempty(os.environ.get("OPENVIKING_TEMP_UPLOAD_MODE"), "local"),
            diagnostics=_env_bool("OPENVIKING_MEMORY_DIAGNOSTICS", False),
        )

    @property
    def memory_root(self) -> str:
        return f"viking://user/{self.user_space}/memories"

    @property
    def resources_root(self) -> str:
        return "viking://resources"

    @property
    def search_target_uri(self) -> str:
        return "viking://"

    def validate_viking_uris(self, uris: Iterable[str], *, allow_root: bool = False) -> list[str]:
        allowed = []
        for uri in uris:
            cleaned = _clean(uri)
            if not cleaned:
                continue
            if cleaned == "viking://":
                if allow_root:
                    allowed.append(cleaned)
                    continue
                raise ValueError("URI must include a viking:// scope")
            parsed = urlparse(cleaned)
            if parsed.scheme != "viking" or not parsed.netloc:
                raise ValueError("URI must use viking://")
            allowed.append(cleaned.rstrip("/"))
        if allowed:
            return allowed
        if allow_root:
            return [self.search_target_uri]
        raise ValueError("viking:// URI is required")

    def validate_resource_uri(self, value: str) -> str:
        cleaned = self.validate_viking_uris([value])[0]
        if not (cleaned == self.resources_root or cleaned.startswith(f"{self.resources_root}/")):
            raise ValueError(f"resource target must stay under {self.resources_root}")
        return cleaned

    def openviking_session_id(self, hermes_session_id: str) -> str:
        raw = sanitize_identifier(hermes_session_id, default="session", max_len=128)
        user_space = sanitize_identifier(self.user_space, default=DEFAULT_USER_SPACE, max_len=48)
        prefix = f"{user_space}__"
        candidate = raw if raw.startswith(prefix) else f"{prefix}{raw}"
        if len(candidate) <= 180:
            return candidate
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]
        return f"{candidate[:167].rstrip('-_.:')}-{digest}"
