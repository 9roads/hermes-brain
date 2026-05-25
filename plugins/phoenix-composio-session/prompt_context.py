from __future__ import annotations

import os
import urllib.parse

try:
    from .client import BootstrapSessionResponse
except ImportError:
    from client import BootstrapSessionResponse


SESSION_ID_ENV = "COMPOSIO_TOOL_ROUTER_SESSION_ID"
MISSING_URL_TEMPLATE_ENV = "COMPOSIO_MISSING_TOOL_URL_TEMPLATE"


def apply_session_environment(response: BootstrapSessionResponse) -> None:
    os.environ[SESSION_ID_ENV] = response.composio_session_id
    os.environ[MISSING_URL_TEMPLATE_ENV] = response.missing_tool_url_template


def clear_session_environment() -> None:
    os.environ.pop(SESSION_ID_ENV, None)
    os.environ.pop(MISSING_URL_TEMPLATE_ENV, None)


def build_prompt_context(response: BootstrapSessionResponse) -> str:
    return "\n".join(
        [
            "Composio Tool Router session:",
            f"- COMPOSIO_TOOL_ROUTER_SESSION_ID: {response.composio_session_id}",
            f"- Missing tool URL template: {response.missing_tool_url_template}",
            "- Use the composio-cli skill for non-Slack connected provider tools.",
            (
                "- Find the session id in this system prompt block on the "
                "COMPOSIO_TOOL_ROUTER_SESSION_ID line."
            ),
            f"- Every composio CLI call must pass --session-id {response.composio_session_id}.",
            (
                "- If auth is missing for a toolkit, replace {toolkit_slug} in the URL "
                "template and show that URL."
            ),
            (
                "- For Slack API actions, use the agent-slack skill and agent-slack CLI "
                "with SLACK_TOKEN. Do not use Composio slack or slackbot toolkits for Slack."
            ),
        ]
    )


def build_error_context(message: str) -> str:
    return "\n".join(
        [
            "Composio Tool Router session:",
            "- A Phoenix backend Tool Router session could not be created for this Hermes session.",
            f"- Error: {message}",
            "- Do not use Composio CLI provider tools unless a session ID is injected later.",
        ]
    )


def missing_tool_url(template: str, toolkit_slug: str) -> str:
    slug = normalize_toolkit_slug(toolkit_slug)

    if not slug:
        raise ValueError("toolkit_slug is required")

    return template.replace("{toolkit_slug}", urllib.parse.quote(slug, safe=""))


def normalize_toolkit_slug(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")
