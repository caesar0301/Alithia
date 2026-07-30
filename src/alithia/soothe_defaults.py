"""Alithia-side defaults for nano paths under ``$SOOTHE_HOME``.

Nano still may hardcode ``~/.soothe`` for some subsystems (memory, skills, cache).
Until that honors ``SOOTHE_HOME`` everywhere, Alithia rewrites known defaults after
loading ``nano.yml`` / ``SootheConfig``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SOOTHE_MEMORY = (Path.home() / ".soothe" / "memory").resolve()


def memory_persist_dir(soothe_home: Path) -> str:
    """Filesystem path for memory under Alithia's SOOTHE_HOME."""
    return str((soothe_home / "memory").expanduser())


def _resolve_persist_dir(persist_dir: str) -> Path:
    return Path(persist_dir).expanduser().resolve()


def apply_soothe_home_defaults(soothe_config: Any, soothe_home: Path) -> None:
    """Rewrite nano config paths that would otherwise use ``~/.soothe``.

    Args:
        soothe_config: Loaded ``SootheConfig`` (from nano.yml).
        soothe_home: Alithia's SOOTHE_HOME (typically ``~/.alithia/soothe``).
    """
    memory = soothe_config.agent.protocols.memory
    target = memory_persist_dir(soothe_home)

    if not memory.persist_dir:
        memory.persist_dir = target
        logger.debug("Set nano memory persist_dir to %s", target)
        return

    try:
        resolved = _resolve_persist_dir(memory.persist_dir)
    except (OSError, ValueError):
        logger.warning(
            "Invalid nano memory persist_dir %r; using %s",
            memory.persist_dir,
            target,
        )
        memory.persist_dir = target
        return

    if resolved == _DEFAULT_SOOTHE_MEMORY:
        if memory.persist_dir != target:
            logger.info(
                "Redirecting nano memory from %s to %s",
                memory.persist_dir,
                target,
            )
        memory.persist_dir = target


__all__ = ["apply_soothe_home_defaults", "memory_persist_dir"]
