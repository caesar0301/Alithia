"""Tests for daily digest metadata persistence."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from alithia_agent.models import ArxivPaper, ScoredPaper
from alithia_agent.paperscout.digest_store import (
    build_daily_digest_record,
    digest_storage_key,
    list_daily_digest_dates,
    load_daily_digest,
    save_daily_digest,
    serialize_scored_paper,
)
from alithia_agent.paperscout.nodes import make_nodes


def _sample_scored() -> ScoredPaper:
    paper = ArxivPaper(
        title="Test Paper",
        summary="A long abstract about transformers.",
        authors=["Alice", "Bob"],
        arxiv_id="2401.00001",
        pdf_url="https://arxiv.org/pdf/2401.00001.pdf",
        published_date=datetime(2024, 1, 15, tzinfo=UTC),
        categories=["cs.AI"],
        affiliations=["MIT"],
        tldr="Short TLDR.",
        code_url="https://github.com/example/repo",
    )
    return ScoredPaper(
        paper=paper,
        score=8.2,
        relevance_factors={"semantic": 0.9},
    )


def test_serialize_scored_paper_excludes_html_and_tex():
    record = serialize_scored_paper(_sample_scored(), rank=1)

    assert record["rank"] == 1
    assert record["score"] == 8.2
    assert record["arxiv_id"] == "2401.00001"
    assert record["tldr"] == "Short TLDR."
    assert record["pdf_url"] == "https://arxiv.org/pdf/2401.00001.pdf"
    assert record["affiliations"] == ["MIT"]
    assert "html_body" not in record
    assert "tex" not in record


def test_build_daily_digest_record_shape(sample_config):
    record = build_daily_digest_record(
        [_sample_scored()],
        digest_date="2026-06-10",
        config=sample_config,
        metrics={
            "source": "scheduler",
            "papers_scored": 50,
            "papers_selected": 1,
            "avg_score": 8.2,
            "tldrs_generated": 1,
        },
    )

    assert record["digest_date"] == "2026-06-10"
    assert record["paper_count"] == 1
    assert record["source"] == "scheduler"
    assert record["query"] == sample_config.query
    assert record["papers"][0]["rank"] == 1
    assert "html_body" not in record


@pytest.mark.asyncio
async def test_save_and_load_daily_digest():
    store = MagicMock()
    store.save = AsyncMock()
    store.load = AsyncMock(
        return_value={
            "digest_date": "2026-06-10",
            "papers": [],
        }
    )
    store.list_keys = AsyncMock(
        return_value=["paperscout:digest:user1:2026-06-09", "paperscout:digest:user1:2026-06-10"]
    )

    record = {"digest_date": "2026-06-10", "papers": []}
    key = await save_daily_digest(store, "user1", record)

    assert key == digest_storage_key("user1", "2026-06-10")
    store.save.assert_awaited_once_with(key, record)

    loaded = await load_daily_digest(store, "user1", "2026-06-10")
    assert loaded["digest_date"] == "2026-06-10"

    dates = await list_daily_digest_dates(store, "user1")
    assert dates == ["2026-06-09", "2026-06-10"]


@pytest.mark.asyncio
async def test_persist_digest_node_saves_metadata(sample_config):
    store = MagicMock()
    store.save = AsyncMock()
    store.load = AsyncMock(return_value=None)

    cfg = sample_config.model_copy(update={"from_date": "2026-06-10", "source": "scheduler"})
    nodes = make_nodes(store, "default_user", cfg)

    result = await nodes["persist_digest"](
        {
            "scored_papers": [_sample_scored()],
            "metrics": {
                "notification_date": "2026-06-10",
                "papers_scored": 10,
                "papers_selected": 1,
                "tldrs_generated": 1,
            },
        }
    )

    assert result["metrics"]["digest_saved"] is True
    store.save.assert_awaited_once()
    saved_key = store.save.await_args.args[0]
    saved_record = store.save.await_args.args[1]
    assert saved_key == "paperscout:digest:default_user:2026-06-10"
    assert saved_record["paper_count"] == 1
    assert saved_record["papers"][0]["tldr"] == "Short TLDR."
    assert "html_body" not in saved_record


@pytest.mark.asyncio
async def test_persist_digest_node_saves_empty_day(sample_config):
    store = MagicMock()
    store.save = AsyncMock()

    nodes = make_nodes(store, "default_user", sample_config)
    result = await nodes["persist_digest"](
        {
            "scored_papers": [],
            "metrics": {"notification_date": "2026-06-29"},
        }
    )

    assert result["metrics"]["digest_saved"] is True
    saved_record = store.save.await_args.args[1]
    assert saved_record["paper_count"] == 0
    assert saved_record["papers"] == []
