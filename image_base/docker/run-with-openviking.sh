#!/usr/bin/env bash
set -Eeuo pipefail

data_dir="${HERMES_HOME:-/opt/data}"
openviking_data_dir="${OPENVIKING_DATA_DIR:-$data_dir/openviking}"
openviking_workspace_dir="${OPENVIKING_WORKSPACE_DIR:-$openviking_data_dir/workspace}"
openviking_config_file="${OPENVIKING_CONFIG_FILE:-$openviking_data_dir/ov.conf}"
openviking_cli_config_file="${OPENVIKING_CLI_CONFIG_FILE:-$openviking_data_dir/ovcli.conf}"
openviking_endpoint="${OPENVIKING_ENDPOINT:-http://127.0.0.1:1933}"
openviking_server_bin="${OPENVIKING_SERVER_BIN:-openviking-server}"
image_config_dir="/opt/hermes/openviking"
log_dir="${OPENVIKING_LOG_DIR:-$data_dir/logs}"
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

load_env_file "$data_dir/.env"

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
