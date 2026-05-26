from __future__ import annotations

import importlib.util
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE = "phoenix_slack_viking_archive_runtime"


class SlackVikingBackfillTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime = sys.modules.get(RUNTIME_MODULE)
        if runtime is not None:
            try:
                runtime.ARCHIVE.shutdown()
            except Exception:
                pass

        for name in list(sys.modules):
            if name.startswith("phoenix_slack_viking_archive_backfill_test_") or name == RUNTIME_MODULE:
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
                    {"messages": [{"ts": "1700000002.000000", "text": "new"}], "response_metadata": {"next_cursor": "h2"}},
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
        thread_calls = [call for call in writer.calls if "/threads/" in call["uri"]]
        self.assertIn("old", thread_calls[0]["content"])
        self.assertIn("new", thread_calls[1]["content"])

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
        thread_contents = [call["content"] for call in writer.calls if "/threads/" in call["uri"]]
        self.assertEqual(len(thread_contents), 3)
        self.assertIn("root", thread_contents[0])
        self.assertIn("reply one", thread_contents[1])
        self.assertIn("reply two", thread_contents[2])

    def test_skips_existing_message_markers_on_rerun(self) -> None:
        backfill = load_backfill_module()
        channel = {"id": "C123", "name": "general"}
        message = {"ts": "1700000001.000000", "text": "already archived"}
        snapshot = backfill.archive.snapshot_from_event(backfill.slack_event(channel, message, root_ts=message["ts"]))
        assert snapshot is not None
        existing = backfill.archive.render_thread_header(snapshot) + backfill.archive.render_message_block(snapshot)
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {"messages": [message], "response_metadata": {}},
                ]
            }
        )
        writer = FakeWriter(backfill, existing={snapshot.thread_uri: existing})
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel(channel)

        self.assertEqual(summary.messages_written, 0)
        self.assertEqual(summary.messages_skipped, 1)
        self.assertEqual(writer.read_calls, [snapshot.thread_uri])
        self.assertEqual(writer.calls, [])

    def test_thread_create_conflict_falls_back_to_append_during_backfill(self) -> None:
        backfill = load_backfill_module()
        client = FakeSlackClient(
            history_pages={
                "C123": [
                    {"messages": [{"ts": "1700000001.000000", "text": "root"}], "response_metadata": {}},
                ]
            }
        )
        writer = FakeWriter(backfill, conflict_on_thread_create=True)
        runner = backfill.SlackBackfill(client=client, archive_writer=writer, options=options(backfill))

        summary = runner.run_for_test_channel({"id": "C123", "name": "general"})

        self.assertEqual(summary.messages_written, 1)
        self.assertEqual([call["mode"] for call in writer.calls], ["create", "create", "append"])


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
        conflict_on_thread_create: bool = False,
    ) -> None:
        self.backfill = backfill
        self.existing = existing or {}
        self.conflict_on_thread_create = conflict_on_thread_create
        self.calls: list[dict[str, str]] = []
        self.read_calls: list[str] = []

    def read(self, uri: str) -> str:
        self.read_calls.append(uri)
        if uri in self.existing:
            return self.existing[uri]
        raise self.backfill.archive.OpenVikingReadError("not found", status_code=404)

    def write(self, uri: str, content: str, *, mode: str) -> dict[str, Any]:
        self.calls.append({"uri": uri, "content": content, "mode": mode})
        if self.conflict_on_thread_create and mode == "create" and "/threads/" in uri:
            raise self.backfill.archive.OpenVikingWriteError("conflict", status_code=409)
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
    module_name = f"phoenix_slack_viking_archive_backfill_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "backfill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.SlackBackfill.run_for_test_channel = run_for_test_channel
    return module


if __name__ == "__main__":
    unittest.main()
