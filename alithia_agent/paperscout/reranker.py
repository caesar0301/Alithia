"""Paper reranking using sentence embeddings.

Ranks ArXiv papers by relevance to user's Zotero library
using sentence transformer embeddings and time-decay weighting.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import numpy as np

from alithia_agent.models import ArxivPaper, ZoteroPaper, ScoredPaper

logger = logging.getLogger(__name__)


class PaperReranker:
    """Paper reranking with sentence transformer embeddings.

    Features:
    - Sentence Transformer embeddings (all-MiniLM-L6-v2)
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
        self.cache_dir = cache_dir or os.environ.get(
            "SENTENCE_TRANSFORMERS_HOME",
            "/tmp/alithia_models",
        )

        if not self.papers:
            logger.warning("No papers provided for reranking")
        if not self.corpus:
            logger.warning("Empty corpus provided for reranking")

    def rerank(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 32,
    ) -> list[ScoredPaper]:
        """Rerank papers using sentence transformers.

        Args:
            model_name: Sentence transformer model.
            batch_size: Batch size for encoding.

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

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading sentence transformer: {model_name}")
            encoder = SentenceTransformer(model_name, cache_folder=self.cache_dir)

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
            corpus_embeddings = encoder.encode(
                corpus_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
            )

            # Extract paper summaries
            paper_texts: list[str] = []
            valid_papers: list[ArxivPaper] = []
            for paper in self.papers:
                if paper.summary and len(paper.summary.strip()) > 50:
                    paper_texts.append(paper.get_searchable_text())
                    valid_papers.append(paper)

            if not paper_texts:
                logger.warning("No valid paper summaries")
                return []

            # Encode papers
            logger.info(f"Encoding {len(paper_texts)} paper summaries")
            paper_embeddings = encoder.encode(
                paper_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
            )

            # Calculate cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity(paper_embeddings, corpus_embeddings)

            # Weighted scores
            scores = (similarities * time_decay_weight).sum(axis=1) * 10

            # Create scored papers
            scored_papers: list[ScoredPaper] = []
            for paper, score, sim_row in zip(valid_papers, scores, similarities):
                scored = ScoredPaper(
                    paper=paper,
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
            return [
                ScoredPaper(paper=p, score=5.0, relevance_factors={"error_fallback": 5.0})
                for p in self.papers
            ]


__all__ = ["PaperReranker"]