#!/usr/bin/env python3
import json
import os
import sys
import urllib.request

api_key = os.environ.get("API_SERVER_KEY")
port = os.environ.get("API_SERVER_PORT", "8642")
home = os.environ.get("HERMES_HOME", "/opt/data")
state_path = os.path.join(home, "gateway_state.json")

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

print("ok")
