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

if [ -z "${SLACK_TOKEN:-}" ] && [ -n "${SLACK_BOT_TOKEN:-}" ]; then
  export SLACK_TOKEN="$SLACK_BOT_TOKEN"
fi

if [ -z "${SLACK_BOT_TOKEN:-}" ] && [ -n "${SLACK_TOKEN:-}" ]; then
  export SLACK_BOT_TOKEN="$SLACK_TOKEN"
fi

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

ensure_nori_slack_cli() {
  if command -v nori-slack >/dev/null 2>&1; then
    return 0
  fi

  echo "[phoenix] nori-slack CLI is not available on PATH" >&2
  exit 1
}

ensure_llmwiki_cli() {
  if command -v llmwiki >/dev/null 2>&1; then
    return 0
  fi

  echo "[phoenix] llmwiki CLI is not available on PATH" >&2
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

ensure_nori_slack_skill() {
  local skill_path="$profile_dir/skills/nori-slack-cli/SKILL.md"

  if [ -f "$skill_path" ]; then
    return 0
  fi

  echo "[phoenix] nori-slack-cli skill is missing from Hermes profile $profile_name" >&2
  exit 1
}

ensure_llmwiki_skill() {
  local skill_path="$profile_dir/skills/llmwiki-cli/SKILL.md"

  if [ -f "$skill_path" ]; then
    return 0
  fi

  echo "[phoenix] llmwiki-cli skill is missing from Hermes profile $profile_name" >&2
  exit 1
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

write_llmwiki_status() {
  local status_file="$1"
  local pid="$2"
  local status="$3"
  local message="${4:-}"

  mkdir -p "$(dirname "$status_file")"
  python3 - "$status_file" "$pid" "$status" "$message" "$PHOENIX_LLMWIKI_ROOT" "$llmwiki_log_file" <<'PY'
import json
import sys
from datetime import datetime, timezone

status_file, pid, status, message, root, log_file = sys.argv[1:7]
payload = {
    "status": status,
    "pid": int(pid) if pid.isdigit() else None,
    "message": message,
    "root": root,
    "log_path": log_file,
    "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open(status_file, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

ensure_llmwiki_schema() {
  local schema_path="$PHOENIX_LLMWIKI_ROOT/.llmwiki/schema.json"
  local template_path="${PHOENIX_LLMWIKI_SCHEMA_TEMPLATE:-/opt/hermes/image_base/llmwiki/schema.json}"
  local force_schema="${PHOENIX_LLMWIKI_SCHEMA_FORCE:-}"

  if [ ! -f "$schema_path" ] || [ "$force_schema" = "1" ] || [ "$force_schema" = "true" ]; then
    if [ ! -f "$template_path" ]; then
      echo "[llmwiki] schema template missing: $template_path" >&2
      exit 1
    fi

    cp "$template_path" "$schema_path"
    echo "[llmwiki] Installed company schema at $schema_path"
  fi

  python3 - "$schema_path" <<'PY'
import json
import sys

schema_path = sys.argv[1]
try:
    with open(schema_path, encoding="utf-8") as handle:
        json.load(handle)
except Exception as exc:
    print(f"[llmwiki] invalid schema JSON at {schema_path}: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

ensure_composio_cli
ensure_nori_slack_cli
ensure_llmwiki_cli
ensure_phoenix_profile
ensure_nori_slack_skill
ensure_llmwiki_skill
ensure_phoenix_kanban_board

export HERMES_HOME="$profile_dir"
export HOME="$profile_home_dir"

workspace_dir="${PHOENIX_WORKSPACE_DIR:-$data_root/workspace}"
llmwiki_root="${PHOENIX_LLMWIKI_ROOT:-${LLMWIKI_ROOT:-$workspace_dir/company}}"
llmwiki_log_dir="${PHOENIX_LLMWIKI_LOG_DIR:-$data_root/logs}"
llmwiki_log_file="${PHOENIX_LLMWIKI_LOG_FILE:-$llmwiki_log_dir/llmwiki-watch.log}"
llmwiki_status_file="${PHOENIX_LLMWIKI_STATUS_FILE:-$data_root/phoenix/llmwiki/watch-status.json}"

export PHOENIX_LLMWIKI_ROOT="$llmwiki_root"
export LLMWIKI_ROOT="$llmwiki_root"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
export LLMWIKI_PROVIDER="${LLMWIKI_PROVIDER:-openai}"
export LLMWIKI_MODEL="${LLMWIKI_MODEL:-gpt-5.5}"
export LLMWIKI_EMBEDDING_MODEL="${LLMWIKI_EMBEDDING_MODEL:-text-embedding-3-small}"

mkdir -p "$PHOENIX_LLMWIKI_ROOT/sources" "$PHOENIX_LLMWIKI_ROOT/wiki" "$PHOENIX_LLMWIKI_ROOT/.llmwiki" "$llmwiki_log_dir"
ensure_llmwiki_schema

llmwiki_pid=""
cleanup_llmwiki() {
  if [ -n "$llmwiki_pid" ] && kill -0 "$llmwiki_pid" 2>/dev/null; then
    kill "$llmwiki_pid" 2>/dev/null || true
    wait "$llmwiki_pid" 2>/dev/null || true
  fi
}
trap cleanup_llmwiki EXIT INT TERM

echo "[llmwiki] Starting llmwiki watch in $PHOENIX_LLMWIKI_ROOT"
(
  cd "$PHOENIX_LLMWIKI_ROOT"
  exec llmwiki watch
) >> "$llmwiki_log_file" 2>&1 &
llmwiki_pid="$!"
write_llmwiki_status "$llmwiki_status_file" "$llmwiki_pid" "running" ""

sleep 1
if ! kill -0 "$llmwiki_pid" 2>/dev/null; then
  write_llmwiki_status "$llmwiki_status_file" "$llmwiki_pid" "failed" "llmwiki watch exited during startup"
  echo "[llmwiki] llmwiki watch exited during startup; see $llmwiki_log_file" >&2
  tail -40 "$llmwiki_log_file" >&2 || true
  exit 1
fi

if [ "$#" -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
  exec "$@"
fi

exec hermes "$@"
