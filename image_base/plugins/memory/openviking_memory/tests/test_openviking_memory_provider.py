from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
import uuid
import zipfile
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = PLUGIN_ROOT.parents[3]
ENV_KEYS = [
    "OPENVIKING_AGENT",
    "OPENVIKING_AGENT_ID",
    "OPENVIKING_ENDPOINT",
    "OPENVIKING_MEMORY_COMMIT_KEEP_RECENT",
    "OPENVIKING_MEMORY_TOOLS",
    "OPENVIKING_USER_SPACE",
]


class OpenVikingMemoryProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_env = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        for name in list(sys.modules):
            if name.startswith("openviking_memory_test_"):
                sys.modules.pop(name, None)
        sys.modules.pop("agent", None)
        sys.modules.pop("agent.memory_provider", None)

    def test_provider_exposes_no_model_tools(self) -> None:
        plugin = load_provider_package()
        provider = plugin.OpenVikingMemoryProvider()
        provider._config = plugin.ProviderConfig(
            enabled_tools={"search", "read", "list", "grep", "add_resource", "capture"}
        )

        self.assertEqual(provider.get_tool_schemas(), [])

    def test_system_prompt_directs_cli_skill_without_memory_tools(self) -> None:
        plugin = load_provider_package()

        self.assertIn("loisa-viking-cli", plugin.SYSTEM_PROMPT)
        self.assertIn("OpenViking CLI", plugin.SYSTEM_PROMPT)
        self.assertIn("Do not search the OpenViking session scope", plugin.SYSTEM_PROMPT)
        self.assertNotIn("loisa_memory_", plugin.SYSTEM_PROMPT)

    def test_availability_is_local_and_does_not_require_openviking_agent(self) -> None:
        plugin = load_provider_package()
        calls: list[str] = []

        class NetworkRaisingHttpx:
            def get(self, *_args: Any, **_kwargs: Any) -> None:
                calls.append("get")
                raise AssertionError("is_available must not make network calls")

            def post(self, *_args: Any, **_kwargs: Any) -> None:
                calls.append("post")
                raise AssertionError("is_available must not make network calls")

        plugin.get_httpx = lambda: NetworkRaisingHttpx()

        self.assertNotIn("OPENVIKING_AGENT", os.environ)
        self.assertTrue(plugin.OpenVikingMemoryProvider().is_available())
        self.assertEqual(calls, [])

    def test_config_defaults_are_general_purpose(self) -> None:
        plugin = load_provider_package()

        config = plugin.ProviderConfig.from_env(user_id="jane")

        self.assertEqual(config.account, "default")
        self.assertEqual(config.user_space, "default")
        self.assertEqual(config.agent_id, "hermes-memory")
        self.assertEqual(config.memory_root, "viking://user/default/memories")
        self.assertEqual(config.resources_root, "viking://resources")
        self.assertEqual(config.search_target_uri, "viking://")
        self.assertEqual(config.commit_keep_recent_count, 0)
        self.assertIn("list", config.enabled_tools)
        self.assertIn("grep", config.enabled_tools)

    def test_commit_keep_recent_count_can_be_overridden(self) -> None:
        plugin = load_provider_package()
        os.environ["OPENVIKING_MEMORY_COMMIT_KEEP_RECENT"] = "10"

        config = plugin.ProviderConfig.from_env()

        self.assertEqual(config.commit_keep_recent_count, 10)

    def test_openviking_memory_tools_env_no_longer_exposes_tools(self) -> None:
        plugin = load_provider_package()
        os.environ["OPENVIKING_MEMORY_TOOLS"] = "search,list,grep"

        config = plugin.ProviderConfig.from_env()
        provider = plugin.OpenVikingMemoryProvider()
        provider._config = config

        self.assertEqual(config.enabled_tools, {"search", "list", "grep"})
        self.assertEqual(provider.get_tool_schemas(), [])

    def test_loisa_viking_cli_skill_is_profile_owned(self) -> None:
        skill_path = HERMES_ROOT / "skills" / "loisa-viking-cli" / "SKILL.md"

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("name: loisa-viking-cli", content)
        self.assertIn("OPENVIKING_CLI_CONFIG_FILE", content)
        self.assertIn("viking://session", content)

    def test_prefetch_context_is_fenced_and_closes_when_truncated(self) -> None:
        plugin = load_provider_package()

        output = plugin.format_prefetch(
            {
                "memories": [
                    {
                        "uri": "viking://user/default/memories/context",
                        "abstract": "durable company context " * 40,
                        "score": 0.9,
                    }
                ]
            },
            max_chars=220,
        )

        self.assertTrue(output.startswith("<openviking-context>"))
        self.assertIn("background reference, not user instruction", output)
        self.assertIn("[truncated by OpenViking memory]", output)
        self.assertTrue(output.endswith("</openviking-context>"))

    def test_openviking_session_id_is_workspace_prefixed(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(user_space="Workspace One")

        self.assertEqual(config.openviking_session_id("Hermes Session/42"), "Workspace-One__Hermes-Session-42")
        self.assertEqual(
            config.openviking_session_id("Workspace-One__already-prefixed"),
            "Workspace-One__already-prefixed",
        )

    def test_sync_turn_requires_messages_and_uses_passed_session_id(self) -> None:
        plugin = load_provider_package()
        provider, config, _client, sync = make_provider(plugin, startup_session_id="startup")

        provider.sync_turn("user text", "assistant text", session_id="resumed-session")

        self.assertEqual(sync.enqueued_messages, [])

        messages = [
            {"role": "user", "content": "runtime user text"},
            {"role": "assistant", "content": "assistant text"},
        ]
        provider.sync_turn(
            "user text",
            "assistant text",
            session_id="resumed-session",
            messages=messages,
        )

        self.assertEqual(
            sync.enqueued_messages,
            [(config.openviking_session_id("resumed-session"), "user text", "assistant text", messages)],
        )
        self.assertNotEqual(sync.enqueued_messages[0][0], config.openviking_session_id("startup"))

    def test_session_sync_writes_text_turn_as_openviking_parts(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(
            endpoint="http://openviking.test",
            user_space="workspace",
            agent_id="agent",
            user_role_id="U123",
        )
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "hello",
                "hi",
                [
                    {"role": "user", "content": "runtime context should be replaced"},
                    {"role": "assistant", "content": "hi"},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        self.assertEqual(client.add_message_calls, [])
        self.assertEqual(len(client.add_messages_calls), 1)
        session_id, batch = client.add_messages_calls[0]
        self.assertEqual(session_id, config.openviking_session_id("startup"))
        self.assertEqual(len(batch), 2)
        user_message = batch[0]
        assistant_message = batch[1]
        self.assertEqual(user_message["role"], "user")
        self.assertIn("Source metadata:\n- actor: U123", user_message["parts"][0]["text"])
        self.assertIn("Message:\nhello", user_message["parts"][0]["text"])
        self.assertNotIn("runtime context should be replaced", user_message["parts"][0]["text"])
        self.assertEqual(assistant_message["role"], "assistant")
        self.assertEqual(assistant_message["parts"], [{"type": "text", "text": "hi"}])

    def test_session_sync_converts_tool_calls_to_tool_parts(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "clean user",
                "done",
                [
                    {"role": "user", "content": "previous"},
                    {"role": "assistant", "content": "previous answer"},
                    {"role": "user", "content": "dirty current user"},
                    {
                        "role": "assistant",
                        "content": "I will inspect it.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "terminal", "arguments": "{\"cmd\":\"ls\"}"},
                            },
                            {
                                "id": "call_2",
                                "type": "function",
                                "function": {"name": "odd_tool", "arguments": "[\"unexpected\"]"},
                            }
                        ],
                    },
                    {"role": "tool", "name": "terminal", "tool_call_id": "call_1", "content": "README.md"},
                    {"role": "tool", "name": "odd_tool", "call_id": "call_2", "content": "array ok"},
                    {"role": "assistant", "content": "done"},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        _session_id, batch = client.add_messages_calls[0]
        self.assertEqual(len(batch), 3)
        self.assertEqual(batch[0]["parts"], [{"type": "text", "text": "clean user"}])
        tool_turn_parts = batch[1]["parts"]
        self.assertEqual(tool_turn_parts[0], {"type": "text", "text": "I will inspect it."})
        self.assertEqual(
            tool_turn_parts[1],
            {
                "type": "tool",
                "tool_id": "call_1",
                "tool_name": "terminal",
                "tool_input": {"cmd": "ls"},
                "tool_output": "README.md",
                "tool_status": "completed",
            },
        )
        self.assertEqual(
            tool_turn_parts[2],
            {
                "type": "tool",
                "tool_id": "call_2",
                "tool_name": "odd_tool",
                "tool_input": {"arguments": ["unexpected"]},
                "tool_output": "array ok",
                "tool_status": "completed",
            },
        )
        self.assertEqual(batch[2]["parts"], [{"type": "text", "text": "done"}])

    def test_session_sync_appends_fallback_assistant_when_final_message_is_missing(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "clean user",
                "final answer",
                [
                    {"role": "user", "content": "dirty current user"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "terminal", "arguments": "{\"cmd\":\"pwd\"}"},
                            }
                        ],
                    },
                    {"role": "tool", "name": "terminal", "tool_call_id": "call_1", "content": "/workspace"},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        _session_id, batch = client.add_messages_calls[0]
        self.assertEqual(len(batch), 3)
        self.assertEqual(batch[0]["parts"], [{"type": "text", "text": "clean user"}])
        self.assertEqual(batch[1]["parts"][0]["tool_output"], "/workspace")
        self.assertEqual(batch[2]["role"], "assistant")
        self.assertEqual(batch[2]["parts"], [{"type": "text", "text": "final answer"}])

    def test_session_sync_chunks_large_batches(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)
        assistant_messages = [
            {"role": "assistant", "content": f"assistant-{index}"}
            for index in range(105)
        ]

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "clean user",
                "assistant-104",
                [{"role": "user", "content": "dirty current user"}, *assistant_messages],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        self.assertEqual(len(client.add_messages_calls), 2)
        first_session_id, first_batch = client.add_messages_calls[0]
        second_session_id, second_batch = client.add_messages_calls[1]
        self.assertEqual(first_session_id, config.openviking_session_id("startup"))
        self.assertEqual(second_session_id, config.openviking_session_id("startup"))
        self.assertEqual(len(first_batch), 100)
        self.assertEqual(len(second_batch), 6)
        self.assertEqual(first_batch[0]["parts"], [{"type": "text", "text": "clean user"}])
        self.assertEqual(second_batch[-1]["parts"], [{"type": "text", "text": "assistant-104"}])

    def test_session_sync_summarizes_multimodal_tool_outputs(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)
        raw_image = "data:image/png;base64," + ("A" * 2000)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "clean user",
                "done",
                [
                    {"role": "user", "content": "dirty current user"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "vision", "arguments": "{}"},
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "name": "vision",
                        "tool_call_id": "call_1",
                        "content": [
                            {"type": "text", "text": "visible summary"},
                            {"type": "image_url", "image_url": {"url": raw_image}},
                            {"payload": "x" * 2000},
                        ],
                    },
                    {"role": "assistant", "content": "done"},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        _session_id, batch = client.add_messages_calls[0]
        tool_output = batch[1]["parts"][0]["tool_output"]
        self.assertIn("visible summary", tool_output)
        self.assertIn("[image attachment]", tool_output)
        self.assertIn("[non-text content omitted]", tool_output)
        self.assertNotIn(raw_image, tool_output)

    def test_session_sync_handles_malformed_and_unmatched_tool_messages(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "clean user",
                "",
                [
                    {"role": "user", "content": "dirty current user"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_bad",
                                "type": "function",
                                "function": {"name": "broken_tool", "arguments": "{not json"},
                            }
                        ],
                    },
                    {"role": "tool", "name": "orphan_tool", "content": "orphan output"},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        _session_id, batch = client.add_messages_calls[0]
        self.assertEqual(len(batch), 3)
        malformed_tool_part = batch[1]["parts"][0]
        self.assertEqual(malformed_tool_part["tool_id"], "call_bad")
        self.assertEqual(malformed_tool_part["tool_name"], "broken_tool")
        self.assertEqual(malformed_tool_part["tool_input"], {"raw_arguments": "{not json"})
        self.assertEqual(malformed_tool_part["tool_status"], "pending")
        unmatched_tool_part = batch[2]["parts"][0]
        self.assertEqual(unmatched_tool_part["tool_id"], "unmatched_1")
        self.assertEqual(unmatched_tool_part["tool_name"], "orphan_tool")
        self.assertEqual(unmatched_tool_part["tool_output"], "orphan output")
        self.assertEqual(unmatched_tool_part["tool_status"], "completed")

    def test_delegate_task_is_captured_as_parent_tool_part(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(endpoint="http://openviking.test", user_space="workspace")
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)

        try:
            sync.enqueue_messages(
                config.openviking_session_id("startup"),
                "research the release",
                "The delegated research found the release notes.",
                [
                    {"role": "user", "content": "dirty current user"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "delegate_1",
                                "type": "function",
                                "function": {
                                    "name": "delegate_task",
                                    "arguments": "{\"goal\":\"research the release\"}",
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "name": "delegate_task",
                        "tool_call_id": "delegate_1",
                        "content": "Found Hermes memory-provider changes.",
                    },
                    {"role": "assistant", "content": "The delegated research found the release notes."},
                ],
            )
            self.assertTrue(sync.flush(timeout=1))
        finally:
            sync.shutdown()

        _session_id, batch = client.add_messages_calls[0]
        tool_part = batch[1]["parts"][0]
        self.assertEqual(tool_part["tool_name"], "delegate_task")
        self.assertEqual(tool_part["tool_input"], {"goal": "research the release"})
        self.assertEqual(tool_part["tool_output"], "Found Hermes memory-provider changes.")

    def test_search_uses_all_context_target_and_ignores_stale_scope_arg(self) -> None:
        plugin = load_provider_package()
        provider, config, client, sync = make_provider(plugin, startup_session_id="startup")

        output = json.loads(provider.handle_tool_call("loisa_memory_search", {"query": "roadmap", "scope": "resources"}))

        expected_session_id = config.openviking_session_id("startup")
        self.assertEqual(sync.ensured_sessions, [expected_session_id])
        self.assertEqual(
            client.search_payloads[0],
            {
                "query": "roadmap",
                "session_id": expected_session_id,
                "target_uri": "viking://",
                "limit": config.search_limit,
                "include_provenance": False,
            },
        )
        self.assertEqual(output["session_id"], expected_session_id)
        self.assertEqual(output["target_uri"], "viking://")
        self.assertEqual(client.record_used_calls, [(expected_session_id, [f"{config.memory_root}/preference"])])

    def test_client_search_posts_to_rest_search_endpoint(self) -> None:
        plugin = load_provider_package()
        httpx = RecordingHttpx()
        plugin.client.get_httpx = lambda: httpx
        config = plugin.ProviderConfig(
            endpoint="http://openviking.test/",
            account="acct",
            user_space="workspace",
            agent_id="agent",
        )
        client = plugin.OpenVikingClient(config)

        response = client.search({"query": "roadmap"})

        self.assertEqual(response, {"result": {"ok": True}})
        self.assertEqual(len(httpx.posts), 1)
        self.assertEqual(httpx.posts[0]["url"], "http://openviking.test/api/v1/search/search")
        self.assertEqual(httpx.posts[0]["json"], {"query": "roadmap"})
        self.assertEqual(httpx.posts[0]["headers"]["X-OpenViking-Account"], "acct")
        self.assertNotIn("X-" + "API-Key", httpx.posts[0]["headers"])
        self.assertNotIn("Authorization", httpx.posts[0]["headers"])

    def test_client_add_messages_posts_to_batch_endpoint(self) -> None:
        plugin = load_provider_package()
        httpx = RecordingHttpx()
        plugin.client.get_httpx = lambda: httpx
        config = plugin.ProviderConfig(endpoint="http://openviking.test/")
        client = plugin.OpenVikingClient(config)
        messages = [{"role": "user", "parts": [{"type": "text", "text": "hello"}]}]

        response = client.add_messages("session-1", messages)

        self.assertEqual(response, {"result": {"ok": True}})
        self.assertEqual(len(httpx.posts), 1)
        self.assertEqual(httpx.posts[0]["url"], "http://openviking.test/api/v1/sessions/session-1/messages/batch")
        self.assertEqual(httpx.posts[0]["json"], {"messages": messages})

    def test_client_list_and_grep_call_openviking_rest_endpoints(self) -> None:
        plugin = load_provider_package()
        httpx = RecordingHttpx()
        plugin.client.get_httpx = lambda: httpx
        config = plugin.ProviderConfig(
            endpoint="http://openviking.test/",
            account="acct",
            user_space="workspace",
            agent_id="agent",
        )
        client = plugin.OpenVikingClient(config)

        list_response = client.list_directory(
            "viking://resources/docs",
            recursive=True,
            node_limit=7,
            show_all_hidden=True,
        )
        grep_response = client.grep({"uri": "viking://resources", "pattern": "TODO"})

        self.assertEqual(list_response, {"result": {"ok": True}})
        self.assertEqual(grep_response, {"result": {"ok": True}})
        self.assertEqual(httpx.gets[0]["url"], "http://openviking.test/api/v1/fs/ls")
        self.assertEqual(
            httpx.gets[0]["params"],
            {
                "uri": "viking://resources/docs",
                "recursive": True,
                "node_limit": 7,
                "show_all_hidden": True,
                "output": "agent",
                "abs_limit": 500,
            },
        )
        self.assertEqual(httpx.posts[0]["url"], "http://openviking.test/api/v1/search/grep")
        self.assertEqual(httpx.posts[0]["json"], {"uri": "viking://resources", "pattern": "TODO"})

    def test_read_accepts_any_viking_scope_and_rejects_non_viking_uris(self) -> None:
        plugin = load_provider_package()
        provider, _config, client, _sync = make_provider(plugin)
        uris = [
            "viking://user/workspace/memories/preference",
            "viking://agent/agent/memories/instruction",
            "viking://resources/docs/runbook",
            "viking://session/workspace/session-1/archive",
            "viking://temp/upload/item",
            "viking://queue/tasks/item",
        ]

        for uri in uris:
            payload = json.loads(provider.handle_tool_call("loisa_memory_read", {"uri": uri, "level": "overview"}))
            self.assertEqual(payload["uri"], uri)
            self.assertEqual(payload["resolved_uri"], uri)
            self.assertIn(f"overview content for {uri}", payload["content"])

        self.assertEqual(client.read_calls, [(uri, "overview") for uri in uris])
        for uri in (
            "https://example.com/doc",
            "viking:///missing-scope",
        ):
            with self.assertLogs(plugin.logger, level="WARNING"):
                error = json.loads(provider.handle_tool_call("loisa_memory_read", {"uri": uri}))
            self.assertIn("error", error)
            self.assertIn("viking://", error["error"])

    def test_list_browses_any_viking_directory(self) -> None:
        plugin = load_provider_package()
        provider, _config, client, _sync = make_provider(plugin)

        payload = json.loads(
            provider.handle_tool_call(
                "loisa_memory_list",
                {
                    "uri": "viking://resources/docs/",
                    "recursive": True,
                    "limit": 2,
                    "include_hidden": True,
                },
            )
        )

        self.assertEqual(
            client.list_calls,
            [
                {
                    "uri": "viking://resources/docs",
                    "recursive": True,
                    "node_limit": 2,
                    "show_all_hidden": True,
                    "output": "agent",
                    "abs_limit": 500,
                }
            ],
        )
        self.assertEqual(payload["uri"], "viking://resources/docs")
        self.assertEqual(payload["count"], 3)
        self.assertTrue(payload["truncated"])
        self.assertEqual(
            payload["entries"],
            [
                {
                    "name": "guide.md",
                    "uri": "viking://resources/docs/guide.md",
                    "type": "file",
                    "abstract": "Guide summary",
                },
                {
                    "name": "archive",
                    "uri": "viking://resources/docs/archive/",
                    "type": "dir",
                },
            ],
        )

    def test_grep_searches_any_viking_scope_and_literal_escapes_pattern(self) -> None:
        plugin = load_provider_package()
        provider, _config, client, _sync = make_provider(plugin)

        payload = json.loads(
            provider.handle_tool_call(
                "loisa_memory_grep",
                {
                    "uri": "viking://resources/docs",
                    "pattern": "foo.bar?",
                    "literal": True,
                    "case_insensitive": True,
                    "exclude_uri": "viking://resources/docs/archive",
                    "limit": 5,
                    "level_limit": 3,
                },
            )
        )

        self.assertEqual(
            client.grep_payloads,
            [
                {
                    "uri": "viking://resources/docs",
                    "pattern": "foo\\.bar\\?",
                    "case_insensitive": True,
                    "node_limit": 5,
                    "level_limit": 3,
                    "exclude_uri": "viking://resources/docs/archive",
                }
            ],
        )
        self.assertEqual(payload["pattern"], "foo.bar?")
        self.assertTrue(payload["literal"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(
            payload["matches"],
            [
                {
                    "uri": "viking://resources/docs/guide.md",
                    "line": 12,
                    "content": "foo.bar? appears here",
                }
            ],
        )

    def test_list_and_grep_accept_internal_scopes_and_reject_non_viking_uris(self) -> None:
        plugin = load_provider_package()
        provider, _config, client, _sync = make_provider(plugin)

        json.loads(
            provider.handle_tool_call(
                "loisa_memory_list",
                {"uri": "viking://session/workspace/session-1/archive"},
            )
        )
        json.loads(
            provider.handle_tool_call(
                "loisa_memory_grep",
                {"uri": "viking://temp/upload/item", "pattern": "secret"},
            )
        )

        self.assertEqual(client.list_calls[-1]["uri"], "viking://session/workspace/session-1/archive")
        self.assertEqual(client.grep_payloads[-1]["uri"], "viking://temp/upload/item")

        for tool_name, args in (
            ("loisa_memory_list", {"uri": "https://example.com/doc"}),
            ("loisa_memory_grep", {"uri": "viking:///missing-scope", "pattern": "secret"}),
        ):
            with self.assertLogs(plugin.logger, level="WARNING"):
                error = json.loads(provider.handle_tool_call(tool_name, args))
            self.assertIn("error", error)
            self.assertIn("viking://", error["error"])

    def test_add_resource_accepts_public_url_without_upload_and_ignores_wait_timeout(self) -> None:
        plugin = load_provider_package()
        provider, config, client, _sync = make_provider(plugin)

        result = json.loads(
            provider.handle_tool_call(
                "loisa_memory_add_resource",
                {
                    "source": "https://docs.example.com/runbook",
                    "parent": f"{config.resources_root}/docs",
                    "reason": "canonical runbook",
                    "wait": True,
                    "timeout": 10,
                },
            )
        )

        self.assertEqual(client.uploaded_files, [])
        self.assertEqual(
            client.add_resource_payloads[0],
            {
                "reason": "canonical runbook",
                "parent": f"{config.resources_root}/docs",
                "create_parent": True,
                "path": "https://docs.example.com/runbook",
            },
        )
        self.assertTrue(result["queued"])
        self.assertEqual(result["root_uri"], f"{config.resources_root}/docs/runbook")

    def test_add_resource_rejects_non_resource_targets(self) -> None:
        plugin = load_provider_package()
        provider, _config, _client, _sync = make_provider(plugin)

        with self.assertLogs(plugin.logger, level="WARNING"):
            error = json.loads(
                provider.handle_tool_call(
                    "loisa_memory_add_resource",
                    {
                        "source": "https://docs.example.com/runbook",
                        "parent": "viking://user/workspace/memories",
                    },
                )
            )

        self.assertIn("error", error)
        self.assertIn("viking://resources", error["error"])

    def test_add_resource_zips_local_directory_without_symlink_escapes(self) -> None:
        plugin = load_provider_package()
        provider, config, client, _sync = make_provider(plugin)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            outside = Path(temp_dir) / "outside"
            nested = root / "nested"
            root.mkdir()
            outside.mkdir()
            nested.mkdir()
            (root / "keep.txt").write_text("safe", encoding="utf-8")
            (nested / "inside.md").write_text("inside", encoding="utf-8")
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            create_symlink(outside / "secret.txt", root / "secret-link.txt")
            create_symlink(outside, root / "outside-dir-link")

            result = json.loads(
                provider.handle_tool_call(
                    "loisa_memory_add_resource",
                    {
                        "source": str(root),
                        "parent": config.resources_root,
                        "exclude": "*.tmp",
                    },
                )
            )

        self.assertEqual(result["status"], "added")
        self.assertEqual(len(client.uploaded_files), 1)
        uploaded_names = client.uploaded_files[0]["zip_names"]
        self.assertEqual(uploaded_names, ["keep.txt", "nested/inside.md"])
        self.assertEqual(client.add_resource_payloads[0]["source_name"], "source")
        self.assertEqual(client.add_resource_payloads[0]["temp_file_id"], "temp-file-1")
        self.assertNotIn("secret-link.txt", uploaded_names)
        self.assertNotIn("outside-dir-link/secret.txt", uploaded_names)

    def test_capture_uses_capture_session_commit_and_forces_async_tool_calls(self) -> None:
        plugin = load_provider_package()
        config = plugin.ProviderConfig(
            endpoint="http://openviking.test",
            user_space="workspace",
            agent_id="agent",
            capture_wait=True,
        )
        client = FakeClient(config)
        sync = plugin.SessionSyncManager(client, config)
        provider = plugin.OpenVikingMemoryProvider()
        provider._config = config
        provider._client = client
        provider._sync = sync
        provider._active_hermes_session_id = "startup"
        provider._active_openviking_session_id = config.openviking_session_id("startup")

        try:
            payload = json.loads(
                provider.handle_tool_call(
                    "loisa_memory_capture",
                    {
                        "content": "Remember that Phoenix uses OpenViking for durable memory.",
                        "source": "test",
                        "wait": True,
                        "timeout": 10,
                    },
                )
            )
        finally:
            sync.shutdown()

        capture_session_id = payload["capture_session_id"]
        self.assertTrue(capture_session_id.startswith(f"{config.openviking_session_id('startup')}__capture__"))
        self.assertEqual(client.ensure_session_calls, [capture_session_id])
        self.assertEqual(len(client.add_message_calls), 1)
        self.assertEqual(client.add_message_calls[0]["session_id"], capture_session_id)
        self.assertEqual(client.add_message_calls[0]["role"], "user")
        self.assertIsNone(client.add_message_calls[0]["role_id"])
        self.assertIn("Memory candidate:", client.add_message_calls[0]["content"])
        self.assertEqual(client.commit_session_calls, [(capture_session_id, 0)])
        self.assertEqual(client.poll_task_calls, [])
        self.assertIsNone(payload["task"])
        self.assertEqual(client.content_write_calls, [])


class FakeSync:
    def __init__(self) -> None:
        self.ensured_sessions: list[str] = []
        self.enqueued_messages: list[tuple[str, str, str, list[dict[str, Any]]]] = []

    def ensure_session(self, session_id: str) -> None:
        self.ensured_sessions.append(session_id)

    def enqueue_messages(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        messages: list[dict[str, Any]],
    ) -> None:
        self.enqueued_messages.append((session_id, user_content, assistant_content, messages))

    def capture(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("test should use the real SessionSyncManager for capture")


class FakeClient:
    def __init__(self, config: Any):
        self.config = config
        self.search_payloads: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []
        self.grep_payloads: list[dict[str, Any]] = []
        self.record_used_calls: list[tuple[str, list[str]]] = []
        self.read_calls: list[tuple[str, str]] = []
        self.uploaded_files: list[dict[str, Any]] = []
        self.add_resource_payloads: list[dict[str, Any]] = []
        self.ensure_session_calls: list[str] = []
        self.add_message_calls: list[dict[str, Any]] = []
        self.add_messages_calls: list[tuple[str, list[dict[str, Any]]]] = []
        self.commit_session_calls: list[tuple[str, int]] = []
        self.poll_task_calls: list[dict[str, Any]] = []
        self.content_write_calls: list[Any] = []

    def unwrap_result(self, response: Any) -> Any:
        if isinstance(response, dict) and "result" in response:
            return response["result"]
        return response

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.search_payloads.append(payload)
        return {
            "result": {
                "total": 1,
                "memories": [
                    {
                        "uri": f"{self.config.memory_root}/preference",
                        "abstract": "OpenViking stores durable memory.",
                        "score": 0.92,
                    }
                ],
            }
        }

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
        self.list_calls.append(
            {
                "uri": uri,
                "recursive": recursive,
                "node_limit": node_limit,
                "show_all_hidden": show_all_hidden,
                "output": output,
                "abs_limit": abs_limit,
            }
        )
        return {
            "result": [
                {
                    "name": "guide.md",
                    "uri": "viking://resources/docs/guide.md",
                    "isDir": False,
                    "abstract": "Guide summary",
                },
                {
                    "name": "archive",
                    "uri": "viking://resources/docs/archive/",
                    "isDir": True,
                },
                {
                    "name": "extra.md",
                    "uri": "viking://resources/docs/extra.md",
                    "isDir": False,
                },
            ]
        }

    def record_used(self, session_id: str, contexts: list[str]) -> dict[str, Any]:
        self.record_used_calls.append((session_id, contexts))
        return {"status": "ok"}

    def stat(self, uri: str) -> dict[str, Any]:
        return {"result": {"type": "dir", "uri": uri}}

    def read_content(self, uri: str, level: str) -> dict[str, Any]:
        self.read_calls.append((uri, level))
        return {"result": {"content": f"{level} content for {uri}"}}

    def grep(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.grep_payloads.append(dict(payload))
        return {
            "result": {
                "matches": [
                    {
                        "uri": "viking://resources/docs/guide.md",
                        "line": 12,
                        "content": "foo.bar? appears here",
                    }
                ],
                "count": 1,
            }
        }

    def upload_temp_file(self, file_path: Path) -> str:
        with zipfile.ZipFile(file_path) as archive:
            names = sorted(archive.namelist())
        self.uploaded_files.append({"name": file_path.name, "zip_names": names})
        return "temp-file-1"

    def add_resource(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.add_resource_payloads.append(dict(payload))
        return {
            "result": {
                "status": "added",
                "root_uri": payload.get("parent", self.config.resources_root).rstrip("/") + "/runbook",
            }
        }

    def ensure_session(self, session_id: str) -> dict[str, Any]:
        self.ensure_session_calls.append(session_id)
        return {"result": {"session_id": session_id}}

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
        self.add_message_calls.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "parts": parts,
                "created_at": created_at,
                "role_id": role_id,
            }
        )
        return {"result": {"ok": True}}

    def add_messages(self, session_id: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        self.add_messages_calls.append((session_id, messages))
        return {"result": {"ok": True}}

    def commit_session(self, session_id: str, *, keep_recent_count: int = 0, telemetry: bool = False) -> dict[str, Any]:
        self.commit_session_calls.append((session_id, keep_recent_count))
        return {"result": {"status": "accepted", "task_id": "task-1"}}

    def poll_task(self, task_id: str, *, timeout: float, interval: float) -> dict[str, Any]:
        self.poll_task_calls.append({"task_id": task_id, "timeout": timeout, "interval": interval})
        return {"task_id": task_id, "status": "completed", "timeout": timeout, "interval": interval}

    def content_write(self, *_args: Any, **_kwargs: Any) -> None:
        self.content_write_calls.append((_args, _kwargs))
        raise AssertionError("capture must not write through content/write")


class RecordingHttpx:
    def __init__(self) -> None:
        self.gets: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> Any:
        self.gets.append({"url": url, **kwargs})
        return FakeResponse({"result": {"ok": True}})

    def post(self, url: str, **kwargs: Any) -> Any:
        self.posts.append({"url": url, **kwargs})
        return FakeResponse({"result": {"ok": True}})


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload


def make_provider(plugin: Any, *, startup_session_id: str = "startup") -> tuple[Any, Any, FakeClient, FakeSync]:
    config = plugin.ProviderConfig(
        endpoint="http://openviking.test",
        user_space="workspace",
        agent_id="agent",
        healthcheck_on_initialize=False,
    )
    client = FakeClient(config)
    sync = FakeSync()
    provider = plugin.OpenVikingMemoryProvider()
    provider._config = config
    provider._client = client
    provider._sync = sync
    provider._active_hermes_session_id = startup_session_id
    provider._active_openviking_session_id = config.openviking_session_id(startup_session_id)
    return provider, config, client, sync


def load_provider_package() -> Any:
    install_agent_memory_provider_stub()
    module_name = f"openviking_memory_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def install_agent_memory_provider_stub() -> None:
    agent_module = types.ModuleType("agent")
    memory_provider_module = types.ModuleType("agent.memory_provider")

    class MemoryProvider:
        pass

    memory_provider_module.MemoryProvider = MemoryProvider
    sys.modules["agent"] = agent_module
    sys.modules["agent.memory_provider"] = memory_provider_module


def create_symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (NotImplementedError, OSError):
        pass


if __name__ == "__main__":
    unittest.main()
