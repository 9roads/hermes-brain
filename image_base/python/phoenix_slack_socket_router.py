from __future__ import annotations

import inspect
import logging
import os
from typing import Any


LOGGER = logging.getLogger(__name__)
PATCH_ATTR = "_phoenix_slack_socket_router_patched"
SOCKET_BASE_ENV = "SLACK_SOCKET_API_BASE"


def _socket_api_base() -> str:
    base_url = os.getenv(SOCKET_BASE_ENV, "").strip()
    if not base_url:
        return ""
    return base_url.rstrip("/") + "/"


def _constructor_kwargs(client_cls: type[Any], source_client: Any, app_token: str, base_url: str) -> dict[str, Any]:
    candidate_kwargs = {
        "token": app_token,
        "base_url": base_url,
        "timeout": getattr(source_client, "timeout", None),
        "ssl": getattr(source_client, "ssl", None),
        "proxy": getattr(source_client, "proxy", None),
        "session": getattr(source_client, "session", None),
        "trust_env_in_session": getattr(source_client, "trust_env_in_session", None),
        "team_id": getattr(source_client, "team_id", None),
        "logger": getattr(source_client, "logger", None),
        "retry_handlers": getattr(source_client, "retry_handlers", None),
    }

    headers = dict(getattr(source_client, "headers", {}) or {})
    for key in list(headers):
        if key.lower() == "authorization":
            headers.pop(key, None)
    if headers:
        candidate_kwargs["headers"] = headers

    parameters = inspect.signature(client_cls).parameters
    return {
        key: value
        for key, value in candidate_kwargs.items()
        if key in parameters and value is not None
    }


def _socket_open_client(client_cls: type[Any], source_client: Any, app_token: str, base_url: str) -> Any:
    return client_cls(**_constructor_kwargs(client_cls, source_client, app_token, base_url))


def _patch_async_socket_mode() -> None:
    try:
        from slack_sdk.socket_mode.async_client import AsyncBaseSocketModeClient
        from slack_sdk.web.async_client import AsyncWebClient
    except ImportError:
        return

    if getattr(AsyncBaseSocketModeClient.issue_new_wss_url, PATCH_ATTR, False):
        return

    original_issue_new_wss_url = AsyncBaseSocketModeClient.issue_new_wss_url

    async def issue_new_wss_url(self: Any) -> str:
        base_url = _socket_api_base()
        if not base_url:
            return await original_issue_new_wss_url(self)

        original_web_client = self.web_client
        self.web_client = _socket_open_client(
            AsyncWebClient,
            source_client=original_web_client,
            app_token=self.app_token,
            base_url=base_url,
        )
        try:
            return await original_issue_new_wss_url(self)
        finally:
            self.web_client = original_web_client

    setattr(issue_new_wss_url, PATCH_ATTR, True)
    AsyncBaseSocketModeClient.issue_new_wss_url = issue_new_wss_url


def _patch_sync_socket_mode() -> None:
    try:
        from slack_sdk.socket_mode.client import BaseSocketModeClient
        from slack_sdk.web import WebClient
    except ImportError:
        return

    if getattr(BaseSocketModeClient.issue_new_wss_url, PATCH_ATTR, False):
        return

    original_issue_new_wss_url = BaseSocketModeClient.issue_new_wss_url

    def issue_new_wss_url(self: Any) -> str:
        base_url = _socket_api_base()
        if not base_url:
            return original_issue_new_wss_url(self)

        original_web_client = self.web_client
        self.web_client = _socket_open_client(
            WebClient,
            source_client=original_web_client,
            app_token=self.app_token,
            base_url=base_url,
        )
        try:
            return original_issue_new_wss_url(self)
        finally:
            self.web_client = original_web_client

    setattr(issue_new_wss_url, PATCH_ATTR, True)
    BaseSocketModeClient.issue_new_wss_url = issue_new_wss_url


try:
    _patch_async_socket_mode()
    _patch_sync_socket_mode()
except Exception:
    LOGGER.exception("Failed to install Phoenix Slack Socket Mode router patch")
