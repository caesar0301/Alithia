"""Tests for affiliation extraction wiring in data_collection_node."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from alithia.models import ArxivPaper
from alithia.paperscout.nodes import make_nodes
from alithia.paperscout.state import PaperScoutRuntimeConfig


def _runtime_config(**overrides) -> PaperScoutRuntimeConfig:
    base = dict(
        arxiv_categories=["cs.AI"],
        max_papers=5,
        max_papers_queried=10,
        send_email=False,
        research_interests_dir=None,
        lookback_days=7,
    )
    base.update(overrides)
    return PaperScoutRuntimeConfig(**base)


def _mock_store():
    store = MagicMock()
    store.load = AsyncMock(return_value=None)
    store.save = AsyncMock(return_value=None)
    return store


def _write_interest(dir_: Path, title: str = "Interest") -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{title.lower()}.md").write_text(
        f"---\ntitle: {title}\n---\n\n{'body text ' * 12}",
        encoding="utf-8",
    )


def _patch_arxiv_one_paper(monkeypatch) -> datetime:
    import arxiv

    published = datetime(2024, 1, 15, tzinfo=UTC)

    author = MagicMock()
    author.name = "Alice"

    result = MagicMock()
    result.title = "Test Paper"
    result.summary = "An abstract " * 10
    result.authors = [author]
    result.entry_id = "http://arxiv.org/abs/2401.00001v1"
    result.pdf_url = "http://arxiv.org/pdf/2401.00001"
    result.published = published

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def results(self, search):
            return iter([result])

    monkeypatch.setattr(arxiv, "Client", _FakeClient)
    return published


def _collection_config(tmp_path: Path, **overrides) -> PaperScoutRuntimeConfig:
    published = overrides.pop("_published", datetime(2024, 1, 15, tzinfo=UTC))
    base = dict(
        research_interests_dir=str(tmp_path),
        zotero=None,
        from_date=published.date().isoformat(),
        to_date=published.date().isoformat(),
    )
    base.update(overrides)
    return _runtime_config(**base)


@pytest.mark.asyncio
async def test_data_collection_passes_llm_config_when_key_set(tmp_path, monkeypatch):
    _write_interest(tmp_path)
    published = _patch_arxiv_one_paper(monkeypatch)

    import alithia.paperscout.nodes as nodes_mod

    captured: dict = {}

    def _extractor_factory(**kw):
        captured.update(kw)
        ext = MagicMock()
        ext.enrich_papers = AsyncMock(side_effect=lambda papers: papers)
        ext.close = AsyncMock(return_value=None)
        return ext

    monkeypatch.setattr(nodes_mod, "AffiliationExtractor", _extractor_factory)

    cfg = _collection_config(
        tmp_path,
        llm_api_key="sk-test",
        llm_api_base="https://api.example.com/v1",
        llm_model="gpt-4",
        _published=published,
    )
    nodes = make_nodes(_mock_store(), "u", cfg)
    await nodes["data_collection"]({})

    assert captured["llm_config"] == {
        "api_key": "sk-test",
        "api_base": "https://api.example.com/v1",
        "model": "gpt-4",
    }


@pytest.mark.asyncio
async def test_data_collection_no_llm_config_without_key(tmp_path, monkeypatch):
    _write_interest(tmp_path)
    published = _patch_arxiv_one_paper(monkeypatch)

    import alithia.paperscout.nodes as nodes_mod

    captured: dict = {}

    def _extractor_factory(**kw):
        captured.update(kw)
        ext = MagicMock()
        ext.enrich_papers = AsyncMock(side_effect=lambda papers: papers)
        ext.close = AsyncMock(return_value=None)
        return ext

    monkeypatch.setattr(nodes_mod, "AffiliationExtractor", _extractor_factory)

    cfg = _collection_config(tmp_path, llm_api_key=None, _published=published)
    nodes = make_nodes(_mock_store(), "u", cfg)
    await nodes["data_collection"]({})

    assert captured["llm_config"] is None


@pytest.mark.asyncio
async def test_data_collection_records_affiliations_metric(tmp_path, monkeypatch):
    _write_interest(tmp_path)
    published = _patch_arxiv_one_paper(monkeypatch)

    import alithia.paperscout.nodes as nodes_mod

    async def _enrich(papers: list[ArxivPaper]) -> list[ArxivPaper]:
        for paper in papers:
            paper.affiliations = ["MIT"]
        return papers

    ext = MagicMock()
    ext.enrich_papers = AsyncMock(side_effect=_enrich)
    ext.close = AsyncMock(return_value=None)
    monkeypatch.setattr(nodes_mod, "AffiliationExtractor", lambda **kw: ext)

    cfg = _collection_config(tmp_path, llm_api_key="sk-test", _published=published)
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = await nodes["data_collection"]({})

    assert result["metrics"]["affiliations_extracted"] == 1
    assert result["discovered_papers"][0].affiliations == ["MIT"]


@pytest.mark.asyncio
async def test_content_generation_preserves_prior_metrics(tmp_path, monkeypatch):
    """content_generation merges tldrs_generated into existing metrics."""
    from datetime import UTC, datetime

    from alithia.models import ArxivPaper, ScoredPaper

    paper = ArxivPaper(
        title="T",
        summary="abstract " * 20,
        authors=["a"],
        arxiv_id="2401.00001",
        pdf_url="u",
        published_date=datetime(2024, 1, 1, tzinfo=UTC),
    )
    scored = [ScoredPaper(paper=paper, score=8.0)]

    monkeypatch.setattr(
        "alithia.paperscout.nodes.generate_tldrs",
        lambda papers, cfg: 1,
    )

    cfg = _runtime_config(research_interests_dir=str(tmp_path), llm_api_key="sk-test")
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["content_generation"](
        {
            "scored_papers": scored,
            "metrics": {"affiliations_extracted": 4, "arxiv_new": 10},
        }
    )

    assert result["metrics"]["affiliations_extracted"] == 4
    assert result["metrics"]["arxiv_new"] == 10
    assert result["metrics"]["tldrs_generated"] == 1
