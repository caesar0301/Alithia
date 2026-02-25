"""
Gap Scanner: detects and fills missing recommendation slots (RFC-0002 PS-002).
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, List

from cogents_core.utils import get_logger

from alithia.storage.base import StorageBackend

if TYPE_CHECKING:
    from .agent import PaperScoutAgent
    from .state import PaperScoutConfig

logger = get_logger(__name__)


class GapScanner:
    """Detects and fills missing recommendation slots."""

    def __init__(self, storage: StorageBackend, user_id: str):
        self._storage = storage
        self._user_id = user_id

    def scan(self, query_categories: str, window_days: int = 7) -> List[date]:
        """Return dates with missing notifications within the window."""
        return self._storage.get_missing_notification_dates(
            self._user_id, query_categories, window_days
        )

    async def fill_gaps(
        self,
        config: "PaperScoutConfig",
        agent: "PaperScoutAgent",
    ) -> Dict[date, str]:
        """
        For each missing date, run PaperScout with that date range.

        Returns {date: status} mapping.
        """
        missing = self.scan(config.query, config.gap_scan_window_days)
        results: Dict[date, str] = {}

        if not missing:
            logger.info("No gaps found")
            return results

        logger.info(f"Found {len(missing)} gap(s) to fill: {[d.isoformat() for d in missing]}")

        for gap_date in sorted(missing):
            logger.info(f"Filling gap for {gap_date.isoformat()}...")

            gap_config = config.model_copy(update={
                "from_date": gap_date.isoformat(),
                "to_date": gap_date.isoformat(),
            })

            try:
                result = agent.run(gap_config)
                status = "success" if result.get("success") else "failed"
                results[gap_date] = status
                logger.info(f"Gap fill for {gap_date}: {status}")
            except Exception as e:
                results[gap_date] = f"error: {e}"
                logger.error(f"Gap fill for {gap_date} failed: {e}")

        return results
