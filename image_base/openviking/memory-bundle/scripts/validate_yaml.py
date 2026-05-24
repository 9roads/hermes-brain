#!/usr/bin/env python3
"""Validate custom memory schema YAML syntax for this bundle.

This checks YAML syntax only. It does not guarantee OpenViking runtime compatibility.
Run from the bundle root:

    python scripts/validate_yaml.py
"""
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
paths = sorted((ROOT / "custom-memory").glob("*.yaml"))

ok = True
for path in paths:
    try:
        with path.open("r", encoding="utf-8") as f:
            yaml.safe_load(f)
        print(f"OK   {path.relative_to(ROOT)}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"FAIL {path.relative_to(ROOT)}: {exc}", file=sys.stderr)

sys.exit(0 if ok else 1)
