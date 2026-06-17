"""Alithia-side defaults for soothe paths under ~/.alithia/soothe.

Soothe still hardcodes ~/.soothe for some subsystems (memory, skills, cache).
Until soothe honors SOOTHE_HOME everywhere, Alithia rewrites known defaults
after loading soothe config.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SOOTHE_MEMORY = (Path.home() / ".soothe" / "memory").resolve()


def memory_persist_dir(soothe_home: Path) -> str:
    """Filesystem path for MemU memory under Alithia's soothe home."""
    return str((soothe_home / "memory").expanduser())


def _resolve_persist_dir(persist_dir: str) -> Path:
    return Path(persist_dir).expanduser().resolve()


def apply_soothe_home_defaults(soothe_config: Any, soothe_home: Path) -> None:
    """Rewrite soothe config paths that would otherwise use ~/.soothe.

    Args:
        soothe_config: Loaded ``SootheConfig`` instance.
        soothe_home: Alithia's SOOTHE_HOME (typically ~/.alithia/soothe).
    """
    memory = soothe_config.agent.protocols.memory
    target = memory_persist_dir(soothe_home)

    if not memory.persist_dir:
        memory.persist_dir = target
        logger.debug("Set soothe memory persist_dir to %s", target)
        return

    try:
        resolved = _resolve_persist_dir(memory.persist_dir)
    except (OSError, ValueError):
        logger.warning(
            "Invalid soothe memory persist_dir %r; using %s",
            memory.persist_dir,
            target,
        )
        memory.persist_dir = target
        return

    if resolved == _DEFAULT_SOOTHE_MEMORY:
        if memory.persist_dir != target:
            logger.info(
                "Redirecting soothe memory from %s to %s",
                memory.persist_dir,
                target,
            )
        memory.persist_dir = target


__all__ = ["apply_soothe_home_defaults", "memory_persist_dir"]
