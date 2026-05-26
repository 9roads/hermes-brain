#!/usr/bin/env python3
import base64
import io
import os
import sys
import tarfile
from pathlib import Path


DEFAULT_LLMWIKI_ROOT = "/opt/data/workspace/company"
MARKDOWN_SUFFIXES = {".md", ".markdown"}


def main() -> int:
    try:
        wiki_root = resolve_wiki_root()
        archive = build_archive(wiki_root)
        sys.stdout.write(base64.b64encode(archive).decode("ascii"))
        return 0
    except Exception as exc:
        print(f"llmwiki snapshot failed: {exc}", file=sys.stderr)
        return 1


def resolve_wiki_root() -> Path:
    configured = (
        os.environ.get("PHOENIX_LLMWIKI_WIKI_ROOT")
        or os.environ.get("LLMWIKI_WIKI_ROOT")
        or ""
    ).strip()
    if configured:
        return Path(configured).expanduser().resolve()

    root = (
        os.environ.get("PHOENIX_LLMWIKI_ROOT")
        or os.environ.get("LLMWIKI_ROOT")
        or DEFAULT_LLMWIKI_ROOT
    ).strip()
    return (Path(root).expanduser() / "wiki").resolve()


def build_archive(wiki_root: Path) -> bytes:
    buffer = io.BytesIO()
    root = wiki_root.resolve(strict=False)

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        if wiki_root.is_dir():
            for file_path in sorted(wiki_root.rglob("*")):
                if not should_include_file(file_path, root):
                    continue

                rel_path = file_path.relative_to(wiki_root).as_posix()
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
