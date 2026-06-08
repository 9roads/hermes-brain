from __future__ import annotations

import importlib
import logging
from typing import Any


LOGGER = logging.getLogger(__name__)

PATCH_MARKER = "__loisa_slack_markdown_blocks_patched__"


def register(ctx: Any) -> None:
    patch_slack_adapter()
    patch_send_message_tool()


def patch_slack_adapter() -> bool:
    try:
        slack_module = importlib.import_module("gateway.platforms.slack")
    except Exception as exc:
        LOGGER.info("Slack adapter patch unavailable: %s", exc)
        return False

    slack_adapter = getattr(slack_module, "SlackAdapter", None)
    send_result = getattr(slack_module, "SendResult", None)
    logger = getattr(slack_module, "logger", LOGGER)

    if slack_adapter is None or send_result is None:
        LOGGER.info("Slack adapter patch unavailable: missing SlackAdapter or SendResult")
        return False

    original_send = getattr(slack_adapter, "send", None)
    original_edit_message = getattr(slack_adapter, "edit_message", None)
    if original_send is None or original_edit_message is None:
        LOGGER.info("Slack adapter patch unavailable: missing send or edit_message")
        return False

    if getattr(getattr(slack_adapter, "send", None), PATCH_MARKER, False) and getattr(
        getattr(slack_adapter, "edit_message", None),
        PATCH_MARKER,
        False,
    ):
        return True

    async def send(
        self: Any,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        if not self._app:
            return send_result(success=False, error="Not connected")

        try:
            slash_ctx = self._pop_slash_context(chat_id)
            if slash_ctx:
                return await self._send_slash_ephemeral(
                    slash_ctx,
                    content,
                )

            fallback = self.format_message(content)

            chunks = self.truncate_message(content, self.MAX_MESSAGE_LENGTH)
            fallback_chunks = self.truncate_message(fallback, self.MAX_MESSAGE_LENGTH)

            thread_ts = self._resolve_thread_ts(reply_to, metadata)
            last_result = None

            broadcast = self.config.extra.get("reply_broadcast", False)

            for i, chunk in enumerate(chunks):
                fallback_chunk = fallback_chunks[i] if i < len(fallback_chunks) else chunk
                kwargs = {
                    "channel": chat_id,
                    "text": fallback_chunk,
                    "blocks": [{"type": "markdown", "text": chunk}],
                }
                if thread_ts:
                    kwargs["thread_ts"] = thread_ts
                    if broadcast and i == 0:
                        kwargs["reply_broadcast"] = True

                last_result = await self._get_client(chat_id).chat_postMessage(**kwargs)

            if thread_ts:
                await self.stop_typing(chat_id)

            sent_ts = last_result.get("ts") if last_result else None
            if sent_ts:
                self._bot_message_ts.add(sent_ts)
                if thread_ts:
                    self._bot_message_ts.add(thread_ts)
                if len(self._bot_message_ts) > self._BOT_TS_MAX:
                    excess = len(self._bot_message_ts) - self._BOT_TS_MAX // 2
                    for old_ts in list(self._bot_message_ts)[:excess]:
                        self._bot_message_ts.discard(old_ts)

            return send_result(
                success=True,
                message_id=sent_ts,
                raw_response=last_result,
            )

        except Exception as exc:
            logger.error("[Slack] Send error: %s", exc, exc_info=True)
            return send_result(success=False, error=str(exc))

    async def edit_message(
        self: Any,
        chat_id: str,
        message_id: str,
        content: str,
        *,
        finalize: bool = False,
    ) -> Any:
        if not self._app:
            return send_result(success=False, error="Not connected")
        try:
            fallback = self.format_message(content)
            await self._get_client(chat_id).chat_update(
                channel=chat_id,
                ts=message_id,
                text=fallback,
                blocks=[{"type": "markdown", "text": content}],
            )
            if finalize:
                await self.stop_typing(chat_id)
            return send_result(success=True, message_id=message_id)
        except Exception as exc:
            logger.error(
                "[Slack] Failed to edit message %s in channel %s: %s",
                message_id,
                chat_id,
                exc,
                exc_info=True,
            )
            return send_result(success=False, error=str(exc))

    setattr(send, PATCH_MARKER, True)
    setattr(edit_message, PATCH_MARKER, True)

    if not hasattr(slack_adapter, "_loisa_original_send"):
        slack_adapter._loisa_original_send = original_send
    if not hasattr(slack_adapter, "_loisa_original_edit_message"):
        slack_adapter._loisa_original_edit_message = original_edit_message

    slack_adapter.send = send
    slack_adapter.edit_message = edit_message
    return True


def patch_send_message_tool() -> bool:
    try:
        send_message_tool = importlib.import_module("tools.send_message_tool")
    except Exception as exc:
        LOGGER.info("send_message tool patch unavailable: %s", exc)
        return False

    if getattr(getattr(send_message_tool, "_send_slack", None), PATCH_MARKER, False) and getattr(
        getattr(send_message_tool, "_send_to_platform", None),
        PATCH_MARKER,
        False,
    ):
        return True

    original_send_to_platform = getattr(send_message_tool, "_send_to_platform", None)
    error_result = getattr(
        send_message_tool,
        "_error",
        lambda message: {"error": message},
    )

    if original_send_to_platform is None:
        LOGGER.info("send_message tool patch unavailable: missing _send_to_platform")
        return False

    async def send_to_platform(
        platform: Any,
        pconfig: Any,
        chat_id: str,
        message: str,
        thread_id: str | None = None,
        media_files: list[Any] | None = None,
        force_document: bool = False,
    ) -> Any:
        from gateway.config import Platform
        from gateway.platforms.base import BasePlatformAdapter
        from gateway.platforms.slack import SlackAdapter

        if platform != Platform.SLACK:
            return await original_send_to_platform(
                platform,
                pconfig,
                chat_id,
                message,
                thread_id=thread_id,
                media_files=media_files,
                force_document=force_document,
            )

        media_files = media_files or []
        max_len = SlackAdapter.MAX_MESSAGE_LENGTH
        chunks = BasePlatformAdapter.truncate_message(message, max_len) if max_len else [message]

        if media_files and not message.strip():
            return {
                "error": (
                    "send_message MEDIA delivery is currently only supported for telegram, "
                    "discord, matrix, weixin, signal, yuanbao and feishu; target slack had "
                    "only media attachments"
                )
            }

        warning = None
        if media_files:
            warning = (
                "MEDIA attachments were omitted for slack; native send_message media delivery "
                "is currently only supported for telegram, discord, matrix, weixin, signal, "
                "yuanbao and feishu"
            )

        last_result = None
        for chunk in chunks:
            result = await send_message_tool._send_slack(pconfig.token, chat_id, chunk)
            if isinstance(result, dict) and result.get("error"):
                return result
            last_result = result

        if warning and isinstance(last_result, dict) and last_result.get("success"):
            warnings = list(last_result.get("warnings", []))
            warnings.append(warning)
            last_result["warnings"] = warnings
        return last_result

    async def send_slack(token: str, chat_id: str, message: str) -> dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"error": "aiohttp not installed. Run: pip install aiohttp"}
        try:
            from gateway.platforms.base import proxy_kwargs_for_aiohttp, resolve_proxy_url

            proxy = resolve_proxy_url()
            session_kwargs, request_kwargs = proxy_kwargs_for_aiohttp(proxy)
            url = "https://slack.com/api/chat.postMessage"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                **session_kwargs,
            ) as session:
                payload = {
                    "channel": chat_id,
                    "text": message,
                    "blocks": [{"type": "markdown", "text": message}],
                }
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    **request_kwargs,
                ) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return {
                            "success": True,
                            "platform": "slack",
                            "chat_id": chat_id,
                            "message_id": data.get("ts"),
                        }
                    return error_result(f"Slack API error: {data.get('error', 'unknown')}")
        except Exception as exc:
            return error_result(f"Slack send failed: {exc}")

    setattr(send_to_platform, PATCH_MARKER, True)
    setattr(send_slack, PATCH_MARKER, True)

    if not hasattr(send_message_tool, "_loisa_original_send_to_platform"):
        send_message_tool._loisa_original_send_to_platform = original_send_to_platform
    if not hasattr(send_message_tool, "_loisa_original_send_slack"):
        send_message_tool._loisa_original_send_slack = getattr(
            send_message_tool,
            "_send_slack",
            None,
        )

    send_message_tool._send_to_platform = send_to_platform
    send_message_tool._send_slack = send_slack
    return True
