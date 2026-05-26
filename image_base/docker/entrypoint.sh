#!/usr/bin/env bash
set -euo pipefail

official_entrypoint="/opt/hermes/docker/entrypoint.sh"
llmwiki_runner="/opt/hermes/image_base/run-with-llmwiki.sh"

exec "$official_entrypoint" "$llmwiki_runner" "$@"
