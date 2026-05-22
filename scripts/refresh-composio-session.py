#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROFILE_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = PROFILE_ROOT / "plugins" / "phoenix-composio-session"
sys.path.insert(0, str(PLUGIN_ROOT))

import session_refresh  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Phoenix Composio Tool Router sessions.")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--toolkit")
    args = parser.parse_args()

    path = session_refresh.write_refresh_marker(args.reason, toolkit=args.toolkit)
    print(f"ok {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
