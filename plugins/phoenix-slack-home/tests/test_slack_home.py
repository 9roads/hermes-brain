from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class SlackHomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_env = {
            key: os.environ.get(key)
            for key in ["SLACK_HOME_CHANNEL", "SLACK_BOT_TOKEN"]
        }
        for key in self.saved_env:
            os.environ.pop(key, None)

        self.slack_home = load_plugin_module()

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        for name in [
            self.slack_home.__name__,
            "gateway",
            "gateway.config",
            "hermes_cli",
            "hermes_cli.config",
        ]:
            sys.modules.pop(name, None)

    def test_scores_explicit_phoenix_channel_above_general(self) -> None:
        phoenix = self.slack_home.SlackChannelCandidate(
            channel_id="C_PHOENIX",
            name="phoenix-updates",
            is_member=True,
            num_members=10,
        )
        general = self.slack_home.SlackChannelCandidate(
            channel_id="C_GENERAL",
            name="general",
            is_member=True,
            is_general=True,
            num_members=100,
        )

        selected = sorted([general, phoenix], key=self.slack_home.score_candidate, reverse=True)[0]

        self.assertEqual(selected.channel_id, "C_PHOENIX")

    def test_apply_home_channel_sets_process_env(self) -> None:
        writes = install_hermes_config_stub()

        result = self.slack_home.apply_home_channel("C123", name="phoenix", gateway=None)

        self.assertTrue(result["ok"])
        self.assertTrue(result["persisted"])
        self.assertEqual(os.environ["SLACK_HOME_CHANNEL"], "C123")
        self.assertEqual(writes["SLACK_HOME_CHANNEL"], "C123")

    def test_sync_gateway_home_channel_updates_runtime_config(self) -> None:
        install_gateway_config_stub()
        gateway = types.SimpleNamespace(config=types.SimpleNamespace(platforms={}))

        synced = self.slack_home.sync_gateway_home_channel(
            gateway,
            "C123",
            "phoenix",
            None,
        )

        self.assertTrue(synced)
        platform = sys.modules["gateway.config"].Platform.SLACK
        self.assertEqual(gateway.config.platforms[platform].home_channel.chat_id, "C123")
        self.assertEqual(gateway.config.platforms[platform].home_channel.name, "phoenix")

    def test_pre_gateway_dispatch_falls_back_to_current_slack_source(self) -> None:
        install_hermes_config_stub()
        install_gateway_config_stub()
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"
        self.slack_home.discover_slack_channels = fail_discovery

        ctx = FakePluginContext()
        self.slack_home.register(ctx)
        gateway = types.SimpleNamespace(config=types.SimpleNamespace(platforms={}))
        event = types.SimpleNamespace(source=slack_source("C_CURRENT", "current-channel"))

        with self.assertLogs(self.slack_home.LOGGER, level="WARNING"):
            ctx.hooks["pre_gateway_dispatch"](event=event, gateway=gateway)

        platform = sys.modules["gateway.config"].Platform.SLACK
        self.assertEqual(os.environ["SLACK_HOME_CHANNEL"], "C_CURRENT")
        self.assertEqual(gateway.config.platforms[platform].home_channel.chat_id, "C_CURRENT")


class FakePluginContext:
    def __init__(self) -> None:
        self.llm = None
        self.hooks: dict[str, object] = {}
        self.tools: dict[str, object] = {}

    def register_hook(self, name: str, handler: object) -> None:
        self.hooks[name] = handler

    def register_tool(self, name: str, **kwargs: object) -> None:
        self.tools[name] = kwargs


def load_plugin_module():
    module_name = f"phoenix_slack_home_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fail_discovery(_token: str):
    raise RuntimeError("network unavailable")


def slack_source(channel_id: str, channel_name: str):
    platform = types.SimpleNamespace(value="slack")
    return types.SimpleNamespace(
        platform=platform,
        chat_id=channel_id,
        chat_name=channel_name,
        thread_id=None,
    )


def install_gateway_config_stub() -> None:
    gateway_module = types.ModuleType("gateway")
    config_module = types.ModuleType("gateway.config")

    class Platform(Enum):
        SLACK = "slack"

    @dataclass
    class HomeChannel:
        platform: Platform
        chat_id: str
        name: str
        thread_id: str | None = None

    @dataclass
    class PlatformConfig:
        enabled: bool = False
        home_channel: HomeChannel | None = None

    config_module.Platform = Platform
    config_module.HomeChannel = HomeChannel
    config_module.PlatformConfig = PlatformConfig
    sys.modules["gateway"] = gateway_module
    sys.modules["gateway.config"] = config_module


def install_hermes_config_stub() -> dict[str, str]:
    hermes_module = types.ModuleType("hermes_cli")
    config_module = types.ModuleType("hermes_cli.config")
    writes: dict[str, str] = {}

    config_module.is_managed = lambda: False
    config_module.save_env_value = lambda key, value: writes.__setitem__(key, value)
    sys.modules["hermes_cli"] = hermes_module
    sys.modules["hermes_cli.config"] = config_module
    return writes


if __name__ == "__main__":
    unittest.main()
