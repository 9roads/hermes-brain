from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackVikingArchiveCommandTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name.startswith("phoenix_slack_viking_archive_command_test_"):
                sys.modules.pop(name, None)

    def test_ignores_non_archive_phoenix_args_and_shows_usage(self) -> None:
        command = load_command_module()

        self.assertIsNone(command.handle_command("hello there"))
        self.assertIn("/phoenix slack-archive backfill", command.handle_command("slack-archive"))

    def test_starts_backfill_process_and_writes_runtime_status(self) -> None:
        command = load_command_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            captured: dict[str, Any] = {}
            fake_process = FakeProcess(pid=1234)

            def fake_launch(argv: list[str], *, env: dict[str, str], log_path: Path) -> FakeProcess:
                captured["argv"] = argv
                captured["env"] = env
                captured["log_path"] = log_path
                return fake_process

            command.launch_backfill_process = fake_launch
            command.start_monitor_thread = lambda *_args, **_kwargs: None

            with patch.dict(os.environ, {command.RUN_DIR_ENV: temp_dir}, clear=False):
                result = command.handle_command(
                    "slack-archive backfill --days 7 --history-limit 50 "
                    "--reply-limit 25 --channel C123 --exclude-archived"
                )
                paths = command.runtime_paths()

            self.assertIn("Started Slack archive backfill pid=1234 days=7", result)
            self.assertEqual(Path(captured["argv"][1]).name, "backfill.py")
            self.assertIn("--days", captured["argv"])
            self.assertIn("7", captured["argv"])
            self.assertIn("--channel", captured["argv"])
            self.assertIn("C123", captured["argv"])
            self.assertIn("--exclude-archived", captured["argv"])
            self.assertEqual(captured["env"]["PYTHONUNBUFFERED"], "1")

            status = json.loads(paths.status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "running")
            self.assertEqual(status["pid"], 1234)
            self.assertIn("backfill.py", " ".join(status["argv"]))
            self.assertEqual(paths.pid_path.read_text(encoding="utf-8").strip(), "1234")
            self.assertEqual(paths.lock_path.read_text(encoding="utf-8").strip(), "1234")
            self.assertIn("starting Slack OpenViking backfill", paths.log_path.read_text(encoding="utf-8"))

    def test_reports_already_running_process(self) -> None:
        command = load_command_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {command.RUN_DIR_ENV: temp_dir}, clear=False):
                paths = command.runtime_paths()
                command.write_status(
                    paths,
                    {
                        "status": "running",
                        "pid": 1234,
                        "started_at": "2026-05-26T10:00:00Z",
                        "log_path": str(paths.log_path),
                    },
                )
                command.is_process_alive = lambda pid: pid == 1234
                command.launch_backfill_process = fail_launch

                result = command.handle_command("slack-archive backfill --days 60")

            self.assertIn("already running pid=1234", result)

    def test_status_marks_stale_running_process_as_unknown_finished(self) -> None:
        command = load_command_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {command.RUN_DIR_ENV: temp_dir}, clear=False):
                paths = command.runtime_paths()
                command.write_status(
                    paths,
                    {
                        "status": "running",
                        "pid": 1234,
                        "started_at": "2026-05-26T10:00:00Z",
                        "log_path": str(paths.log_path),
                    },
                )
                paths.lock_path.write_text("1234\n", encoding="utf-8")
                paths.pid_path.write_text("1234\n", encoding="utf-8")
                paths.log_path.write_text("line one\nline two\n", encoding="utf-8")
                command.is_process_alive = lambda _pid: False

                result = command.handle_command("slack-archive status")

                status = json.loads(paths.status_path.read_text(encoding="utf-8"))
                self.assertFalse(paths.lock_path.exists())
                self.assertFalse(paths.pid_path.exists())

            self.assertIn("unknown_finished", result)
            self.assertEqual(status["status"], "unknown_finished")
            self.assertIn("line two", result)

    def test_monitor_records_completion_and_cleans_lock(self) -> None:
        command = load_command_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {command.RUN_DIR_ENV: temp_dir}, clear=False):
                paths = command.runtime_paths()
                command.ensure_run_dir(paths)
                paths.lock_path.write_text("1234\n", encoding="utf-8")
                paths.pid_path.write_text("1234\n", encoding="utf-8")
                paths.log_path.write_text('{"status": "ok"}\n', encoding="utf-8")

                command.monitor_backfill_process(
                    FakeProcess(pid=1234, exit_code=0),
                    paths,
                    ["python", "backfill.py"],
                    "2026-05-26T10:00:00Z",
                )

                status = json.loads(paths.status_path.read_text(encoding="utf-8"))
                self.assertFalse(paths.lock_path.exists())
                self.assertFalse(paths.pid_path.exists())

            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["exit_code"], 0)
            self.assertEqual(status["pid"], 1234)


class FakeProcess:
    def __init__(self, *, pid: int, exit_code: int = 0) -> None:
        self.pid = pid
        self.exit_code = exit_code

    def wait(self) -> int:
        return self.exit_code


def fail_launch(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("backfill process should not be launched")


def load_command_module() -> Any:
    module_name = f"phoenix_slack_viking_archive_command_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "command.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
