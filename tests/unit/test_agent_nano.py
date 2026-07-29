"""Unit tests for soothe-nano agent bootstrap (no soothed)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from soothe_nano.config import SootheConfig
from soothe_nano.config.models import SubagentConfig

from alithia_agent.agent import (
    apply_alithia_defaults,
    build_agent,
    default_nano_config_path,
    load_nano_config,
)
from alithia_agent.stream import format_stream_chunk


def test_default_nano_config_path_under_alithia_soothe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOOTHE_HOME", "/tmp/alithia-test/soothe")
    assert default_nano_config_path() == Path("/tmp/alithia-test/soothe/config/nano.yml")


def test_load_nano_config_zero_config_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yml"
    with pytest.raises(FileNotFoundError):
        load_nano_config(missing)


def test_apply_alithia_defaults_enables_plugins_and_deepxiv() -> None:
    cfg = apply_alithia_defaults(SootheConfig())
    assert cfg.subagents["paperscout"].enabled is True
    assert cfg.subagents["paperlens"].enabled is True
    assert cfg.tools.deepxiv.enabled is True
    assert cfg.persistence.default_backend == "sqlite"
    assert cfg.agent.protocols.durability.checkpointer == "sqlite"


def test_apply_alithia_defaults_reenables_disabled_subagents() -> None:
    base = SootheConfig(
        subagents={
            "paperscout": SubagentConfig(enabled=False),
            "paperlens": SubagentConfig(enabled=False),
        }
    )
    cfg = apply_alithia_defaults(base)
    assert cfg.subagents["paperscout"].enabled is True
    assert cfg.subagents["paperlens"].enabled is True


def test_build_agent_calls_create_nano_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_agent = MagicMock(name="nano")
    fake_agent.subagents = []
    create = MagicMock(return_value=fake_agent)
    monkeypatch.setattr("alithia_agent.agent.create_nano_agent", create)
    monkeypatch.setattr(
        "alithia_agent.plugin_registration.register_alithia_plugins",
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
