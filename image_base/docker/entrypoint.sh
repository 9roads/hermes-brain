#!/usr/bin/env bash
set -euo pipefail

main_wrapper="/opt/hermes/image_base/main-wrapper.sh"
openviking_runner="/opt/hermes/image_base/run-with-openviking.sh"

if [ "$$" -eq 1 ] && [ -x /init ]; then
  exec /init "$main_wrapper" "$@"
fi

if [ "$(id -u)" -eq 0 ]; then
  if [ -x /command/s6-setuidgid ]; then
    exec /command/s6-setuidgid hermes "$openviking_runner" "$@"
  fi

  echo "[loisa] cannot drop root privileges: /command/s6-setuidgid is unavailable" >&2
  exit 126
fi

exec "$openviking_runner" "$@"
