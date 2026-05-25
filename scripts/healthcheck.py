#!/usr/bin/env python3
import json
import os
import shutil
import sys
import urllib.request

DEFAULT_HERMES_HOME = "/opt/data/profiles/phoenix"
DEFAULT_OPENVIKING_CONFIG_FILE = "/opt/data/openviking/ov.conf"


api_key = os.environ.get("API_SERVER_KEY")
port = os.environ.get("API_SERVER_PORT", "8642")
home = os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME)
state_path = os.path.join(home, "gateway_state.json")
openviking_endpoint = (
    os.environ.get("OPENVIKING_ENDPOINT") or "http://127.0.0.1:1933"
).strip().rstrip("/")
openviking_config_file = os.environ.get(
    "OPENVIKING_CONFIG_FILE",
    DEFAULT_OPENVIKING_CONFIG_FILE,
)

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

# 3. Company memory backend
if not os.path.isfile(openviking_config_file):
    print(f"openviking config missing: {openviking_config_file}", file=sys.stderr)
    sys.exit(1)

openviking_ok = False
last_error = ""

for health_path in ("/health", "/ready"):
    try:
        with urllib.request.urlopen(f"{openviking_endpoint}{health_path}", timeout=3) as r:
            data = json.loads(r.read().decode())
        if data.get("status") in {"ok", "ready"} or data.get("healthy") is True:
            openviking_ok = True
            break
        last_error = f"bad {health_path}: {data}"
    except Exception as e:
        last_error = str(e)

if not openviking_ok:
    print(f"openviking unhealthy at {openviking_endpoint}: {last_error}", file=sys.stderr)
    sys.exit(1)

# 4. Phoenix Composio Tool Router runtime
for name in (
    "BROWSERBASE_API_KEY",
    "BROWSERBASE_PROJECT_ID",
    "COMPOSIO_API_KEY",
    "PHOENIX_BACKEND_URL",
    "PHOENIX_HERMES_PLUGIN_TOKEN",
    "TAVILY_API_KEY",
):
    if not os.environ.get(name, "").strip():
        print(f"{name} missing from Hermes runtime env", file=sys.stderr)
        sys.exit(1)

if not shutil.which("composio"):
    print("composio CLI is not available on PATH", file=sys.stderr)
    sys.exit(1)

print("ok")
