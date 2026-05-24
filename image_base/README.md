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
the image only if missing. Runtime state, indexes, queues, resources, logs, and
memory files live under `/opt/data/openviking/`.

The image installs OpenViking `0.3.19` and `httpx` `0.28.1` into
`/opt/hermes/.venv`, installs the `openviking_memory` provider, and copies the
memory bundle to `/opt/hermes/openviking/memory-bundle/`. The dedicated company
custom schemas are still exposed to OpenViking at:

- `/opt/hermes/openviking/company-memory/`

The wrapper preserves the official Hermes entrypoint. OpenViking is started
after the official entrypoint has bootstrapped `/opt/data` and dropped to the
`hermes` user.
