from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    from . import client, prompt_context, session_refresh, slack_context
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import client
    import prompt_context
    import session_refresh
    import slack_context


LOGGER = logging.getLogger(__name__)

_bootstrapped_sessions: set[str] = set()
_refresh_marker_initialized = False
_refresh_marker_version: str | None = None


def register(ctx: Any) -> None:
    def pre_gateway_dispatch(*args: Any, **kwargs: Any) -> None:
        hook_kwargs = coerce_hook_kwargs(args, kwargs)
        event = hook_kwargs.get("event")
        context = slack_context.extract_slack_context(event)

        if context is None:
            return None

        slack_context.remember_slack_context(
            context,
            session_id=slack_context.read_session_id(hook_kwargs),
        )
        return None

    def pre_llm_call(*args: Any, **kwargs: Any) -> dict[str, str] | None:
        hook_kwargs = coerce_hook_kwargs(args, kwargs)
        session_id = slack_context.read_session_id(hook_kwargs) or "hermes_session_unknown"

        refresh_bootstraps_if_marker_changed()

        if session_id in _bootstrapped_sessions:
            return None

        actor_context = slack_context.get_slack_context(session_id)

        try:
            response = client.create_tool_router_session(
                client.BootstrapSessionRequest(
                    session_id=session_id,
                    **(actor_context.request_fields() if actor_context else {}),
                )
            )
            _bootstrapped_sessions.add(session_id)
            prompt_context.apply_session_environment(response)
            return {"context": prompt_context.build_prompt_context(response)}
        except Exception as exc:
            LOGGER.warning("Phoenix Composio Tool Router bootstrap failed: %s", exc)
            return {"context": prompt_context.build_error_context(str(exc))}

    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)
    ctx.register_hook("pre_llm_call", pre_llm_call)


def refresh_bootstraps_if_marker_changed() -> None:
    global _refresh_marker_initialized, _refresh_marker_version

    marker_version = session_refresh.read_refresh_marker_version()

    if not _refresh_marker_initialized:
        _refresh_marker_initialized = True
        _refresh_marker_version = marker_version
        return

    if marker_version == _refresh_marker_version:
        return

    _refresh_marker_version = marker_version
    _bootstrapped_sessions.clear()
    prompt_context.clear_session_environment()


def coerce_hook_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    if not args:
        return kwargs

    merged = dict(kwargs)

    for index, arg in enumerate(args):
        if isinstance(arg, dict):
            merged.update(arg)
        else:
            merged[f"arg_{index}"] = arg

    return merged
