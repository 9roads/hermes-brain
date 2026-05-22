from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


REFRESH_PATH_ENV = "PHOENIX_COMPOSIO_SESSION_REFRESH_PATH"
DEFAULT_REFRESH_PATH = "state/phoenix-composio-session/refresh.json"


def refresh_marker_path(environ: Mapping[str, str] | None = None) -> Path:
    env = environ or os.environ
    explicit_path = env.get(REFRESH_PATH_ENV)

    if explicit_path:
        return Path(explicit_path)

    hermes_home = env.get("HERMES_HOME")

    if hermes_home:
        return Path(hermes_home) / DEFAULT_REFRESH_PATH

    return Path.home() / ".hermes" / DEFAULT_REFRESH_PATH


def read_refresh_marker_version(environ: Mapping[str, str] | None = None) -> str | None:
    path = refresh_marker_path(environ)

    try:
        stat = path.stat()
    except OSError:
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        version = payload.get("version") if isinstance(payload, dict) else None

        if isinstance(version, str) and version.strip():
            return version.strip()
    except Exception:
        pass

    return f"mtime:{stat.st_mtime_ns}:size:{stat.st_size}"


def write_refresh_marker(
    reason: str,
    *,
    toolkit: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    path = refresh_marker_path(environ)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": uuid.uuid4().hex,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reason": reason,
        "toolkit": toolkit,
    }

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)

    os.replace(temp_path, path)
    return path
