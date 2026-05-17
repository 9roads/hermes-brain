from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from .config import load_config
    from .summarizer import build_turn_record, read_session_id, summarize_session
    from .wiki_structure import ensure_wiki_structure
    from .writer import (
        append_turn_buffer,
        load_turn_buffer,
        sanitize_text,
        write_session_summary_receipt,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from config import load_config
    from summarizer import build_turn_record, read_session_id, summarize_session
    from wiki_structure import ensure_wiki_structure
    from writer import (
        append_turn_buffer,
        load_turn_buffer,
        sanitize_text,
        write_session_summary_receipt,
    )


_injected_sessions: set[str] = set()
_finalized_sessions: set[str] = set()


def register(ctx: Any) -> None:
    config = load_config()
    ensure_wiki_structure(config.wiki_root)
    read_context = load_read_context()

    def pre_llm_call(*args: Any, **kwargs: Any) -> dict[str, str] | None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        session_id = read_session_id(kwargs)

        if session_id in _injected_sessions:
            return None

        _injected_sessions.add(session_id)
        return {
            "context": read_context.replace("${COMPANY_MEMORY_WIKI_ROOT}", str(config.wiki_root)),
        }

    def post_llm_call(*args: Any, **kwargs: Any) -> None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        session_id = read_session_id(kwargs)
        record = build_turn_record(config, kwargs)
        append_turn_buffer(config, session_id, record)

    def on_session_end(*args: Any, **kwargs: Any) -> None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        session_id = read_session_id(kwargs)
        config.state_dir.mkdir(parents=True, exist_ok=True)
        marker = config.state_dir / "last-session-end.txt"
        marker.write_text(sanitize_text(session_id, 160), encoding="utf-8")

    def on_session_finalize(*args: Any, **kwargs: Any) -> dict[str, str] | None:
        kwargs = coerce_hook_kwargs(args, kwargs)
        session_id = read_session_id(kwargs)

        if session_id in _finalized_sessions:
            return None

        _finalized_sessions.add(session_id)
        ensure_wiki_structure(config.wiki_root)
        records = load_turn_buffer(config, session_id)
        summary, model = summarize_session(ctx, config, session_id=session_id, records=records)
        platform = str(
            kwargs.get("platform")
            or kwargs.get("surface")
            or (records[-1].get("platform") if records else "")
            or "unknown"
        )
        receipt = write_session_summary_receipt(
            config,
            session_id=session_id,
            platform=platform,
            model=model,
            summary=summary,
        )

        return {
            "company_memory_session_summary_receipt": str(receipt),
        }

    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_llm_call", post_llm_call)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)


def load_read_context() -> str:
    path = Path(__file__).with_name("read_context.md")

    return path.read_text(encoding="utf-8")


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
