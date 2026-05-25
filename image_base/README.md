# Phoenix Hermes OpenViking Image

This directory is image build source, not Hermes profile-distribution payload.
`hermes/distribution.yaml` intentionally does not include `image_base/`.

Build the custom image from the repository root:

```bash
docker build -t phoenix-hermes-openviking:local hermes/image_base
```

Run it with a persistent `/opt/data` volume and an OpenViking root API key:

```bash
docker run --rm -it \
  -v phoenix-hermes-data:/opt/data \
  -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e OPENVIKING_ROOT_API_KEY="$OPENVIKING_ROOT_API_KEY" \
  phoenix-hermes-openviking:local gateway run -v
```

On first boot, `/opt/data/openviking/ov.conf` and `ovcli.conf` are copied from
the image only if missing. Runtime state, indexes, queues, resources, and
memory files live under `/opt/data/openviking/`. The default OpenViking log is
`/opt/data/logs/openviking.log`.

The image installs OpenViking `0.3.19`, `httpx` `0.28.1`, and
`loisa-composio-cli` `0.1.3`. On gateway startup, the image wrapper installs or
updates the Phoenix Hermes profile, ensures the shared `phoenix-ingestion`
Kanban board exists, starts OpenViking from `/opt/data/openviking`, and then
runs the requested Hermes command. The `openviking_memory` provider is
installed and the memory bundle is copied to
`/opt/hermes/openviking/memory-bundle/`. The dedicated company custom schemas
are still exposed to OpenViking at:

- `/opt/hermes/openviking/company-memory/`

The wrapper preserves the official Hermes entrypoint. Phoenix setup and
OpenViking startup happen after the official entrypoint has bootstrapped
`/opt/data` and dropped to the `hermes` user.
