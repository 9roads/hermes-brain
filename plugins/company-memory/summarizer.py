from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

try:
    from .config import PluginConfig
    from .writer import sanitize_text
except ImportError:
    from config import PluginConfig
    from writer import sanitize_text


SUMMARY_FIELDS = [
    "topic",
    "user_goal",
    "completed_work",
    "decisions",
    "files_or_artifacts",
    "open_items",
    "contradictions",
    "follow_up_targets",
    "source_refs",
    "handoff_notes",
]


def build_turn_record(config: PluginConfig, kwargs: dict[str, Any]) -> dict[str, Any]:
    session_id = read_session_id(kwargs)
    assistant_text = first_present(
        kwargs,
        "assistant_response",
        "response",
        "output_text",
        "content",
        "text",
    )
    tool_names = extract_tool_names(kwargs)

    return {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "platform": str(first_present(kwargs, "platform", "source", "surface") or "unknown"),
        "model": str(first_present(kwargs, "model", "model_name") or ""),
        "assistant_preview": sanitize_text(assistant_text or "", config.max_turn_preview_chars),
        "tool_names": tool_names,
        "metadata": compact_metadata(kwargs),
    }


def summarize_session(
    ctx: Any,
    config: PluginConfig,
    *,
    session_id: str,
    records: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    cleaned_records = records[-config.max_buffer_turns :]
    prompt = build_summary_prompt(session_id, cleaned_records)

    if not cleaned_records:
        return fallback_summary(session_id, cleaned_records), "deterministic-fallback"

    llm = getattr(ctx, "llm", None)
    model_label = infer_session_model(cleaned_records) or "host-default"

    if llm and hasattr(llm, "complete_structured"):
        try:
            return normalize_summary(
                llm.complete_structured(prompt=prompt, schema=summary_schema())
            ), model_label
        except Exception:
            pass

    if llm and hasattr(llm, "complete"):
        try:
            raw = llm.complete(prompt=prompt)
            return normalize_summary(parse_jsonish(raw)), model_label
        except Exception:
            pass

    return fallback_summary(session_id, cleaned_records), "deterministic-fallback"


def infer_session_model(records: list[dict[str, Any]]) -> str | None:
    for record in reversed(records):
        model = sanitize_text(record.get("model") or "", 120)
        if model:
            return model

    return None


def build_summary_prompt(session_id: str, records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=True, indent=2, default=str)

    return f"""Create a safe company-memory session summary as strict JSON.

Session id: {session_id}

Rules:
- Include only durable work-memory candidates.
- Include decisions, completed work, files/artifacts, open items, contradictions, follow-up targets, and safe source refs when present.
- Do not include raw transcripts, full messages, secrets, bearer tokens, preview URLs, .env content, auth.json, private personal details, gossip, protected traits, or long source excerpts.
- Keep each list item concise.
- If there is little useful content, say so briefly.

Records:
{payload}
"""


def summary_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "topic": {"type": "string"},
            "user_goal": {"type": "string"},
            "completed_work": {"type": "array", "items": {"type": "string"}},
            "decisions": {"type": "array", "items": {"type": "string"}},
            "files_or_artifacts": {"type": "array", "items": {"type": "string"}},
            "open_items": {"type": "array", "items": {"type": "string"}},
            "contradictions": {"type": "array", "items": {"type": "string"}},
            "follow_up_targets": {"type": "array", "items": {"type": "string"}},
            "source_refs": {"type": "array", "items": {"type": "string"}},
            "handoff_notes": {"type": "string"},
        },
        "required": SUMMARY_FIELDS,
    }


def normalize_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = parse_jsonish(value)

    if not isinstance(value, dict):
        value = {}

    normalized: dict[str, Any] = {}

    for field in SUMMARY_FIELDS:
        raw = value.get(field)

        if field in {
            "completed_work",
            "decisions",
            "files_or_artifacts",
            "open_items",
            "contradictions",
            "follow_up_targets",
            "source_refs",
        }:
            normalized[field] = normalize_string_list(raw)
        else:
            normalized[field] = sanitize_text(raw or "", 2000)

    if not normalized["topic"]:
        normalized["topic"] = "Hermes Session Summary"

    return normalized


def fallback_summary(session_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    previews = [
        sanitize_text(record.get("assistant_preview", ""), 280)
        for record in records[-5:]
        if record.get("assistant_preview")
    ]

    return normalize_summary(
        {
            "topic": "Hermes Session Summary",
            "user_goal": f"Session {session_id} ended. The model summary service was unavailable.",
            "completed_work": previews,
            "decisions": [],
            "files_or_artifacts": [],
            "open_items": [],
            "contradictions": [],
            "follow_up_targets": [],
            "source_refs": [],
            "handoff_notes": "Deterministic fallback summary generated from redacted assistant turn previews.",
        }
    )


def read_session_id(kwargs: dict[str, Any]) -> str:
    raw = first_present(kwargs, "session_id", "conversation_id", "run_id", "task_id")
    return sanitize_text(raw or "unknown-session", 120)


def first_present(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in values and values[key] is not None:
            return values[key]

    return None


def compact_metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "event",
        "source",
        "surface",
        "platform",
        "conversation_id",
        "run_id",
        "task_id",
    }
    return {
        key: sanitize_text(value, 240)
        for key, value in kwargs.items()
        if key in allowed and isinstance(value, (str, int, float, bool))
    }


def extract_tool_names(kwargs: dict[str, Any]) -> list[str]:
    tool_names: list[str] = []

    for key in ("tool_calls", "tools_used", "tool_results"):
        raw = kwargs.get(key)

        if isinstance(raw, list):
            for item in raw:
                name = extract_tool_name(item)
                if name and name not in tool_names:
                    tool_names.append(name)

    return tool_names[:20]


def extract_tool_name(value: Any) -> str | None:
    if isinstance(value, str):
        return sanitize_text(value, 80)

    if isinstance(value, dict):
        for key in ("name", "tool_name", "function", "id"):
            raw = value.get(key)
            if isinstance(raw, str):
                return sanitize_text(raw, 80)

    return None


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    raw_values = value if isinstance(value, list) else [value]
    items = [sanitize_text(item, 700).strip() for item in raw_values]
    return [item for item in items if item][:20]


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "topic": "Hermes Session Summary",
            "handoff_notes": sanitize_text(text, 2000),
        }
