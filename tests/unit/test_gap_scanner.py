"""
Tests for GapScanner with big_bang date support.

Verifies that:
- big_bang filters out dates before the cutoff
- scan() and fill_gaps() respect big_bang
- without big_bang, all missing dates are returned
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from alithia.paperscout.gap_scanner import GapScanner


@pytest.fixture
def mock_storage():
    return MagicMock()


class TestGapScannerBigBang:
    def test_scan_without_big_bang(self, mock_storage):
        """Without big_bang, all missing dates are returned."""
        today = date.today()
        missing = [today - timedelta(days=i) for i in range(1, 4)]
        mock_storage.get_missing_notification_dates.return_value = missing

        scanner = GapScanner(mock_storage, "user1")
        result = scanner.scan("cs.AI", window_days=7)

        assert result == missing

    def test_scan_with_big_bang_filters_old_dates(self, mock_storage):
        """big_bang filters out dates before the cutoff."""
        today = date.today()
        big_bang = today - timedelta(days=2)
        missing = [today - timedelta(days=i) for i in range(1, 5)]
        mock_storage.get_missing_notification_dates.return_value = missing

        scanner = GapScanner(mock_storage, "user1", big_bang=big_bang)
        result = scanner.scan("cs.AI", window_days=7)

        for d in result:
            assert d >= big_bang
        assert (today - timedelta(days=3)) not in result
        assert (today - timedelta(days=4)) not in result

    def test_scan_big_bang_on_boundary(self, mock_storage):
        """Date equal to big_bang should be included."""
        today = date.today()
        big_bang = today - timedelta(days=2)
        missing = [today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=3)]
        mock_storage.get_missing_notification_dates.return_value = missing

        scanner = GapScanner(mock_storage, "user1", big_bang=big_bang)
        result = scanner.scan("cs.AI")

        assert big_bang in result
        assert (today - timedelta(days=3)) not in result

    def test_scan_big_bang_future_returns_empty(self, mock_storage):
        """If big_bang is in the future, no dates should be returned."""
        today = date.today()
        big_bang = today + timedelta(days=1)
        missing = [today - timedelta(days=i) for i in range(1, 4)]
        mock_storage.get_missing_notification_dates.return_value = missing

        scanner = GapScanner(mock_storage, "user1", big_bang=big_bang)
        result = scanner.scan("cs.AI")

        assert result == []

    def test_scan_no_missing_dates(self, mock_storage):
        mock_storage.get_missing_notification_dates.return_value = []
        scanner = GapScanner(mock_storage, "user1", big_bang=date.today() - timedelta(days=7))
        result = scanner.scan("cs.AI")
        assert result == []


class TestGapScannerFillGaps:
    @pytest.mark.asyncio
    async def test_fill_gaps_respects_big_bang(self, mock_storage):
        """fill_gaps should only process dates >= big_bang."""
        today = date.today()
        big_bang = today - timedelta(days=2)
        missing = [today - timedelta(days=i) for i in range(1, 5)]
        mock_storage.get_missing_notification_dates.return_value = missing

        scanner = GapScanner(mock_storage, "user1", big_bang=big_bang)

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True}

        mock_config = MagicMock()
        mock_config.query = "cs.AI"
        mock_config.gap_scan_window_days = 7
        mock_config.model_copy.return_value = mock_config

        results = await scanner.fill_gaps(mock_config, mock_agent)

        # Should only have filled 2 dates (days 1 and 2), not 3 and 4
        assert len(results) == 2
        for d in results:
            assert d >= big_bang

    @pytest.mark.asyncio
    async def test_fill_gaps_no_missing(self, mock_storage):
        mock_storage.get_missing_notification_dates.return_value = []
        scanner = GapScanner(mock_storage, "user1")

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.query = "cs.AI"
        mock_config.gap_scan_window_days = 7

        results = await scanner.fill_gaps(mock_config, mock_agent)
        assert results == {}
        mock_agent.run.assert_not_called()
