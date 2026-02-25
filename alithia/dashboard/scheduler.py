"""
Background scheduler: runs PaperScout on a daily cron and retries recent failures.

Mirrors the GitHub Actions daily-papers.yml workflow with in-app scheduling.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from noesium.core.utils import get_logger

from alithia.storage.base import StorageBackend

from .models import RunAgentRequest

logger = get_logger(__name__)

DEFAULT_HOUR = 23
DEFAULT_MINUTE = 0
DEFAULT_RETRY_WINDOW_DAYS = 3


class PaperScoutScheduler:
    """Configurable background scheduler for daily paper discovery with gap retry."""

    def __init__(
        self,
        storage: StorageBackend,
        config: Dict[str, Any],
        user_id: str,
    ):
        self._storage = storage
        self._config = config
        self._user_id = user_id
        self._task: Optional[asyncio.Task] = None
        self._dispatcher = None  # set via set_dispatcher after construction

        sched = config.get("scheduler", {})
        self._enabled = sched.get("enabled", False)
        self._hour = sched.get("hour", DEFAULT_HOUR)
        self._minute = sched.get("minute", DEFAULT_MINUTE)
        self._tz_name = sched.get("timezone", "UTC")
        self._retry_window = sched.get("retry_window_days", DEFAULT_RETRY_WINDOW_DAYS)

        ps_settings = config.get("paperscout_agent", config.get("arxrec", {}))
        bb = ps_settings.get("big_bang")
        self._big_bang: Optional[date] = date.fromisoformat(bb) if bb else None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def next_run(self) -> Optional[str]:
        """Human-readable next scheduled run time (UTC)."""
        if not self._enabled:
            return None
        now = datetime.now(timezone.utc)
        nxt = now.replace(hour=self._hour, minute=self._minute, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt.isoformat()

    def set_dispatcher(self, dispatcher: Any) -> None:
        self._dispatcher = dispatcher

    async def start(self) -> None:
        if not self._enabled:
            logger.info("Scheduler disabled in config")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"Scheduler started — daily run at {self._hour:02d}:{self._minute:02d} UTC, "
            f"retry window {self._retry_window}d"
        )

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        try:
            while True:
                sleep_secs = self._seconds_until_next_run()
                logger.info(f"Scheduler sleeping {sleep_secs}s until next run")
                await asyncio.sleep(sleep_secs)
                await self._execute_daily()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Scheduler loop crashed")

    def _seconds_until_next_run(self) -> float:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=self._hour, minute=self._minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    async def _execute_daily(self) -> None:
        """Run the daily paperscout job and retry recent gaps."""
        if not self._dispatcher:
            logger.warning("Scheduler has no dispatcher, skipping")
            return

        yesterday = date.today() - timedelta(days=1)

        if self._big_bang and yesterday < self._big_bang:
            logger.info(f"Scheduler: yesterday ({yesterday}) is before big_bang ({self._big_bang}), skipping")
            return

        yesterday_iso = yesterday.isoformat()
        logger.info(f"Scheduler: dispatching daily paperscout for {yesterday_iso}")

        try:
            req = RunAgentRequest(
                agent_type="paperscout",
                parameters={"from_date": yesterday_iso, "to_date": yesterday_iso, "source": "scheduler"},
            )
            await self._dispatcher.dispatch(req)
        except Exception:
            logger.exception(f"Scheduler: failed to dispatch paperscout for {yesterday_iso}")

        await self._retry_gaps()

    async def _retry_gaps(self) -> None:
        """Retry dates within retry_window_days that have no successful processed range."""
        if not self._dispatcher or not self._storage:
            return

        ps_settings = self._config.get("paperscout_agent", self._config.get("arxrec", {}))
        query = ps_settings.get("query", "")
        if not query:
            return

        today = date.today()
        processed = self._storage.get_processed_ranges(self._user_id, query, days_back=self._retry_window + 1)
        processed_dates = set()
        for r in processed:
            fd = r.get("from_date", "")
            if len(fd) == 8:
                processed_dates.add(fd)

        for days_ago in range(2, self._retry_window + 1):
            gap_date = today - timedelta(days=days_ago)

            if self._big_bang and gap_date < self._big_bang:
                break

            gap_key = gap_date.strftime("%Y%m%d")
            if gap_key in processed_dates:
                continue

            gap_iso = gap_date.isoformat()
            logger.info(f"Scheduler: retrying gap date {gap_iso}")
            try:
                req = RunAgentRequest(
                    agent_type="paperscout",
                    parameters={"from_date": gap_iso, "to_date": gap_iso, "source": "scheduler_retry"},
                )
                await self._dispatcher.dispatch(req)
            except Exception:
                logger.exception(f"Scheduler: failed to retry gap {gap_iso}")
