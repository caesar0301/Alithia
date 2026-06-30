"""Tests for the optional-Zotero profile_analysis gate and the
data_collection interests wiring (RFC-010 §10).

These call ``make_nodes`` directly with a mock store. Soothe event
registration happens at import time and is available in the test venv.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from alithia_agent.paperscout.nodes import make_nodes
from alithia_agent.paperscout.state import PaperScoutRuntimeConfig


def _runtime_config(**overrides) -> PaperScoutRuntimeConfig:
    base = dict(
        arxiv_categories=["cs.AI"],
        max_papers=5,
        max_papers_queried=10,
        send_email=False,
        research_interests_dir=None,
    )
    base.update(overrides)
    return PaperScoutRuntimeConfig(**base)


def _mock_store():
    store = MagicMock()
    store.load = AsyncMock(return_value=None)
    store.save = AsyncMock(return_value=None)
    return store


def _write_interest(dir_: Path, title: str = "Interest"):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{title.lower()}.md").write_text(
        f"---\ntitle: {title}\n---\n\n{'body text ' * 12}",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# profile_analysis_node — optional zotero gate (RFC-010 §10.1)
# ---------------------------------------------------------------------------


def test_profile_analysis_passes_with_interests_and_no_zotero(tmp_path):
    _write_interest(tmp_path)
    cfg = _runtime_config(research_interests_dir=str(tmp_path), zotero=None)
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["profile_analysis"]({})
    assert result.get("errors") is None or result.get("errors") == []
    assert "Profile validated" in result["info"][0]


def test_profile_analysis_fails_with_no_knowledge_source(tmp_path):
    # No zotero AND an empty interests dir → fail fast.
    cfg = _runtime_config(research_interests_dir=str(tmp_path), zotero=None)
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["profile_analysis"]({})
    assert result["errors"]
    assert "No knowledge source" in result["errors"][0]


def test_profile_analysis_fails_with_missing_interests_dir():
    cfg = _runtime_config(research_interests_dir="/nonexistent/path/xyz", zotero=None)
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["profile_analysis"]({})
    assert result["errors"]
    assert "No knowledge source" in result["errors"][0]


def test_profile_analysis_passes_with_zotero_and_no_interests(tmp_path):
    # zotero configured, no interest files → passes (existing path preserved).
    from alithia_agent.paperscout.state import ZoteroRuntimeConfig

    cfg = _runtime_config(
        research_interests_dir=str(tmp_path),  # exists but empty
        zotero=ZoteroRuntimeConfig(api_key="k", library_id="L1"),
    )
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["profile_analysis"]({})
    assert not result.get("errors")
    assert "Profile validated" in result["info"][0]


def test_profile_analysis_smtp_still_required_when_send_email(tmp_path):
    _write_interest(tmp_path)
    cfg = _runtime_config(
        research_interests_dir=str(tmp_path),
        zotero=None,
        send_email=True,
        smtp=None,
    )
    nodes = make_nodes(_mock_store(), "u", cfg)
    result = nodes["profile_analysis"]({})
    assert any("SMTP" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# data_collection_node — sync + load interests (RFC-010 §8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_collection_loads_interests_into_state(tmp_path, monkeypatch):
    _write_interest(tmp_path, "Multimodal")
    _write_interest(tmp_path, "Agents")

    # Avoid real ArXiv fetch: patch arxiv.Client.results to return nothing.
    import arxiv

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def results(self, search):
            return iter([])

    monkeypatch.setattr(arxiv, "Client", _FakeClient)
    # Patch affiliation extractor to a no-op.
    import alithia_agent.paperscout.nodes as nodes_mod

    fake_extractor = MagicMock()
    fake_extractor.enrich_papers = AsyncMock(side_effect=lambda papers: papers)
    fake_extractor.close = AsyncMock(return_value=None)
    monkeypatch.setattr(nodes_mod, "AffiliationExtractor", lambda **kw: fake_extractor)

    cfg = _runtime_config(
        research_interests_dir=str(tmp_path),
        zotero=None,  # no zotero → sync is a no-op
        lookback_days=7,
    )
    store = _mock_store()
    nodes = make_nodes(store, "u", cfg)

    result = await nodes["data_collection"]({})

    interests = result.get("research_interests", [])
    assert len(interests) == 2
    titles = {i.title for i in interests}
    assert titles == {"Multimodal", "Agents"}
    assert result["metrics"]["interests_count"] == 2
    # zotero sync was skipped (no zotero config).
    assert result["metrics"]["zotero_sync"]["skipped"] is True


# ---------------------------------------------------------------------------
# relevance_assessment_node — reranker receives interests (smoke)
# ---------------------------------------------------------------------------


def test_relevance_assessment_passes_interests_to_reranker(monkeypatch):
    from datetime import datetime

    from alithia_agent.models import ArxivPaper, ScoredPaper

    paper = ArxivPaper(
        title="T",
        summary="summary " * 20,
        authors=["a"],
        arxiv_id="1",
        pdf_url="u",
        published_date=datetime(2024, 1, 1),
    )

    captured: dict = {}

    class _SpyReranker:
        def __init__(self, papers, *, interests=None, **kw):
            captured["papers"] = papers
            captured["interests"] = interests

        def rerank(self):
            return [ScoredPaper(paper=paper, score=7.0)]

    import alithia_agent.paperscout.nodes as nodes_mod

    monkeypatch.setattr(nodes_mod, "PaperReranker", _SpyReranker)

    from alithia_agent.research_interests import ResearchInterest

    interest = ResearchInterest(title="X", body="b")
    cfg = _runtime_config(max_papers=5)
    nodes = make_nodes(_mock_store(), "u", cfg)

    result = nodes["relevance_assessment"](
        {
            "discovered_papers": [paper],
            "research_interests": [interest],
        }
    )

    assert captured["interests"] == [interest]
    assert captured["papers"] == [paper]
    assert len(result["scored_papers"]) == 1
