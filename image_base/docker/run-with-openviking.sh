#!/usr/bin/env bash
set -Eeuo pipefail

default_data_root="/opt/data"
profile_name="${HERMES_PROFILE_NAME:-${PHOENIX_HERMES_PROFILE_NAME:-phoenix}}"
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
export PHOENIX_HERMES_PROFILE_NAME="${PHOENIX_HERMES_PROFILE_NAME:-$profile_name}"
export PATH="/opt/hermes/.venv/bin:$root_bin_dir:$profile_bin_dir:$PATH"

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

profile_distribution_repo="${HERMES_PROFILE_DISTRIBUTION_REPO:-$profile_distribution_repo}"
export HERMES_PROFILE_DISTRIBUTION_REPO="$profile_distribution_repo"

mkdir -p "$root_home_dir" "$profile_home_dir" "$root_bin_dir" "$profile_bin_dir"

ensure_composio_cli() {
  if command -v composio >/dev/null 2>&1; then
    return 0
  fi

  echo "[phoenix] composio CLI is not available on PATH" >&2
  exit 1
}

run_root_hermes() {
  HERMES_HOME="$data_root" HOME="$root_home_dir" "$@"
}

run_profile_hermes() {
  HERMES_HOME="$profile_dir" HOME="$profile_home_dir" "$@"
}

ensure_phoenix_profile() {
  echo "[phoenix] Preparing Hermes profile $profile_name in $profile_dir"

  if run_root_hermes hermes profile info "$profile_name" >/dev/null 2>&1; then
    run_root_hermes hermes profile update "$profile_name" --force-config --yes \
      || run_root_hermes hermes profile install "$profile_distribution_repo" \
        --name "$profile_name" \
        --alias \
        --yes \
        --force
  else
    run_root_hermes hermes profile install "$profile_distribution_repo" \
      --name "$profile_name" \
      --alias \
      --yes \
      --force
  fi

  run_root_hermes hermes profile info "$profile_name" >/dev/null
}

ensure_phoenix_kanban_board() {
  local board_id="${PHOENIX_INGESTION_KANBAN_BOARD_ID:-phoenix-ingestion}"
  local board_name="${PHOENIX_INGESTION_KANBAN_BOARD_NAME:-Phoenix Ingestion}"
  local workspace_dir="${PHOENIX_INGESTION_KANBAN_WORKSPACE:-$data_root/phoenix/kanban-workspace}"

  mkdir -p "$workspace_dir"

  kanban_board_exists() {
    local boards_json

    boards_json="$(run_profile_hermes hermes kanban boards list --json 2>/dev/null)" || return 1

    python3 - "$board_id" "$boards_json" <<'PY'
import json
import sys

board_id = sys.argv[1]
boards_json = sys.argv[2]

try:
    boards = json.loads(boards_json)
except Exception:
    sys.exit(1)

for board in boards:
    if board.get("slug") == board_id and not board.get("archived", False):
        sys.exit(0)

sys.exit(1)
PY
  }

  if ! kanban_board_exists; then
    run_profile_hermes hermes kanban boards create "$board_id" \
      --name "$board_name" \
      || kanban_board_exists
  fi

  kanban_board_exists
}

ensure_composio_cli
ensure_phoenix_profile
ensure_phoenix_kanban_board

export HERMES_HOME="$profile_dir"
export HOME="$profile_home_dir"

openviking_data_dir="${OPENVIKING_DATA_DIR:-$data_root/openviking}"
openviking_workspace_dir="${OPENVIKING_WORKSPACE_DIR:-$openviking_data_dir/workspace}"
openviking_config_file="${OPENVIKING_CONFIG_FILE:-$openviking_data_dir/ov.conf}"
openviking_cli_config_file="${OPENVIKING_CLI_CONFIG_FILE:-$openviking_data_dir/ovcli.conf}"
openviking_endpoint="${OPENVIKING_ENDPOINT:-http://127.0.0.1:1933}"
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

if [ -z "${OPENVIKING_ROOT_API_KEY:-}" ] && [ -n "${OPENVIKING_API_KEY:-}" ]; then
  export OPENVIKING_ROOT_API_KEY="$OPENVIKING_API_KEY"
fi

if grep -q '\${OPENVIKING_ROOT_API_KEY}' "$openviking_config_file" \
  && [ -z "${OPENVIKING_ROOT_API_KEY:-}" ]; then
  echo "[openviking] OPENVIKING_ROOT_API_KEY is required for $openviking_config_file" >&2
  exit 1
fi

if [ -n "${OPENVIKING_ROOT_API_KEY:-}" ] && [ -z "${OPENVIKING_API_KEY:-}" ]; then
  export OPENVIKING_API_KEY="$OPENVIKING_ROOT_API_KEY"
fi

export OPENVIKING_CONFIG_FILE="$openviking_config_file"
export OPENVIKING_CLI_CONFIG_FILE="$openviking_cli_config_file"
export OPENVIKING_ENDPOINT="$openviking_endpoint"
export OPENVIKING_ACCOUNT="${OPENVIKING_ACCOUNT:-default}"
export OPENVIKING_USER_SPACE="${OPENVIKING_USER_SPACE:-default}"
export OPENVIKING_USER="${OPENVIKING_USER:-$OPENVIKING_USER_SPACE}"
export OPENVIKING_AGENT_ID="${OPENVIKING_AGENT_ID:-hermes-memory}"

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

    if python3 - "$openviking_endpoint" <<'PY'
import json
import sys
import urllib.request

endpoint = sys.argv[1].rstrip("/")
for path in ("/health", "/ready"):
    try:
        with urllib.request.urlopen(f"{endpoint}{path}", timeout=2) as response:
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
