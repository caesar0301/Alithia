"""Tests for shared logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from alithia_agent.logging_config import configure_logging


def _close_root_handlers() -> None:
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.close()
    root_logger.handlers.clear()


def test_log_rotation_creates_backup_files(tmp_path: Path) -> None:
    log_file = tmp_path / "alithia.log"
    configure_logging(
        log_file=log_file,
        log_max_bytes=200,
        log_backup_count=2,
        console=False,
    )

    try:
        logger = logging.getLogger("test.rotation")
        for _ in range(30):
            logger.info("x" * 80)
    finally:
        _close_root_handlers()

    rotated = list(tmp_path.glob("alithia.log*"))
    assert log_file in rotated
    assert any(path.name.endswith(".1") for path in rotated)


def test_daemon_config_defaults_use_rotation_constants() -> None:
    from alithia_agent.config.schema import DaemonConfig
    from alithia_agent.logging_config import DEFAULT_LOG_BACKUP_COUNT, DEFAULT_LOG_MAX_BYTES

    daemon = DaemonConfig()
    assert daemon.log_max_bytes == DEFAULT_LOG_MAX_BYTES
    assert daemon.log_backup_count == DEFAULT_LOG_BACKUP_COUNT
