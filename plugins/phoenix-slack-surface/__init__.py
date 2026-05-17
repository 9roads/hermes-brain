from __future__ import annotations

from typing import Any


PHOENIX_COMMAND = "phoenix"
PHOENIX_USAGE = "Use `/phoenix <message>` to ask Phoenix about this workspace."


def register(ctx: Any) -> None:
    def handle_phoenix(raw_args: str = "") -> str:
        if raw_args.strip():
            return "Phoenix is available from Slack with `/phoenix <message>`."

        return PHOENIX_USAGE

    def pre_gateway_dispatch(*args: Any, **kwargs: Any) -> dict[str, str] | None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        event = kwargs.get("event")
        text = getattr(event, "text", None)
        source = getattr(event, "source", None)
        platform = getattr(getattr(source, "platform", None), "value", None)

        if platform != "slack" or not isinstance(text, str):
            return None

        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        command_token, _, raw_message = stripped.partition(" ")
        command = command_token.lstrip("/").split("@", 1)[0].lower()

        if command != PHOENIX_COMMAND:
            return None

        message = raw_message.strip()
        if not message:
            return None

        return {"action": "rewrite", "text": message}

    ctx.register_command(
        PHOENIX_COMMAND,
        handler=handle_phoenix,
        description="Ask Phoenix about this workspace",
        args_hint="<message>",
    )
    ctx.register_hook("pre_gateway_dispatch", pre_gateway_dispatch)


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
