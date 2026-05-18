from __future__ import annotations


DELIVERY_TARGETS = [
    "log",
    "github_comment",
    "telegram",
    "discord",
    "slack",
    "signal",
    "sms",
    "whatsapp",
    "matrix",
    "mattermost",
    "homeassistant",
    "email",
    "dingtalk",
    "feishu",
    "wecom",
    "weixin",
    "bluebubbles",
    "qqbot",
]

STRING_OR_STRING_LIST = {
    "oneOf": [
        {"type": "string"},
        {
            "type": "array",
            "items": {"type": "string"},
        },
    ],
}

WEBHOOK = {
    "type": "object",
    "description": (
        "Hermes dynamic webhook route options. Mirrors the documented "
        "hermes webhook subscribe CLI surface; unsupported delivery extras are omitted."
    ),
    "additionalProperties": False,
    "properties": {
        "prompt": {
            "type": "string",
            "description": (
                "Prompt template rendered from the Composio event payload. "
                "Supports Hermes webhook {dot.notation} placeholders."
            ),
        },
        "events": {
            **STRING_OR_STRING_LIST,
            "description": (
                "Accepted Hermes webhook event types. Lists are joined as the CLI "
                "--events comma-separated value."
            ),
        },
        "description": {
            "type": "string",
            "description": "Human-readable purpose for the Hermes route.",
        },
        "skills": {
            **STRING_OR_STRING_LIST,
            "description": (
                "Hermes skills to load for agent runs. Lists are joined as the CLI "
                "--skills comma-separated value."
            ),
        },
        "deliver": {
            "type": "string",
            "enum": DELIVERY_TARGETS,
            "description": "Where Hermes should deliver the agent result.",
        },
        "deliver_chat_id": {
            "type": "string",
            "description": "Target chat or channel ID mapped to --deliver-chat-id.",
        },
        "deliver_only": {
            "type": "boolean",
            "description": (
                "When true, skip the agent and deliver the rendered prompt directly. "
                "Requires a real delivery target, not log."
            ),
        },
    },
}

LIST_TRIGGERS = {
    "name": "list_triggers",
    "description": (
        "List available Composio trigger types for connected accounts in the current "
        "Phoenix workspace. Use before creating a trigger to inspect required config."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "toolkit_slugs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional toolkit slugs to filter, such as github or slack.",
            },
            "connected_account_id": {
                "type": "string",
                "description": "Optional connected account ID to filter trigger types.",
            },
            "search": {
                "type": "string",
                "description": "Optional search text for trigger names, slugs, or descriptions.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum trigger types to return.",
            },
            "cursor": {
                "type": "string",
                "description": "Pagination cursor returned by the backend.",
            },
        },
    },
}

CREATE_TRIGGER = {
    "name": "create_trigger",
    "description": (
        "Create a Composio trigger instance through Phoenix, then create the matching "
        "Hermes dynamic webhook route in the Phoenix profile."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trigger_slug": {
                "type": "string",
                "description": "Composio trigger slug from list_triggers.",
            },
            "trigger_config": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "Provider-specific trigger config from the trigger schema. "
                    "Keys are passed through to Phoenix for validation and Composio creation."
                ),
            },
            "connected_account_id": {
                "type": "string",
                "description": (
                    "Optional Phoenix/Composio connected account ID. Omit only when "
                    "there is exactly one valid account for the trigger toolkit."
                ),
            },
            "webhook": WEBHOOK,
        },
        "required": ["trigger_slug"],
    },
}

DELETE_TRIGGER = {
    "name": "delete_trigger",
    "description": (
        "Delete an active Phoenix-managed Composio trigger, then remove its Hermes "
        "dynamic webhook route from the Phoenix profile."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trigger_id": {
                "type": "string",
                "description": "Active trigger ID returned by create_trigger or get_active_triggers.",
            },
        },
        "required": ["trigger_id"],
    },
}

GET_ACTIVE_TRIGGERS = {
    "name": "get_active_triggers",
    "description": (
        "List active Phoenix-managed Composio trigger instances and their Hermes "
        "route metadata for the current workspace."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "toolkit_slugs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional toolkit slugs to filter.",
            },
            "connected_account_id": {
                "type": "string",
                "description": "Optional connected account ID to filter.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum active triggers to return.",
            },
            "cursor": {
                "type": "string",
                "description": "Pagination cursor returned by the backend.",
            },
        },
    },
}
