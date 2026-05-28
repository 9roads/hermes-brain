# Phoenix Hermes Profile

This directory is the Phoenix-owned Hermes profile distribution source. It is intended to be mirrored with the `https://github.com/9roads/hermes-brain` git subrepo workflow.

Edit static agent behavior here: `SOUL.md`, `config.yaml`, `skills/`, `plugins/`, `cron/`, and `scripts/`. Runtime state does not belong here.

Hermes reads MCP servers from `config.yaml` under `mcp_servers`; Phoenix should not add MCP servers to an installed sandbox at runtime. This profile intentionally does not configure a static Composio MCP server. Composio access is bootstrapped per Hermes session by `plugins/phoenix-composio-session` and used through the `composio-cli` skill for non-Slack connected tools. Slack API access uses the `nori-slack-cli` skill and `nori-slack` CLI with `SLACK_BOT_TOKEN`.

Required Phoenix runtime env for connected tools:

- `PHOENIX_BACKEND_URL`
- `PHOENIX_WORKSPACE_ID`
- `PHOENIX_HERMES_PLUGIN_TOKEN`
- `COMPOSIO_API_KEY`
- `SLACK_BOT_TOKEN`

When Hermes connects through the Phoenix Slack Socket Mode router,
`SLACK_APP_TOKEN` is the Phoenix fake xapp token and `SLACK_SOCKET_API_BASE`
points at the router API, for example `https://socket-router.example.com/api/`.
Those router values are process-level runtime config for Socket Mode startup,
not terminal passthrough values. Terminal tools should only receive
`SLACK_BOT_TOKEN` or legacy `SLACK_TOKEN`, and normal Slack Web API calls go
directly to Slack with that real bot token.

The Phoenix Hermes image installs pinned `loisa-composio-cli` and `nori-slack-cli` at build time, exposing `composio` and `nori-slack` on `PATH`. The image wrapper maps legacy `SLACK_TOKEN` to `SLACK_BOT_TOKEN` when needed and verifies the profile-owned `nori-slack-cli` skill is installed.

Phoenix runs Hermes in trusted Daytona sandboxes, so `config.yaml` sets `approvals.mode: off`. Hermes docs define this as skipping terminal approval checks, equivalent to `HERMES_YOLO_MODE=true`; switch it back to `smart` or `manual` for non-sandboxed or user-owned hosts.

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
4. Run `node ace hermes:daytona:rollout restart` from `backend/` to update installed profiles, or `node ace hermes:daytona:rollout full` to recreate workspace sandboxes from the configured image.

Phoenix injects workspace secrets and dynamic values through the Daytona command environment at runtime. The installed profile `.env` remains user-owned and should not be written by the backend.
