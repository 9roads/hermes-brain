"""Retired model-facing tool schemas for the OpenViking memory provider.

The provider now keeps automatic memory lifecycle behavior but exposes no model
tools. Interactive OpenViking access goes through the profile-owned
loisa-viking-cli skill and OpenViking CLI.
"""

from __future__ import annotations

from typing import Any

SEARCH_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_search",
    "description": (
        "Semantic search over Loisa memory in OpenViking. "
        "Returns ranked viking:// URIs for deeper reading across every OpenViking scope."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Memory/context search query."},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "description": "Maximum result count.",
            },
            "since": {
                "type": "string",
                "description": "Optional lower time bound such as 7d or 2026-05-24.",
            },
            "until": {
                "type": "string",
                "description": "Optional upper time bound such as 2h or 2026-05-24.",
            },
            "include_provenance": {
                "type": "boolean",
                "description": "Include OpenViking query-plan/provenance details when available.",
            },
        },
        "required": ["query"],
    },
}

READ_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_read",
    "description": (
        "Read content at any viking:// URI. "
        "Use abstract for an L0 summary, overview for L1 key points, and full "
        "for L2 complete content. Start with abstract or overview; use full "
        "only when exact details are needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "viking:// URI returned by loisa_memory_search.",
            },
            "level": {
                "type": "string",
                "enum": ["abstract", "overview", "full"],
                "description": "Read detail level: abstract=L0, overview=L1, full=L2. Defaults to overview.",
            },
            "max_chars": {
                "type": "integer",
                "minimum": 300,
                "maximum": 20000,
                "description": "Optional output character cap.",
            },
        },
        "required": ["uri"],
    },
}

LIST_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_list",
    "description": (
        "List entries under a viking:// directory deterministically. "
        "Use when semantic search is too fuzzy or you already know the memory/resource path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "viking:// directory URI to browse, or viking:// for the root.",
            },
            "recursive": {
                "type": "boolean",
                "description": "List subdirectories recursively. Defaults to false.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "description": "Maximum entries to return. Defaults to 100.",
            },
            "include_hidden": {
                "type": "boolean",
                "description": "Include hidden OpenViking entries when supported. Defaults to false.",
            },
        },
        "required": ["uri"],
    },
}

GREP_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_grep",
    "description": (
        "Exact text or regex search across viking:// files in any OpenViking scope. "
        "Use for identifiers, quoted phrases, exact terms, or regex patterns."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "viking:// scope to search, or viking:// for every scope.",
            },
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for, or exact text when literal is true.",
            },
            "literal": {
                "type": "boolean",
                "description": "Escape pattern and treat it as exact text. Defaults to false.",
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Ignore case while matching. Defaults to false.",
            },
            "exclude_uri": {
                "type": "string",
                "description": "Optional viking:// URI prefix to exclude from search.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum matches to return. Defaults to 10.",
            },
            "level_limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "description": "Maximum directory depth to traverse. Defaults to 5.",
            },
        },
        "required": ["uri", "pattern"],
    },
}

ADD_RESOURCE_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_add_resource",
    "description": (
        "Add public URLs or bounded local files/directories as OpenViking resources. "
        "For private sources, first export a safe local artifact, then add that path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Public URL, git URL, local file path, local directory path, or file:// URI.",
            },
            "to": {
                "type": "string",
                "description": "Optional exact target under viking://resources.",
            },
            "parent": {
                "type": "string",
                "description": "Optional parent under viking://resources. Defaults to the resource root.",
            },
            "create_parent": {
                "type": "boolean",
                "description": "Create the parent directory when supported. Defaults to true.",
            },
            "reason": {
                "type": "string",
                "description": "Why this source should become reusable context.",
            },
            "instruction": {
                "type": "string",
                "description": "Optional OpenViking processing instruction for the source.",
            },
            "strict": {
                "type": "boolean",
                "description": "Use strict resource parsing.",
            },
            "ignore_dirs": {
                "type": "string",
                "description": "Comma-separated directory names to skip for directory uploads.",
            },
            "include": {
                "type": "string",
                "description": "Glob pattern for included files.",
            },
            "exclude": {
                "type": "string",
                "description": "Glob pattern for excluded files.",
            },
            "directly_upload_media": {
                "type": "boolean",
                "description": "Whether OpenViking should upload media files directly.",
            },
            "preserve_structure": {
                "type": "boolean",
                "description": "Whether OpenViking should preserve source directory structure.",
            },
            "telemetry": {
                "type": "boolean",
                "description": "Return OpenViking telemetry when diagnostics are enabled.",
            },
        },
        "required": ["source"],
    },
}

CAPTURE_SCHEMA: dict[str, Any] = {
    "name": "loisa_memory_capture",
    "description": (
        "Capture explicit durable memory. "
        "Use only for user-requested remember operations or high-confidence durable facts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Durable memory candidate to extract.",
            },
            "source": {
                "type": "string",
                "description": "Compact source reference such as a session, resource URI, issue URL, or doc URI.",
            },
            "actor": {
                "type": "string",
                "description": "Optional actor/source identity for audit.",
            },
        },
        "required": ["content"],
    },
}


def tool_schemas(enabled: set[str]) -> list[dict[str, Any]]:
    return []
