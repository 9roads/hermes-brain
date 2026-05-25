# Phoenix Hermes Profile

This directory is the Phoenix-owned Hermes profile distribution source. It is intended to be mirrored with the `https://github.com/9roads/hermes-brain` git subrepo workflow.

Edit static agent behavior here: `SOUL.md`, `config.yaml`, `skills/`, `plugins/`, `cron/`, and `scripts/`. Runtime state does not belong here.

Hermes reads MCP servers from `config.yaml` under `mcp_servers`; Phoenix should not add MCP servers to an installed sandbox at runtime. This profile intentionally does not configure a static Composio MCP server. Composio access is bootstrapped per Hermes session by `plugins/phoenix-composio-session` and used through the `composio-cli` skill for non-Slack connected tools. Slack API access uses the `agent-slack` skill and `agent-slack` CLI with `SLACK_TOKEN`.

Required Phoenix runtime env for connected tools:

- `PHOENIX_BACKEND_URL`
- `PHOENIX_WORKSPACE_ID`
- `PHOENIX_HERMES_PLUGIN_TOKEN`
- `COMPOSIO_API_KEY`
- `SLACK_TOKEN`

The Phoenix Hermes image installs pinned `loisa-composio-cli` and `agent-slack` at build time, exposing `composio` and `agent-slack` on `PATH`. The image wrapper installs the `agent-slack` skill into the active profile when it is missing.

Reference docs:

- [Profiles: Running Multiple Agents](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- [Profile Distributions: Share a Whole Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions)
- [Working with Skills](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills/)
- [here.now docs](https://here.now/docs)

Do not commit `.env`, `auth.json`, memories, sessions, `state.db*`, logs, caches, workspace state, or OAuth tokens.

Rollout flow:

1. Edit this distribution.
2. Bump `distribution.yaml` version.
3. Push/pull through the subrepo workflow for `9roads/hermes-brain`.
4. Run `node ace hermes:daytona:rollout restart` from `backend/` to update installed profiles, or `node ace hermes:daytona:rollout full` to recreate workspace sandboxes from the configured image.

Phoenix injects workspace secrets and dynamic values through the Daytona command environment at runtime. The installed profile `.env` remains user-owned and should not be written by the backend.
