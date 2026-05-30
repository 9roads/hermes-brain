from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import types
import unittest
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = PLUGIN_ROOT.parents[1]


class PhoenixComposioSessionTests(unittest.TestCase):
    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name.startswith("phoenix_composio_session_test_"):
                sys.modules.pop(name, None)

        for name in (
            "COMPOSIO_TOOL_ROUTER_SESSION_ID",
            "COMPOSIO_MISSING_TOOL_URL_TEMPLATE",
            "HERMES_HOME",
            "HERMES_KANBAN_DB",
            "HERMES_KANBAN_TASK",
            "HERMES_PROFILE",
            "HERMES_PROFILE_NAME",
            "HERMES_SESSION_ID",
            "PHOENIX_HERMES_PROFILE_NAME",
        ):
            os.environ.pop(name, None)

    def test_extracts_slack_context_with_and_without_user_id(self) -> None:
        plugin = load_plugin_package()

        context = plugin.slack_context.extract_slack_context(slack_event())

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.slack_team_id, "T123")
        self.assertEqual(context.slack_user_id, "U123")
        self.assertEqual(context.slack_channel_id, "C123")
        self.assertEqual(context.slack_thread_id, "1700000000.000100")

        missing_user_context = plugin.slack_context.extract_slack_context(slack_event(user_id=None))

        self.assertIsNotNone(missing_user_context)
        assert missing_user_context is not None
        self.assertIsNone(missing_user_context.slack_user_id)
        self.assertEqual(missing_user_context.slack_channel_id, "C123")

    def test_backend_bootstrap_request_uses_auth_headers_and_expected_payload(self) -> None:
        plugin = load_plugin_package()
        opener = FakeOpener(
            {
                "composio_session_id": "trs_123",
                "missing_tool_url_template": "https://app.test/tools?toolkit={toolkit_slug}",
            }
        )

        response = plugin.client.create_tool_router_session(
            plugin.client.BootstrapSessionRequest(
                session_id="hermes-session-1",
                slack_team_id="T123",
                slack_user_id="U123",
                slack_channel_id="C123",
                slack_thread_id="1700000000.000100",
            ),
            environ={
                "PHOENIX_BACKEND_URL": "https://backend.test/",
                "PHOENIX_WORKSPACE_ID": "workspace one",
                "PHOENIX_HERMES_PLUGIN_TOKEN": "plugin-token",
                "COMPOSIO_API_KEY": "project-key",
            },
            opener=opener,
        )

        self.assertEqual(response.composio_session_id, "trs_123")
        self.assertEqual(len(opener.requests), 1)

        request = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://backend.test/api/v1/internal/hermes/workspaces/workspace%20one/composio/tool-router-session",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer plugin-token")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("User-agent"), "phoenix-hermes-composio-session/0.1.0")

        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "workspace_id": "workspace one",
                "session_id": "hermes-session-1",
                "slack_team_id": "T123",
                "slack_user_id": "U123",
                "slack_channel_id": "C123",
                "slack_thread_id": "1700000000.000100",
            },
        )

    def test_plugin_injects_session_context_once_before_llm_work(self) -> None:
        plugin = load_plugin_package()
        calls: list[Any] = []

        def fake_create_tool_router_session(request: Any) -> Any:
            calls.append(request)
            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_session",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = fake_create_tool_router_session
        with temporary_mapping(plugin) as mapping_path:
            ctx = FakePluginContext()
            plugin.register(ctx)

            ctx.hooks["pre_gateway_dispatch"](session_id="session-1", event=slack_event())
            injected = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
            repeated = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
            mapping = read_mapping_file(mapping_path)
            mapping_mode = mapping_path.stat().st_mode & 0o777

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].slack_user_id, "U123")
        self.assertEqual(calls[0].slack_channel_id, "C123")
        self.assertIsNone(repeated)
        self.assertEqual(os.environ["COMPOSIO_TOOL_ROUTER_SESSION_ID"], "trs_session")
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_session", injected["context"])
        self.assertIn("Use the composio-cli skill for non-Slack", injected["context"])
        self.assertIn("Composio Tool Router session:", injected["context"])
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID line", injected["context"])
        self.assertIn("must pass --session-id trs_session", injected["context"])
        self.assertIn("nori-slack-cli skill", injected["context"])
        self.assertIn("SLACK_BOT_TOKEN", injected["context"])
        self.assertNotIn("Composio Slackbot tools are allowed", injected["context"])
        self.assertEqual(
            mapping["sessions"]["session-1"]["composio_session_id"],
            "trs_session",
        )
        self.assertEqual(mapping_mode, 0o600)

    def test_existing_mapping_avoids_backend_bootstrap(self) -> None:
        plugin = load_plugin_package()

        def unexpected_create_tool_router_session(request: Any) -> Any:
            raise AssertionError(f"unexpected backend bootstrap for {request.session_id}")

        plugin.client.create_tool_router_session = unexpected_create_tool_router_session

        with temporary_mapping(plugin):
            plugin.session_mapping.store_session_response(
                "session-1",
                plugin.client.BootstrapSessionResponse(
                    composio_session_id="trs_cached",
                    missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
                ),
            )
            ctx = FakePluginContext()
            plugin.register(ctx)

            injected = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)

        self.assertEqual(os.environ["COMPOSIO_TOOL_ROUTER_SESSION_ID"], "trs_cached")
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_cached", injected["context"])

    def test_worker_reuses_parent_mapping_and_writes_alias(self) -> None:
        plugin = load_plugin_package()

        def unexpected_create_tool_router_session(request: Any) -> Any:
            raise AssertionError(f"unexpected backend bootstrap for {request.session_id}")

        plugin.client.create_tool_router_session = unexpected_create_tool_router_session

        with temporary_mapping(plugin) as mapping_path:
            with tempfile.TemporaryDirectory() as raw_tmp:
                kanban_db = Path(raw_tmp) / "kanban.db"
                write_kanban_task(kanban_db, session_id="origin-session")
                plugin.session_mapping.store_session_response(
                    "origin-session",
                    plugin.client.BootstrapSessionResponse(
                        composio_session_id="trs_parent",
                        missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
                    ),
                )
                ctx = FakePluginContext()
                plugin.register(ctx)

                with patched_environ(
                    HERMES_SESSION_ID="worker-session",
                    HERMES_KANBAN_DB=str(kanban_db),
                    HERMES_KANBAN_TASK="t_worker",
                ):
                    injected = ctx.hooks["pre_llm_call"](is_first_turn=True)

            mapping = read_mapping_file(mapping_path)

        self.assertEqual(os.environ["COMPOSIO_TOOL_ROUTER_SESSION_ID"], "trs_parent")
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_parent", injected["context"])
        self.assertEqual(
            mapping["sessions"]["worker-session"]["composio_session_id"],
            "trs_parent",
        )

    def test_missing_or_invalid_mapping_keeps_shared_only_session(self) -> None:
        plugin = load_plugin_package()
        calls: list[Any] = []

        def fake_create_tool_router_session(request: Any) -> Any:
            calls.append(request)
            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_shared",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = fake_create_tool_router_session

        with temporary_mapping(plugin) as mapping_path:
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text("{not valid json", encoding="utf-8")

            with tempfile.TemporaryDirectory() as raw_tmp:
                kanban_db = Path(raw_tmp) / "kanban.db"
                write_kanban_task(kanban_db, session_id="missing-origin-session")
                ctx = FakePluginContext()
                plugin.register(ctx)

                with patched_environ(
                    HERMES_SESSION_ID="worker-session",
                    HERMES_KANBAN_DB=str(kanban_db),
                    HERMES_KANBAN_TASK="t_worker",
                ):
                    ctx.hooks["pre_llm_call"](is_first_turn=True)

            mapping = read_mapping_file(mapping_path)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].session_id, "worker-session")
        self.assertIsNone(calls[0].slack_user_id)
        self.assertIsNone(calls[0].slack_channel_id)
        self.assertEqual(
            mapping["sessions"]["worker-session"]["composio_session_id"],
            "trs_shared",
        )

    def test_worker_without_mapping_falls_back_to_shared_session(self) -> None:
        plugin = load_plugin_package()
        calls: list[Any] = []

        def fake_create_tool_router_session(request: Any) -> Any:
            calls.append(request)
            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_shared",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = fake_create_tool_router_session

        with temporary_mapping(plugin):
            with tempfile.TemporaryDirectory() as raw_tmp:
                kanban_db = Path(raw_tmp) / "kanban.db"
                write_kanban_task(kanban_db, session_id=None)
                ctx = FakePluginContext()
                plugin.register(ctx)

                with patched_environ(
                    HERMES_SESSION_ID="worker-session",
                    HERMES_KANBAN_DB=str(kanban_db),
                    HERMES_KANBAN_TASK="t_worker",
                ):
                    ctx.hooks["pre_llm_call"](session_id="worker-session", is_first_turn=True)

        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0].slack_user_id)
        self.assertIsNone(calls[0].slack_channel_id)

    def test_missing_tool_url_slug_replacement_is_url_safe(self) -> None:
        plugin = load_plugin_package()

        url = plugin.prompt_context.missing_tool_url(
            "https://app.test/tools?toolkit={toolkit_slug}&connect=1",
            "Google Calendar",
        )

        self.assertEqual(url, "https://app.test/tools?toolkit=google_calendar&connect=1")

    def test_failed_bootstrap_is_retried_for_same_session(self) -> None:
        plugin = load_plugin_package()
        calls = 0

        def flaky_create_tool_router_session(request: Any) -> Any:
            nonlocal calls
            calls += 1

            if calls == 1:
                raise RuntimeError("temporary failure")

            return plugin.client.BootstrapSessionResponse(
                composio_session_id="trs_retry",
                missing_tool_url_template="https://app.test/tools?toolkit={toolkit_slug}",
            )

        plugin.client.create_tool_router_session = flaky_create_tool_router_session

        with temporary_mapping(plugin):
            ctx = FakePluginContext()
            plugin.register(ctx)

            failed = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
            retried = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)
            repeated = ctx.hooks["pre_llm_call"](session_id="session-1", is_first_turn=True)

        self.assertEqual(calls, 2)
        self.assertIn("could not be created", failed["context"])
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID: trs_retry", retried["context"])
        self.assertIsNone(repeated)

    def test_composio_cli_skill_examples_always_include_session_id(self) -> None:
        content = (HERMES_ROOT / "skills" / "composio-cli" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        command_blocks = re.findall(r"```bash\n(.*?)```", content, flags=re.S)

        self.assertIn("COMPOSIO_API_KEY", content)
        self.assertIn("Composio Tool Router session:", content)
        self.assertIn("COMPOSIO_TOOL_ROUTER_SESSION_ID:", content)
        self.assertIn("Slack API work must use the `nori-slack-cli` skill", content)
        self.assertNotIn("--toolkits slackbot", content)
        self.assertIn("Do not use Composio `slack` or `slackbot` toolkits", content)
        self.assertGreaterEqual(len(command_blocks), 3)

        for block in command_blocks:
            if any(command in block for command in ("composio search", "composio execute", "composio proxy")):
                self.assertIn("--session-id", block)

    def test_profile_removes_static_mcp_and_documents_runtime_requirements(self) -> None:
        config = (HERMES_ROOT / "config.yaml").read_text(encoding="utf-8")
        plugin_yaml = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        healthcheck = (HERMES_ROOT / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
        dockerfile = (HERMES_ROOT / "image_base" / "Dockerfile").read_text(encoding="utf-8")
        soul = (HERMES_ROOT / "SOUL.md").read_text(encoding="utf-8")
        readme = (HERMES_ROOT / "README.md").read_text(encoding="utf-8")
        env_example = (HERMES_ROOT / ".env.EXAMPLE").read_text(encoding="utf-8")
        mcp = json.loads((HERMES_ROOT / "mcp.json").read_text(encoding="utf-8"))

        self.assertIn("- phoenix-composio-session", config)
        self.assertIn("- PARALLEL_API_KEY", config)
        self.assertRegex(config, r"disabled_toolsets:\n\s+- web")
        self.assertRegex(config, r"disabled_toolsets:[\s\S]*\n\s+- browser")
        self.assertNotIn("cloud_provider: browserbase", config)
        self.assertNotIn("COMPOSIO_MCP_URL", config)
        self.assertNotIn("mcp_servers:\n  composio:", config)
        self.assertIn("- SLACK_BOT_TOKEN", config)
        self.assertIn("- SLACK_TOKEN", config)
        self.assertNotIn("- SLACK_APP_TOKEN", config)
        self.assertNotIn("- SLACK_SOCKET_API_BASE", config)
        self.assertNotIn("- SLACK_API_BASE", config)
        self.assertNotIn("composio", mcp.get("mcpServers", {}))
        self.assertIn("COMPOSIO_API_KEY", plugin_yaml)
        self.assertIn('shutil.which("composio")', healthcheck)
        self.assertIn('shutil.which("nori-slack")', healthcheck)
        self.assertIn('shutil.which("parallel-cli")', healthcheck)
        self.assertIn('shutil.which("agent-browser")', healthcheck)
        self.assertIn("COMPOSIO_API_KEY", healthcheck)
        self.assertIn("KERNEL_API_KEY", healthcheck)
        self.assertIn("PARALLEL_API_KEY", healthcheck)
        self.assertIn("AGENT_BROWSER_PROVIDER", healthcheck)
        self.assertIn("PHOENIX_BACKEND_URL", healthcheck)
        self.assertIn("PHOENIX_HERMES_PLUGIN_TOKEN", healthcheck)
        self.assertNotIn("BROWSERBASE_API_KEY", healthcheck)
        self.assertNotIn("BROWSERBASE_PROJECT_ID", healthcheck)
        self.assertIn("parallel-web-tools[cli]==${PARALLEL_WEB_TOOLS_VERSION}", dockerfile)
        self.assertIn("parallel-cli --version", dockerfile)
        self.assertIn("agent-browser", dockerfile)
        self.assertIn("AGENT_BROWSER_PROVIDER=kernel", dockerfile)
        self.assertIn("PARALLEL_API_KEY", readme)
        self.assertIn("KERNEL_API_KEY", readme)
        self.assertIn("parallel-cli", readme)
        self.assertIn("agent-browser", readme)
        self.assertIn("PARALLEL_API_KEY=", env_example)
        self.assertIn("KERNEL_API_KEY=", env_example)
        self.assertNotIn("BROWSERBASE_API_KEY=", env_example)
        self.assertNotIn("BROWSERBASE_PROJECT_ID=", env_example)
        self.assertIn("nori-slack-cli", soul)
        self.assertIn("SLACK_BOT_TOKEN", soul)
        self.assertIn("## External tools", soul)
        self.assertIn("Parallel CLI skills", soul)
        self.assertNotIn("Composio Slackbot tools are allowed", soul)

    def test_parallel_profile_skills_are_limited_and_skip_onboarding(self) -> None:
        skills_dir = HERMES_ROOT / "skills"
        expected = {
            "parallel-web-search",
            "parallel-web-extract",
            "parallel-deep-research",
            "parallel-findall",
            "parallel-monitor",
            "parallel-data-enrichment",
        }
        actual = {path.name for path in skills_dir.glob("parallel-*") if path.is_dir()}

        self.assertEqual(expected, actual)

        forbidden = (
            "parallel-cli-setup",
            "## Setup",
            "## Prerequisites",
            "Prerequisites",
            "pipx",
            "install and authenticate",
            "balance add",
            "If `parallel-cli` is not found",
        )

        for skill in expected:
            content = (skills_dir / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("parallel-cli", content)
            self.assertIn("PARALLEL_API_KEY", content)
            for phrase in forbidden:
                self.assertNotIn(phrase, content, f"{skill} contains onboarding text: {phrase}")


class FakePluginContext:
    def __init__(self) -> None:
        self.hooks: dict[str, Any] = {}

    def register_hook(self, name: str, handler: Any) -> None:
        self.hooks[name] = handler


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.requests: list[Any] = []

    def __call__(self, request: Any, *, timeout: int) -> FakeResponse:
        self.requests.append(request)
        self.timeout = timeout
        return FakeResponse(self.payload)


def slack_event(user_id: str | None = "U123") -> types.SimpleNamespace:
    source = types.SimpleNamespace(
        platform=types.SimpleNamespace(value="slack"),
        team_id="T123",
        chat_id="C123",
        user_id=user_id,
        user_name="Predrag",
        thread_id="1700000000.000100",
    )
    return types.SimpleNamespace(
        source=source,
        raw_message={
            "team": "T123",
            "channel": "C123",
            "user": user_id,
            "thread_ts": "1700000000.000100",
            "ts": "1700000001.000200",
        },
    )


def load_plugin_package():
    module_name = f"phoenix_composio_session_test_{uuid.uuid4().hex}"
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


@contextmanager
def patched_environ(**updates: str | None):
    previous = {name: os.environ.get(name) for name in updates}

    for name, value in updates.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def temporary_mapping(plugin: Any):
    with tempfile.TemporaryDirectory() as raw_tmp:
        previous = plugin.session_mapping.MAPPING_PATH
        mapping_path = Path(raw_tmp) / "composio" / "mapping.json"
        plugin.session_mapping.MAPPING_PATH = mapping_path

        try:
            yield mapping_path
        finally:
            plugin.session_mapping.MAPPING_PATH = previous


def read_mapping_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_kanban_task(
    path: Path,
    *,
    session_id: str | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO tasks (id, session_id) VALUES (?, ?)",
                ("t_worker", session_id),
            )


if __name__ == "__main__":
    unittest.main()
