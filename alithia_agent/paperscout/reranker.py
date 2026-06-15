"""Paper reranking using FastEmbed embeddings.

Ranks ArXiv papers by relevance to user's Zotero library
using FastEmbed ONNX embeddings and time-decay weighting.

Model cache is isolated from Soothe framework.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from alithia_agent.models import ArxivPaper, ScoredPaper, ZoteroPaper

logger = logging.getLogger(__name__)

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
        corpus: list[ZoteroPaper],
        cache_dir: str | None = None,
    ):
        """Initialize reranker.

        Args:
            papers: ArXiv papers to rank.
            corpus: User's Zotero library.
            cache_dir: Cache directory for models.
        """
        self.papers = papers
        self.corpus = corpus
        self.cache_dir = cache_dir or str(get_model_cache_dir())

        if not self.papers:
            logger.warning("No papers provided for reranking")
        if not self.corpus:
            logger.warning("Empty corpus provided for reranking")

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

        if not self.corpus:
            logger.warning("Empty corpus, returning papers with default scores")
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
            # Sort corpus by date (newest first)
            sorted_corpus = sorted(
                [p for p in self.corpus if p.date_added],
                key=lambda x: x.date_added or datetime.min,
                reverse=True,
            )

            if not sorted_corpus:
                logger.warning("No valid corpus items after filtering")
                return [
                    ScoredPaper(paper=p, score=5.0, relevance_factors={"fallback": 5.0})
                    for p in self.papers
                ]

            # Time-decay weighting
            time_decay_weight = 1 / (1 + np.log10(np.arange(len(sorted_corpus)) + 1))
            time_decay_weight = time_decay_weight / time_decay_weight.sum()

            # Extract corpus abstracts
            corpus_texts: list[str] = []
            valid_indices: list[int] = []
            for idx, paper in enumerate(sorted_corpus):
                if paper.abstract and len(paper.abstract.strip()) > 50:
                    corpus_texts.append(paper.abstract)
                    valid_indices.append(idx)

            if not corpus_texts:
                logger.warning("No valid abstracts in corpus")
                return [
                    ScoredPaper(paper=p, score=5.0, relevance_factors={"no_corpus_text": 5.0})
                    for p in self.papers
                ]

            # Update weights for valid items
            time_decay_weight = time_decay_weight[valid_indices]
            time_decay_weight = time_decay_weight / time_decay_weight.sum()

            # Encode corpus
            logger.info(f"Encoding {len(corpus_texts)} corpus abstracts")
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

            # Weighted scores
            scores = (similarities * time_decay_weight).sum(axis=1) * 10

            # Create scored papers
            scored_papers: list[ScoredPaper] = []
            for arxiv_paper, score, sim_row in zip(valid_papers, scores, similarities):
                scored = ScoredPaper(
                    paper=arxiv_paper,
                    score=float(score),
                    relevance_factors={
                        "corpus_similarity": float(score),
                        "corpus_size": len(corpus_texts),
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

        Uses title keyword matching and recency.
        """
        logger.info("Using keyword-based fallback ranking")

        # Get keywords from corpus titles
        corpus_keywords: set[str] = set()
        for zotero_paper in self.corpus:
            if zotero_paper.title:
                # Extract significant words from title
                words = zotero_paper.title.lower().split()
                for w in words:
                    if len(w) > 4 and w not in {"the", "for", "with", "from", "this", "that"}:
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
