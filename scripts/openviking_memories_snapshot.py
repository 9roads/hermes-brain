#!/usr/bin/env python3
import base64
import io
import json
import os
import sys
import tarfile
from pathlib import Path


DEFAULT_HERMES_HOME = "/opt/data/profiles/phoenix"
MARKDOWN_SUFFIXES = {".md", ".markdown"}


def main() -> int:
    try:
        config = load_config(resolve_config_path())
        workspace = resolve_workspace(config)
        account = clean_path_component(
            os.environ.get("OPENVIKING_ACCOUNT")
            or str(config.get("default_account") or "")
            or "default",
            "OPENVIKING_ACCOUNT",
        )
        user_space = clean_path_component(
            os.environ.get("OPENVIKING_USER_SPACE")
            or os.environ.get("OPENVIKING_USER")
            or str(config.get("default_user") or "")
            or "default",
            "OPENVIKING_USER_SPACE",
        )
        memories_root = workspace / "viking" / "local" / account / "user" / user_space / "memories"
        archive = build_archive(memories_root)
        sys.stdout.write(base64.b64encode(archive).decode("ascii"))
        return 0
    except Exception as exc:
        print(f"openviking memories snapshot failed: {exc}", file=sys.stderr)
        return 1


def resolve_config_path() -> Path:
    configured = os.environ.get("OPENVIKING_CONFIG_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()

    hermes_home = os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME).strip() or DEFAULT_HERMES_HOME
    return Path(hermes_home).expanduser() / "openviking" / "ov.conf"


def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"OpenViking config must be a JSON object: {config_path}")

    return data


def resolve_workspace(config: dict) -> Path:
    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    raw_workspace = str(storage.get("workspace") or "").strip()

    if not raw_workspace:
        raw_workspace = os.environ.get("OPENVIKING_WORKSPACE_DIR", "").strip()

    if not raw_workspace:
        hermes_home = os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME).strip() or DEFAULT_HERMES_HOME
        raw_workspace = str(Path(hermes_home).expanduser() / "openviking" / "workspace")

    expanded = os.path.expandvars(raw_workspace)
    return Path(expanded).expanduser().resolve()


def clean_path_component(value: str, env_name: str) -> str:
    cleaned = value.strip()
    if (
        not cleaned
        or cleaned in {".", ".."}
        or "/" in cleaned
        or "\\" in cleaned
        or "\x00" in cleaned
    ):
        raise ValueError(f"{env_name} is not a safe OpenViking path component")
    return cleaned


def build_archive(memories_root: Path) -> bytes:
    buffer = io.BytesIO()
    root = memories_root.resolve(strict=False)

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        if memories_root.is_dir():
            for file_path in sorted(memories_root.rglob("*")):
                if not should_include_file(file_path, root):
                    continue

                rel_path = file_path.relative_to(memories_root).as_posix()
                try:
                    content = file_path.read_bytes()
                    tarinfo = tarfile.TarInfo(rel_path)
                    tarinfo.size = len(content)
                    tarinfo.mode = 0o644
                    tarinfo.mtime = 0
                    archive.addfile(tarinfo, io.BytesIO(content))
                except ValueError as exc:
                    print(f"skipping unsupported tar path {rel_path}: {exc}", file=sys.stderr)

    return buffer.getvalue()


def should_include_file(file_path: Path, root: Path) -> bool:
    if file_path.is_symlink() or not file_path.is_file():
        return False

    suffix = file_path.suffix.lower()
    if suffix not in MARKDOWN_SUFFIXES:
        return False

    try:
        resolved = file_path.resolve(strict=True)
        rel = resolved.relative_to(root)
    except (OSError, ValueError):
        return False

    return not any(part.startswith(".") for part in rel.parts)


if __name__ == "__main__":
    raise SystemExit(main())
