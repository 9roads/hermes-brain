from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

try:
    from . import schemas
except ImportError:
    import schemas


HTTP_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class LoisaConfig:
    backend_url: str
    workspace_id: str
    token: str


@dataclass(frozen=True)
class BootstrapSessionRequest:
    session_id: str
    slack_team_id: str | None = None
    slack_user_id: str | None = None
    slack_channel_id: str | None = None
    slack_thread_id: str | None = None


@dataclass(frozen=True)
class BootstrapSessionResponse:
    composio_session_id: str
    missing_tool_url_template: str


class BootstrapRequestError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.data = data


UrlOpen = Callable[..., Any]


def create_tool_router_session(
    input: BootstrapSessionRequest,
    *,
    environ: dict[str, str] | None = None,
    opener: UrlOpen | None = None,
) -> BootstrapSessionResponse:
    config = load_config(environ)
    url = build_url(config, schemas.BOOTSTRAP_ENDPOINT)
    payload = {
        "workspace_id": config.workspace_id,
        "session_id": input.session_id,
        "slack_team_id": input.slack_team_id,
        "slack_user_id": input.slack_user_id,
        "slack_channel_id": input.slack_channel_id,
        "slack_thread_id": input.slack_thread_id,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
            "User-Agent": schemas.USER_AGENT,
        },
    )

    try:
        with (opener or urllib.request.urlopen)(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            data = parse_json_bytes(response.read())
            return parse_bootstrap_response(data)
    except urllib.error.HTTPError as error:
        data = parse_json_bytes(error.read())
        raise BootstrapRequestError(
            f"Loisa backend returned HTTP {error.code}",
            status=error.code,
            data=data,
        ) from error
    except BootstrapRequestError:
        raise
    except Exception as error:
        raise BootstrapRequestError(str(error)) from error


def parse_bootstrap_response(data: Any) -> BootstrapSessionResponse:
    payload = data

    if isinstance(payload, dict) and not has_response_fields(payload):
        nested = payload.get("data")
        if isinstance(nested, dict):
            payload = nested

    if not isinstance(payload, dict):
        raise BootstrapRequestError("Loisa backend returned a non-object response", data=data)

    composio_session_id = read_text(payload.get("composio_session_id"))
    missing_tool_url_template = read_text(payload.get("missing_tool_url_template"), max_length=4000)

    if not composio_session_id:
        raise BootstrapRequestError("Loisa backend response omitted composio_session_id", data=data)

    if not missing_tool_url_template:
        raise BootstrapRequestError(
            "Loisa backend response omitted missing_tool_url_template",
            data=data,
        )

    if schemas.TOOLKIT_SLUG_PLACEHOLDER not in missing_tool_url_template:
        raise BootstrapRequestError(
            "Loisa backend response missing-tool URL lacks {toolkit_slug}",
            data=data,
        )

    return BootstrapSessionResponse(
        composio_session_id=composio_session_id,
        missing_tool_url_template=missing_tool_url_template,
    )


def has_response_fields(payload: dict[str, Any]) -> bool:
    return all(field in payload for field in schemas.BOOTSTRAP_RESPONSE_FIELDS)


def load_config(environ: dict[str, str] | None = None) -> LoisaConfig:
    source = environ or os.environ
    backend_url = read_env(source, "LOISA_BACKEND_URL").rstrip("/")
    workspace_id = read_env(source, "LOISA_WORKSPACE_ID")
    token = read_env(source, "LOISA_HERMES_PLUGIN_TOKEN")

    return LoisaConfig(
        backend_url=backend_url,
        workspace_id=workspace_id,
        token=token,
    )


def build_url(config: LoisaConfig, path: str) -> str:
    return (
        f"{config.backend_url}/api/v1/internal/hermes/workspaces/"
        f"{quote_path(config.workspace_id)}{path}"
    )


def quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def read_env(environ: dict[str, str], name: str) -> str:
    value = read_text(environ.get(name), max_length=5000)

    if not value:
        raise BootstrapRequestError(f"{name} is required")

    return value


def parse_json_bytes(raw: bytes) -> Any:
    if not raw:
        return None

    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return raw.decode("utf-8", errors="replace")


def read_text(value: Any, *, max_length: int = 500) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    return text[:max_length]

