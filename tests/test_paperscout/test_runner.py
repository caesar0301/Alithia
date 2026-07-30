from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from alithia.config.schema import (
    Config,
    DaemonSchedulerConfig,
    PaperScoutAgentConfig,
    ResearcherProfileConfig,
    StorageConfig,
    ZoteroProfileConfig,
)
from alithia.daemon.scheduler import PaperScoutScheduler
from alithia.paperscout.runner import (
    PaperScoutRunResult,
    build_scheduler_config,
    run_paperscout_for_dates,
)
from alithia.paperscout.state import (
    PaperScoutRuntimeConfig,
    SmtpRuntimeConfig,
    ZoteroRuntimeConfig,
)


@pytest.fixture
def global_config() -> Config:
    return Config(
        researcher_profile=ResearcherProfileConfig(
            email="test@example.com",
            zotero=ZoteroProfileConfig(zotero_id="123", zotero_key="key"),
        ),
        storage=StorageConfig(user_id="test_user"),
        paperscout_agent=PaperScoutAgentConfig(
            query="cs.AI+cs.LG",
            send_email=False,
        ),
    )


@pytest.fixture
def runtime_config() -> PaperScoutRuntimeConfig:
    return PaperScoutRuntimeConfig(
        arxiv_categories=["cs.AI", "cs.LG"],
        query="cs.AI+cs.LG",
        send_email=False,
        smtp=SmtpRuntimeConfig(
            host="smtp.example.com",
            port=587,
            user="test@example.com",
            password="testpass",
        ),
        zotero=ZoteroRuntimeConfig(
            api_key="test_key",
            library_id="test_library",
        ),
    )


def test_build_scheduler_config_sets_date_range(global_config: Config) -> None:
    runtime = build_scheduler_config(
        global_config,
        from_date="2026-05-17",
        to_date="2026-05-17",
        source="scheduler_retry",
    )

    assert runtime.from_date == "2026-05-17"
    assert runtime.to_date == "2026-05-17"
    assert runtime.source == "scheduler_retry"


def test_with_scheduler_params_returns_copy(runtime_config: PaperScoutRuntimeConfig) -> None:
    scheduled = runtime_config.with_scheduler_params(
        from_date="2026-06-01",
        to_date="2026-06-02",
        source="scheduler",
    )

    assert runtime_config.from_date is None
    assert scheduled.from_date == "2026-06-01"
    assert scheduled.to_date == "2026-06-02"
    assert scheduled.source == "scheduler"


@pytest.mark.asyncio
async def test_run_paperscout_for_dates_returns_failed_on_workflow_error(
    global_config: Config,
) -> None:
    mock_store = AsyncMock()

    with patch(
        "alithia.paperscout.runner.create_paperscout_graph",
    ) as mock_create_graph:
        compiled = AsyncMock()
        compiled.ainvoke = AsyncMock(side_effect=RuntimeError("workflow exploded"))
        mock_create_graph.return_value.compile.return_value = compiled

        result = await run_paperscout_for_dates(
            global_config,
            mock_store,
            "test_user",
            from_date="2026-06-01",
            to_date="2026-06-01",
            source="scheduler",
        )

    assert result.status == "failed"
    assert result.paper_count == 0
    assert "workflow exploded" in result.errors[0]


@pytest.mark.asyncio
async def test_run_paperscout_for_dates_returns_sent_with_papers(
    global_config: Config,
) -> None:
    mock_store = AsyncMock()

    with patch(
        "alithia.paperscout.runner.create_paperscout_graph",
    ) as mock_create_graph:
        compiled = AsyncMock()
        compiled.ainvoke = AsyncMock(
            return_value={
                "errors": [],
                "metrics": {"paper_count": 4},
            }
        )
        mock_create_graph.return_value.compile.return_value = compiled

        result = await run_paperscout_for_dates(
            global_config,
            mock_store,
            "test_user",
            from_date="2026-06-01",
            to_date="2026-06-01",
            source="scheduler_retry",
        )

    assert result == PaperScoutRunResult(
        paper_count=4,
        status="sent",
        errors=[],
        metrics={"paper_count": 4},
    )


@pytest.mark.asyncio
async def test_scheduler_startup_backfill_uses_startup_cap(tmp_path: Path) -> None:
    storage = AsyncMock()
    cfg = DaemonSchedulerConfig(
        enabled=True,
        max_retry_age_days=30,
        max_retries_per_run=3,
        backfill_on_startup=True,
        startup_backfill_cap=7,
    )
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

    today = date.today()
    scheduler._gap_scanner.scan = lambda _max_age_days: [  # type: ignore[method-assign]
        today - timedelta(days=offset) for offset in range(1, 11)
    ]

    await scheduler._backfill_on_startup()

    assert len(dispatched) == 7
    assert all(d["source"] == "scheduler_retry" for d in dispatched)
    assert dispatched[0]["from_date"] == (today - timedelta(days=10)).isoformat()
