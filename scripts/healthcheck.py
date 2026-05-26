#!/usr/bin/env python3
import json
import os
import shutil
import sys
import urllib.request

DEFAULT_HERMES_HOME = "/opt/data/profiles/phoenix"
DEFAULT_LLMWIKI_ROOT = "/opt/data/workspace/company"
DEFAULT_LLMWIKI_STATUS_FILE = "/opt/data/phoenix/llmwiki/watch-status.json"


api_key = os.environ.get("API_SERVER_KEY")
port = os.environ.get("API_SERVER_PORT", "8642")
home = os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME)
state_path = os.path.join(home, "gateway_state.json")
llmwiki_root = os.environ.get("PHOENIX_LLMWIKI_ROOT") or os.environ.get("LLMWIKI_ROOT") or DEFAULT_LLMWIKI_ROOT
llmwiki_sources_dir = os.path.join(llmwiki_root, "sources")
llmwiki_wiki_dir = os.path.join(llmwiki_root, "wiki")
llmwiki_schema_file = os.path.join(llmwiki_root, ".llmwiki", "schema.json")
llmwiki_status_file = os.environ.get("PHOENIX_LLMWIKI_STATUS_FILE", DEFAULT_LLMWIKI_STATUS_FILE)

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

# 3. Company wiki backend
if not os.path.isdir(llmwiki_sources_dir):
    print(f"llmwiki sources dir missing: {llmwiki_sources_dir}", file=sys.stderr)
    sys.exit(1)

if not os.path.isdir(llmwiki_wiki_dir):
    print(f"llmwiki wiki dir missing: {llmwiki_wiki_dir}", file=sys.stderr)
    sys.exit(1)

try:
    with open(llmwiki_schema_file) as f:
        json.load(f)
except Exception as e:
    print(f"cannot read llmwiki schema: {e}", file=sys.stderr)
    sys.exit(1)

try:
    with open(llmwiki_status_file) as f:
        llmwiki_status = json.load(f)
except Exception as e:
    print(f"cannot read llmwiki watch status: {e}", file=sys.stderr)
    sys.exit(1)

watch_pid = llmwiki_status.get("pid")
if llmwiki_status.get("status") != "running" or not isinstance(watch_pid, int) or watch_pid <= 0:
    print(f"llmwiki watch not running: {llmwiki_status}", file=sys.stderr)
    sys.exit(1)

try:
    os.kill(watch_pid, 0)
except Exception as e:
    print(f"llmwiki watch pid unhealthy: {e}", file=sys.stderr)
    sys.exit(1)

# 4. Phoenix connected-tool runtime
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

if not shutil.which("nori-slack"):
    print("nori-slack CLI is not available on PATH", file=sys.stderr)
    sys.exit(1)

if not shutil.which("llmwiki"):
    print("llmwiki CLI is not available on PATH", file=sys.stderr)
    sys.exit(1)

print("ok")
