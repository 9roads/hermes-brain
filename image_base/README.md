# Loisa Hermes OpenViking Image

This directory is image build source, not Hermes profile-distribution payload.
`hermes/distribution.yaml` intentionally does not include `image_base/`.

Build the custom image from the repository root:

```bash
docker build -t loisa-hermes-openviking:local hermes/image_base
```

The image extends
`nousresearch/hermes-agent:v2026.6.5@sha256:9ad3b04ec916ea2c2da22358fd43b024c788d74073210695af88bfc2e63869b4`.
That upstream release uses s6-overlay as PID 1, so the Loisa image entrypoint
is `/init /opt/hermes/image_base/main-wrapper.sh`. The wrapper drops to the
`hermes` user and runs the Loisa OpenViking bootstrap as the s6 main program.

Run it with a persistent `/opt/data` volume:

```bash
docker run --rm -it \
  -v loisa-hermes-data:/opt/data \
  -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
  -e KERNEL_API_KEY="$KERNEL_API_KEY" \
  -e LINKD_API_KEY="$LINKD_API_KEY" \
  loisa-hermes-openviking:local gateway run -v
```

The image installs OpenViking `0.3.23`, `httpx` `0.28.1`, `slack_sdk`
`3.42.0`, `tiktoken` `0.13.0`, `linkdapi` `1.0.9`,
`parallel-web-tools[cli]` `0.5.0`,
`@onkernel/cli` `0.19.3`, `loisa-composio-cli` `0.1.3`, `nori-slack-cli`
`0.1.1`, Codex CLI `0.134.0`, Bun `1.3.14`, and the `hermes-lcm` plugin from
`https://github.com/stephenschoettler/hermes-lcm.git`. The plugin is installed
into `/opt/hermes/plugins/hermes-lcm` so it is available as a bundled Hermes
plugin; the Loisa profile enables `hermes-lcm` and selects
`context.engine: lcm`.

The Node runtime remains available for bundled CLIs, and Bun plus `bunx` are on
`PATH` for Codex-managed app projects. On gateway startup, the wrapper configures
Bun's shared cache under `/opt/data/bun/install/cache`, writes Bun config for the
Hermes runtime homes, and enables the isolated linker with the global virtual
store. Hermes no longer copies a custom app-creator `AGENTS.md`; new projects
are initialized with `bun init --react=shadcn --yes` and
`bunx --bun skills add shadcn/ui --yes` before Codex is invoked.

On gateway startup, the wrapper installs or updates the Loisa Hermes profile,
marks it as the sticky active Hermes profile for the `/opt/data` root,
verifies required CLIs including `parallel-cli` and `kernel`, verifies
the profile-owned `distribution-skills/nori-slack-cli` and
`distribution-skills/loisa-viking-cli` skills exist,
seeds Parallel CLI auth under the profile home from `PARALLEL_API_KEY`, names the default Kanban
board `General Tasks` when it still has Hermes' default display name, restarts
the upstream dashboard service when enabled so it picks up the installed
profile, starts OpenViking from `/opt/data/openviking`, and then runs the
requested Hermes command. Loisa passes `KERNEL_API_KEY` for Kernel CLI auth
and remote browser automation plus `LINKD_API_KEY` for LinkdAPI scripts at
runtime.

The profile defaults to OpenRouter `openai/gpt-5.5` with `xhigh` reasoning and
no fallback chain. When both `OPENAI_BASE_URL` and `OPENAI_API_KEY` are present,
the wrapper applies a temporary OpenAI-compatible model override with the Hermes
CLI immediately after the forced profile update and before `profile use`.

Codex CLI auth is runtime state, not a baked image secret. The wrapper stores
Codex config and API-key login cache under `/opt/data/codex` by default. When
both `OPENAI_API_KEY` and `OPENAI_BASE_URL` are set, Codex CLI auth is
initialized from that runtime state and the base URL is written to Codex's
user-level `openai_base_url` config.

On first boot, `/opt/data/openviking/ov.conf` and `ovcli.conf` are copied from
the image only if missing. Runtime state, indexes, queues, resources, and
memory files live under `/opt/data/openviking/`. The default OpenViking log is
`/opt/data/logs/openviking.log`.
On every boot, the wrapper patches the persisted OpenViking server config from
`OPENVIKING_HOST`, `OPENVIKING_PORT`, `OPENVIKING_AUTH_MODE`, and
`OPENVIKING_ROOT_API_KEY`. Local Docker runtime binds OpenViking on
`0.0.0.0:{openvikingPort}` with API-key auth while keeping `OPENVIKING_ENDPOINT`
loopback for in-container Hermes tools. The wrapper also writes the same key into
`ovcli.conf` so `ov` can talk to the local OpenViking server.

The `openviking_memory` provider is installed with one Loisa memory override:
the built-in personal `profile` category is disabled and a `company` category
stores the shared company profile at `viking://user/<space>/memories/company.md`.
All other memory behavior uses OpenViking's native categories. The provider does
not expose model tools; interactive memory/resource work uses the profile-owned
`distribution-skills/loisa-viking-cli` skill and the `ov` or `openviking` CLI.

The wrapper preserves upstream s6 stage2 setup. Loisa setup and OpenViking
startup happen after s6 has bootstrapped `/opt/data`; the Loisa main wrapper
then drops to the `hermes` user before running the gateway command.
`run-with-openviking.sh` also defaults `HERMES_GATEWAY_NO_SUPERVISE=1` so
upstream Hermes does not redirect `gateway run` into its own per-profile s6
service. Loisa keeps a single foreground gateway process as the container main
program for Nomad.

The image also installs a Python startup patch for Slack Socket Mode. When
`SLACK_SOCKET_API_BASE` is set, Socket Mode `apps.connections.open` uses that
base URL and `SLACK_APP_TOKEN`; normal Slack Web API calls continue using the
existing bot-token Slack client. These router values are consumed by the Hermes
gateway process and should not be exposed through terminal env passthrough.
