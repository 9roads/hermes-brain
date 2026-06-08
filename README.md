# Loisa Hermes Profile

This directory is the Loisa-owned Hermes profile distribution source. It is intended to be mirrored with the `https://github.com/9roads/hermes-brain` git subrepo workflow.

Edit static agent behavior here: `SOUL.md`, `config.yaml`, `distribution-skills/`, `plugins/`, `cron/`, and `scripts/`. Runtime state does not belong here.

Hermes reads MCP servers from `config.yaml` under `mcp_servers`; Loisa should not add MCP servers to an installed sandbox at runtime. This profile intentionally does not configure a static Composio MCP server. Composio access is bootstrapped per Hermes session by `plugins/loisa-composio-session` and used through the `composio-cli` skill for non-Slack connected tools. Slack API access uses the `nori-slack-cli` skill and `nori-slack` CLI with `SLACK_BOT_TOKEN`. Public web work uses the profile-owned Parallel CLI skills and an authenticated `parallel-cli`, including search, extraction, Task/deep research, FindAll, Monitor, and data enrichment. Browser automation uses the profile-owned `kernel-cli` skill and `kernel` CLI with Kernel. Professional profile, company, and job data enrichment uses the `linkdapi-python-sdk` skill with the preinstalled LinkdAPI Python SDK and `LINKD_API_KEY`; the skill declares `required_environment_variables` so Hermes forwards the key to terminal sandboxes when the skill is loaded. These Loisa-owned skills live in `distribution-skills/`, which `config.yaml` loads through `skills.external_dirs`, leaving the default `skills/` directory for user-created skills. The built-in Hermes `web` and `browser` toolsets are globally disabled.

Required Loisa runtime env for connected tools:

- `LOISA_BACKEND_URL`
- `LOISA_WORKSPACE_ID`
- `LOISA_HERMES_PLUGIN_TOKEN`
- `COMPOSIO_API_KEY`
- `LINKD_API_KEY`
- `KERNEL_API_KEY`
- `PARALLEL_API_KEY`
- `SLACK_BOT_TOKEN`

When Hermes connects through the Loisa Slack Socket Mode router,
`SLACK_APP_TOKEN` is the Loisa fake xapp token and `SLACK_SOCKET_API_BASE`
points at the router API, for example `https://socket-router.example.com/api/`.
Those router values are process-level runtime config for Socket Mode startup,
not terminal passthrough values. Terminal tools should only receive
`SLACK_BOT_TOKEN` or legacy `SLACK_TOKEN`, and normal Slack Web API calls go
directly to Slack with that real bot token.

The Loisa Hermes image installs pinned `parallel-web-tools[cli]`,
`@onkernel/cli`, `loisa-composio-cli`, `nori-slack-cli`, `linkdapi`, and Bun at
build time, exposing `parallel-cli`, `kernel`, `composio`, `nori-slack`, `bun`,
and `bunx` on `PATH`. Loisa passes `KERNEL_API_KEY` at runtime for Kernel CLI
auth, passes `LINKD_API_KEY` for LinkdAPI SDK usage, maps legacy `SLACK_TOKEN`
to `SLACK_BOT_TOKEN` when needed, seeds Parallel CLI auth from
`PARALLEL_API_KEY` into the profile home, configures Bun's shared cache/global
store for Codex-created app projects, and verifies required CLIs and
profile-owned core skills are available.

Loisa runs Hermes in trusted Nomad jobs, so `config.yaml` sets `approvals.mode: off`. Hermes docs define this as skipping terminal approval checks, equivalent to `HERMES_YOLO_MODE=true`; switch it back to `smart` or `manual` for non-sandboxed or user-owned hosts.

Reference docs:

- [Profiles: Running Multiple Agents](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- [Profile Distributions: Share a Whole Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions)
- [Configuration: Smart Approvals](https://hermes-agent.nousresearch.com/docs/user-guide/configuration#smart-approvals)
- [Working with Skills](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills/)
- [here.now docs](https://here.now/docs)

Do not commit `.env`, `auth.json`, memories, sessions, `state.db*`, logs, caches, workspace state, or OAuth tokens.

Rollout flow:

1. Edit this distribution.
2. Bump `distribution.yaml` version.
3. Push/pull through the subrepo workflow for `9roads/hermes-brain`.
4. Run `node ace hermes:nomad:rollout restart` from `backend/` to update installed profiles, or `node ace hermes:nomad:rollout full` to recreate workspace jobs from the configured image.

Loisa injects workspace secrets and dynamic values through the Nomad task environment at runtime. The installed profile `.env` remains user-owned and should not be written by the backend.
