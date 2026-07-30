from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from alithia.config.schema import DaemonSchedulerConfig
from alithia.daemon.gap_scanner import GapScanner
from alithia.daemon.scheduler import PaperScoutScheduler
from alithia.storage.sqlite import SQLiteStorage


def test_daemon_scheduler_config_defaults() -> None:
    cfg = DaemonSchedulerConfig()
    assert cfg.max_retry_age_days == 30
    assert cfg.max_retries_per_run == 3
    assert cfg.backfill_on_startup is True
    assert cfg.startup_backfill_cap is None


def test_gap_scanner_returns_unretrieved_days(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "alithia.db")
    user_id = "u1"
    query = "cs.AI+cs.CV"
    today = date.today()

    d1 = (today - timedelta(days=1)).isoformat()
    d2 = (today - timedelta(days=2)).isoformat()
    d3 = (today - timedelta(days=3)).isoformat()

    storage.save_notification_record(
        {
            "user_id": user_id,
            "query_categories": query,
            "notification_date": d1,
            "status": "sent",
            "paper_count": 5,
        }
    )
    storage.save_notification_record(
        {
            "user_id": user_id,
            "query_categories": query,
            "notification_date": d2,
            "status": "empty",
            "paper_count": 0,
        }
    )
    storage.save_notification_record(
        {
            "user_id": user_id,
            "query_categories": query,
            "notification_date": d3,
            "status": "failed",
            "paper_count": 0,
        }
    )

    scanner = GapScanner(storage=storage, user_id=user_id, query_categories=query)
    days = scanner.scan(max_retry_age_days=4)

    # d1 is terminal sent, excluded. d2/d3 are retriable. day-4 has no record and is retriable.
    assert [d.isoformat() for d in days] == [
        (today - timedelta(days=4)).isoformat(),
        d3,
        d2,
    ]


@pytest.mark.asyncio
async def test_scheduler_retries_oldest_first_with_cap(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "alithia.db")
    cfg = DaemonSchedulerConfig(
        enabled=True,
        max_retry_age_days=30,
        max_retries_per_run=3,
    )
    today = date.today()
    scheduler = PaperScoutScheduler(
        storage=storage,
        config=cfg,
        user_id="u1",
        query_categories="cs.AI",
    )

    dispatched: list[dict[str, str]] = []

    async def dispatcher(payload: dict[str, str]) -> None:
        dispatched.append(payload)

    scheduler.set_dispatcher(dispatcher)

    # Inject deterministic unretrieved set in unsorted order.
    scheduler._gap_scanner.scan = lambda _max_age_days: [  # type: ignore[method-assign]
        today - timedelta(days=1),
        today - timedelta(days=4),
        today - timedelta(days=2),
        today - timedelta(days=3),
    ]

    await scheduler._retry_gaps(excluded_dates={today - timedelta(days=1)})

    assert [d["from_date"] for d in dispatched] == [
        (today - timedelta(days=4)).isoformat(),
        (today - timedelta(days=3)).isoformat(),
        (today - timedelta(days=2)).isoformat(),
    ]
    assert all(d["source"] == "scheduler_retry" for d in dispatched)
