"""Gap Scanner: detects and fills missing notification slots.

Implements RFC-0002 PS-002: Gap detection bounded by configurable window.
Detects dates within a window that have no successful notification and
returns them for retry.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from alithia_agent.storage.sqlite import SQLiteStorage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GapScanner:
    """Detects missing notification slots within a time window."""

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

    def scan(self, window_days: int = 7) -> list[date]:
        """Return dates with missing notifications within the window.

        Args:
            window_days: Number of days to look back from today.

        Returns:
            List of dates missing notifications, respecting big_bang constraint.
        """
        missing_strs = self._storage.get_missing_notification_dates(
            self._user_id,
            self._query_categories,
            window_days,
        )

        missing_dates = [date.fromisoformat(d) for d in missing_strs]

        # Filter by big_bang if configured
        if self._big_bang:
            missing_dates = [d for d in missing_dates if d >= self._big_bang]

        if missing_dates:
            logger.info(
                f"Found {len(missing_dates)} gap(s): {[d.isoformat() for d in missing_dates]}"
            )
        else:
            logger.info("No gaps found in notification window")

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
