"""Shared logging configuration for CLI and daemon."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

FILE_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
FILE_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
CONSOLE_LOG_FORMAT = "[%(levelname)s] %(message)s"
DEFAULT_LOG_FILE = "logs/alithia.log"
DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5


def configure_logging(
    *,
    level: int = logging.INFO,
    log_file: Path | None = None,
    log_max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    log_backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
    console: bool = True,
    console_stream: object | None = None,
    reset_handlers: bool = True,
) -> Path | None:
    """Configure root logger with consistent file and console formats.

    File logs include timestamp, level, and logger name.
    Console logs stay compact for interactive use.

    Args:
        level: Root log level.
        log_file: Optional path for file output.
        log_max_bytes: Max size per log file before rotation.
        log_backup_count: Number of rotated log files to retain.
        console: Whether to attach a console handler.
        console_stream: Stream for console output (defaults to stderr).
        reset_handlers: Clear existing root handlers before configuring.

    Returns:
        Resolved log file path when file logging is enabled.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if reset_handlers:
        root_logger.handlers.clear()

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT, datefmt=FILE_LOG_DATEFMT))
        root_logger.addHandler(file_handler)

    if console:
        stream = console_stream if console_stream is not None else sys.stderr
        console_handler = logging.StreamHandler(stream)  # type: ignore[arg-type]
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT))
        root_logger.addHandler(console_handler)

    return log_file


__all__ = [
    "CONSOLE_LOG_FORMAT",
    "DEFAULT_LOG_BACKUP_COUNT",
    "DEFAULT_LOG_FILE",
    "DEFAULT_LOG_MAX_BYTES",
    "FILE_LOG_DATEFMT",
    "FILE_LOG_FORMAT",
    "configure_logging",
]
