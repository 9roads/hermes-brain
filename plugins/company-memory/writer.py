from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

try:
    from .config import PluginConfig, SUMMARY_SCHEMA_VERSION
except ImportError:
    from config import PluginConfig, SUMMARY_SCHEMA_VERSION


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"dtn_[A-Za-z0-9_-]{8,}"),
    re.compile(r"kg_[A-Za-z0-9_-]{8,}"),
    re.compile(r"phx_[A-Za-z0-9_-]{8,}"),
    re.compile(r"xox[a-z]-[A-Za-z0-9-]{8,}", re.IGNORECASE),
    re.compile(r"xapp-[A-Za-z0-9-]{8,}", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
    re.compile(r"(x-daytona-preview-token[=:]\s*)[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
    re.compile(r"https://[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]*daytona[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]*", re.IGNORECASE),
]


def sanitize_text(value: Any, limit: int | None = None) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, default=str)

    for pattern in SECRET_PATTERNS:
        text = pattern.sub(_redaction_replacement, text)

    text = text.replace("\x00", "")

    if limit and len(text) > limit:
        return f"{text[:limit].rstrip()}... [truncated]"

    return text


def append_turn_buffer(config: PluginConfig, session_id: str, record: dict[str, Any]) -> Path:
    path = buffer_path(config, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True, default=str))
        handle.write("\n")

    return path


def load_turn_buffer(config: PluginConfig, session_id: str) -> list[dict[str, Any]]:
    path = buffer_path(config, session_id)

    if not path.exists():
        return []

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict):
                records.append(value)

    return records


def write_session_summary_receipt(
    config: PluginConfig,
    *,
    session_id: str,
    platform: str,
    model: str,
    summary: dict[str, Any],
    generated_at: datetime | None = None,
) -> Path:
    now = generated_at or datetime.now(timezone.utc)
    safe_session_id = safe_path_component(session_id or "unknown-session")
    directory = (
        config.wiki_root
        / "raw"
        / "session-summaries"
        / now.strftime("%Y")
        / now.strftime("%m")
        / now.strftime("%d")
    )
    directory.mkdir(parents=True, exist_ok=True)

    existing = sorted(directory.glob(f"*-{safe_session_id}.md"))

    if existing:
        return existing[-1]

    body = render_summary_body(summary)
    digest = sha256(body.encode("utf-8")).hexdigest()
    filename = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{safe_session_id}.md"
    target = directory / filename
    frontmatter = {
        "source_type": "hermes_session_summary",
        "session_id": session_id,
        "platform": platform or "unknown",
        "model": model or "unknown",
        "ingested": now.isoformat(),
        "sha256": digest,
        "summary_schema": SUMMARY_SCHEMA_VERSION,
        "confidence": "low",
    }
    content = f"---\n{render_frontmatter(frontmatter)}---\n\n{body}"

    atomic_write_text(target, sanitize_text(content))
    return target


def buffer_path(config: PluginConfig, session_id: str) -> Path:
    return config.state_dir / "buffers" / f"{safe_path_component(session_id)}.jsonl"


def safe_path_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())[:120].strip(".-")
    return normalized or "unknown"


def atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(target.parent),
        prefix=f".{target.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        temp_name = handle.name

    Path(temp_name).replace(target)


def render_frontmatter(values: dict[str, Any]) -> str:
    lines = []

    for key, value in values.items():
        if isinstance(value, str):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=True)}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=True, default=str)}")

    return "\n".join(lines) + "\n"


def render_summary_body(summary: dict[str, Any]) -> str:
    title = sanitize_text(summary.get("topic") or "Hermes Session Summary", 140)
    sections = [
        f"# {title}",
        render_section("User Goal", summary.get("user_goal")),
        render_list_section("Completed Work", summary.get("completed_work")),
        render_list_section("Decisions", summary.get("decisions")),
        render_list_section("Files Or Artifacts", summary.get("files_or_artifacts")),
        render_list_section("Open Items", summary.get("open_items")),
        render_list_section("Contradictions Or Uncertainty", summary.get("contradictions")),
        render_list_section("Follow Up Targets", summary.get("follow_up_targets")),
        render_section("Handoff Notes", summary.get("handoff_notes")),
        render_list_section("Source References", summary.get("source_refs")),
    ]

    return "\n\n".join(section for section in sections if section).strip() + "\n"


def render_section(title: str, value: Any) -> str:
    text = sanitize_text(value or "", 2400).strip()

    if not text:
        return ""

    return f"## {title}\n\n{text}"


def render_list_section(title: str, value: Any) -> str:
    if not value:
        return ""

    values = value if isinstance(value, list) else [value]
    items = [sanitize_text(item, 800).strip() for item in values]
    items = [item for item in items if item]

    if not items:
        return ""

    return f"## {title}\n\n" + "\n".join(f"- {item}" for item in items)


def _redaction_replacement(match: re.Match[str]) -> str:
    if match.lastindex:
        prefix = match.group(1) or ""
        return f"{prefix}[redacted]"

    return "[redacted]"
