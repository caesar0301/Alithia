"""Paper reranking using FastEmbed embeddings.

Ranks ArXiv papers by relevance to the user's research-interests knowledge
base (RFC-010): a directory of Markdown knowledge units — hand-written
interests plus Zotero items synced into zotero/*.md. All units are
``ResearchInterest`` objects normalized into one corpus before a single
embedding pass with time-decay weighting; see RFC-010 §9.

Model cache is isolated from Soothe framework.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

from alithia_agent.models import ArxivPaper, ScoredPaper
from alithia_agent.research_interests import ResearchInterest

logger = logging.getLogger(__name__)


@dataclass
class _CorpusUnit:
    """A homogeneous row in the unified corpus (RFC-010 §9.1).

    Both interest units and Zotero papers are normalized into this shape
    before embedding, so the time-decay + cosine algorithm runs unchanged.
    """

    text: str
    weight: float
    date_added: datetime | None
    origin: Literal["manual", "zotero"]  # ResearchInterest.source provenance


# Default embedding model (same as soothe for consistency)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_model_cache_dir() -> Path:
    """Get Alithia's own model cache directory (isolated from Soothe).

    Priority:
    1. ALITHIA_EMBEDDING_CACHE env var (for Docker builds)
    2. Default: ~/.cache/alithia/models/embeddings
    """
    env_cache = os.environ.get("ALITHIA_EMBEDDING_CACHE")
    if env_cache:
        return Path(env_cache)
    return Path.home() / ".cache" / "alithia" / "models" / "embeddings"


def load_encoder(model_name: str, cache_dir: Path) -> tuple[Any | None, str]:
    """Load FastEmbed encoder.

    Args:
        model_name: Model name to load.
        cache_dir: Cache directory.

    Returns:
        Tuple of (encoder, source) or (None, "fallback").
    """
    # Set HF mirror for reliable downloads (especially in China)
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    try:
        from fastembed import TextEmbedding

        logger.info(f"Loading FastEmbed encoder: {model_name}")
        logger.info(f"Cache directory: {cache_dir}")

        encoder = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))
        logger.info("FastEmbed encoder loaded successfully")
        return encoder, "fastembed"

    except ImportError:
        logger.warning("fastembed not installed, using fallback scoring")
        return None, "fallback"
    except Exception as e:
        logger.error(f"Failed to load encoder: {e}")
        logger.warning("Will use fallback scoring instead")
        return None, "fallback"


def encode_texts(encoder: Any, texts: list[str]) -> list[np.ndarray]:
    """Encode texts to embedding vectors using FastEmbed.

    Args:
        encoder: Loaded TextEmbedding instance.
        texts: Input strings to embed.

    Returns:
        List of embedding vectors as numpy arrays.
    """
    if not texts:
        return []
    embeddings = list(encoder.embed(texts))
    return [np.array(emb) for emb in embeddings]


def _to_datetime(value: date | datetime | str | None) -> datetime | None:
    """Normalize a date/datetime/ISO-string to a datetime for recency sorting.

    A bare ``date`` (interest units carry ``date_added: date``) is promoted to
    midnight so it sorts alongside the datetimes Zotero provides. An ISO
    ``YYYY-MM-DD`` string is parsed defensively — ``model_copy`` can bypass
    validation and leave a raw string on the field. None sorts to the recency
    bottom (lowest time-decay weight).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            try:
                d = datetime.fromisoformat(s[:10])
                return d
            except ValueError:
                return None
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


class PaperReranker:
    """Paper reranking with FastEmbed embeddings.

    Features:
    - FastEmbed ONNX embeddings (all-MiniLM-L6-v2)
    - Time-decay weighting for corpus recency
    - Fallback scoring for edge cases
    """

    def __init__(
        self,
        papers: list[ArxivPaper],
        *,
        interests: list[ResearchInterest] | None = None,
        cache_dir: str | None = None,
    ):
        """Initialize reranker.

        Args:
            papers: ArXiv papers to rank.
            interests: Research-interest knowledge units (RFC-010) — the unified
                corpus: hand-written units plus Zotero items synced into
                zotero/*.md. This is the ONLY knowledge source the reranker
                scores against; the legacy Zotero-paper corpus slot was removed.
            cache_dir: Cache directory for models.
        """
        self.papers = papers
        self.interests = interests or []
        self.cache_dir = cache_dir or str(get_model_cache_dir())

        if not self.papers:
            logger.warning("No papers provided for reranking")
        if not self.interests:
            logger.warning("No research interests provided for reranking")

    def rerank(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        batch_size: int = 32,
    ) -> list[ScoredPaper]:
        """Rerank papers using FastEmbed.

        Args:
            model_name: FastEmbed model.
            batch_size: Batch size for encoding (not used in fastembed, kept for API compat).

        Returns:
            List of ScoredPaper sorted by relevance (highest first).
        """
        if not self.papers:
            logger.warning("No papers to rerank")
            return []

        if not self.interests:
            logger.warning("No interests, returning papers with default scores")
            return [
                ScoredPaper(paper=p, score=5.0, relevance_factors={"default": 5.0})
                for p in self.papers
            ]

        # Load encoder
        encoder, source = load_encoder(model_name, Path(self.cache_dir))

        if encoder is None:
            logger.warning("Using fallback scoring (no embedding model available)")
            return self._fallback_rank()

        try:
            # Build the unified corpus (RFC-010 §9.1): every knowledge unit is
            # a ResearchInterest — hand-written (source=manual) or synced from
            # Zotero (source=zotero). Each produces one _CorpusUnit row. Units
            # without a date_added sort to the recency bottom (lowest decay).
            units: list[_CorpusUnit] = []

            for interest in self.interests:
                text = interest.get_searchable_text()
                if text and len(text.strip()) > 50:
                    units.append(
                        _CorpusUnit(
                            text=text,
                            weight=max(float(interest.weight), 0.0),
                            date_added=_to_datetime(interest.date_added),
                            origin=interest.source,
                        )
                    )

            # Sort unified corpus by date (newest first); undated units last.
            units.sort(key=lambda u: u.date_added or datetime.min, reverse=True)

            if not units:
                logger.warning("No valid corpus items after filtering")
                return [
                    ScoredPaper(paper=p, score=5.0, relevance_factors={"fallback": 5.0})
                    for p in self.papers
                ]

            # Time-decay weighting over the unified corpus (unchanged algorithm).
            time_decay_weight = 1 / (1 + np.log10(np.arange(len(units)) + 1))
            time_decay_weight = time_decay_weight / time_decay_weight.sum()

            corpus_texts = [u.text for u in units]
            unit_weights = np.array([u.weight for u in units], dtype=float)

            # Encode corpus
            logger.info(
                f"Encoding {len(corpus_texts)} corpus units "
                f"({sum(1 for u in units if u.origin == 'manual')} manual, "
                f"{sum(1 for u in units if u.origin == 'zotero')} zotero)"
            )
            corpus_embeddings = encode_texts(encoder, corpus_texts)
            corpus_matrix = np.array(corpus_embeddings)

            # Extract paper summaries
            paper_texts: list[str] = []
            valid_papers: list[ArxivPaper] = []
            for arxiv_paper in self.papers:
                if arxiv_paper.summary and len(arxiv_paper.summary.strip()) > 50:
                    paper_texts.append(arxiv_paper.get_searchable_text())
                    valid_papers.append(arxiv_paper)

            if not paper_texts:
                logger.warning("No valid paper summaries")
                return []

            # Encode papers
            logger.info(f"Encoding {len(paper_texts)} paper summaries")
            paper_embeddings = encode_texts(encoder, paper_texts)
            paper_matrix = np.array(paper_embeddings)

            # Normalize embeddings for cosine similarity
            corpus_norm = corpus_matrix / np.linalg.norm(corpus_matrix, axis=1, keepdims=True)
            paper_norm = paper_matrix / np.linalg.norm(paper_matrix, axis=1, keepdims=True)

            # Calculate cosine similarity
            similarities = np.dot(paper_norm, corpus_norm.T)

            # Weighted scores: time-decay * per-unit weight (RFC-010 §9.2).
            column_weight = time_decay_weight * unit_weights
            column_weight = column_weight / column_weight.sum()
            scores = (similarities * column_weight).sum(axis=1) * 10

            # Create scored papers
            scored_papers: list[ScoredPaper] = []
            for arxiv_paper, score, sim_row in zip(valid_papers, scores, similarities):
                scored = ScoredPaper(
                    paper=arxiv_paper,
                    score=float(score),
                    relevance_factors={
                        "corpus_similarity": float(score),
                        "corpus_size": len(corpus_texts),
                        "interests_count": len(self.interests),
                        "interest_weight": float(
                            max(
                                (u.weight for u in units if u.origin == "manual"),
                                default=0.0,
                            )
                        ),
                        "max_similarity": float(sim_row.max()),
                        "mean_similarity": float(sim_row.mean()),
                    },
                )
                scored_papers.append(scored)

            # Sort by score
            scored_papers.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"Successfully reranked {len(scored_papers)} papers")
            return scored_papers

        except Exception as e:
            logger.error(f"Reranking error: {e}")
            return self._fallback_rank()

    def _fallback_rank(self) -> list[ScoredPaper]:
        """Fallback ranking when embeddings unavailable.

        Uses keyword matching against the unified corpus (interest titles/tags
        + zotero titles) and recency. See RFC-010 §9.4.
        """
        logger.info("Using keyword-based fallback ranking")

        stopwords = {"the", "for", "with", "from", "this", "that"}

        # Get keywords from interest titles/tags (the unified knowledge base:
        # hand-written interests + Zotero-synced units, all ResearchInterest).
        corpus_keywords: set[str] = set()

        for interest in self.interests:
            for src in (interest.title, " ".join(interest.tags)):
                if src:
                    for w in src.lower().split():
                        if len(w) > 4 and w not in stopwords:
                            corpus_keywords.add(w)

        scored: list[ScoredPaper] = []
        for arxiv_paper in self.papers:
            # Count keyword overlap
            title_words = set(arxiv_paper.title.lower().split()) if arxiv_paper.title else set()
            overlap = len(title_words & corpus_keywords)

            # Base score with keyword bonus
            score = 5.0 + min(overlap * 0.5, 3.0)

            # Recency bonus
            if arxiv_paper.published_date:
                days_old = (datetime.now() - arxiv_paper.published_date.replace(tzinfo=None)).days
                if days_old < 7:
                    score += 1.0
                elif days_old < 30:
                    score += 0.5

            scored.append(
                ScoredPaper(
                    paper=arxiv_paper,
                    score=score,
                    relevance_factors={
                        "keyword_overlap": overlap,
                        "recency_bonus": arxiv_paper.published_date is not None,
                        "fallback": True,
                    },
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored


__all__ = ["PaperReranker", "load_encoder", "get_model_cache_dir", "EMBEDDING_MODEL_NAME"]
