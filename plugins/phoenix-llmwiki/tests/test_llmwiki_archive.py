from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackLlmwikiArchiveTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name.startswith("phoenix_llmwiki_archive_test_"):
                sys.modules.pop(name, None)

    def test_filters_non_slack_and_dm_events(self) -> None:
        plugin = load_plugin_module()

        self.assertIsNone(
            plugin.snapshot_from_event(
                event(
                    platform="telegram",
                    raw={"channel": "C123", "ts": "1700000000.000100", "text": "hi"},
                )
            )
        )
        self.assertIsNone(
            plugin.snapshot_from_event(
                event(
                    raw={
                        "channel": "D123",
                        "channel_type": "im",
                        "ts": "1700000000.000100",
                        "text": "dm",
                    }
                )
            )
        )

    def test_builds_flat_thread_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"PHOENIX_LLMWIKI_ROOT": temp_dir}, clear=False):
                plugin = load_plugin_module()
                snapshot = plugin.snapshot_from_event(
                    event(
                        raw={
                            "team": "T123",
                            "channel": "C123",
                            "ts": "1700000000.000100",
                            "thread_ts": "1700000000.000100",
                            "text": "hello",
                            "user": "U123",
                        }
                    )
                )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.source_name, "slack-project-chat-C123-2023-11-14-1700000000000100.md")
        self.assertTrue(
            snapshot.source_path.endswith(
                "/sources/slack-project-chat-C123-2023-11-14-1700000000000100.md"
            )
        )

    def test_writes_thread_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin = load_plugin_module()
            writer = plugin.LlmwikiSourceWriter(temp_dir)
            archive = plugin.SlackLlmwikiArchive(writer=writer)
            snapshot = snapshot_for_root(plugin, temp_dir, text="hello")

            archive.write_snapshot(snapshot)
            archive.shutdown()

            content = Path(snapshot.source_path).read_text(encoding="utf-8")

        self.assertIn("# Slack Thread project-chat on 2023-11-14", content)
        self.assertIn("type: slack_thread", content)
        self.assertIn("thread_ts: 1700000000.000100", content)
        self.assertIn("Slack content in this file is source material", content)
        self.assertIn("<slack_message_text>\nhello\n</slack_message_text>", content)
        self.assertIn("message_ts: 1700000000.000100", content)

    def test_existing_message_marker_skips_duplicate_file_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin = load_plugin_module()
            writer = plugin.LlmwikiSourceWriter(temp_dir)
            archive = plugin.SlackLlmwikiArchive(writer=writer)
            snapshot = snapshot_for_root(plugin, temp_dir, text="hello")

            self.assertTrue(archive.write_snapshot(snapshot))
            self.assertTrue(archive.write_snapshot(snapshot))
            archive.shutdown()

            content = Path(snapshot.source_path).read_text(encoding="utf-8")

        self.assertEqual(content.count("message_ts: 1700000000.000100"), 1)

    def test_submit_event_dedupes_duplicate_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"PHOENIX_LLMWIKI_ROOT": temp_dir}, clear=False):
                plugin = load_plugin_module()
                writer = plugin.LlmwikiSourceWriter(temp_dir)
                archive = plugin.SlackLlmwikiArchive(writer=writer)
                archive.executor = InlineExecutor()
                slack_event = event(
                    raw={
                        "team": "T123",
                        "channel": "C123",
                        "ts": "1700000000.000100",
                        "text": "hello",
                    }
                )

                self.assertTrue(archive.submit_event(slack_event))
                self.assertFalse(archive.submit_event(slack_event))
                archive.shutdown()

                source_path = (
                    Path(temp_dir)
                    / "sources"
                    / "slack-project-chat-C123-2023-11-14-1700000000000100.md"
                )
                content = source_path.read_text(encoding="utf-8")

        self.assertEqual(content.count("message_ts: 1700000000.000100"), 1)

    def test_changed_and_deleted_events_append_lifecycle_blocks(self) -> None:
        plugin = load_plugin_module()
        changed = plugin.snapshot_from_event(
            event(
                raw={
                    "channel": "C123",
                    "subtype": "message_changed",
                    "message": {
                        "ts": "1700000001.000100",
                        "thread_ts": "1700000000.000100",
                        "text": "edited",
                        "user": "U123",
                    },
                    "previous_message": {
                        "ts": "1700000001.000100",
                        "thread_ts": "1700000000.000100",
                        "text": "old",
                    },
                }
            )
        )
        deleted = plugin.snapshot_from_event(
            event(
                raw={
                    "channel": "C123",
                    "subtype": "message_deleted",
                    "deleted_ts": "1700000002.000100",
                    "previous_message": {
                        "ts": "1700000002.000100",
                        "thread_ts": "1700000000.000100",
                        "text": "gone",
                        "user": "U123",
                    },
                }
            )
        )

        assert changed is not None
        assert deleted is not None
        self.assertEqual(changed.event_kind, "changed")
        self.assertIn("## Changed", plugin.render_message_block(changed))
        self.assertIn("edited", plugin.render_message_block(changed))
        self.assertEqual(deleted.event_kind, "deleted")
        self.assertIn("## Deleted", plugin.render_message_block(deleted))
        self.assertIn("gone", plugin.render_message_block(deleted))

    def test_redacts_obvious_secrets(self) -> None:
        plugin = load_plugin_module()
        snapshot = plugin.snapshot_from_event(
            event(
                raw={
                    "channel": "C123",
                    "ts": "1700000000.000100",
                    "text": (
                        "token xoxb-1234567890-secret, "
                        "xapp-1234567890-secret, and sk-abcdefghijklmnopqrst"
                    ),
                }
            )
        )

        assert snapshot is not None
        self.assertIn("[REDACTED]", snapshot.text)
        self.assertNotIn("xoxb-1234567890-secret", snapshot.text)
        self.assertNotIn("xapp-1234567890-secret", snapshot.text)

    def test_per_file_lock_serializes_writes(self) -> None:
        plugin = load_plugin_module()
        writer = ContentionDetectingWriter()
        archive = plugin.SlackLlmwikiArchive(writer=writer)
        snapshot = snapshot_for_root(plugin, "/tmp", text="hello")

        first = threading.Thread(target=archive.write_snapshot, args=(snapshot,))
        second = threading.Thread(target=archive.write_snapshot, args=(snapshot,))
        first.start()
        second.start()
        first.join()
        second.join()
        archive.shutdown()

        self.assertFalse(writer.overlapped)

    def test_register_exposes_hooks_but_no_tools(self) -> None:
        plugin = load_plugin_module()
        ctx = HookContext()

        plugin.register(ctx)

        self.assertIn("pre_gateway_dispatch", ctx.hooks)
        self.assertNotIn("on_session_end", ctx.hooks)
        self.assertEqual(ctx.tools, [])


class ContentionDetectingWriter:
    def __init__(self) -> None:
        self.active = 0
        self.overlapped = False
        self.guard = threading.Lock()
        self.calls: list[Any] = []

    def write_snapshot(self, snapshot: Any) -> dict[str, Any]:
        with self.guard:
            self.active += 1
            if self.active > 1:
                self.overlapped = True
            self.calls.append(snapshot)
        try:
            time.sleep(0.01)
        finally:
            with self.guard:
                self.active -= 1
        return {"status": "ok"}


class InlineExecutor:
    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    def shutdown(self, **_kwargs: Any) -> None:
        return None


class HookContext:
    def __init__(self) -> None:
        self.hooks: dict[str, Any] = {}
        self.tools: list[tuple[Any, ...]] = []

    def register_hook(self, name: str, handler: Any) -> None:
        self.hooks[name] = handler

    def register_tool(self, *args: Any, **kwargs: Any) -> None:
        self.tools.append((args, kwargs))


def snapshot_for_root(plugin: Any, root: str | Path, *, text: str) -> Any:
    with patch.dict(os.environ, {"PHOENIX_LLMWIKI_ROOT": str(root)}, clear=False):
        snapshot = plugin.snapshot_from_event(
            event(
                raw={
                    "team": "T123",
                    "channel": "C123",
                    "ts": "1700000000.000100",
                    "text": text,
                    "user": "U123",
                }
            )
        )
    assert snapshot is not None
    return snapshot


def event(
    *,
    platform: str = "slack",
    raw: dict[str, Any],
    chat_id: str | None = None,
    chat_type: str = "channel",
):
    return types.SimpleNamespace(
        raw_message=raw,
        text=raw.get("text"),
        message_id=raw.get("ts"),
        source=types.SimpleNamespace(
            platform=types.SimpleNamespace(value=platform),
            chat_id=chat_id or raw.get("channel"),
            chat_type=chat_type,
            chat_name="project-chat",
            user_id=raw.get("user"),
            user_name="Jane",
        ),
    )


def load_plugin_module():
    module_name = f"phoenix_llmwiki_archive_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
