"""Unit tests for soothe-nano agent bootstrap (no soothed)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from soothe_nano.config import SootheConfig
from soothe_nano.config.models import SubagentConfig

from alithia.agent import (
    apply_alithia_defaults,
    build_agent,
    default_config_path,
    load_config,
)
from alithia.stream import format_stream_chunk


def test_default_config_path_under_alithia_soothe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOOTHE_HOME", "/tmp/alithia-test/soothe")
    assert default_config_path() == Path("/tmp/alithia-test/soothe/config/nano.yml")


def test_load_config_zero_config_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yml"
    with pytest.raises(FileNotFoundError):
        load_config(missing)


def test_load_config_reads_nano_yml(tmp_path: Path) -> None:
    path = tmp_path / "nano.yml"
    path.write_text(
        "providers:\n"
        "  - name: local\n"
        "    provider_type: openai\n"
        "    api_key: test\n"
        "    models: [m]\n"
        "router_profiles:\n"
        "  - name: default\n"
        "    router:\n"
        "      default: local:m\n"
        "active_router_profile: default\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.active_router_profile == "default"


def test_apply_alithia_defaults_enables_plugins_and_deepxiv() -> None:
    cfg = apply_alithia_defaults(SootheConfig())
    assert cfg.subagents["paperscout"].enabled is True
    assert cfg.subagents["paperlens"].enabled is True
    assert cfg.subagents["omr"].enabled is True
    assert cfg.tools.deepxiv.enabled is True
    assert cfg.persistence.default_backend == "sqlite"
    assert cfg.agent.protocols.durability.checkpointer == "sqlite"


def test_apply_alithia_defaults_reenables_disabled_subagents() -> None:
    base = SootheConfig(
        subagents={
            "paperscout": SubagentConfig(enabled=False),
            "paperlens": SubagentConfig(enabled=False),
            "omr": SubagentConfig(enabled=False),
        }
    )
    cfg = apply_alithia_defaults(base)
    assert cfg.subagents["paperscout"].enabled is True
    assert cfg.subagents["paperlens"].enabled is True
    assert cfg.subagents["omr"].enabled is True


def test_build_agent_calls_create_nano_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_agent = MagicMock(name="nano")
    fake_agent.subagents = []
    create = MagicMock(return_value=fake_agent)
    monkeypatch.setattr("alithia.agent.create_nano_agent", create)
    monkeypatch.setattr(
        "alithia.plugin_registration.register_alithia_plugins",
        lambda: None,
    )

    agent = build_agent(SootheConfig())
    assert agent is fake_agent
    create.assert_called_once()
    passed = create.call_args[0][0]
    assert passed.subagents["paperscout"].enabled is True
    assert passed.tools.deepxiv.enabled is True


def test_format_stream_chunk_ai_message() -> None:
    from langchain_core.messages import AIMessageChunk

    chunk = ((), "messages", (AIMessageChunk(content="hello"), {}))
    assert format_stream_chunk(chunk) == "hello"
    assert format_stream_chunk(((), "custom", {"type": "x"})) is None
