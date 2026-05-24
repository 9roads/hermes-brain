#!/usr/bin/env bash
set -euo pipefail

official_entrypoint="/opt/hermes/docker/entrypoint.sh"
openviking_runner="/opt/hermes/image_base/run-with-openviking.sh"

exec "$official_entrypoint" "$openviking_runner" "$@"
