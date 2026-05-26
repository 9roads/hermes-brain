from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path
from typing import Any


PLUGIN_NAME = "phoenix-llmwiki"
CHANNEL_ID = "CARCHIVESMOKE"


class SmokeFailure(RuntimeError):
    pass


class HookContext:
    def __init__(self) -> None:
        self.hooks: dict[str, Any] = {}

    def register_hook(self, name: str, handler: Any) -> None:
        self.hooks[name] = handler


def main() -> int:
    os.environ.setdefault("PHOENIX_LLMWIKI_ARCHIVE_WORKERS", "1")

    hermes_home = Path(os.environ.get("HERMES_HOME", "/opt/data/profiles/phoenix")).resolve()
    assert_profile_enables_plugin(hermes_home)

    plugin = load_plugin(hermes_home)
    ctx = HookContext()
    plugin.register(ctx)
    hook = ctx.hooks.get("pre_gateway_dispatch")
    if hook is None:
        raise SmokeFailure("plugin did not register pre_gateway_dispatch")

    root_ts = slack_ts(time.time())
    reply_ts = slack_ts(time.time() + 0.001)
    root = event(root_ts, "Hermes llmwiki archive smoke root")
    reply = event(reply_ts, "Hermes llmwiki archive smoke reply", thread_ts=root_ts)

    snapshot = plugin.snapshot_from_event(root)
    if snapshot is None:
        raise SmokeFailure("plugin did not recognize synthetic Slack channel event")

    hook(event=root)
    hook(event=reply)
    plugin.ARCHIVE.executor.shutdown(wait=True, cancel_futures=False)

    source_path = Path(snapshot.source_path)
    content = wait_for_content(source_path, "Hermes llmwiki archive smoke reply")

    if "Slack Thread archive-smoke" not in content:
        raise SmokeFailure(f"source file missing thread header: {source_path}")
    if "Hermes llmwiki archive smoke root" not in content:
        raise SmokeFailure(f"source file missing root message: {source_path}")
    if "Hermes llmwiki archive smoke reply" not in content:
        raise SmokeFailure(f"source file missing reply message: {source_path}")

    print(
        json.dumps(
            {
                "status": "ok",
                "plugin": PLUGIN_NAME,
                "hook": "pre_gateway_dispatch",
                "source_path": str(source_path),
            },
            sort_keys=True,
        )
    )
    return 0


def assert_profile_enables_plugin(hermes_home: Path) -> None:
    config_path = hermes_home / "config.yaml"
    plugin_yaml = hermes_home / "plugins" / PLUGIN_NAME / "plugin.yaml"
    plugin_init = hermes_home / "plugins" / PLUGIN_NAME / "__init__.py"

    for path in (config_path, plugin_yaml, plugin_init):
        if not path.exists():
            raise SmokeFailure(f"missing installed profile file: {path}")

    config_text = config_path.read_text(encoding="utf-8")
    if f"- {PLUGIN_NAME}" not in config_text:
        raise SmokeFailure(f"{PLUGIN_NAME} is not enabled in installed config.yaml")

    plugin_yaml_text = plugin_yaml.read_text(encoding="utf-8")
    if f"name: {PLUGIN_NAME}" not in plugin_yaml_text:
        raise SmokeFailure("installed plugin.yaml has unexpected plugin name")
    if "pre_gateway_dispatch" not in plugin_yaml_text:
        raise SmokeFailure("installed plugin.yaml does not declare pre_gateway_dispatch")


def load_plugin(hermes_home: Path) -> Any:
    plugin_path = hermes_home / "plugins" / PLUGIN_NAME / "__init__.py"
    spec = importlib.util.spec_from_file_location("phoenix_llmwiki_smoke_plugin", plugin_path)
    if spec is None or spec.loader is None:
        raise SmokeFailure(f"could not load plugin spec from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def event(ts: str, text: str, *, thread_ts: str | None = None) -> types.SimpleNamespace:
    raw: dict[str, Any] = {
        "type": "message",
        "team": "TARCHIVESMOKE",
        "channel": CHANNEL_ID,
        "channel_type": "channel",
        "ts": ts,
        "text": text,
        "user": "UARCHIVESMOKE",
        "user_name": "Archive Smoke",
    }
    if thread_ts:
        raw["thread_ts"] = thread_ts

    return types.SimpleNamespace(
        raw_message=raw,
        text=text,
        message_id=ts,
        source=types.SimpleNamespace(
            platform=types.SimpleNamespace(value="slack"),
            chat_id=CHANNEL_ID,
            chat_type="channel",
            chat_name="archive-smoke",
            user_id="UARCHIVESMOKE",
            user_name="Archive Smoke",
            slack_team_id="TARCHIVESMOKE",
        ),
    )


def slack_ts(seconds: float) -> str:
    whole = int(seconds)
    micros = int(round((seconds - whole) * 1_000_000))
    return f"{whole}.{micros:06d}"


def wait_for_content(path: Path, expected: str) -> str:
    deadline = time.monotonic() + float(os.environ.get("LLMWIKI_ARCHIVE_SMOKE_TIMEOUT", "30"))
    last_error = ""
    while time.monotonic() < deadline:
        try:
            content = path.read_text(encoding="utf-8")
            if expected in content:
                return content
            last_error = f"expected text not found in {path}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise SmokeFailure(last_error or f"timed out reading {path}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
