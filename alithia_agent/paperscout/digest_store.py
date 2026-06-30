"""Persist daily PaperScout digest metadata for offline analysis.

Stores scored paper metadata (rank, score, TLDR, URLs, etc.) per notification
date. Does not persist rendered email HTML.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from alithia_agent.models import AcademicPaper, ArxivPaper, ScoredPaper
from alithia_agent.paperscout.state import PaperScoutRuntimeConfig

DIGEST_KEY_PREFIX = "paperscout:digest"


def digest_storage_key(user_id: str, digest_date: str) -> str:
    """KV key for a user's daily digest record."""
    return f"{DIGEST_KEY_PREFIX}:{user_id}:{digest_date}"


def digest_key_prefix(user_id: str) -> str:
    """Prefix for listing all digest keys for a user."""
    return f"{DIGEST_KEY_PREFIX}:{user_id}:"


def _iso_datetime(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


def serialize_scored_paper(scored: ScoredPaper, rank: int) -> dict[str, Any]:
    """Serialize one ranked paper for storage (no HTML, no LaTeX source)."""
    paper = scored.paper
    record: dict[str, Any] = {
        "rank": rank,
        "score": scored.score,
        "relevance_factors": dict(scored.relevance_factors),
        "title": paper.title,
        "authors": list(paper.authors),
    }

    if isinstance(paper, ArxivPaper):
        record.update(
            {
                "arxiv_id": paper.arxiv_id,
                "summary": paper.summary,
                "tldr": paper.tldr,
                "pdf_url": paper.pdf_url,
                "published_date": _iso_datetime(paper.published_date),
                "categories": list(paper.categories),
                "affiliations": list(paper.affiliations) if paper.affiliations else None,
                "code_url": paper.code_url,
                "journal_ref": paper.journal_ref,
                "comments": paper.comments,
            }
        )
    elif isinstance(paper, AcademicPaper):
        record.update(
            {
                "arxiv_id": paper.arxiv_id,
                "summary": paper.abstract,
                "pdf_url": paper.source_url,
                "published_date": str(paper.year) if paper.year else None,
                "categories": list(paper.keywords),
            }
        )
    else:
        record["arxiv_id"] = getattr(paper, "arxiv_id", None)
        record["summary"] = getattr(paper, "summary", None) or getattr(paper, "abstract", None)
        record["pdf_url"] = getattr(paper, "pdf_url", None) or getattr(paper, "source_url", None)

    return record


def build_daily_digest_record(
    scored_papers: list[ScoredPaper],
    *,
    digest_date: str,
    config: PaperScoutRuntimeConfig,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable daily digest record."""
    metrics = dict(metrics or {})
    analysis_metrics = {
        key: metrics[key]
        for key in (
            "source",
            "arxiv_found",
            "arxiv_new",
            "papers_scored",
            "papers_selected",
            "avg_score",
            "tldrs_generated",
            "affiliations_extracted",
            "interests_count",
        )
        if key in metrics
    }

    return {
        "digest_date": digest_date,
        "saved_at": datetime.now().isoformat(),
        "source": metrics.get("source", config.source),
        "query": config.query,
        "arxiv_categories": list(config.arxiv_categories),
        "paper_count": len(scored_papers),
        "metrics": analysis_metrics,
        "papers": [
            serialize_scored_paper(sp, rank=index)
            for index, sp in enumerate(scored_papers, start=1)
        ],
    }


async def save_daily_digest(
    store: Any,
    user_id: str,
    record: dict[str, Any],
) -> str:
    """Persist a daily digest record. Returns the storage key used."""
    digest_date = record["digest_date"]
    key = digest_storage_key(user_id, digest_date)
    await store.save(key, record)
    return key


async def load_daily_digest(
    store: Any,
    user_id: str,
    digest_date: str,
) -> dict[str, Any] | None:
    """Load a persisted daily digest record."""
    return await store.load(digest_storage_key(user_id, digest_date))


async def list_daily_digest_dates(store: Any, user_id: str) -> list[str]:
    """List digest dates (YYYY-MM-DD) persisted for a user, sorted ascending."""
    prefix = digest_key_prefix(user_id)
    keys = await store.list_keys(prefix)
    dates = [key.rsplit(":", 1)[-1] for key in keys]
    return sorted(dates)


__all__ = [
    "DIGEST_KEY_PREFIX",
    "build_daily_digest_record",
    "digest_key_prefix",
    "digest_storage_key",
    "list_daily_digest_dates",
    "load_daily_digest",
    "save_daily_digest",
    "serialize_scored_paper",
]
