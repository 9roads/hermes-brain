from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE = "phoenix_llmwiki_runtime"


class SlackLlmwikiBackfillTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime = sys.modules.get(RUNTIME_MODULE)
        if runtime is not None:
            try:
                runtime.ARCHIVE.shutdown()
            except Exception:
                pass

        for name in list(sys.modules):
            if name.startswith("phoenix_llmwiki_backfill_test_") or name == RUNTIME_MODULE:
                sys.modules.pop(name, None)

    def test_selects_default_and_explicit_token_envs(self) -> None:
        backfill = load_backfill_module()
        now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)

        default_args = backfill.parse_args([])
        default_options = backfill.options_from_args(
            default_args,
            env={"SLACK_BOT_TOKEN": "xoxb-bot", "SLACK_TOKEN": "xoxb-fallback"},
            now=now,
        )
        self.assertEqual(default_options.token, "xoxb-bot")
        self.assertEqual(default_options.token_env, "SLACK_BOT_TOKEN")
        self.assertEqual(default_options.latest, "1779796800.000000")
        self.assertEqual(default_options.oldest, "1774612800.000000")

        explicit_args = backfill.parse_args(["--token-env", "SLACK_TOKEN"])
        explicit_options = backfill.options_from_args(
            explicit_args,
            env={"SLACK_BOT_TOKEN": "xoxb-bot", "SLACK_TOKEN": "xoxb-explicit"},
            now=now,
        )
        self.assertEqual(explicit_options.token, "xoxb-explicit")
        self.assertEqual(explicit_options.token_env, "SLACK_TOKEN")

    def test_lists_public_and_private_channels_and_skips_dm_like_ids(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            list_pages=[
                {
                    "channels": [
                        {"id": "C123", "name": "general"},
                        {"id": "D123", "name": "dm"},
                    ],
                    "response_metadata": {"next_cursor": "next"},
                },
                {
                    "channels": [
                        {"id": "G123", "name": "private", "is_private": True},
                        {"id": "U123", "name": "user"},
                    ],
                    "response_metadata": {},
                },
            ]
        )
        runner = backfill.SlackBackfill(
            client=client,
            archive_writer=FakeWriter(backfill),
            options=options(backfill, exclude_archived=True),
        )

        try:
            channels = list(runner.iter_channels())
        finally:
            runner.archive.shutdown()

        self.assertEqual([channel["id"] for channel in channels], ["C123", "G123"])
        self.assertEqual(client.list_calls[0]["types"], "public_channel,private_channel")
        self.assertTrue(client.list_calls[0]["exclude_archived"])
        self.assertEqual(client.list_calls[1]["cursor"], "next")

    def test_history_uses_bounds_and_cursor_pagination(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {
                        "messages": [{"ts": "1700000002.000000", "text": "new"}],
                        "response_metadata": {"next_cursor": "h2"},
                    },
                    {"messages": [{"ts": "1700000001.000000", "text": "old"}], "response_metadata": {}},
                ]
            }
        )
        writer = FakeWriter(backfill)
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel({"id": "C123", "name": "general"})

        self.assertEqual(summary.messages_written, 2)
        self.assertEqual(client.history_calls[0]["oldest"], "1700000000.000000")
        self.assertEqual(client.history_calls[0]["latest"], "1700000100.000000")
        self.assertTrue(client.history_calls[0]["inclusive"])
        self.assertEqual(client.history_calls[1]["cursor"], "h2")
        self.assertIn("old", writer.calls[0]["content"])
        self.assertIn("new", writer.calls[1]["content"])
        self.assertTrue(
            writer.calls[0]["path"].endswith("sources/slack-general-C123-2023-11-14-1700000001000000.md")
        )
        self.assertTrue(
            writer.calls[1]["path"].endswith("sources/slack-general-C123-2023-11-14-1700000002000000.md")
        )

    def test_fetches_replies_for_roots_and_skips_duplicate_root_reply(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {
                        "messages": [
                            {"ts": "1700000003.000000", "text": "solo"},
                            {"ts": "1700000001.000000", "text": "root", "reply_count": 2},
                        ],
                        "response_metadata": {},
                    }
                ]
            },
            reply_pages={
                ("C123", "1700000001.000000"): [
                    {
                        "messages": [
                            {"ts": "1700000002.000000", "thread_ts": "1700000001.000000", "text": "reply"},
                            {"ts": "1700000001.000000", "thread_ts": "1700000001.000000", "text": "root duplicate"},
                        ],
                        "response_metadata": {},
                    }
                ]
            },
        )
        writer = FakeWriter(backfill)
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel({"id": "C123", "name": "general"})

        self.assertEqual(len(client.reply_calls), 1)
        self.assertEqual(client.reply_calls[0]["ts"], "1700000001.000000")
        self.assertEqual(summary.messages_written, 3)
        self.assertEqual(summary.messages_skipped, 0)

    def test_writes_thread_messages_oldest_first(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {
                        "messages": [{"ts": "1700000001.000000", "text": "root", "reply_count": 2}],
                        "response_metadata": {},
                    }
                ]
            },
            reply_pages={
                ("C123", "1700000001.000000"): [
                    {
                        "messages": [
                            {"ts": "1700000003.000000", "thread_ts": "1700000001.000000", "text": "reply two"},
                            {"ts": "1700000002.000000", "thread_ts": "1700000001.000000", "text": "reply one"},
                            {"ts": "1700000001.000000", "thread_ts": "1700000001.000000", "text": "root duplicate"},
                        ],
                        "response_metadata": {},
                    }
                ]
            },
        )
        writer = FakeWriter(backfill)
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel({"id": "C123", "name": "general"})

        self.assertEqual(summary.messages_written, 3)
        self.assertEqual(len(writer.calls), 3)
        self.assertEqual(len({call["path"] for call in writer.calls}), 1)
        self.assertTrue(
            writer.calls[0]["path"].endswith("sources/slack-general-C123-2023-11-14-1700000001000000.md")
        )
        self.assertIn("root", writer.calls[0]["content"])
        self.assertIn("reply one", writer.calls[1]["content"])
        self.assertIn("reply two", writer.calls[2]["content"])

    def test_skips_existing_message_markers_on_rerun(self) -> None:
        backfill = load_backfill_module()
        channel = {"id": "C123", "name": "general"}
        message = {"ts": "1700000001.000000", "text": "already archived"}
        snapshot = backfill.archive.snapshot_from_event(backfill.slack_event(channel, message, root_ts=message["ts"]))
        assert snapshot is not None
        existing = backfill.archive.render_source_append(snapshot, include_header=True)
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {"messages": [message], "response_metadata": {}},
                ]
            }
        )
        writer = FakeWriter(backfill, existing={snapshot.source_path: existing})
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel(channel)

        self.assertEqual(summary.messages_written, 0)
        self.assertEqual(summary.messages_skipped, 1)
        self.assertEqual(writer.read_calls, [snapshot.source_path])
        self.assertEqual(writer.calls, [])

    def test_backfill_and_realtime_messages_render_identically(self) -> None:
        backfill = load_backfill_module()
        channel = {"id": "C123", "name": "general", "context_team_id": "T123"}
        message = {
            "team": "T123",
            "ts": "1700000001.000000",
            "thread_ts": "1700000000.000000",
            "text": "same source text",
            "user": "U123",
            "user_name": "Jane",
            "permalink": "https://example.slack.com/archives/C123/p1700000001000000",
        }

        backfill_snapshot = backfill.archive.snapshot_from_event(
            backfill.slack_event(channel, message, root_ts=message["thread_ts"])
        )
        realtime_snapshot = backfill.archive.snapshot_from_event(
            types.SimpleNamespace(
                raw_message={
                    **message,
                    "channel": "C123",
                    "channel_name": "general",
                    "channel_type": "channel",
                },
                text=message["text"],
                message_id=message["ts"],
                source=types.SimpleNamespace(
                    platform=types.SimpleNamespace(value="slack"),
                    chat_id="C123",
                    chat_type="channel",
                    chat_name="general",
                    user_id="U123",
                    user_name="Jane",
                    slack_team_id="T123",
                ),
            )
        )

        assert backfill_snapshot is not None
        assert realtime_snapshot is not None
        self.assertEqual(backfill_snapshot.source_path, realtime_snapshot.source_path)
        self.assertEqual(
            backfill.archive.render_source_append(backfill_snapshot, include_header=True),
            backfill.archive.render_source_append(realtime_snapshot, include_header=True),
        )

    def test_batch_writer_stages_until_commit(self) -> None:
        backfill = load_backfill_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"PHOENIX_LLMWIKI_ROOT": temp_dir}, clear=False):
                writer = backfill.BatchLlmwikiSourceWriter(backfill.archive.LlmwikiSourceWriter(temp_dir))
                snapshot = backfill.archive.snapshot_from_event(
                    backfill.slack_event(
                        {"id": "C123", "name": "general"},
                        {"ts": "1700000001.000000", "text": "staged"},
                        root_ts="1700000001.000000",
                    )
                )
                assert snapshot is not None

                writer.write_snapshot(snapshot)

                self.assertFalse(Path(snapshot.source_path).exists())
                self.assertTrue((writer.stage_dir / snapshot.source_name).exists())

                result = writer.commit()

                self.assertEqual(result["files"], 1)
                self.assertFalse(writer.stage_dir.exists())
                content = Path(snapshot.source_path).read_text(encoding="utf-8")
                self.assertIn("staged", content)
                self.assertIn("# Slack Thread general on 2023-11-14", content)

    def test_run_publishes_staged_sources_after_backfill(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            list_pages=[{"channels": [{"id": "C123", "name": "general"}], "response_metadata": {}}],
            history_pages={
                "C123": [
                    {
                        "messages": [{"ts": "1700000001.000000", "text": "published at end"}],
                        "response_metadata": {},
                    }
                ]
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"PHOENIX_LLMWIKI_ROOT": temp_dir}, clear=False):
                writer = backfill.BatchLlmwikiSourceWriter(backfill.archive.LlmwikiSourceWriter(temp_dir))
                runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

                summary = runner.run()

                source_path = (
                    Path(temp_dir)
                    / "sources"
                    / "slack-general-C123-2023-11-14-1700000001000000.md"
                )
                self.assertEqual(summary.messages_written, 1)
                self.assertTrue(source_path.exists())
                self.assertFalse(writer.stage_dir.exists())
                self.assertIn("published at end", source_path.read_text(encoding="utf-8"))


class FakeSlackClient:
    def __init__(
        self,
        *,
        list_pages: list[dict[str, Any]] | None = None,
        history_pages: dict[str, list[dict[str, Any]]] | None = None,
        reply_pages: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.list_pages = list(list_pages or [{"channels": [], "response_metadata": {}}])
        self.history_pages = {key: list(value) for key, value in (history_pages or {}).items()}
        self.reply_pages = {key: list(value) for key, value in (reply_pages or {}).items()}
        self.list_calls: list[dict[str, Any]] = []
        self.history_calls: list[dict[str, Any]] = []
        self.reply_calls: list[dict[str, Any]] = []

    def conversations_list(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return self.list_pages.pop(0)

    def conversations_history(self, **kwargs: Any) -> dict[str, Any]:
        self.history_calls.append(kwargs)
        return self.history_pages.setdefault(kwargs["channel"], [{"messages": [], "response_metadata": {}}]).pop(0)

    def conversations_replies(self, **kwargs: Any) -> dict[str, Any]:
        self.reply_calls.append(kwargs)
        return self.reply_pages.setdefault((kwargs["channel"], kwargs["ts"]), [{"messages": [], "response_metadata": {}}]).pop(0)


class FakeWriter:
    def __init__(
        self,
        backfill: Any,
        *,
        existing: dict[str, str] | None = None,
    ) -> None:
        self.backfill = backfill
        self.existing = existing or {}
        self.calls: list[dict[str, str]] = []
        self.read_calls: list[str] = []

    def read(self, path: str) -> str:
        self.read_calls.append(path)
        if path in self.existing:
            return self.existing[path]
        raise self.backfill.archive.SourceReadError("not found", not_found=True)

    def write_snapshot(self, snapshot: Any) -> dict[str, Any]:
        existing = self.existing.get(snapshot.source_path, "")
        content = self.backfill.archive.render_source_append(snapshot, include_header=not bool(existing))
        self.existing[snapshot.source_path] = existing + content
        self.calls.append({"path": snapshot.source_path, "content": content})
        return {"status": "ok"}


def options(backfill: Any, *, exclude_archived: bool = False) -> Any:
    return backfill.BackfillOptions(
        token="xoxb-test",
        token_env="SLACK_BOT_TOKEN",
        oldest="1700000000.000000",
        latest="1700000100.000000",
        channel_ids=(),
        exclude_archived=exclude_archived,
    )


def run_for_test_channel(self: Any, channel: dict[str, Any]) -> Any:
    try:
        if self.backfill_channel(channel):
            self.summary.channels_archived += 1
    finally:
        self.archive.shutdown()
    self.summary.threads_read = self.guard.read_count
    return self.summary


def load_backfill_module() -> Any:
    module_name = f"phoenix_llmwiki_backfill_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "backfill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.SlackBackfill.run_for_test_channel = run_for_test_channel
    return module


if __name__ == "__main__":
    unittest.main()
