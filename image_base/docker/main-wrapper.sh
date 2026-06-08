#!/command/with-contenv bash
set -euo pipefail

openviking_runner="/opt/hermes/image_base/run-with-openviking.sh"

if [ ! -x "$openviking_runner" ]; then
  echo "[loisa] OpenViking runner is not executable: $openviking_runner" >&2
  exit 127
fi

if [ "$(id -u)" -eq 0 ]; then
  exec /command/s6-setuidgid hermes "$openviking_runner" "$@"
fi

exec "$openviking_runner" "$@"
