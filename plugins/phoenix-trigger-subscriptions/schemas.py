from __future__ import annotations


DELIVERY_TARGETS = [
    "log",
    "slack",
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
        "Hermes dynamic webhook route options for Phoenix trigger subscriptions. "
        "Only log and Slack delivery are enabled in this profile."
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
            "description": "Where Hermes should deliver the agent result. Supported values: log, slack.",
        },
        "deliver_chat_id": {
            "type": "string",
            "description": "Slack channel/chat ID mapped to --deliver-chat-id.",
        },
        "deliver_only": {
            "type": "boolean",
            "description": (
                "When true, skip the agent and deliver the rendered prompt directly. "
                "Requires deliver to be slack."
            ),
        },
    },
}

LIST_TRIGGERS = {
    "name": "list_triggers",
    "description": (
        "List available Composio trigger types for connected accounts in the current "
        "Phoenix workspace. Returns compact trigger summaries; call get_trigger_schema "
        "for the selected trigger before creating it."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "toolkit_slugs": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional toolkit slugs to filter, such as github or googlesheets. "
                    "Trigger tools do not apply to Slack connections."
                ),
            },
            "connected_account_id": {
                "type": "string",
                "description": "Optional connected account ID to filter trigger types.",
            },
            "search": {
                "type": "string",
                "description": "Optional search text for trigger names, slugs, or descriptions.",
            },
        },
    },
}

GET_TRIGGER_SCHEMA = {
    "name": "get_trigger_schema",
    "description": (
        "Return full Composio trigger schema details for a trigger selected from "
        "list_triggers, including setup config and payload schema. Call before create_trigger."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trigger_slug": {
                "type": "string",
                "description": "Composio trigger slug from list_triggers.",
            },
        },
        "required": ["trigger_slug"],
    },
}

CREATE_TRIGGER = {
    "name": "create_trigger",
    "description": (
        "Create a Composio trigger instance through Phoenix, then create the matching "
        "Hermes dynamic webhook route in the Phoenix profile. Call get_trigger_schema "
        "for the selected trigger first."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "trigger_slug": {
                "type": "string",
                "description": "Composio trigger slug from list_triggers after inspecting get_trigger_schema.",
            },
            "trigger_config": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "Provider-specific trigger config from get_trigger_schema. Keys are "
                    "passed through to Phoenix for validation and Composio creation."
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
                "description": "Active trigger ID returned by create_trigger or list_triggers.",
            },
        },
        "required": ["trigger_id"],
    },
}
