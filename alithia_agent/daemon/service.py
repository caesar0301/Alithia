"""Daemon Service: main daemon orchestration with signal handling.

Provides:
- Signal handling (SIGINT, SIGTERM for graceful shutdown)
- PID file management (exclusive lock to prevent multiple instances)
- Logging setup
- Scheduler lifecycle management
- Status reporting
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alithia_agent import ALITHIA_HOME
from alithia_agent.config.loader import load_config
from alithia_agent.config.schema import Config
from alithia_agent.daemon.scheduler import PaperScoutScheduler
from alithia_agent.logging_config import configure_logging
from alithia_agent.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


class DaemonService:
    """Main daemon service for background paper scanning."""

    def __init__(
        self,
        config: Config | None = None,
        config_path: Path | None = None,
    ):
        """Initialize daemon service.

        Args:
            config: Alithia Config object (loaded from config_path if None).
            config_path: Optional config file path.
        """
        config_path_str = str(config_path) if config_path else None
        self._config = config or load_config(config_path_str)
        self._daemon_config = self._config.daemon

        # Storage setup
        db_path = ALITHIA_HOME / "data" / "alithia.db"
        self._storage = SQLiteStorage(db_path)
        self._user_id = self._config.storage.user_id

        # Query from paperscout config
        self._query_categories = self._config.paperscout_agent.query

        # Big bang date
        self._big_bang = self._config.paperscout_agent.big_bang or self._daemon_config.big_bang

        # Scheduler
        self._scheduler: PaperScoutScheduler | None = None

        # Daemon state
        self._is_running = False
        self._shutdown_requested = False
        self._pid_file: Path | None = None

    @property
    def is_running(self) -> bool:
        """Check if daemon is active."""
        return self._is_running

    def _setup_logging(self) -> None:
        """Configure daemon logging."""
        log_file = ALITHIA_HOME / self._daemon_config.log_file
        configure_logging(
            level=logging.INFO,
            log_file=log_file,
            console=True,
            console_stream=sys.stdout,
        )
        logger.info(f"Daemon logging configured: {log_file}")

    def _acquire_pid_lock(self) -> bool:
        """Acquire PID file lock to ensure single instance.

        Returns:
            True if lock acquired, False if another instance running.
        """
        self._pid_file = ALITHIA_HOME / self._daemon_config.pid_file
        self._pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if PID file exists
        if self._pid_file.exists():
            try:
                existing_pid = int(self._pid_file.read_text().strip())
                # Check if process is still running
                if self._is_process_running(existing_pid):
                    logger.error(f"Another daemon instance running with PID {existing_pid}")
                    return False
                else:
                    logger.info(f"Removing stale PID file (process {existing_pid} not running)")
                    self._pid_file.unlink()
            except (ValueError, OSError) as e:
                logger.warning(f"Invalid PID file, removing: {e}")
                self._pid_file.unlink()

        # Write our PID
        try:
            self._pid_file.write_text(str(os.getpid()))
            logger.info(f"Acquired PID lock: {self._pid_file} (PID {os.getpid()})")
            return True
        except OSError as e:
            logger.error(f"Failed to write PID file: {e}")
            return False

    def _release_pid_lock(self) -> None:
        """Release PID file lock."""
        if self._pid_file and self._pid_file.exists():
            try:
                self._pid_file.unlink()
                logger.info(f"Released PID lock: {self._pid_file}")
            except OSError as e:
                logger.warning(f"Failed to remove PID file: {e}")

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running."""
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except OSError:
            return False

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def handle_shutdown(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info(f"Received {sig_name}, initiating graceful shutdown")
            self._shutdown_requested = True

            # Stop scheduler
            if self._scheduler:
                self._scheduler.stop()

        # Register handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        logger.info("Signal handlers configured (SIGINT, SIGTERM)")

    async def _create_dispatcher(self) -> Callable:
        """Create dispatcher callback for scheduler.

        Returns:
            Async callable that runs paperscout for given date.
        """
        from alithia_agent.paperscout.runner import run_paperscout_for_dates

        async def dispatch(params: dict[str, Any]) -> None:
            """Run paperscout for a date.

            Args:
                params: Dict with from_date, to_date, source.
            """
            from_date = params["from_date"]
            to_date = params["to_date"]
            source = params.get("source", "scheduler")

            logger.info(f"Dispatching paperscout: {from_date} to {to_date} (source={source})")

            try:
                self._storage.save_notification_record(
                    {
                        "user_id": self._user_id,
                        "query_categories": self._query_categories,
                        "notification_date": from_date,
                        "status": "pending",
                        "paper_count": 0,
                    }
                )

                result = await run_paperscout_for_dates(
                    self._config,
                    self._storage,
                    self._user_id,
                    from_date=from_date,
                    to_date=to_date,
                    source=source,
                )

                self._storage.save_notification_record(
                    {
                        "user_id": self._user_id,
                        "query_categories": self._query_categories,
                        "notification_date": from_date,
                        "status": result.status,
                        "paper_count": result.paper_count,
                        "error_message": "; ".join(result.errors) if result.errors else None,
                    }
                )

                logger.info(
                    f"Paperscout completed for {from_date}: "
                    f"{result.paper_count} papers (status={result.status})"
                )

            except Exception as e:
                logger.exception(f"Paperscout failed for {from_date}")

                self._storage.save_notification_record(
                    {
                        "user_id": self._user_id,
                        "query_categories": self._query_categories,
                        "notification_date": from_date,
                        "status": "failed",
                        "error_message": str(e),
                    }
                )

        return dispatch

    async def run(self) -> int:
        """Run the daemon service.

        Returns:
            Exit code (0 for clean shutdown, 1 for error).
        """
        # Setup
        self._setup_logging()

        # Check if scheduler enabled
        if not self._daemon_config.scheduler.enabled:
            logger.info("Scheduler disabled in config, daemon will not run")
            print("Scheduler disabled. Enable daemon.scheduler.enabled in config.")
            return 0

        # Acquire PID lock
        if not self._acquire_pid_lock():
            return 1

        self._is_running = True

        try:
            # Setup signal handlers
            self._setup_signal_handlers()

            # Create scheduler
            self._scheduler = PaperScoutScheduler(
                storage=self._storage,
                config=self._daemon_config.scheduler,
                user_id=self._user_id,
                query_categories=self._query_categories,
                big_bang=self._big_bang,
            )

            # Set dispatcher
            dispatcher = await self._create_dispatcher()
            self._scheduler.set_dispatcher(dispatcher)

            # Start scheduler
            await self._scheduler.start()

            logger.info("Daemon service started")
            print(f"Daemon started. PID: {os.getpid()}")
            print(f"Next run: {self._scheduler.next_run}")

            # Wait until shutdown
            while not self._shutdown_requested and self._scheduler.is_running:
                await asyncio.sleep(1)

            logger.info("Daemon service shutting down")

        except Exception:
            logger.exception("Daemon service error")
            return 1

        finally:
            # Cleanup
            if self._scheduler:
                self._scheduler.stop()
            self._release_pid_lock()
            self._storage.close()
            self._is_running = False

        logger.info("Daemon service stopped cleanly")
        return 0

    def get_status(self) -> dict[str, Any]:
        """Get daemon status for reporting.

        Returns:
            Dict with daemon and scheduler status.
        """
        status = {
            "pid": os.getpid() if self._is_running else None,
            "pid_file": str(self._pid_file) if self._pid_file else None,
            "running": self._is_running,
            "config": {
                "scheduler_enabled": self._daemon_config.scheduler.enabled,
                "schedule": (
                    f"{self._daemon_config.scheduler.hour:02d}:"
                    f"{self._daemon_config.scheduler.minute:02d} UTC"
                ),
                "retry_window_days": self._daemon_config.scheduler.retry_window_days,
                "big_bang": self._big_bang.isoformat() if self._big_bang else None,
            },
        }

        if self._scheduler:
            status["scheduler"] = self._scheduler.get_status()

        return status


def run_daemon(config_path: Path | None = None) -> int:
    """Run daemon service entry point.

    Args:
        config_path: Optional config file path.

    Returns:
        Exit code.
    """
    service = DaemonService(config_path=config_path)
    return asyncio.run(service.run())


def get_daemon_status(config_path: Path | None = None) -> dict[str, Any]:
    """Get daemon status without running.

    Loads config only — does not initialize storage or acquire locks.

    Args:
        config_path: Optional config file path.

    Returns:
        Status dict.
    """
    config_path_str = str(config_path) if config_path else None
    config = load_config(config_path_str)
    daemon_config = config.daemon
    big_bang = config.paperscout_agent.big_bang or daemon_config.big_bang

    return {
        "pid": None,
        "pid_file": str(ALITHIA_HOME / daemon_config.pid_file),
        "running": False,
        "config": {
            "scheduler_enabled": daemon_config.scheduler.enabled,
            "schedule": (
                f"{daemon_config.scheduler.hour:02d}:{daemon_config.scheduler.minute:02d} UTC"
            ),
            "retry_window_days": daemon_config.scheduler.retry_window_days,
            "big_bang": big_bang.isoformat() if big_bang else None,
        },
    }


__all__ = ["DaemonService", "run_daemon", "get_daemon_status"]
