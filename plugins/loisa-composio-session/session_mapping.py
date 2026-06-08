from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    from . import client
except ImportError:
    import client


MAPPING_VERSION = 1
MAPPING_PATH = Path("/opt/data/composio/mapping.json")
UNKNOWN_SESSION_ID = "hermes_session_unknown"


def current_hermes_session_id() -> str | None:
    return clean_session_id(os.environ.get("HERMES_SESSION_ID"))


def is_kanban_worker() -> bool:
    return bool(clean_text(os.environ.get("HERMES_KANBAN_TASK"), max_length=120))


def resolve_mapped_session(session_id: str | None) -> client.BootstrapSessionResponse | None:
    session_id = clean_session_id(session_id)

    if not session_id:
        return None

    direct = read_session_response(session_id)

    if direct is not None:
        return direct

    parent_session_id = read_kanban_parent_session_id()

    if not parent_session_id or parent_session_id == session_id:
        return None

    parent = read_session_response(parent_session_id)

    if parent is None:
        return None

    store_session_response(session_id, parent)
    return parent


def store_session_response(
    session_id: str | None,
    response: client.BootstrapSessionResponse,
) -> bool:
    session_id = clean_session_id(session_id)

    if not session_id:
        return False

    entry = {
        "composio_session_id": response.composio_session_id,
        "missing_tool_url_template": response.missing_tool_url_template,
        "updated_at": int(time.time()),
    }

    try:
        with mapping_lock():
            data = read_mapping_unlocked()
            sessions = data.setdefault("sessions", {})

            if not isinstance(sessions, dict):
                sessions = {}
                data["sessions"] = sessions

            sessions[session_id] = entry
            write_mapping_unlocked(data)
        return True
    except OSError:
        return False


def read_session_response(session_id: str | None) -> client.BootstrapSessionResponse | None:
    session_id = clean_session_id(session_id)

    if not session_id:
        return None

    data = read_mapping()
    sessions = data.get("sessions")

    if not isinstance(sessions, dict):
        return None

    raw = sessions.get(session_id)

    if not isinstance(raw, dict):
        return None

    try:
        return client.parse_bootstrap_response(raw)
    except Exception:
        return None


def read_kanban_parent_session_id() -> str | None:
    task_id = clean_text(os.environ.get("HERMES_KANBAN_TASK"), max_length=120)
    db_path = clean_text(os.environ.get("HERMES_KANBAN_DB"), max_length=5000)

    if not task_id or not db_path:
        return None

    path = Path(db_path).expanduser()

    if not path.exists():
        return None

    try:
        with closing(sqlite3.connect(path)) as conn:
            row = conn.execute(
                "SELECT session_id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if row is None:
        return None

    return clean_session_id(row[0])


def read_mapping() -> dict[str, Any]:
    try:
        return read_mapping_unlocked()
    except OSError:
        return empty_mapping()


def read_mapping_unlocked() -> dict[str, Any]:
    path = MAPPING_PATH.expanduser()

    if not path.exists():
        return empty_mapping()

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return empty_mapping()

    if not isinstance(raw, dict):
        return empty_mapping()

    sessions = raw.get("sessions")

    if not isinstance(sessions, dict):
        sessions = {}

    return {"version": MAPPING_VERSION, "sessions": sessions}


def write_mapping_unlocked(data: dict[str, Any]) -> None:
    path = MAPPING_PATH.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": MAPPING_VERSION,
        "sessions": data.get("sessions") if isinstance(data.get("sessions"), dict) else {},
    }
    fd, tmp_name = tempfile.mkstemp(
        prefix=".mapping.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")

        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def mapping_lock() -> Iterator[None]:
    path = MAPPING_PATH.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False

    with os.fdopen(fd, "r+") as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            locked = True
        except Exception:
            locked = False

        try:
            yield
        finally:
            if locked:
                try:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass


def empty_mapping() -> dict[str, Any]:
    return {"version": MAPPING_VERSION, "sessions": {}}


def clean_session_id(value: Any) -> str | None:
    session_id = clean_text(value, max_length=200)

    if not session_id or session_id == UNKNOWN_SESSION_ID:
        return None

    return session_id


def clean_text(value: Any, *, max_length: int = 500) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    return text[:max_length]
