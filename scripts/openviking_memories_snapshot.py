#!/usr/bin/env python3
import base64
import io
import json
import os
import sys
import tarfile
from pathlib import Path


DEFAULT_OPENVIKING_CONFIG_FILE = "/opt/data/openviking/ov.conf"
DEFAULT_OPENVIKING_WORKSPACE = "/opt/data/openviking/workspace"
DEFAULT_AGENT_ID = "hermes-memory"
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
        agent_id = clean_path_component(
            os.environ.get("OPENVIKING_AGENT_ID")
            or os.environ.get("OPENVIKING_AGENT")
            or str(config.get("default_agent") or "")
            or DEFAULT_AGENT_ID,
            "OPENVIKING_AGENT_ID",
        )
        archive = build_archive(
            resolve_snapshot_roots(workspace, account, user_space, agent_id)
        )
        sys.stdout.write(base64.b64encode(archive).decode("ascii"))
        return 0
    except Exception as exc:
        print(f"openviking wiki snapshot failed: {exc}", file=sys.stderr)
        return 1


def resolve_config_path() -> Path:
    configured = os.environ.get("OPENVIKING_CONFIG_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()

    return Path(DEFAULT_OPENVIKING_CONFIG_FILE)


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
        raw_workspace = DEFAULT_OPENVIKING_WORKSPACE

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


def resolve_snapshot_roots(
    workspace: Path, account: str, user_space: str, agent_id: str
) -> list[tuple[str, list[Path]]]:
    return [
        (
            "company/memories",
            [
                workspace / "viking" / account / "user" / user_space / "memories",
                workspace / "viking" / "local" / account / "user" / user_space / "memories",
            ],
        ),
        (
            "agent/memories",
            [
                workspace / "viking" / account / "agent" / agent_id / "memories",
                workspace / "viking" / "local" / account / "agent" / agent_id / "memories",
            ],
        ),
        (
            "resources",
            [
                workspace / "viking" / account / "resources",
                workspace / "viking" / "local" / account / "resources",
            ],
        ),
    ]


def build_archive(snapshot_roots: list[tuple[str, list[Path]]]) -> bytes:
    buffer = io.BytesIO()
    archived_paths = set()

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        for output_root, candidates in snapshot_roots:
            for source_root in candidates:
                source_root_resolved = source_root.resolve(strict=False)
                if not source_root.is_dir():
                    continue

                add_directory(archive, archived_paths, output_root)

                for directory_path in sorted(source_root.rglob("*")):
                    if not should_include_directory(directory_path, source_root_resolved):
                        continue

                    rel_path = directory_path.relative_to(source_root).as_posix()
                    add_directory(archive, archived_paths, f"{output_root}/{rel_path}")

                for file_path in sorted(source_root.rglob("*")):
                    if not should_include_file(file_path, source_root_resolved):
                        continue

                    rel_path = file_path.relative_to(source_root).as_posix()
                    archive_path = f"{output_root}/{rel_path}".strip("/")
                    if archive_path in archived_paths:
                        continue

                    try:
                        content = file_path.read_bytes()
                        tarinfo = tarfile.TarInfo(archive_path)
                        tarinfo.size = len(content)
                        tarinfo.mode = 0o644
                        tarinfo.mtime = 0
                        archive.addfile(tarinfo, io.BytesIO(content))
                        archived_paths.add(archive_path)
                    except ValueError as exc:
                        print(
                            f"skipping unsupported tar path {archive_path}: {exc}",
                            file=sys.stderr,
                        )

    return buffer.getvalue()


def add_directory(
    archive: tarfile.TarFile, archived_paths: set[str], archive_path: str
) -> None:
    cleaned_path = archive_path.strip("/")
    if not cleaned_path or cleaned_path in archived_paths:
        return

    tarinfo = tarfile.TarInfo(cleaned_path)
    tarinfo.type = tarfile.DIRTYPE
    tarinfo.mode = 0o755
    tarinfo.mtime = 0
    archive.addfile(tarinfo)
    archived_paths.add(cleaned_path)


def should_include_directory(directory_path: Path, root: Path) -> bool:
    if directory_path.is_symlink() or not directory_path.is_dir():
        return False

    try:
        resolved = directory_path.resolve(strict=True)
        rel = resolved.relative_to(root)
    except (OSError, ValueError):
        return False

    return not any(part.startswith(".") for part in rel.parts)


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
