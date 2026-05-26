from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

COMMAND_PREFIX = "slack-archive"
DEFAULT_RUN_DIR = "/opt/data/phoenix/slack-viking-archive"
RUN_DIR_ENV = "PHOENIX_SLACK_VIKING_ARCHIVE_RUN_DIR"
LOG_FILE_ENV = "PHOENIX_SLACK_VIKING_ARCHIVE_LOG_FILE"
STATUS_FILE_ENV = "PHOENIX_SLACK_VIKING_ARCHIVE_STATUS_FILE"
DEFAULT_DAYS = 60
DEFAULT_HISTORY_LIMIT = 200
DEFAULT_REPLY_LIMIT = 200
MAX_DAYS = 365
MAX_LOG_STATUS_LINES = 3

_MONITOR_THREADS: list[threading.Thread] = []


@dataclass(frozen=True)
class RuntimePaths:
    run_dir: Path
    log_path: Path
    status_path: Path
    lock_path: Path
    pid_path: Path


class CommandUsageError(ValueError):
    pass


class CommandArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CommandUsageError(message)


def handle_command(raw_args: str) -> str | None:
    try:
        tokens = split_args(str(raw_args or ""))
    except CommandUsageError as exc:
        return f"Could not parse Slack archive command: {exc}\n\n{usage()}"
    if not tokens:
        return None

    if tokens[0].lower() != COMMAND_PREFIX:
        return None

    if len(tokens) == 1 or tokens[1] in {"help", "--help", "-h"}:
        return usage()

    subcommand = tokens[1].lower()
    paths = runtime_paths()

    if subcommand == "backfill":
        return start_backfill(tokens[2:], paths=paths)

    if subcommand == "status":
        return render_status(paths)

    return f"Unknown slack-archive command: {tokens[1]}\n\n{usage()}"


def split_args(raw_args: str) -> list[str]:
    try:
        return shlex.split(raw_args)
    except ValueError as exc:
        raise CommandUsageError(str(exc)) from exc


def usage() -> str:
    return (
        "Slack archive commands:\n"
        "/phoenix slack-archive backfill --days 60\n"
        "/phoenix slack-archive status"
    )


def runtime_paths(env: dict[str, str] | os._Environ[str] = os.environ) -> RuntimePaths:
    run_dir = Path(env.get(RUN_DIR_ENV) or DEFAULT_RUN_DIR)
    log_path = Path(env.get(LOG_FILE_ENV) or run_dir / "backfill.log")
    status_path = Path(env.get(STATUS_FILE_ENV) or run_dir / "backfill-status.json")
    return RuntimePaths(
        run_dir=run_dir,
        log_path=log_path,
        status_path=status_path,
        lock_path=run_dir / "backfill.lock",
        pid_path=run_dir / "backfill.pid",
    )


def start_backfill(args: list[str], *, paths: RuntimePaths) -> str:
    try:
        parsed = parse_backfill_args(args)
    except CommandUsageError as exc:
        return f"Could not start Slack archive backfill: {exc}\n\n{usage()}"

    ensure_run_dir(paths)
    refreshed = refresh_status(paths)
    if refreshed.get("status") == "running":
        return running_message(refreshed, paths)

    lock_fd = acquire_lock(paths)
    if lock_fd is None:
        refreshed = refresh_status(paths)
        return running_message(refreshed, paths)

    started_at = utc_now()
    argv = build_backfill_argv(parsed)

    try:
        append_log_header(paths, argv, started_at)
        process = launch_backfill_process(argv, env=build_process_env(), log_path=paths.log_path)
        write_lock(lock_fd, process.pid)
        paths.pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
        write_status(
            paths,
            {
                "status": "running",
                "pid": process.pid,
                "started_at": started_at,
                "argv": safe_argv(argv),
                "log_path": str(paths.log_path),
            },
        )
        start_monitor_thread(process, paths, safe_argv(argv), started_at)
    except Exception:
        close_fd(lock_fd)
        cleanup_runtime_files(paths, pid=None)
        raise

    return (
        f"Started Slack archive backfill pid={process.pid} "
        f"days={parsed.days}. Log: {paths.log_path}"
    )


def parse_backfill_args(args: list[str]) -> argparse.Namespace:
    parser = CommandArgumentParser(prog="slack-archive backfill", add_help=False)
    parser.add_argument("--days", type=days_value, default=DEFAULT_DAYS)
    parser.add_argument("--history-limit", type=page_limit, default=DEFAULT_HISTORY_LIMIT)
    parser.add_argument("--reply-limit", type=page_limit, default=DEFAULT_REPLY_LIMIT)
    parser.add_argument("--channel", action="append", default=[])
    parser.add_argument("--latest-ts")
    parser.add_argument("--oldest-ts")
    parser.add_argument("--token-env")
    parser.add_argument("--exclude-archived", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parsed, unknown = parser.parse_known_args(args)
    if unknown:
        raise CommandUsageError(f"unsupported arguments: {' '.join(unknown)}")
    return parsed


def build_backfill_argv(args: argparse.Namespace) -> list[str]:
    script = Path(__file__).resolve().with_name("backfill.py")
    argv = [
        sys.executable,
        str(script),
        "--days",
        str(args.days),
        "--history-limit",
        str(args.history_limit),
        "--reply-limit",
        str(args.reply_limit),
        "--log-level",
        args.log_level,
    ]

    for channel_id in args.channel:
        argv.extend(["--channel", channel_id])

    for option_name, flag in [
        ("latest_ts", "--latest-ts"),
        ("oldest_ts", "--oldest-ts"),
        ("token_env", "--token-env"),
    ]:
        value = getattr(args, option_name)
        if value:
            argv.extend([flag, value])

    if args.exclude_archived:
        argv.append("--exclude-archived")

    return argv


def build_process_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def launch_backfill_process(
    argv: list[str],
    *,
    env: dict[str, str],
    log_path: Path,
) -> subprocess.Popen[Any]:
    with log_path.open("a", encoding="utf-8") as log_file:
        return subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            start_new_session=True,
        )


def start_monitor_thread(
    process: subprocess.Popen[Any],
    paths: RuntimePaths,
    argv: list[str],
    started_at: str,
) -> None:
    thread = threading.Thread(
        target=monitor_backfill_process,
        args=(process, paths, argv, started_at),
        name=f"slack-viking-backfill-monitor-{process.pid}",
        daemon=True,
    )
    _MONITOR_THREADS.append(thread)
    thread.start()


def monitor_backfill_process(
    process: subprocess.Popen[Any],
    paths: RuntimePaths,
    argv: list[str],
    started_at: str,
) -> None:
    exit_code = process.wait()
    finished_at = utc_now()
    status = "completed" if exit_code == 0 else "failed"
    write_status(
        paths,
        {
            "status": status,
            "pid": process.pid,
            "exit_code": exit_code,
            "started_at": started_at,
            "finished_at": finished_at,
            "argv": argv,
            "log_path": str(paths.log_path),
            "last_log_lines": tail_log_lines(paths.log_path),
        },
    )
    cleanup_runtime_files(paths, pid=process.pid)


def render_status(paths: RuntimePaths) -> str:
    ensure_run_dir(paths)
    status = refresh_status(paths)
    if not status:
        return f"Slack archive backfill has not been started. Log: {paths.log_path}"

    state = str(status.get("status") or "unknown")
    pid = status.get("pid")
    started_at = status.get("started_at") or "unknown"
    finished_at = status.get("finished_at")
    exit_code = status.get("exit_code")
    log_path = status.get("log_path") or str(paths.log_path)

    if state == "running":
        return f"Slack archive backfill is running pid={pid} started_at={started_at}. Log: {log_path}"

    pieces = [f"Slack archive backfill {state}"]
    if pid:
        pieces.append(f"pid={pid}")
    if exit_code is not None:
        pieces.append(f"exit_code={exit_code}")
    pieces.append(f"started_at={started_at}")
    if finished_at:
        pieces.append(f"finished_at={finished_at}")
    pieces.append(f"Log: {log_path}")

    last_lines = status.get("last_log_lines") or tail_log_lines(paths.log_path)
    if last_lines:
        pieces.append("Last log: " + " | ".join(redact_secrets(line) for line in last_lines))

    return " ".join(str(piece) for piece in pieces)


def refresh_status(paths: RuntimePaths) -> dict[str, Any]:
    status = read_status(paths)
    if status.get("status") != "running":
        return status

    pid = int_value(status.get("pid"))
    if pid and is_process_alive(pid):
        return status

    stale_status = {
        **status,
        "status": "unknown_finished",
        "finished_at": utc_now(),
        "last_log_lines": tail_log_lines(paths.log_path),
    }
    write_status(paths, stale_status)
    cleanup_runtime_files(paths, pid=pid or None)
    return stale_status


def acquire_lock(paths: RuntimePaths) -> int | None:
    try:
        return os.open(paths.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pid = int_value(read_text(paths.lock_path).strip())
        if pid and is_process_alive(pid):
            return None
        try:
            paths.lock_path.unlink()
        except FileNotFoundError:
            pass
        return os.open(paths.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)


def write_lock(lock_fd: int, pid: int) -> None:
    os.write(lock_fd, f"{pid}\n".encode("utf-8"))
    close_fd(lock_fd)


def close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def cleanup_runtime_files(paths: RuntimePaths, *, pid: int | None) -> None:
    for path in (paths.lock_path, paths.pid_path):
        if pid is not None and path.exists():
            current_pid = int_value(read_text(path).strip())
            if current_pid and current_pid != pid:
                continue
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def ensure_run_dir(paths: RuntimePaths) -> None:
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.log_path.parent.mkdir(parents=True, exist_ok=True)
    paths.status_path.parent.mkdir(parents=True, exist_ok=True)


def append_log_header(paths: RuntimePaths, argv: list[str], started_at: str) -> None:
    paths.log_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n[{started_at}] starting Slack OpenViking backfill\n")
        log_file.write("command: " + " ".join(shlex.quote(part) for part in safe_argv(argv)) + "\n")


def write_status(paths: RuntimePaths, payload: dict[str, Any]) -> None:
    ensure_run_dir(paths)
    temp_path = paths.status_path.with_suffix(paths.status_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(paths.status_path)


def read_status(paths: RuntimePaths) -> dict[str, Any]:
    try:
        raw = paths.status_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def running_message(status: dict[str, Any], paths: RuntimePaths) -> str:
    pid = status.get("pid") or int_value(read_text(paths.pid_path).strip())
    started_at = status.get("started_at") or "unknown"
    return f"Slack archive backfill is already running pid={pid} started_at={started_at}. Log: {paths.log_path}"


def tail_log_lines(path: Path, *, limit: int = MAX_LOG_STATUS_LINES) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []

    return [line for line in lines if line.strip()][-limit:]


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def safe_argv(argv: list[str]) -> list[str]:
    safe: list[str] = []
    redact_next = False
    for part in argv:
        if redact_next:
            safe.append("[redacted]")
            redact_next = False
            continue
        if part in {"--token", "--api-key"}:
            safe.append(part)
            redact_next = True
            continue
        safe.append(redact_secrets(part))
    return safe


def redact_secrets(value: str) -> str:
    text = str(value)
    for prefix in ("xoxb-", "xoxa-", "xoxp-", "xapp-", "sk-"):
        index = text.lower().find(prefix)
        if index >= 0:
            return text[:index] + prefix + "[redacted]"
    return text


def days_value(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > MAX_DAYS:
        raise argparse.ArgumentTypeError(f"days must be between 1 and {MAX_DAYS}")
    return parsed


def page_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > 999:
        raise argparse.ArgumentTypeError("limit must be between 1 and 999")
    return parsed


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
