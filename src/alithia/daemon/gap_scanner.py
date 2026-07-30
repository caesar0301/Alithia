"""Gap Scanner: detects unretrieved notification days.

Implements RFC-0002 PS-002: Gap detection bounded by configurable window.
Detects dates within a bounded window that are not terminally retrieved
(`status != sent`) and returns them for retry.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from alithia.storage.sqlite import SQLiteStorage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GapScanner:
    """Detects unretrieved notification days within a time window."""

    def __init__(
        self,
        storage: SQLiteStorage,
        user_id: str,
        query_categories: str,
        big_bang: date | None = None,
    ):
        """Initialize GapScanner.

        Args:
            storage: SQLiteStorage instance for persistence.
            user_id: User identifier.
            query_categories: ArXiv query string (e.g., "cs.AI+cs.CV+cs.LG+cs.CL").
            big_bang: Optional tracking start date. No gaps before this date.
        """
        self._storage = storage
        self._user_id = user_id
        self._query_categories = query_categories
        self._big_bang = big_bang

    def scan(self, max_retry_age_days: int = 30) -> list[date]:
        """Return unretrieved dates within retry-age window.

        Args:
            max_retry_age_days: Number of days to look back from today.

        Returns:
            List of unretrieved dates, respecting big_bang constraint.
        """
        unretrieved_strs = self._storage.get_unretrieved_notification_dates(
            self._user_id,
            self._query_categories,
            max_retry_age_days,
        )

        missing_dates = [date.fromisoformat(d) for d in unretrieved_strs]

        # Filter by big_bang if configured
        if self._big_bang:
            missing_dates = [d for d in missing_dates if d >= self._big_bang]

        if missing_dates:
            logger.info(
                f"Found {len(missing_dates)} unretrieved day(s): "
                f"{[d.isoformat() for d in missing_dates]}"
            )
        else:
            logger.info("No unretrieved days found in retry window")

        return missing_dates

    def has_gap_for_yesterday(self) -> bool:
        """Check if yesterday has a missing notification.

        Quick check for scheduler to decide if daily run is needed.

        Returns:
            True if yesterday needs a notification.
        """
        yesterday = date.today() - date.resolution  # 1 day ago
        yesterday_str = yesterday.isoformat()

        # Check if big_bang blocks this date
        if self._big_bang and yesterday < self._big_bang:
            logger.info(
                f"Yesterday ({yesterday_str}) is before big_bang ({self._big_bang}), skipping"
            )
            return False

        # Check for existing notification
        record = self._storage.get_notification_record(
            self._user_id,
            self._query_categories,
            yesterday_str,
        )

        if record and record.get("status") == "sent":
            logger.info(f"Yesterday ({yesterday_str}) already has sent notification")
            return False

        return True


__all__ = ["GapScanner"]
