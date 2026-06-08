from __future__ import annotations

BOOTSTRAP_ENDPOINT = "/composio/tool-router-session"
USER_AGENT = "loisa-hermes-composio-session/0.1.0"

REQUIRED_ENV = (
    "LOISA_BACKEND_URL",
    "LOISA_WORKSPACE_ID",
    "LOISA_HERMES_PLUGIN_TOKEN",
    "COMPOSIO_API_KEY",
)

BOOTSTRAP_REQUEST_FIELDS = (
    "workspace_id",
    "session_id",
    "slack_team_id",
    "slack_user_id",
    "slack_channel_id",
    "slack_thread_id",
)

BOOTSTRAP_RESPONSE_FIELDS = (
    "composio_session_id",
    "missing_tool_url_template",
)

TOOLKIT_SLUG_PLACEHOLDER = "{toolkit_slug}"
