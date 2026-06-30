"""Tests for the interests-only reranker (RFC-010 §9).

These tests monkeypatch ``load_encoder`` to return a fake encoder producing
deterministic vectors, so they don't require a fastembed model download. The
fake encoder maps text to a vector whose dimensions encode topic signals, so
we can assert ranking order and relevance factors.

Note: Zotero items no longer have a separate corpus path. They arrive as
``ResearchInterest(source="zotero")`` units (written by the sync step), so the
reranker scores *only* against interests.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from alithia_agent.models import ArxivPaper
from alithia_agent.paperscout.reranker import PaperReranker, weighted_similarity_to_score
from alithia_agent.research_interests import ResearchInterest


class _FakeEncoder:
    """Encodes text into a 4-dim vector where each dim counts a topic token.

    dim0 = 'contrastive'/'vision'/'language' tokens (multimodal signal)
    dim1 = 'graph'/'network' tokens (unrelated signal)
    dim2 = 'reinforcement' tokens
    dim3 = constant padding
    """

    def embed(self, texts: list[str]):
        for t in texts:
            v = np.zeros(4, dtype=float)
            words = t.lower().split()
            v[0] = sum(1 for w in words if w in {"contrastive", "vision", "language"})
            v[1] = sum(1 for w in words if w in {"graph", "network"})
            v[2] = sum(1 for w in words if "reinforcement" in w)
            v[3] = 1.0
            yield v


def _paper(title: str, topic: str) -> ArxivPaper:
    summary = " ".join([topic] * 30)
    return ArxivPaper(
        title=title,
        summary=summary,
        authors=["a"],
        arxiv_id=title.lower().replace(" ", ""),
        pdf_url="u",
        published_date=datetime(2024, 1, 1),
    )


def _interest(
    title: str,
    body_topic: str,
    *,
    weight: float = 1.0,
    tags=None,
    source: str = "manual",
) -> ResearchInterest:
    body = " ".join([body_topic] * 30)
    return ResearchInterest(
        title=title,
        body=body,
        tags=tags or [],
        weight=weight,
        source=source,  # type: ignore[arg-type]
    )


@pytest.fixture
def patched_encoder():
    with patch(
        "alithia_agent.paperscout.reranker.load_encoder",
        return_value=(_FakeEncoder(), "fastembed"),
    ):
        yield


def test_interests_only_ranks_by_interest_similarity(patched_encoder):
    """Interests drive ranking (RFC-010 §9 — interests-only must NOT fall
    through to the all-5.0 default)."""
    mm_paper = _paper("Multimodal Paper", "contrastive vision language")
    rl_paper = _paper("RL Paper", "reinforcement learning")
    interests = [_interest("Multimodal", "contrastive vision language")]

    scored = PaperReranker(papers=[rl_paper, mm_paper], interests=interests).rerank()

    assert len(scored) == 2
    # The multimodal paper must rank above the RL paper.
    assert scored[0].paper.title == "Multimodal Paper"
    assert scored[0].score > scored[1].score
    assert scored[0].relevance_factors["interests_count"] == 1


def test_mixed_manual_and_zotero_source_units_unified(patched_encoder):
    """Hand-written (manual) and Zotero-synced (source=zotero) interest units
    are both scored as ResearchInterest rows in one corpus."""
    mm_paper = _paper("Multimodal Paper", "contrastive vision language")
    interests = [
        _interest("Multimodal", "contrastive vision language", source="manual"),
        _interest("GraphPaper", "graph network", source="zotero"),
    ]

    scored = PaperReranker(papers=[mm_paper], interests=interests).rerank()

    assert len(scored) == 1
    f = scored[0].relevance_factors
    assert f["interests_count"] == 2
    assert f["corpus_size"] == 2  # both units embedded


def test_weight_amplifies_interest_contribution(patched_encoder):
    """A higher-weight interest reports a larger interest_weight factor
    (RFC-010 §9.2)."""
    mm_paper = _paper("Multimodal Paper", "contrastive vision language")

    f_low = (
        PaperReranker(
            papers=[mm_paper],
            interests=[_interest("MM-low", "contrastive vision language", weight=1.0)],
        )
        .rerank()[0]
        .relevance_factors["interest_weight"]
    )
    f_high = (
        PaperReranker(
            papers=[mm_paper],
            interests=[_interest("MM-high", "contrastive vision language", weight=5.0)],
        )
        .rerank()[0]
        .relevance_factors["interest_weight"]
    )
    assert f_high > f_low
    assert f_high == 5.0
    assert f_low == 1.0


def test_empty_interests_returns_default(patched_encoder):
    paper = _paper("Any", "contrastive vision language")
    scored = PaperReranker(papers=[paper], interests=[]).rerank()
    assert len(scored) == 1
    assert scored[0].score == 5.0
    assert scored[0].relevance_factors.get("default") == 5.0


def test_fallback_rank_draws_keywords_from_interest_tags():
    """When no encoder is available, _fallback_rank pulls keywords from
    interest titles/tags (RFC-010 §9.4)."""
    mm_paper = _paper("Multimodal contrastive", "anything")
    interests = [_interest("Multimodal", "irrelevant body", tags=["contrastive", "visionlanguage"])]

    with patch(
        "alithia_agent.paperscout.reranker.load_encoder",
        return_value=(None, "fallback"),
    ):
        scored = PaperReranker(papers=[mm_paper], interests=interests).rerank()

    assert len(scored) == 1
    # 'contrastive' is a >4-char keyword from the interest tags; the paper
    # title contains it → overlap bonus → score > 5.0 base.
    assert scored[0].score > 5.0
    # relevance_factors is dict[str, float]; the bool fallback flag coerces to 1.0.
    assert scored[0].relevance_factors.get("fallback")


def test_interest_without_date_sorts_to_recency_bottom(patched_encoder):
    """Manual units without date_added should not crash and should sort to the
    recency bottom (lowest time-decay weight). Smoke test: runs and ranks."""
    mm_paper = _paper("Multimodal Paper", "contrastive vision language")
    dated = _interest("Dated", "contrastive vision language").model_copy(
        update={"date_added": "2024-01-01"}
    )
    interests = [
        dated,
        _interest("Undated", "contrastive vision language"),
    ]
    scored = PaperReranker(papers=[mm_paper], interests=interests).rerank()
    assert len(scored) == 1
    assert scored[0].relevance_factors["interests_count"] == 2


def test_weighted_similarity_to_score_maps_cosine_range():
    assert weighted_similarity_to_score(-1.0) == 0.0
    assert weighted_similarity_to_score(0.0) == 5.0
    assert weighted_similarity_to_score(1.0) == 10.0


def test_opposing_embeddings_produce_valid_scores():
    """Negative cosine similarity must not fail ScoredPaper validation."""

    class _OpposingEncoder:
        def embed(self, texts: list[str]):
            for t in texts:
                if "interest corpus marker" in t.lower():
                    yield np.array([1.0, 0.0, 0.0, 0.0])
                else:
                    yield np.array([-1.0, 0.0, 0.0, 0.0])

    paper = _paper("Unrelated Paper", "paper abstract text")
    interests = [
        _interest(
            "Interest",
            "interest corpus marker " + ("text " * 30),
        )
    ]

    with patch(
        "alithia_agent.paperscout.reranker.load_encoder",
        return_value=(_OpposingEncoder(), "fastembed"),
    ):
        scored = PaperReranker(papers=[paper], interests=interests).rerank()

    assert len(scored) == 1
    assert 0.0 <= scored[0].score <= 10.0
    assert scored[0].score == 0.0
