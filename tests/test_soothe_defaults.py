"""Tests for Alithia soothe path defaults."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from alithia_agent.soothe_defaults import apply_soothe_home_defaults, memory_persist_dir


def _config_with_persist_dir(persist_dir: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        agent=SimpleNamespace(
            protocols=SimpleNamespace(
                memory=SimpleNamespace(persist_dir=persist_dir),
            ),
        ),
    )


def test_memory_persist_dir_under_alithia_soothe_home() -> None:
    soothe_home = Path("/tmp/alithia/soothe")
    assert memory_persist_dir(soothe_home) == "/tmp/alithia/soothe/memory"


def test_apply_sets_persist_dir_when_unset() -> None:
    soothe_home = Path("/tmp/alithia/soothe")
    config = _config_with_persist_dir(None)

    apply_soothe_home_defaults(config, soothe_home)

    assert config.agent.protocols.memory.persist_dir == "/tmp/alithia/soothe/memory"


def test_apply_redirects_default_soothe_memory_path() -> None:
    soothe_home = Path("/tmp/alithia/soothe")
    config = _config_with_persist_dir("~/.soothe/memory")

    apply_soothe_home_defaults(config, soothe_home)

    assert config.agent.protocols.memory.persist_dir == "/tmp/alithia/soothe/memory"


def test_apply_preserves_custom_persist_dir() -> None:
    soothe_home = Path("/tmp/alithia/soothe")
    custom = "/var/custom/memory"
    config = _config_with_persist_dir(custom)

    apply_soothe_home_defaults(config, soothe_home)

    assert config.agent.protocols.memory.persist_dir == custom
