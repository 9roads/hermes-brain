# Phoenix Hermes OpenViking Image

This directory is image build source, not Hermes profile-distribution payload.
`hermes/distribution.yaml` intentionally does not include `image_base/`.

Build the custom image from the repository root:

```bash
docker build -t phoenix-hermes-openviking:local hermes/image_base
```

The image extends
`nousresearch/hermes-agent:v2026.5.29.2@sha256:2bba4ab37729ebdd864d4caf277b24fec4cd8bfc2855185fd9f4c90f9bf7bfa3`.
That upstream release uses s6-overlay as PID 1, so the Phoenix image entrypoint
is `/init /opt/hermes/image_base/main-wrapper.sh`. The wrapper drops to the
`hermes` user and runs the Phoenix OpenViking bootstrap as the s6 main program.

Run it with a persistent `/opt/data` volume:

```bash
docker run --rm -it \
  -v phoenix-hermes-data:/opt/data \
  -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e KERNEL_API_KEY="$KERNEL_API_KEY" \
  phoenix-hermes-openviking:local gateway run -v
```

The image installs OpenViking `0.3.19`, `httpx` `0.28.1`, `slack_sdk`
`3.42.0`, `tiktoken` `0.13.0`, `parallel-web-tools[cli]` `0.5.0`,
`@onkernel/cli` `0.19.3`, `loisa-composio-cli` `0.1.3`, `nori-slack-cli`
`0.1.1`, Codex CLI `0.134.0`, Bun `1.3.14`, and the `hermes-lcm` plugin from
`https://github.com/stephenschoettler/hermes-lcm.git`. The plugin is installed
into `/opt/hermes/plugins/hermes-lcm` so it is available as a bundled Hermes
plugin; the Phoenix profile enables `hermes-lcm` and selects
`context.engine: lcm`.

The Node runtime remains available for bundled CLIs, and Bun plus `bunx` are on
`PATH` for Codex-managed app projects. On gateway startup, the wrapper configures
Bun's shared cache under `/opt/data/bun/install/cache`, writes Bun config for the
Hermes runtime homes, and enables the isolated linker with the global virtual
store. Hermes no longer copies a custom app-creator `AGENTS.md`; new projects
are initialized with `bun init --react=shadcn --yes` and
`bunx --bun skills add shadcn/ui --yes` before Codex is invoked.

On gateway startup, the wrapper installs or updates the Phoenix Hermes profile,
verifies required CLIs including `parallel-cli` and `kernel`, verifies
the profile-owned `nori-slack-cli` and `loisa-viking-cli` skills exist,
initializes Codex CLI API-key auth from `OPENAI_API_KEY`, seeds Parallel CLI
auth under the profile home from `PARALLEL_API_KEY`, names the default Kanban
board `General Tasks` when it still has Hermes' default display name, starts
OpenViking from `/opt/data/openviking`, and then runs the requested Hermes
command. Phoenix passes only `KERNEL_API_KEY` for Kernel CLI auth and remote
browser automation at runtime.

Codex CLI auth is runtime state, not a baked image secret. The wrapper stores
Codex config and API-key login cache under `/opt/data/codex` by default. When
`OPENAI_BASE_URL` is set, it is written to Codex's user-level
`openai_base_url` config.

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

The wrapper preserves upstream s6 stage2 setup. Phoenix setup and OpenViking
startup happen after s6 has bootstrapped `/opt/data`; the Phoenix main wrapper
then drops to the `hermes` user before running the gateway command.
`run-with-openviking.sh` also defaults `HERMES_GATEWAY_NO_SUPERVISE=1` so
upstream Hermes does not redirect `gateway run` into its own per-profile s6
service. Phoenix keeps a single foreground gateway process as the container main
program for Nomad.

The image also installs a Python startup patch for Slack Socket Mode. When
`SLACK_SOCKET_API_BASE` is set, Socket Mode `apps.connections.open` uses that
base URL and `SLACK_APP_TOKEN`; normal Slack Web API calls continue using the
existing bot-token Slack client. These router values are consumed by the Hermes
gateway process and should not be exposed through terminal env passthrough.
