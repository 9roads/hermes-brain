"""Safe local upload helpers for OpenViking resources."""

from __future__ import annotations

import fnmatch
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from .client import OpenVikingClient
from .config import ProviderConfig, REMOTE_RESOURCE_PREFIXES


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _is_windows_absolute_path(value: str) -> bool:
    return len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] in {"/", "\\"}


def is_remote_resource_source(value: str) -> bool:
    return value.startswith(REMOTE_RESOURCE_PREFIXES)


def is_local_path_reference(value: str) -> bool:
    if not value or "\n" in value or "\r" in value:
        return False
    if is_remote_resource_source(value):
        return False
    if _is_windows_absolute_path(value):
        return True
    return (
        value.startswith(("/", "./", "../", "~/", ".\\", "..\\", "~\\"))
        or "/" in value
        or "\\" in value
    )


def path_from_file_uri(uri: str) -> Path | str:
    parsed = urlparse(uri)
    if parsed.netloc not in {"", "localhost"}:
        return f"Unsupported non-local file URI: {uri}"
    return Path(url2pathname(parsed.path)).expanduser()


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    name = Path(rel_path).name
    return any(fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def zip_directory(
    dir_path: Path,
    *,
    ignore_dirs: Any = None,
    include: Any = None,
    exclude: Any = None,
) -> Path:
    root = dir_path.resolve()
    ignored_dirs = set(_split_csv(ignore_dirs))
    include_patterns = _split_csv(include)
    exclude_patterns = _split_csv(exclude)
    zip_path = Path(tempfile.gettempdir()) / f"openviking_memory_upload_{uuid.uuid4().hex}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in dir_path.rglob("*"):
            if file_path.is_symlink():
                continue
            if not file_path.is_file():
                continue
            try:
                resolved = file_path.resolve()
                resolved.relative_to(root)
            except ValueError:
                continue
            rel_path = str(file_path.relative_to(dir_path)).replace("\\", "/")
            rel_parts = Path(rel_path).parts
            if ignored_dirs and any(part in ignored_dirs for part in rel_parts[:-1]):
                continue
            if include_patterns and not _matches_any(rel_path, include_patterns):
                continue
            if exclude_patterns and _matches_any(rel_path, exclude_patterns):
                continue
            archive.write(file_path, arcname=rel_path)

    return zip_path


def _validate_target(config: ProviderConfig, key: str, value: str) -> str:
    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned:
        return ""
    cleaned = config.validate_resource_uri(cleaned)
    if key == "to" and cleaned == config.resources_root:
        raise ValueError(f"'to' must point to a resource item under {config.resources_root}")
    return cleaned


def build_resource_payload(config: ProviderConfig, args: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "reason",
        "instruction",
        "strict",
        "ignore_dirs",
        "include",
        "exclude",
        "directly_upload_media",
        "preserve_structure",
    ):
        if key in args and args[key] not in {None, ""}:
            payload[key] = args[key]

    if config.diagnostics and args.get("telemetry"):
        payload["telemetry"] = True

    if args.get("to") and args.get("parent"):
        raise ValueError("Cannot specify both 'to' and 'parent'")
    if args.get("to"):
        payload["to"] = _validate_target(config, "to", args["to"])
    else:
        parent = _validate_target(config, "parent", args.get("parent") or config.resources_root)
        payload["parent"] = parent
        payload["create_parent"] = bool(args.get("create_parent", True))

    return payload


def add_resource_from_source(
    client: OpenVikingClient,
    config: ProviderConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    source = str(args.get("source") or args.get("url") or "").strip()
    if not source:
        raise ValueError("source is required")

    payload = build_resource_payload(config, args)
    parsed = urlparse(source)
    cleanup_path: Path | None = None
    source_path: Path | str | None

    if is_remote_resource_source(source):
        source_path = None
    elif parsed.scheme == "file":
        source_path = path_from_file_uri(source)
        if isinstance(source_path, str):
            raise ValueError(source_path)
    elif parsed.scheme and not _is_windows_absolute_path(source):
        source_path = None
    else:
        source_path = Path(source).expanduser()

    try:
        if source_path is None:
            payload["path"] = source
        elif isinstance(source_path, Path) and source_path.exists():
            if source_path.is_dir():
                payload["source_name"] = source_path.name
                cleanup_path = zip_directory(
                    source_path,
                    ignore_dirs=args.get("ignore_dirs"),
                    include=args.get("include"),
                    exclude=args.get("exclude"),
                )
                upload_path = cleanup_path
            elif source_path.is_file():
                payload["source_name"] = source_path.name
                upload_path = source_path
            else:
                raise ValueError(f"Unsupported local resource path: {source}")
            payload["temp_file_id"] = client.upload_temp_file(upload_path)
        elif is_local_path_reference(source):
            raise ValueError(f"Local resource path does not exist: {source}")
        else:
            payload["path"] = source

        response = client.add_resource(payload)
        result = client.unwrap_result(response)
        if not isinstance(result, dict):
            result = {}
        return {"payload": payload, "result": result}
    finally:
        if cleanup_path:
            cleanup_path.unlink(missing_ok=True)
