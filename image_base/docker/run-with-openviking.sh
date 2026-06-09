#!/usr/bin/env bash
set -Eeuo pipefail

default_data_root="/opt/data"
profile_name="${HERMES_PROFILE_NAME:-${LOISA_HERMES_PROFILE_NAME:-loisa}}"
profile_distribution_repo="${HERMES_PROFILE_DISTRIBUTION_REPO:-https://github.com/9roads/hermes-brain.git}"
initial_hermes_home="${HERMES_HOME:-$default_data_root}"
profile_suffix="/profiles/$profile_name"

if [[ "$initial_hermes_home" == *"$profile_suffix" ]]; then
  data_root="${initial_hermes_home%"$profile_suffix"}"
  profile_dir="$initial_hermes_home"
else
  data_root="$initial_hermes_home"
  profile_dir="$data_root/profiles/$profile_name"
fi

root_home_dir="$data_root/home"
profile_home_dir="$profile_dir/home"
root_bin_dir="$root_home_dir/.local/bin"
profile_bin_dir="$profile_home_dir/.local/bin"

export HERMES_PROFILE_NAME="$profile_name"
export LOISA_HERMES_PROFILE_NAME="${LOISA_HERMES_PROFILE_NAME:-$profile_name}"
export HERMES_GATEWAY_NO_SUPERVISE="${HERMES_GATEWAY_NO_SUPERVISE:-1}"
export PATH="/opt/hermes/bin:/opt/hermes/.venv/bin:$root_bin_dir:$profile_bin_dir:$PATH"

load_env_file() {
  local env_file="$1"
  local line key value

  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*export[[:space:]]+(.+)$ ]] && line="${BASH_REMATCH[1]}"

    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"

      if [[ "$value" =~ ^\"(.*)\"$ ]]; then
        value="${BASH_REMATCH[1]}"
      elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
      fi

      export "$key=$value"
    fi
  done < "$env_file"
}

load_env_file "$data_root/.env"
load_env_file "$profile_dir/.env"

codex_home="${CODEX_HOME:-${LOISA_CODEX_HOME:-$data_root/codex}}"
export LOISA_CODEX_HOME="$codex_home"
export CODEX_HOME="$codex_home"

if [ -z "${SLACK_TOKEN:-}" ] && [ -n "${SLACK_BOT_TOKEN:-}" ]; then
  export SLACK_TOKEN="$SLACK_BOT_TOKEN"
fi

if [ -z "${SLACK_BOT_TOKEN:-}" ] && [ -n "${SLACK_TOKEN:-}" ]; then
  export SLACK_BOT_TOKEN="$SLACK_TOKEN"
fi

export SLACK_API_BASE="${SLACK_API_BASE:-https://slack.com/api/}"

profile_distribution_repo="${HERMES_PROFILE_DISTRIBUTION_REPO:-$profile_distribution_repo}"
export HERMES_PROFILE_DISTRIBUTION_REPO="$profile_distribution_repo"

mkdir -p "$root_home_dir" "$profile_home_dir" "$root_bin_dir" "$profile_bin_dir" "$codex_home"

ensure_hermes_cli() {
  local system_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

  if ! command -v hermes >/dev/null 2>&1; then
    echo "[hermes] hermes CLI is not available on PATH" >&2
    exit 1
  fi

  if ! hermes --help >/dev/null 2>&1; then
    echo "[hermes] hermes CLI failed to run" >&2
    exit 1
  fi

  if ! /opt/hermes/hermes --help >/dev/null 2>&1; then
    echo "[hermes] /opt/hermes/hermes failed to run" >&2
    exit 1
  fi

  if ! PATH="$system_path" hermes --help >/dev/null 2>&1; then
    echo "[hermes] hermes CLI is not available from the system PATH" >&2
    exit 1
  fi
}

ensure_python() {
  if command -v python >/dev/null 2>&1; then
    return 0
  fi

  echo "[loisa] python is not available on PATH" >&2
  exit 1
}

ensure_openviking_cli() {
  if ! command -v openviking >/dev/null 2>&1; then
    echo "[openviking] openviking CLI is not available on PATH" >&2
    exit 1
  fi

  if ! command -v ov >/dev/null 2>&1; then
    echo "[openviking] ov CLI alias is not available on PATH" >&2
    exit 1
  fi
}

patch_openviking_studio_bootstrap() {
  local patch_script="${OPENVIKING_STUDIO_PATCH_SCRIPT:-/opt/hermes/image_base/loisa_openviking_studio_patch.py}"

  if [ ! -f "$patch_script" ]; then
    echo "[openviking] Studio bootstrap patch is not available: $patch_script" >&2
    exit 1
  fi

  python "$patch_script"
}

configure_openviking_cli_language() {
  HOME="$root_home_dir" ov language en >/dev/null
  HOME="$profile_home_dir" ov language en >/dev/null
}

configure_openviking_cli_runtime() {
  local cli_config_file="$1"
  local tmp_file="$cli_config_file.tmp.$$"

  python - "$cli_config_file" "$tmp_file" <<'PY'
import json
import os
from pathlib import Path
import sys

config_file = Path(sys.argv[1])
tmp_file = Path(sys.argv[2])

try:
    config = json.loads(config_file.read_text(encoding="utf-8"))
except FileNotFoundError:
    config = {}

if not isinstance(config, dict):
    config = {}

config["url"] = os.environ["OPENVIKING_ENDPOINT"]
config["account"] = os.environ["OPENVIKING_ACCOUNT"]
config["user"] = os.environ["OPENVIKING_USER"]
config["agent_id"] = os.environ["OPENVIKING_AGENT_ID"]
auth_mode = os.environ.get("OPENVIKING_AUTH_MODE", "").strip()
if auth_mode:
    config["auth_mode"] = auth_mode

api_key = os.environ.get("OPENVIKING_API_KEY") or os.environ.get("OPENVIKING_ROOT_API_KEY")
if api_key:
    config["api_key"] = api_key
else:
    config.pop("api_key", None)

tmp_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
os.replace(tmp_file, config_file)
PY
  chmod 640 "$cli_config_file" 2>/dev/null || true
}

configure_openviking_server_runtime() {
  local config_file="$1"
  local tmp_file="$config_file.tmp.$$"

  python - "$config_file" "$tmp_file" <<'PY'
import json
import os
from pathlib import Path
import sys

config_file = Path(sys.argv[1])
tmp_file = Path(sys.argv[2])

try:
    config = json.loads(config_file.read_text(encoding="utf-8"))
except FileNotFoundError:
    config = {}

if not isinstance(config, dict):
    config = {}

server = config.get("server")
if not isinstance(server, dict):
    server = {}

server["host"] = os.environ["OPENVIKING_HOST"]
server["port"] = int(os.environ["OPENVIKING_PORT"])
root_api_key = os.environ.get("OPENVIKING_ROOT_API_KEY", "").strip()
auth_mode = os.environ.get("OPENVIKING_AUTH_MODE", "").strip()

if root_api_key:
    server["root_api_key"] = root_api_key
    server["auth_mode"] = auth_mode or "api_key"
elif server["host"] not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit(
        "OPENVIKING_ROOT_API_KEY is required when OPENVIKING_HOST is not localhost"
    )
else:
    server.pop("root_api_key", None)
    if auth_mode:
        server["auth_mode"] = auth_mode
    else:
        server["auth_mode"] = "dev"

config["server"] = server

tmp_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
os.replace(tmp_file, config_file)
PY
  chmod 640 "$config_file" 2>/dev/null || true
}

ensure_composio_cli() {
  if command -v composio >/dev/null 2>&1; then
    return 0
  fi

  echo "[loisa] composio CLI is not available on PATH" >&2
  exit 1
}

ensure_nori_slack_cli() {
  if command -v nori-slack >/dev/null 2>&1; then
    return 0
  fi

  echo "[loisa] nori-slack CLI is not available on PATH" >&2
  exit 1
}

ensure_parallel_cli() {
  if ! command -v parallel-cli >/dev/null 2>&1; then
    echo "[loisa] parallel-cli is not available on PATH" >&2
    exit 1
  fi

  parallel-cli --version >/dev/null
}

configure_parallel_cli() {
  local config_dir="$profile_home_dir/.config/parallel-web-tools"
  local auth_file="$config_dir/auth.json"
  local previous_umask
  local status

  if [ -z "${PARALLEL_API_KEY:-}" ]; then
    echo "[parallel] PARALLEL_API_KEY is not set; Parallel CLI auth was not initialized"
    return 0
  fi

  previous_umask="$(umask)"
  umask 077
  mkdir -p "$config_dir"

  if python - "$auth_file" <<'PY'
import json
import os
from pathlib import Path
import sys

api_key = os.environ.get("PARALLEL_API_KEY", "")
if not api_key:
    raise SystemExit("PARALLEL_API_KEY is not set")

auth_file = Path(sys.argv[1])
tmp_file = auth_file.with_name(f"{auth_file.name}.tmp.{os.getpid()}")
payload = {
    "version": 1,
    "selected_org_id": "loisa",
    "orgs": {
        "loisa": {
            "api_key": api_key,
            "org_name": "Loisa",
        }
    },
    "client_id": None,
}

tmp_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp_file.chmod(0o600)
os.replace(tmp_file, auth_file)
auth_file.chmod(0o600)
PY
  then
    :
  else
    status=$?
    umask "$previous_umask"
    return "$status"
  fi

  chmod 0700 "$config_dir" 2>/dev/null || true
  env -u PARALLEL_API_KEY HOME="$profile_home_dir" parallel-cli auth --json >/dev/null || {
    status=$?
    umask "$previous_umask"
    return "$status"
  }
  umask "$previous_umask"
}

ensure_kernel_cli() {
  if ! command -v kernel >/dev/null 2>&1; then
    echo "[loisa] kernel CLI is not available on PATH" >&2
    exit 1
  fi

  kernel --version >/dev/null
}

ensure_bun_cli() {
  if ! command -v bun >/dev/null 2>&1; then
    echo "[loisa] bun CLI is not available on PATH" >&2
    exit 1
  fi

  if ! command -v bunx >/dev/null 2>&1; then
    echo "[loisa] bunx CLI is not available on PATH" >&2
    exit 1
  fi

  bun --version >/dev/null
}

ensure_codex_cli() {
  if command -v codex >/dev/null 2>&1; then
    return 0
  fi

  echo "[codex] codex CLI is not available on PATH" >&2
  exit 1
}

toml_string() {
  local value="$1"

  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

write_bunfig() {
  local config_file="$1"
  local tmp_file="$config_file.tmp.$$"

  mkdir -p "$(dirname "$config_file")"

  {
    printf '[install]\n'
    printf 'linker = "isolated"\n'
    printf 'globalStore = true\n'
    printf '\n'
    printf '[install.cache]\n'
    printf 'dir = %s\n' "$(toml_string "$BUN_INSTALL_CACHE_DIR")"
    printf 'disable = false\n'
    printf 'disableManifest = false\n'
  } > "$tmp_file"

  mv "$tmp_file" "$config_file"
  chmod 0644 "$config_file" 2>/dev/null || true
}

configure_bun() {
  export BUN_INSTALL_CACHE_DIR="${BUN_INSTALL_CACHE_DIR:-$data_root/bun/install/cache}"
  export BUN_INSTALL_GLOBAL_STORE="${BUN_INSTALL_GLOBAL_STORE:-1}"

  mkdir -p "$BUN_INSTALL_CACHE_DIR"
  write_bunfig "$root_home_dir/.bunfig.toml"
  write_bunfig "$profile_home_dir/.bunfig.toml"
}

configure_codex_cli() {
  local config_file="$codex_home/config.toml"
  local previous_umask
  local tmp_file="$config_file.tmp.$$"

  previous_umask="$(umask)"
  umask 077
  mkdir -p "$codex_home"

  {
    printf 'forced_login_method = "api"\n'
    printf 'cli_auth_credentials_store = "file"\n'
    printf 'check_for_update_on_startup = false\n'
    if [ -n "${OPENAI_BASE_URL:-}" ]; then
      printf 'openai_base_url = %s\n' "$(toml_string "$OPENAI_BASE_URL")"
    fi
  } > "$tmp_file"
  mv "$tmp_file" "$config_file"
  chmod 600 "$config_file" 2>/dev/null || true

  if [ -n "${OPENAI_API_KEY:-}" ]; then
    printf '%s\n' "$OPENAI_API_KEY" | codex login --with-api-key >/dev/null
  else
    echo "[codex] OPENAI_API_KEY is not set; Codex CLI auth was not initialized"
  fi

  umask "$previous_umask"
}

run_root_hermes() {
  HERMES_HOME="$data_root" HOME="$root_home_dir" "$@"
}

run_profile_hermes() {
  HERMES_HOME="$profile_dir" HOME="$profile_home_dir" "$@"
}

truthy() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

is_local_profile_distribution_repo() {
  case "$profile_distribution_repo" in
    http://*|https://*|ssh://*|git://*|git@*) return 1 ;;
    *) return 0 ;;
  esac
}

remove_legacy_distribution_skill_shadows() {
  run_profile_hermes python - <<'PY'
import filecmp
import os
import shutil
from pathlib import Path

profile_dir = Path(os.environ["HERMES_HOME"])
local_skills = profile_dir / "skills"
distribution_skills = profile_dir / "distribution-skills"

if not local_skills.is_dir() or not distribution_skills.is_dir():
    raise SystemExit(0)


def relative_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def directories_match(left: Path, right: Path) -> bool:
    left_files = relative_files(left)
    right_files = relative_files(right)
    if left_files != right_files:
        return False
    return all(filecmp.cmp(left / rel, right / rel, shallow=False) for rel in left_files)


removed = []
kept = []
for dist_skill in sorted(path for path in distribution_skills.iterdir() if path.is_dir()):
    local_skill = local_skills / dist_skill.name
    if not local_skill.is_dir():
        continue
    if directories_match(local_skill, dist_skill):
        shutil.rmtree(local_skill)
        removed.append(dist_skill.name)
    else:
        kept.append(dist_skill.name)

if removed:
    print("[loisa] Removed legacy default skill shadows: " + ", ".join(removed))
if kept:
    print("[loisa] Kept modified local skill overrides: " + ", ".join(kept))
PY
}

apply_openai_model_override() {
  if [ -z "${OPENAI_BASE_URL:-}" ] || [ -z "${OPENAI_API_KEY:-}" ]; then
    return 0
  fi

  echo "[loisa] Applying OpenAI-compatible Hermes model config"
  run_profile_hermes hermes config set model.provider custom
  run_profile_hermes hermes config set model.default gpt-5.5
  run_profile_hermes hermes config set model.base_url '${OPENAI_BASE_URL}'
  run_profile_hermes hermes config set model.api_key '${OPENAI_API_KEY}'
  run_profile_hermes hermes config set model.api_mode codex_responses
  run_profile_hermes hermes fallback clear
  run_profile_hermes hermes config set fallback_providers.0.provider openrouter
  run_profile_hermes hermes config set fallback_providers.0.model moonshotai/kimi-k2.6
  run_profile_hermes hermes config set fallback_providers.0.reasoning_effort xhigh
}

ensure_loisa_profile() {
  echo "[loisa] Preparing Hermes profile $profile_name in $profile_dir"

  if run_root_hermes hermes profile info "$profile_name" >/dev/null 2>&1; then
    if is_local_profile_distribution_repo; then
      run_root_hermes hermes profile install "$profile_distribution_repo" \
        --name "$profile_name" \
        --alias \
        --yes \
        --force
    else
      run_root_hermes hermes profile update "$profile_name" --force-config --yes \
        || run_root_hermes hermes profile install "$profile_distribution_repo" \
          --name "$profile_name" \
          --alias \
          --yes \
          --force
    fi
  else
    run_root_hermes hermes profile install "$profile_distribution_repo" \
      --name "$profile_name" \
      --alias \
      --yes \
      --force
  fi

  run_root_hermes hermes profile info "$profile_name" >/dev/null
  apply_openai_model_override
  run_root_hermes hermes profile use "$profile_name" >/dev/null
}

restart_dashboard_service() {
  local service_dir="${HERMES_DASHBOARD_SERVICE_DIR:-/run/service/dashboard}"

  truthy "${HERMES_DASHBOARD:-}" || return 0
  [ -x /command/s6-svc ] || return 0
  [ -p "$service_dir/supervise/control" ] || return 0

  echo "[loisa] Restarting Hermes dashboard in profile $profile_name"
  /command/s6-svc -k "$service_dir" || {
    echo "[loisa] Hermes dashboard restart signal failed" >&2
    return 0
  }
}

ensure_nori_slack_skill() {
  local skill_path="$profile_dir/distribution-skills/nori-slack-cli/SKILL.md"

  if [ -f "$skill_path" ]; then
    return 0
  fi

  echo "[loisa] nori-slack-cli skill is missing from Hermes profile $profile_name" >&2
  exit 1
}

ensure_loisa_viking_skill() {
  local skill_path="$profile_dir/distribution-skills/loisa-viking-cli/SKILL.md"

  if [ -f "$skill_path" ]; then
    return 0
  fi

  echo "[loisa] loisa-viking-cli skill is missing from Hermes profile $profile_name" >&2
  exit 1
}

ensure_default_kanban_board_name() {
  run_profile_hermes python - <<'PY'
from hermes_cli import kanban_db as kb

desired_name = "General Tasks"
meta = kb.read_board_metadata(kb.DEFAULT_BOARD)
current_name = str(meta.get("name") or "").strip()

if current_name == desired_name:
    pass
elif current_name in {"", "Default", "default"}:
    kb.write_board_metadata(kb.DEFAULT_BOARD, name=desired_name)
    print(f"[loisa] Named default Kanban board '{desired_name}'")
else:
    print(f"[loisa] Keeping existing default Kanban board name '{current_name}'")
PY
}

ensure_hermes_cli
ensure_python
ensure_openviking_cli
patch_openviking_studio_bootstrap
configure_openviking_cli_language
ensure_composio_cli
ensure_nori_slack_cli
ensure_parallel_cli
ensure_kernel_cli
ensure_bun_cli
configure_bun
ensure_codex_cli
configure_codex_cli
ensure_loisa_profile
remove_legacy_distribution_skill_shadows
configure_parallel_cli
ensure_nori_slack_skill
ensure_loisa_viking_skill
ensure_default_kanban_board_name
restart_dashboard_service

export HERMES_HOME="$profile_dir"
export HOME="$profile_home_dir"

openviking_data_dir="${OPENVIKING_DATA_DIR:-$data_root/openviking}"
openviking_workspace_dir="${OPENVIKING_WORKSPACE_DIR:-$openviking_data_dir/workspace}"
openviking_config_file="${OPENVIKING_CONFIG_FILE:-$openviking_data_dir/ov.conf}"
openviking_cli_config_file="${OPENVIKING_CLI_CONFIG_FILE:-$openviking_data_dir/ovcli.conf}"
openviking_host="${OPENVIKING_HOST:-127.0.0.1}"
openviking_port="${OPENVIKING_PORT:-1933}"
openviking_endpoint="${OPENVIKING_ENDPOINT:-http://127.0.0.1:$openviking_port}"
openviking_server_bin="${OPENVIKING_SERVER_BIN:-openviking-server}"
image_config_dir="/opt/hermes/openviking"
log_dir="${OPENVIKING_LOG_DIR:-$data_root/logs}"
log_file="${OPENVIKING_LOG_FILE:-$log_dir/openviking.log}"
startup_timeout_seconds="${OPENVIKING_STARTUP_TIMEOUT_SECONDS:-90}"

mkdir -p "$openviking_data_dir" "$openviking_workspace_dir" "$log_dir"

if [ ! -f "$openviking_config_file" ]; then
  cp "$image_config_dir/ov.conf" "$openviking_config_file"
  chmod 640 "$openviking_config_file" 2>/dev/null || true
fi

if [ ! -f "$openviking_cli_config_file" ]; then
  cp "$image_config_dir/ovcli.conf" "$openviking_cli_config_file"
  chmod 640 "$openviking_cli_config_file" 2>/dev/null || true
fi

export OPENVIKING_CONFIG_FILE="$openviking_config_file"
export OPENVIKING_CLI_CONFIG_FILE="$openviking_cli_config_file"
export OPENVIKING_HOST="$openviking_host"
export OPENVIKING_PORT="$openviking_port"
export OPENVIKING_ENDPOINT="$openviking_endpoint"
export OPENVIKING_ACCOUNT="${OPENVIKING_ACCOUNT:-default}"
export OPENVIKING_USER_SPACE="${OPENVIKING_USER_SPACE:-default}"
export OPENVIKING_USER="${OPENVIKING_USER:-$OPENVIKING_USER_SPACE}"
export OPENVIKING_AGENT_ID="${OPENVIKING_AGENT_ID:-default}"
export OPENVIKING_ROOT_API_KEY="${OPENVIKING_ROOT_API_KEY:-}"

configure_openviking_server_runtime "$openviking_config_file"
configure_openviking_cli_runtime "$openviking_cli_config_file"

if ! command -v "$openviking_server_bin" >/dev/null 2>&1; then
  if [ -x /opt/hermes/.venv/bin/openviking-server ]; then
    openviking_server_bin="/opt/hermes/.venv/bin/openviking-server"
  else
    echo "[openviking] openviking-server is not available on PATH or in /opt/hermes/.venv/bin" >&2
    exit 1
  fi
fi

openviking_pid=""
cleanup_openviking() {
  if [ -n "$openviking_pid" ] && kill -0 "$openviking_pid" 2>/dev/null; then
    kill "$openviking_pid" 2>/dev/null || true
    wait "$openviking_pid" 2>/dev/null || true
  fi
}
trap cleanup_openviking EXIT INT TERM

echo "[openviking] Starting OpenViking on $openviking_endpoint"
"$openviking_server_bin" --config "$openviking_config_file" >> "$log_file" 2>&1 &
openviking_pid="$!"

wait_for_openviking() {
  local deadline=$((SECONDS + startup_timeout_seconds))

  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! kill -0 "$openviking_pid" 2>/dev/null; then
      echo "[openviking] OpenViking exited before becoming healthy; see $log_file" >&2
      exit 1
    fi

    if python - "$openviking_endpoint" <<'PY'
import json
import os
import sys
import urllib.request

endpoint = sys.argv[1].rstrip("/")
headers = {}
api_key = os.environ.get("OPENVIKING_ROOT_API_KEY", "").strip()
if api_key:
    headers["X-API-Key"] = api_key
for path in ("/health", "/ready"):
    try:
        request = urllib.request.Request(f"{endpoint}{path}", headers=headers)
        with urllib.request.urlopen(request, timeout=2) as response:
            if response.status >= 400:
                continue
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") in {"ok", "ready"} or data.get("healthy") is True:
                sys.exit(0)
    except Exception:
        pass
sys.exit(1)
PY
    then
      echo "[openviking] OpenViking is healthy"
      return 0
    fi

    sleep 1
  done

  echo "[openviking] Timed out waiting for OpenViking health; see $log_file" >&2
  exit 1
}

wait_for_openviking
trap - EXIT INT TERM

if [ "$#" -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
  exec "$@"
fi

exec hermes "$@"
