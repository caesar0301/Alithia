"""
Tests for PaperScoutScheduler.

Verifies:
- big_bang clamping for daily runs and retry gaps
- next_run calculation
- enabled/disabled behavior
- retry_gaps skips processed dates and dates before big_bang
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from alithia.dashboard.scheduler import PaperScoutScheduler


def _make_config(enabled=True, hour=23, minute=0, retry_window=3, big_bang=None):
    cfg = {
        "scheduler": {
            "enabled": enabled,
            "hour": hour,
            "minute": minute,
            "timezone": "UTC",
            "retry_window_days": retry_window,
        },
        "paperscout_agent": {
            "query": "cs.AI+cs.LG",
        },
    }
    if big_bang:
        cfg["paperscout_agent"]["big_bang"] = big_bang
    return cfg


class TestSchedulerInit:
    def test_disabled_by_default(self):
        sched = PaperScoutScheduler(MagicMock(), {"scheduler": {}}, "user1")
        assert not sched.enabled

    def test_enabled_from_config(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=True), "user1")
        assert sched.enabled

    def test_big_bang_parsed(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(big_bang="2025-01-15"), "user1")
        assert sched._big_bang == date(2025, 1, 15)

    def test_big_bang_none_when_absent(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(), "user1")
        assert sched._big_bang is None


class TestSchedulerNextRun:
    def test_next_run_when_disabled(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=False), "user1")
        assert sched.next_run is None

    def test_next_run_returns_iso_string(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=True, hour=3), "user1")
        nxt = sched.next_run
        assert nxt is not None
        parsed = datetime.fromisoformat(nxt)
        assert parsed.hour == 3
        assert parsed.minute == 0


class TestSchedulerStartStop:
    @pytest.mark.asyncio
    async def test_start_disabled_no_task(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=False), "user1")
        await sched.start()
        assert sched._task is None

    @pytest.mark.asyncio
    async def test_start_enabled_creates_task(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=True), "user1")
        await sched.start()
        assert sched._task is not None
        sched.stop()
        assert sched._task is None

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(enabled=False), "user1")
        sched.stop()  # no error even when not started


class TestSchedulerExecuteDaily:
    @pytest.mark.asyncio
    async def test_skips_when_yesterday_before_big_bang(self):
        """If yesterday < big_bang, daily run should be skipped entirely."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        config = _make_config(big_bang=tomorrow)

        sched = PaperScoutScheduler(MagicMock(), config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._execute_daily()
        dispatcher.dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatches_when_no_big_bang(self):
        config = _make_config()
        storage = MagicMock()
        storage.get_processed_ranges.return_value = []

        sched = PaperScoutScheduler(storage, config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._execute_daily()
        assert dispatcher.dispatch.call_count >= 1

        # First call should be for yesterday
        first_call = dispatcher.dispatch.call_args_list[0]
        req = first_call[0][0]
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert req.parameters["from_date"] == yesterday

    @pytest.mark.asyncio
    async def test_dispatches_when_yesterday_after_big_bang(self):
        old_date = (date.today() - timedelta(days=30)).isoformat()
        config = _make_config(big_bang=old_date)
        storage = MagicMock()
        storage.get_processed_ranges.return_value = []

        sched = PaperScoutScheduler(storage, config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._execute_daily()
        assert dispatcher.dispatch.call_count >= 1


class TestSchedulerRetryGaps:
    @pytest.mark.asyncio
    async def test_retry_skips_processed_dates(self):
        """Already processed dates should not be retried."""
        config = _make_config(retry_window=3)
        storage = MagicMock()

        today = date.today()
        # Mark day-2 as processed
        day2 = (today - timedelta(days=2)).strftime("%Y%m%d")
        storage.get_processed_ranges.return_value = [{"from_date": day2, "to_date": day2, "papers_found": 5}]

        sched = PaperScoutScheduler(storage, config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._retry_gaps()

        # Only day-3 should be retried (day-2 is processed)
        if dispatcher.dispatch.call_count > 0:
            for call in dispatcher.dispatch.call_args_list:
                req = call[0][0]
                assert req.parameters["from_date"] != (today - timedelta(days=2)).isoformat()

    @pytest.mark.asyncio
    async def test_retry_skips_dates_before_big_bang(self):
        """Dates before big_bang should not be retried."""
        today = date.today()
        big_bang = (today - timedelta(days=1)).isoformat()
        config = _make_config(retry_window=5, big_bang=big_bang)
        storage = MagicMock()
        storage.get_processed_ranges.return_value = []

        sched = PaperScoutScheduler(storage, config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._retry_gaps()

        # No dates should be retried because retry starts at day-2
        # and big_bang is day-1, so all retry candidates (day-2..day-5) are before big_bang
        # except... day-2 through day-5 are all < big_bang (day-1)? No:
        # big_bang = today - 1 day. retry range is day-2..day-5.
        # day-2 < big_bang → skip. day-3 < big_bang → break. etc.
        # So no dispatches.
        dispatcher.dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_no_dispatcher(self):
        """If no dispatcher is set, retry_gaps does nothing."""
        config = _make_config(retry_window=3)
        sched = PaperScoutScheduler(MagicMock(), config, "user1")
        # No dispatcher set
        await sched._retry_gaps()  # Should not raise

    @pytest.mark.asyncio
    async def test_retry_dispatches_unprocessed_within_window(self):
        """Unprocessed dates within the retry window and after big_bang should be dispatched."""
        today = date.today()
        big_bang = (today - timedelta(days=10)).isoformat()
        config = _make_config(retry_window=3, big_bang=big_bang)
        storage = MagicMock()
        storage.get_processed_ranges.return_value = []

        sched = PaperScoutScheduler(storage, config, "user1")
        dispatcher = AsyncMock()
        sched.set_dispatcher(dispatcher)

        await sched._retry_gaps()

        # Should retry day-2 and day-3
        assert dispatcher.dispatch.call_count == 2
        retried_dates = set()
        for call in dispatcher.dispatch.call_args_list:
            req = call[0][0]
            retried_dates.add(req.parameters["from_date"])

        assert (today - timedelta(days=2)).isoformat() in retried_dates
        assert (today - timedelta(days=3)).isoformat() in retried_dates


class TestSecondsUntilNextRun:
    def test_returns_positive(self):
        sched = PaperScoutScheduler(MagicMock(), _make_config(hour=23, minute=59), "user1")
        secs = sched._seconds_until_next_run()
        assert secs > 0
        assert secs <= 86400  # at most 24 hours
