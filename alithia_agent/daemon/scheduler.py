"""Background scheduler: runs PaperScout on a daily schedule with gap retry.

Configurable async loop that:
- Runs daily at configured hour/minute UTC
- Scans for papers from yesterday
- Retries gaps within retry_window_days
- Respects big_bang date constraint
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from alithia_agent.config.schema import DaemonSchedulerConfig
from alithia_agent.daemon.gap_scanner import GapScanner
from alithia_agent.storage.sqlite import SQLiteStorage

logger = logging.getLogger(__name__)

# Default values
DEFAULT_HOUR = 23
DEFAULT_MINUTE = 0
DEFAULT_RETRY_WINDOW_DAYS = 3


class PaperScoutScheduler:
    """Configurable background scheduler for daily paper discovery with gap retry."""

    def __init__(
        self,
        storage: SQLiteStorage,
        config: DaemonSchedulerConfig,
        user_id: str,
        query_categories: str,
        big_bang: date | None = None,
    ):
        """Initialize scheduler.

        Args:
            storage: SQLiteStorage for persistence.
            config: DaemonSchedulerConfig with schedule settings.
            user_id: User identifier.
            query_categories: ArXiv query string.
            big_bang: Optional tracking start date.
        """
        self._storage = storage
        self._config = config
        self._user_id = user_id
        self._query_categories = query_categories
        self._big_bang = big_bang

        self._task: asyncio.Task | None = None
        self._dispatcher: Callable[[dict[str, Any]], Any] | None = None
        self._gap_scanner = GapScanner(
            storage=storage,
            user_id=user_id,
            query_categories=query_categories,
            big_bang=big_bang,
        )

        self._is_running = False
        self._last_run: datetime | None = None
        self._run_count = 0

    @property
    def enabled(self) -> bool:
        """Check if scheduler is enabled in config."""
        return self._config.enabled

    @property
    def next_run(self) -> str | None:
        """Human-readable next scheduled run time (UTC)."""
        if not self._config.enabled:
            return None

        now = datetime.now(UTC)
        target = now.replace(
            hour=self._config.hour, minute=self._config.minute, second=0, microsecond=0
        )
        if target <= now:
            target += timedelta(days=1)

        return target.isoformat()

    @property
    def is_running(self) -> bool:
        """Check if scheduler loop is active."""
        return self._is_running

    @property
    def last_run(self) -> str | None:
        """Human-readable last run time."""
        if self._last_run:
            return self._last_run.isoformat()
        return None

    def set_dispatcher(self, dispatcher: Callable[[dict[str, Any]], Any]) -> None:
        """Set the callback for dispatching paperscout runs.

        Args:
            dispatcher: Async callable that takes a dict with:
                - from_date: str (YYYY-MM-DD)
                - to_date: str (YYYY-MM-DD)
                - source: str ("scheduler" or "scheduler_retry")
        """
        self._dispatcher = dispatcher

    async def start(self) -> None:
        """Start the scheduler loop."""
        if not self._config.enabled:
            logger.info("Scheduler disabled in config, not starting")
            return

        if self._task is not None:
            logger.warning("Scheduler already running")
            return

        self._is_running = True
        self._task = asyncio.create_task(self._loop())

        logger.info(
            f"Scheduler started — daily run at "
            f"{self._config.hour:02d}:{self._config.minute:02d} UTC, "
            f"retry window {self._config.retry_window_days}d"
        )

    def stop(self) -> None:
        """Stop the scheduler loop."""
        if self._task:
            self._task.cancel()
            self._task = None
            self._is_running = False
            logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Main scheduler loop."""
        try:
            while True:
                sleep_secs = self._seconds_until_next_run()
                logger.info(
                    f"Scheduler sleeping {sleep_secs:.0f}s until next run ({self.next_run})"
                )
                await asyncio.sleep(sleep_secs)
                await self._execute_daily()

        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
            self._is_running = False

        except Exception:
            logger.exception("Scheduler loop crashed")
            self._is_running = False

    def _seconds_until_next_run(self) -> float:
        """Calculate seconds until next scheduled run."""
        now = datetime.now(UTC)
        target = now.replace(
            hour=self._config.hour, minute=self._config.minute, second=0, microsecond=0
        )
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    async def _execute_daily(self) -> None:
        """Run the daily paperscout job and retry recent gaps."""
        if not self._dispatcher:
            logger.warning("Scheduler has no dispatcher, skipping run")
            return

        self._last_run = datetime.now(UTC)
        self._run_count += 1

        yesterday = date.today() - timedelta(days=1)

        # Check big_bang constraint
        if self._big_bang and yesterday < self._big_bang:
            logger.info(
                f"Scheduler: yesterday ({yesterday}) before big_bang ({self._big_bang}), skipping"
            )
            return

        yesterday_iso = yesterday.isoformat()
        logger.info(f"Scheduler: dispatching daily paperscout for {yesterday_iso}")

        try:
            await self._dispatcher(
                {
                    "from_date": yesterday_iso,
                    "to_date": yesterday_iso,
                    "source": "scheduler",
                }
            )
        except Exception:
            logger.exception(f"Scheduler: failed to dispatch paperscout for {yesterday_iso}")

        # Retry gaps
        await self._retry_gaps()

    async def _retry_gaps(self) -> None:
        """Retry dates within retry_window_days that have no sent notification."""
        if not self._dispatcher:
            return

        # Get missing dates from gap scanner
        missing = self._gap_scanner.scan(self._config.retry_window_days)

        if not missing:
            logger.info("No gaps to retry")
            return

        # Filter out yesterday (already handled in _execute_daily)
        today = date.today()
        yesterday = today - timedelta(days=1)
        gaps = [d for d in missing if d != yesterday]

        logger.info(f"Scheduler: found {len(gaps)} gap(s) to retry")

        for gap_date in gaps:
            gap_iso = gap_date.isoformat()
            logger.info(f"Scheduler: retrying gap date {gap_iso}")

            try:
                await self._dispatcher(
                    {
                        "from_date": gap_iso,
                        "to_date": gap_iso,
                        "source": "scheduler_retry",
                    }
                )
            except Exception:
                logger.exception(f"Scheduler: failed to retry gap {gap_iso}")

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status for reporting.

        Returns:
            Dict with enabled, running, next_run, last_run, run_count.
        """
        return {
            "enabled": self._config.enabled,
            "running": self._is_running,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "run_count": self._run_count,
            "schedule": f"{self._config.hour:02d}:{self._config.minute:02d} UTC",
            "retry_window_days": self._config.retry_window_days,
            "big_bang": self._big_bang.isoformat() if self._big_bang else None,
        }


__all__ = ["PaperScoutScheduler"]
