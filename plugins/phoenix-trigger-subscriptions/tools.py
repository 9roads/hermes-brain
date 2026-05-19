from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


HTTP_TIMEOUT_SECONDS = 30
CLI_TIMEOUT_SECONDS = 60
TOOLSET = "phoenix_trigger_subscriptions"


@dataclass(frozen=True)
class PhoenixConfig:
    backend_url: str
    workspace_id: str
    token: str


@dataclass(frozen=True)
class BackendResponse:
    ok: bool
    status: int | None
    data: Any


@dataclass(frozen=True)
class CliResult:
    ok: bool
    profile: str
    argv: list[str]
    exit_code: int | None
    stdout: str
    stderr: str


def list_triggers(args: dict[str, Any], **_: Any) -> str:
    response = request_json("GET", "/triggers/types", query=clean_query(args))
    return json_tool_response(response.data)


def get_active_triggers(args: dict[str, Any], **_: Any) -> str:
    response = request_json("GET", "/triggers/active", query=clean_query(args))
    return json_tool_response(response.data)


def create_trigger(args: dict[str, Any], **_: Any) -> str:
    validation_error = validate_create_args(args)

    if validation_error:
        return json_tool_response(validation_error)

    webhook = read_mapping(args.get("webhook")) or {}
    direct_delivery_error = validate_direct_delivery(webhook)

    if direct_delivery_error:
        return json_tool_response(direct_delivery_error)

    payload = {
        "trigger_slug": read_text(args.get("trigger_slug")),
        "trigger_config": read_mapping(args.get("trigger_config")) or {},
        "webhook": webhook,
    }
    connected_account_id = read_text(args.get("connected_account_id"))

    if connected_account_id:
        payload["connected_account_id"] = connected_account_id

    created = request_json("POST", "/triggers", payload=payload)

    if not created.ok:
        return json_tool_response(created.data)

    if backend_response_needs_agent_action(created.data):
        return json_tool_response(created.data)

    route_name = extract_first_text(
        created.data,
        [
            ("hermes_route_name",),
            ("route_name",),
            ("webhook", "route_name"),
            ("hermes_webhook", "route_name"),
            ("route", "name"),
        ],
    )
    route_secret = extract_first_text(
        created.data,
        [
            ("hermes_route_secret",),
            ("route_secret",),
            ("webhook", "secret"),
            ("hermes_webhook", "secret"),
            ("route", "secret"),
        ],
    )
    trigger_id = extract_trigger_id(created.data)

    if not route_name:
        return json_tool_response(
            {
                "ok": False,
                "error": "backend_response_missing_route_name",
                "message": "Phoenix did not return the Hermes route name needed for CLI subscribe.",
                "backend": created.data,
            }
        )

    if not route_secret:
        return json_tool_response(
            {
                "ok": False,
                "error": "backend_response_missing_route_secret",
                "message": "Phoenix did not return the route secret needed for CLI subscribe.",
                "backend": created.data,
            }
        )

    subscribe = subscribe_webhook_route(route_name, route_secret, webhook)

    finalize = None
    if trigger_id:
        finalize = finalize_trigger(
            trigger_id,
            {
                "route_name": route_name,
                "success": subscribe.ok,
                "hermes_cli": cli_result_payload(subscribe, secrets=[route_secret]),
            },
        )

    if not subscribe.ok:
        return json_tool_response(
            {
                "ok": False,
                "error": "hermes_webhook_subscribe_failed",
                "trigger": created.data,
                "hermes_cli": cli_result_payload(subscribe, secrets=[route_secret]),
                "finalize": finalize.data if finalize else None,
            }
        )

    if finalize and not finalize.ok:
        return json_tool_response(
            {
                "ok": False,
                "error": "phoenix_trigger_finalize_failed",
                "trigger": created.data,
                "hermes_route": {
                    "name": route_name,
                    "profile": subscribe.profile,
                    "cli": cli_result_payload(subscribe, secrets=[route_secret]),
                },
                "finalize": finalize.data,
            }
        )

    return json_tool_response(
        {
            "ok": True,
            "trigger": created.data,
            "hermes_route": {
                "name": route_name,
                "profile": subscribe.profile,
                "cli": cli_result_payload(subscribe, secrets=[route_secret]),
            },
            "finalize": finalize.data if finalize else None,
        }
    )


def delete_trigger(args: dict[str, Any], **_: Any) -> str:
    trigger_id = read_text(args.get("trigger_id"))

    if not trigger_id:
        return json_tool_response(
            {
                "ok": False,
                "error": "trigger_id_required",
                "message": "delete_trigger requires trigger_id.",
            }
        )

    deleted = request_json("DELETE", f"/triggers/{quote_path(trigger_id)}")

    if not deleted.ok:
        return json_tool_response(deleted.data)

    route_name = extract_first_text(
        deleted.data,
        [
            ("hermes_route_name",),
            ("route_name",),
            ("webhook", "route_name"),
            ("hermes_webhook", "route_name"),
            ("route", "name"),
            ("trigger", "hermes_route_name"),
            ("trigger", "route_name"),
        ],
    )

    if not route_name:
        return json_tool_response(
            {
                "ok": False,
                "error": "backend_response_missing_route_name",
                "message": "Phoenix deleted the trigger but did not return a Hermes route to remove.",
                "backend": deleted.data,
            }
        )

    remove = remove_webhook_route(route_name)

    if not remove.ok:
        return json_tool_response(
            {
                "ok": False,
                "error": "hermes_webhook_remove_failed",
                "backend": deleted.data,
                "hermes_cli": cli_result_payload(remove),
            }
        )

    return json_tool_response(
        {
            "ok": True,
            "backend": deleted.data,
            "hermes_route": {
                "name": route_name,
                "profile": remove.profile,
                "cli": cli_result_payload(remove),
            },
        }
    )


def validate_create_args(args: dict[str, Any]) -> dict[str, Any] | None:
    if not read_text(args.get("trigger_slug")):
        return {
            "ok": False,
            "error": "trigger_slug_required",
            "message": "create_trigger requires trigger_slug from list_triggers.",
        }

    trigger_config = args.get("trigger_config")
    if trigger_config is not None and not isinstance(trigger_config, dict):
        return {
            "ok": False,
            "error": "trigger_config_must_be_object",
            "message": "trigger_config must be an object with provider-specific keys.",
        }

    webhook = args.get("webhook")
    if webhook is not None and not isinstance(webhook, dict):
        return {
            "ok": False,
            "error": "webhook_must_be_object",
            "message": "webhook must be an object mirroring hermes webhook subscribe options.",
        }

    return None


def validate_direct_delivery(webhook: dict[str, Any]) -> dict[str, Any] | None:
    if webhook.get("deliver_only") is not True:
        return None

    deliver = (read_text(webhook.get("deliver")) or "log").lower()

    if deliver == "log":
        return {
            "ok": False,
            "error": "deliver_only_requires_delivery_target",
            "message": "deliver_only requires webhook.deliver to be a real target, not log.",
        }

    return None


def request_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> BackendResponse:
    try:
        config = load_config()
        url = build_url(config, path, query=query)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
                "User-Agent": "phoenix-hermes-trigger-subscriptions/0.1.0",
            },
        )

        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", None)
            data = parse_json_bytes(response.read())
            return BackendResponse(True, status, data)
    except urllib.error.HTTPError as error:
        data = parse_json_bytes(error.read())
        if not isinstance(data, dict):
            data = {"message": data}
        data.setdefault("ok", False)
        data.setdefault("status", error.code)
        data.setdefault("error", f"phoenix_backend_http_{error.code}")
        return BackendResponse(False, error.code, data)
    except Exception as error:
        return BackendResponse(
            False,
            None,
            {
                "ok": False,
                "error": "phoenix_backend_request_failed",
                "message": str(error),
            },
        )


def finalize_trigger(trigger_id: str, payload: dict[str, Any]) -> BackendResponse:
    return request_json("POST", f"/triggers/{quote_path(trigger_id)}/finalize", payload=payload)


def subscribe_webhook_route(
    route_name: str, route_secret: str, webhook: dict[str, Any]
) -> CliResult:
    args = build_subscribe_args(route_name, route_secret, webhook)
    return run_profile_cli(args, secrets=[route_secret])


def remove_webhook_route(route_name: str) -> CliResult:
    return run_profile_cli(["webhook", "remove", route_name])


def build_subscribe_args(
    route_name: str, route_secret: str, webhook: dict[str, Any]
) -> list[str]:
    args = ["webhook", "subscribe", route_name]
    add_text_option(args, "--prompt", webhook.get("prompt"))
    add_csv_option(args, "--events", webhook.get("events"))
    add_text_option(args, "--description", webhook.get("description"))
    add_csv_option(args, "--skills", webhook.get("skills"))
    add_text_option(args, "--deliver", webhook.get("deliver"))
    add_text_option(args, "--deliver-chat-id", webhook.get("deliver_chat_id"))

    if webhook.get("deliver_only") is True:
        args.append("--deliver-only")

    args.extend(["--secret", route_secret])
    return args


def run_profile_cli(args: list[str], *, secrets: list[str] | None = None) -> CliResult:
    profile = profile_name()
    primary = [profile, *args]
    result = run_command(primary, secrets=secrets)

    if result.exit_code is None and result.stderr == "command_not_found":
        fallback = ["hermes", "--profile", profile, *args]
        return run_command(fallback, profile=profile, secrets=secrets)

    return result


def run_command(
    argv: list[str],
    *,
    profile: str | None = None,
    secrets: list[str] | None = None,
) -> CliResult:
    command_profile = profile or profile_name()

    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
        return CliResult(
            ok=completed.returncode == 0,
            profile=command_profile,
            argv=argv,
            exit_code=completed.returncode,
            stdout=redact(completed.stdout, secrets),
            stderr=redact(completed.stderr, secrets),
        )
    except FileNotFoundError:
        return CliResult(
            ok=False,
            profile=command_profile,
            argv=argv,
            exit_code=None,
            stdout="",
            stderr="command_not_found",
        )
    except subprocess.TimeoutExpired as error:
        return CliResult(
            ok=False,
            profile=command_profile,
            argv=argv,
            exit_code=None,
            stdout=redact(error.stdout or "", secrets),
            stderr=f"command_timeout_after_{CLI_TIMEOUT_SECONDS}s",
        )
    except Exception as error:
        return CliResult(
            ok=False,
            profile=command_profile,
            argv=argv,
            exit_code=None,
            stdout="",
            stderr=redact(str(error), secrets),
        )


def load_config() -> PhoenixConfig:
    backend_url = read_env("PHOENIX_BACKEND_URL")
    workspace_id = read_env("PHOENIX_WORKSPACE_ID")
    token = read_env("PHOENIX_HERMES_PLUGIN_TOKEN")
    return PhoenixConfig(
        backend_url=backend_url.rstrip("/"),
        workspace_id=workspace_id,
        token=token,
    )


def read_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"{name} is required")

    return value


def profile_name() -> str:
    return os.getenv("PHOENIX_HERMES_PROFILE_NAME", "phoenix").strip() or "phoenix"


def build_url(
    config: PhoenixConfig, path: str, *, query: dict[str, Any] | None = None
) -> str:
    base = (
        f"{config.backend_url}/api/v1/internal/hermes/workspaces/"
        f"{quote_path(config.workspace_id)}"
    )
    url = f"{base}{path}"
    encoded_query = encode_query(query or {})

    if encoded_query:
        return f"{url}?{encoded_query}"

    return url


def encode_query(query: dict[str, Any]) -> str:
    pairs: list[tuple[str, str]] = []

    for key, value in sorted(query.items()):
        if value is None or value == "":
            continue
        if isinstance(value, list):
            for item in value:
                text = read_text(item)
                if text:
                    pairs.append((key, text))
        else:
            text = read_text(value)
            if text:
                pairs.append((key, text))

    return urllib.parse.urlencode(pairs)


def clean_query(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "toolkit_slugs",
        "connected_account_id",
        "search",
        "limit",
        "cursor",
    }
    return {key: value for key, value in args.items() if key in allowed}


def parse_json_bytes(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()

    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def cli_result_payload(result: CliResult, *, secrets: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "profile": result.profile,
        "argv": redact_list(result.argv, secrets),
        "exit_code": result.exit_code,
        "stdout": redact(result.stdout, secrets),
        "stderr": redact(result.stderr, secrets),
    }


def json_tool_response(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def backend_response_needs_agent_action(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    if payload.get("ok") is False:
        return True

    status = read_text(payload.get("status") or payload.get("code") or payload.get("action"))
    return status in {
        "choice_required",
        "setup_required",
        "setup_unsupported",
        "requires_setup",
        "requires_action",
    }


def extract_trigger_id(payload: Any) -> str:
    return extract_first_text(
        payload,
        [
            ("trigger_id",),
            ("id",),
            ("external_trigger_id",),
            ("trigger", "id"),
            ("trigger", "trigger_id"),
            ("trigger", "external_trigger_id"),
        ],
    )


def extract_first_text(payload: Any, paths: list[tuple[str, ...]]) -> str:
    for path in paths:
        value = payload

        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)

        text = read_text(value)
        if text:
            return text

    return ""


def add_text_option(args: list[str], flag: str, value: Any) -> None:
    text = read_text(value)

    if text:
        args.extend([flag, text])


def add_csv_option(args: list[str], flag: str, value: Any) -> None:
    csv = read_csv(value)

    if csv:
        args.extend([flag, csv])


def read_csv(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(text for text in [read_text(item) for item in value] if text)

    return read_text(value)


def read_mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def read_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value).strip()


def quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def redact_list(values: list[str], secrets: list[str] | None = None) -> list[str]:
    return [redact(value, secrets) for value in values]


def redact(value: Any, secrets: list[str] | None = None) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)

    for secret in secrets or []:
        if secret:
            text = text.replace(secret, "[redacted]")

    token = os.getenv("PHOENIX_HERMES_PLUGIN_TOKEN", "").strip()
    if token:
        text = text.replace(token, "[redacted]")

    return text
