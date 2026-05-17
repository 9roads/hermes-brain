from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PLUGIN_STATE_DIR_NAME = "company-memory"
SUMMARY_SCHEMA_VERSION = "company-memory-session-summary-v1"
DEFAULT_WIKI_ROOT = "/opt/data/workspace/wiki"


@dataclass(frozen=True)
class PluginConfig:
    wiki_root: Path
    hermes_home: Path
    state_dir: Path
    max_turn_preview_chars: int
    max_buffer_turns: int


def load_config() -> PluginConfig:
    hermes_home = Path(os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    wiki_root = Path(os.environ.get("COMPANY_MEMORY_WIKI_ROOT") or DEFAULT_WIKI_ROOT)
    state_dir = hermes_home / "local" / PLUGIN_STATE_DIR_NAME

    return PluginConfig(
        wiki_root=wiki_root,
        hermes_home=hermes_home,
        state_dir=state_dir,
        max_turn_preview_chars=_read_int_env("HERMES_SESSION_SUMMARY_TURN_PREVIEW_CHARS", 1800),
        max_buffer_turns=_read_int_env("HERMES_SESSION_SUMMARY_MAX_TURNS", 80),
    )


def _read_int_env(name: str, fallback: int) -> int:
    raw = os.environ.get(name)

    if not raw:
        return fallback

    try:
        parsed = int(raw)
    except ValueError:
        return fallback

    return parsed if parsed > 0 else fallback
