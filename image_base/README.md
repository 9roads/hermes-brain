# Phoenix Hermes OpenViking Image

This directory is image build source, not Hermes profile-distribution payload.
`hermes/distribution.yaml` intentionally does not include `image_base/`.

Build the custom image from the repository root:

```bash
docker build -t phoenix-hermes-openviking:local hermes/image_base
```

Run it with a persistent `/opt/data` volume:

```bash
docker run --rm -it \
  -v phoenix-hermes-data:/opt/data \
  -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  phoenix-hermes-openviking:local gateway run -v
```

The image installs OpenViking `0.3.19`, `httpx` `0.28.1`, `slack_sdk`
`3.42.0`, `tiktoken` `0.13.0`, `loisa-composio-cli` `0.1.3`,
`nori-slack-cli` `0.1.1`, and the `hermes-lcm` plugin from
`https://github.com/stephenschoettler/hermes-lcm.git`. The plugin is installed
into `/opt/hermes/plugins/hermes-lcm` so it is available as a bundled Hermes
plugin; the Phoenix profile enables `hermes-lcm` and selects
`context.engine: lcm`.

On gateway startup, the wrapper installs or updates the Phoenix Hermes profile,
verifies the profile-owned `nori-slack-cli` and `loisa-viking-cli` skills exist,
starts OpenViking from `/opt/data/openviking`, and then runs the requested Hermes
command.

On first boot, `/opt/data/openviking/ov.conf` and `ovcli.conf` are copied from
the image only if missing. Runtime state, indexes, queues, resources, and
memory files live under `/opt/data/openviking/`. The default OpenViking log is
`/opt/data/logs/openviking.log`.

The `openviking_memory` provider is installed with one Phoenix memory override:
the built-in personal `profile` category is disabled and a `company` category
stores the shared company profile at `viking://user/<space>/memories/company.md`.
All other memory behavior uses OpenViking's native categories. The provider does
not expose model tools; interactive memory/resource work uses the profile-owned
`loisa-viking-cli` skill and the `ov` or `openviking` CLI.

The wrapper preserves the official Hermes entrypoint. Phoenix setup and
OpenViking startup happen after the official entrypoint has bootstrapped
`/opt/data` and dropped to the `hermes` user.
