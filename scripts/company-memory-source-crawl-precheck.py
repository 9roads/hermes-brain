#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


DEFAULT_HERMES_HOME = "/opt/data/profiles/phoenix"
DEFAULT_MIN_INTERVAL_MINUTES = 15
DEFAULT_STANDARD_INTERVAL_MINUTES = 60


def main() -> int:
    hermes_home = Path(os.environ.get("HERMES_HOME") or DEFAULT_HERMES_HOME)
    wiki_root = Path(os.environ.get("COMPANY_MEMORY_WIKI_ROOT") or str(hermes_home / "wiki"))
    state_dir = wiki_root / "raw" / "_state"
    policy_path = state_dir / "adaptive-policy.json"
    now = datetime.now(timezone.utc)
    policy = read_json(policy_path)
    last_run_at = parse_time(policy.get("last_run_at")) if isinstance(policy, dict) else None
    due_mode = decide_mode(wiki_root, policy, last_run_at, now)

    if due_mode == "skip":
        print(json.dumps({"wakeAgent": False, "reason": "adaptive_cooldown"}))
        return 0

    context = {
        "schema_version": 1,
        "mode": due_mode,
        "now": now.isoformat(),
        "last_run_at": last_run_at.isoformat() if last_run_at else None,
        "policy_path": str(policy_path),
        "wiki_root": str(wiki_root),
        "toolkit_budgets": default_budgets(due_mode),
        "read_only": True,
        "raw_output_root": str(wiki_root / "raw" / "runs"),
    }

    print(json.dumps({"wakeAgent": True, "context": context}, sort_keys=True))
    return 0


def decide_mode(
    wiki_root: Path,
    policy: Any,
    last_run_at: datetime | None,
    now: datetime,
) -> str:
    pending_hint_count = count_recent_raw_inputs(wiki_root, last_run_at)

    if pending_hint_count > 200:
        return "catchup"

    if pending_hint_count > 0:
        return "standard"

    if not last_run_at:
        return "quick"

    age = now - last_run_at
    cooldown_until = parse_time(policy.get("cooldown_until")) if isinstance(policy, dict) else None

    if cooldown_until and now < cooldown_until:
        return "skip"

    if age >= timedelta(minutes=DEFAULT_STANDARD_INTERVAL_MINUTES):
        return "quick"

    if age < timedelta(minutes=DEFAULT_MIN_INTERVAL_MINUTES):
        return "skip"

    next_toolkits = policy.get("next_toolkits") if isinstance(policy, dict) else None

    if isinstance(next_toolkits, list) and next_toolkits:
        return "quick"

    return "skip"


def count_recent_raw_inputs(wiki_root: Path, since: datetime | None) -> int:
    roots = [
        wiki_root / "raw" / "session-summaries",
        wiki_root / "raw" / "runs",
    ]
    count = 0

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if since is None:
                count += 1
                continue

            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified > since:
                count += 1

            if count > 200:
                return count

    return count


def default_budgets(mode: str) -> dict[str, dict[str, int]]:
    if mode == "catchup":
        return {"default": {"lookback_hours": 72, "max_items": 400, "max_detail_reads": 60}}

    if mode == "standard":
        return {"default": {"lookback_hours": 24, "max_items": 200, "max_detail_reads": 30}}

    return {"default": {"lookback_hours": 12, "max_items": 80, "max_detail_reads": 12}}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    sys.exit(main())
