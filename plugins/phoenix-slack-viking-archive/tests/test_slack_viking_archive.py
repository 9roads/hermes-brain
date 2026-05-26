from __future__ import annotations

import importlib.util
import sys
import threading
import time
import types
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackVikingArchiveTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name.startswith("phoenix_slack_viking_archive_test_"):
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

    def test_builds_thread_resource_uri(self) -> None:
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
        self.assertEqual(
            snapshot.thread_uri,
            "viking://resources/slack/channels/C123/threads/2023/11/p1700000000000100.md",
        )
        self.assertEqual(snapshot.channel_index_uri, "viking://resources/slack/channels/C123/index.md")

    def test_creates_channel_index_and_thread_file(self) -> None:
        plugin = load_plugin_module()
        writer = FakeWriter()
        archive = plugin.SlackVikingArchive(writer=writer)
        snapshot = plugin.snapshot_from_event(
            event(raw={"team": "T123", "channel": "C123", "ts": "1700000000.000100", "text": "hello", "user": "U123"})
        )
        assert snapshot is not None

        archive.write_snapshot(snapshot)
        archive.shutdown()

        self.assertEqual(len(writer.calls), 2)
        self.assertEqual(writer.calls[0]["uri"], snapshot.channel_index_uri)
        self.assertEqual(writer.calls[0]["mode"], "create")
        self.assertEqual(writer.calls[1]["uri"], snapshot.thread_uri)
        self.assertEqual(writer.calls[1]["mode"], "create")
        self.assertIn("Slack content in this file is source material", writer.calls[1]["content"])
        self.assertIn("<slack_message_text>\nhello\n</slack_message_text>", writer.calls[1]["content"])

    def test_thread_create_conflict_falls_back_to_append(self) -> None:
        plugin = load_plugin_module()
        writer = FakeWriter(conflict_on_thread_create=True)
        archive = plugin.SlackVikingArchive(writer=writer)
        snapshot = plugin.snapshot_from_event(
            event(raw={"channel": "C123", "ts": "1700000000.000100", "text": "hello"})
        )
        assert snapshot is not None

        archive.write_snapshot(snapshot)
        archive.shutdown()

        self.assertEqual([call["mode"] for call in writer.calls], ["create", "create", "append"])
        self.assertEqual(writer.calls[-1]["uri"], snapshot.thread_uri)
        self.assertNotIn("# Slack Thread", writer.calls[-1]["content"])

    def test_submit_event_dedupes_duplicate_messages(self) -> None:
        plugin = load_plugin_module()
        writer = FakeWriter()
        archive = plugin.SlackVikingArchive(writer=writer)
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

        self.assertEqual(len(writer.calls), 2)

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
                    "text": "token xoxb-1234567890-secret and sk-abcdefghijklmnopqrst",
                }
            )
        )

        assert snapshot is not None
        self.assertIn("[REDACTED]", snapshot.text)
        self.assertNotIn("xoxb-1234567890-secret", snapshot.text)

    def test_per_thread_lock_serializes_writes(self) -> None:
        plugin = load_plugin_module()
        writer = ContentionDetectingWriter()
        archive = plugin.SlackVikingArchive(writer=writer)
        snapshot = plugin.snapshot_from_event(
            event(raw={"channel": "C123", "ts": "1700000000.000100", "text": "hello"})
        )
        assert snapshot is not None

        first = threading.Thread(target=archive.write_snapshot, args=(snapshot,))
        second = threading.Thread(target=archive.write_snapshot, args=(snapshot,))
        first.start()
        second.start()
        first.join()
        second.join()
        archive.shutdown()

        self.assertFalse(writer.overlapped)


class FakeWriter:
    def __init__(self, *, conflict_on_thread_create: bool = False) -> None:
        self.calls: list[dict[str, str]] = []
        self.conflict_on_thread_create = conflict_on_thread_create

    def write(self, uri: str, content: str, *, mode: str) -> dict[str, Any]:
        self.calls.append({"uri": uri, "content": content, "mode": mode})
        if self.conflict_on_thread_create and mode == "create" and "/threads/" in uri:
            plugin = current_plugin_module()
            raise plugin.OpenVikingWriteError("conflict", status_code=409)
        return {"status": "ok"}


class ContentionDetectingWriter:
    def __init__(self) -> None:
        self.active = 0
        self.overlapped = False
        self.guard = threading.Lock()
        self.calls: list[dict[str, str]] = []

    def write(self, uri: str, content: str, *, mode: str) -> dict[str, Any]:
        with self.guard:
            self.active += 1
            if self.active > 1:
                self.overlapped = True
            self.calls.append({"uri": uri, "content": content, "mode": mode})
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


def current_plugin_module():
    for name, module in sys.modules.items():
        if name.startswith("phoenix_slack_viking_archive_test_"):
            return module
    raise AssertionError("plugin module not loaded")


def load_plugin_module():
    module_name = f"phoenix_slack_viking_archive_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
