"""Focused REST client for the OpenViking memory provider."""

from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any

from .config import ProviderConfig


def get_httpx():
    try:
        import httpx

        return httpx
    except ImportError:
        return None


class OpenVikingClient:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._endpoint = config.endpoint.rstrip("/")
        self._httpx = get_httpx()
        if self._httpx is None:
            raise ImportError("httpx is required for the OpenViking memory provider")

    def _url(self, path: str) -> str:
        return f"{self._endpoint}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-OpenViking-Account": self.config.account,
            "X-OpenViking-User": self.config.user_space,
            "X-OpenViking-Agent": self.config.agent_id,
        }
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _multipart_headers(self) -> dict[str, str]:
        headers = self._headers()
        headers.pop("Content-Type", None)
        return headers

    def _parse_response(self, response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception:
            data = None

        if response.status_code >= 400:
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    code = error.get("code", "HTTP_ERROR")
                    message = error.get("message", response.text)
                    raise RuntimeError(f"{code}: {message}")
                detail = data.get("detail")
                if detail:
                    raise RuntimeError(str(detail))
                if data.get("status") == "error":
                    raise RuntimeError(str(data))
            response.raise_for_status()

        if isinstance(data, dict) and data.get("status") == "error":
            error = data.get("error")
            if isinstance(error, dict):
                code = error.get("code", "OPENVIKING_ERROR")
                message = error.get("message", "")
                raise RuntimeError(f"{code}: {message}")
            raise RuntimeError(str(data))

        return data if isinstance(data, dict) else {}

    @staticmethod
    def unwrap_result(response: Any) -> Any:
        if isinstance(response, dict) and "result" in response:
            return response.get("result")
        return response

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._httpx.get(
            self._url(path),
            headers=self._headers(),
            timeout=kwargs.pop("timeout", self.config.request_timeout),
            **kwargs,
        )
        return self._parse_response(response)

    def post(self, path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        response = self._httpx.post(
            self._url(path),
            json=payload or {},
            headers=self._headers(),
            timeout=kwargs.pop("timeout", self.config.request_timeout),
            **kwargs,
        )
        return self._parse_response(response)

    def health(self, timeout: float = 3.0) -> bool:
        for path in ("/health", "/ready"):
            try:
                response = self._httpx.get(self._url(path), headers=self._headers(), timeout=timeout)
                if response.status_code >= 400:
                    continue
                data = response.json()
                if data.get("status") in {"ok", "ready"} or data.get("healthy") is True:
                    return True
            except Exception:
                continue
        return False

    def ensure_session(self, session_id: str) -> dict[str, Any]:
        return self.get(f"/api/v1/sessions/{session_id}", params={"auto_create": "true"})

    def add_message(
        self,
        session_id: str,
        role: str,
        *,
        content: str | None = None,
        parts: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
        role_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": role}
        if parts is not None:
            payload["parts"] = parts
        else:
            payload["content"] = content or ""
        if created_at:
            payload["created_at"] = created_at
        if role_id:
            payload["role_id"] = role_id
        return self.post(f"/api/v1/sessions/{session_id}/messages", payload)

    def commit_session(
        self,
        session_id: str,
        *,
        keep_recent_count: int = 0,
        telemetry: bool = False,
    ) -> dict[str, Any]:
        return self.post(
            f"/api/v1/sessions/{session_id}/commit",
            {"keep_recent_count": keep_recent_count, "telemetry": telemetry},
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.get(f"/api/v1/tasks/{task_id}")

    def poll_task(self, task_id: str, *, timeout: float, interval: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {"task_id": task_id, "status": "pending"}
        while time.monotonic() < deadline:
            response = self.get_task(task_id)
            result = self.unwrap_result(response)
            if isinstance(result, dict):
                last = result
                status = str(result.get("status") or "").lower()
                if status in {"completed", "failed", "cancelled", "canceled"}:
                    return result
            time.sleep(interval)
        return {"task_id": task_id, "status": "timeout", "last": last, "timeout_seconds": timeout}

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/v1/search/search", payload)

    def list_directory(
        self,
        uri: str,
        *,
        recursive: bool = False,
        node_limit: int = 100,
        show_all_hidden: bool = False,
        output: str = "agent",
        abs_limit: int = 500,
    ) -> dict[str, Any]:
        return self.get(
            "/api/v1/fs/ls",
            params={
                "uri": uri,
                "recursive": recursive,
                "node_limit": node_limit,
                "show_all_hidden": show_all_hidden,
                "output": output,
                "abs_limit": abs_limit,
            },
        )

    def stat(self, uri: str) -> dict[str, Any]:
        return self.get("/api/v1/fs/stat", params={"uri": uri})

    def read_content(self, uri: str, level: str) -> dict[str, Any]:
        endpoint = "/api/v1/content/read"
        if level == "abstract":
            endpoint = "/api/v1/content/abstract"
        elif level == "overview":
            endpoint = "/api/v1/content/overview"
        return self.get(endpoint, params={"uri": uri})

    def record_used(self, session_id: str, contexts: list[str]) -> dict[str, Any]:
        if not contexts:
            return {}
        return self.post(f"/api/v1/sessions/{session_id}/used", {"contexts": contexts})

    def grep(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/v1/search/grep", payload)

    def upload_temp_file(self, file_path: Path) -> str:
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = {
            "upload_mode": self.config.temp_upload_mode,
            "telemetry": "true" if self.config.diagnostics else "false",
        }
        with file_path.open("rb") as handle:
            response = self._httpx.post(
                self._url("/api/v1/resources/temp_upload"),
                files={"file": (file_path.name, handle, mime_type)},
                data=data,
                headers=self._multipart_headers(),
                timeout=self.config.request_timeout,
            )
        parsed = self._parse_response(response)
        result = self.unwrap_result(parsed)
        if not isinstance(result, dict) or not result.get("temp_file_id"):
            raise RuntimeError("OpenViking temp_upload did not return temp_file_id")
        return str(result["temp_file_id"])

    def add_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/v1/resources", payload)
