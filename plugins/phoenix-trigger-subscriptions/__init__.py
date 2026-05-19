from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from . import schemas, tools
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    import schemas
    import tools


TOOLSET = tools.TOOLSET


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="list_triggers",
        toolset=TOOLSET,
        schema=schemas.LIST_TRIGGERS,
        handler=tools.list_triggers,
    )
    ctx.register_tool(
        name="get_trigger_schema",
        toolset=TOOLSET,
        schema=schemas.GET_TRIGGER_SCHEMA,
        handler=tools.get_trigger_schema,
    )
    ctx.register_tool(
        name="create_trigger",
        toolset=TOOLSET,
        schema=schemas.CREATE_TRIGGER,
        handler=tools.create_trigger,
    )
    ctx.register_tool(
        name="delete_trigger",
        toolset=TOOLSET,
        schema=schemas.DELETE_TRIGGER,
        handler=tools.delete_trigger,
    )
