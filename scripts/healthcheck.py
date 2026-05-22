#!/usr/bin/env python3
import json
import os
import shutil
import sys
import urllib.request

DEFAULT_HERMES_HOME = "/opt/data/profiles/phoenix"
DEFAULT_WIKI_ROOT = "/opt/data/workspace/wiki"

api_key = os.environ.get("API_SERVER_KEY")
port = os.environ.get("API_SERVER_PORT", "8642")
home = os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME)
state_path = os.path.join(home, "gateway_state.json")
wiki_root = os.environ.get("COMPANY_MEMORY_WIKI_ROOT") or DEFAULT_WIKI_ROOT

# 1. API health
headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

try:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers=headers)
    with urllib.request.urlopen(req, timeout=3) as r:
        data = json.loads(r.read().decode())
    if data.get("status") != "ok":
        raise RuntimeError(f"bad api health: {data}")
except Exception as e:
    print(f"api unhealthy: {e}", file=sys.stderr)
    sys.exit(1)

# 2. Gateway state
try:
    with open(state_path) as f:
        state = json.load(f)
except Exception as e:
    print(f"cannot read gateway state: {e}", file=sys.stderr)
    sys.exit(1)

if state.get("gateway_state") != "running":
    print(f"gateway not running: {state.get('gateway_state')}", file=sys.stderr)
    sys.exit(1)

platforms = state.get("platforms") or {}
bad_platforms = {
    name: info
    for name, info in platforms.items()
    if isinstance(info, dict)
    and info.get("state") not in {"connected", "running", "ok"}
}

if bad_platforms:
    print(f"bad platforms: {bad_platforms}", file=sys.stderr)
    sys.exit(1)

# 3. Company-memory wiki scaffold
required_wiki_files = ("SCHEMA.md", "index.md", "current-state.md")
missing_wiki_files = [
    name for name in required_wiki_files if not os.path.isfile(os.path.join(wiki_root, name))
]

if missing_wiki_files:
    print(
        f"wiki scaffold missing under {wiki_root}: {', '.join(missing_wiki_files)}",
        file=sys.stderr,
    )
    sys.exit(1)

# 4. Composio Tool Router CLI runtime
if not os.environ.get("COMPOSIO_API_KEY", "").strip():
    print("COMPOSIO_API_KEY missing from Hermes runtime env", file=sys.stderr)
    sys.exit(1)

if not shutil.which("composio"):
    print("composio CLI is not available on PATH", file=sys.stderr)
    sys.exit(1)

print("ok")
