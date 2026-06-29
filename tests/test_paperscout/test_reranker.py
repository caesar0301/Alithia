"""Tests for PaperScout reranker (interests-only API, RFC-010 §9).

The legacy ``corpus`` (ZoteroPaper) parameter was removed: Zotero items now
flow through the markdown sync into ``ResearchInterest`` units, so the
reranker scores only against interests. These tests cover the public contract
at the no-model level (fastembed is skipped; see test_reranker_unified.py for
the embedding-path tests with a fake encoder).
"""

import pytest

from alithia_agent.paperscout.reranker import PaperReranker
from alithia_agent.research_interests import ResearchInterest


def _interest(title: str = "Interest", body: str = "body text " * 12) -> ResearchInterest:
    return ResearchInterest(title=title, body=body)


def test_reranker_initialization(sample_arxiv_paper):
    """Test PaperReranker initialization with interests."""
    reranker = PaperReranker(papers=[sample_arxiv_paper], interests=[_interest()])

    assert reranker is not None
    assert len(reranker.papers) == 1
    assert len(reranker.interests) == 1


def test_reranker_empty_papers():
    """Test reranker with empty papers list."""
    reranker = PaperReranker(papers=[], interests=[_interest()])
    scored = reranker.rerank()
    assert scored == []


def test_reranker_empty_interests(sample_arxiv_paper):
    """No interests → default 5.0 scores (the degenerate fallback)."""
    reranker = PaperReranker(papers=[sample_arxiv_paper], interests=[])
    scored = reranker.rerank()
    assert len(scored) == 1
    assert scored[0].score == 5.0  # Default fallback score


@pytest.mark.skip(reason="Requires fastembed model download")
def test_reranker_basic_scoring(sample_arxiv_paper):
    """Test basic paper scoring (integration test, requires model)."""
    reranker = PaperReranker(papers=[sample_arxiv_paper], interests=[_interest()])
    scored = reranker.rerank()
    assert len(scored) == 1
    assert scored[0].score > 0.0
    assert "corpus_similarity" in scored[0].relevance_factors
