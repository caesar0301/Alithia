"""Similarity engine for PaperLens.

Sentence transformer embeddings for semantic similarity matching.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

from alithia_agent.models import AcademicPaper, ScoredPaper

logger = logging.getLogger(__name__)


class SimilarityEngine:
    """Sentence transformer similarity engine.

    Encodes query and papers, computes cosine similarity.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        use_gpu: bool = False,
        cache_dir: str | None = None,
    ):
        """Initialize similarity engine.

        Args:
            model_name: Sentence transformer model name.
            use_gpu: Use GPU for computation.
            cache_dir: Directory for caching models.
        """
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.cache_dir = cache_dir or os.environ.get(
            "SENTENCE_TRANSFORMERS_HOME",
            "/tmp/alithia_models",
        )

        # Determine device
        device = "cpu"
        if use_gpu:
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    logger.info("Using GPU for embeddings")
                else:
                    logger.warning("GPU requested but CUDA not available, using CPU")
            except ImportError:
                logger.warning("torch not available, using CPU")

        # Load model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence transformer: {model_name} (device: {device})")
            self.model = SentenceTransformer(model_name, device=device, cache_folder=self.cache_dir)
            logger.info("Sentence transformer loaded successfully")
        except ImportError as e:
            raise ImportError(
                f"sentence-transformers not installed. "
                f"Install with: pip install sentence-transformers"
            ) from e

    def calculate_scores(
        self,
        query: str,
        papers: list[AcademicPaper],
    ) -> list[ScoredPaper]:
        """Calculate similarity scores for all papers.

        Args:
            query: Research topic/question string.
            papers: List of AcademicPaper objects.

        Returns:
            List of ScoredPaper objects sorted by score (highest first).
        """
        if not papers:
            logger.warning("No papers to score")
            return []

        if not query:
            logger.warning("Empty query, returning papers with default scores")
            return [
                ScoredPaper(paper=p, score=5.0, relevance_factors={"default": 5.0})
                for paper in papers
            ]

        logger.info(f"Calculating similarity for {len(papers)} papers")

        # Encode query
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        # Extract searchable texts
        paper_texts = []
        valid_papers: list[AcademicPaper] = []
        for paper in papers:
            text = paper.get_searchable_text()
            if text and len(text.strip()) > 50:  # Require minimum content
                paper_texts.append(text)
                valid_papers.append(paper)
            else:
                logger.warning(f"Paper has insufficient text: {paper.display_title}")

        if not paper_texts:
            logger.warning("No valid paper texts to encode")
            return []

        # Encode papers (batch)
        logger.info(f"Encoding {len(paper_texts)} paper texts")
        paper_embeddings = self.model.encode(
            paper_texts,
            convert_to_tensor=True,
            batch_size=32,
            show_progress_bar=False,
        )

        # Calculate cosine similarity
        from sentence_transformers import util
        similarities = util.cos_sim(query_embedding, paper_embeddings)[0]

        # Create ScoredPaper objects
        scored_papers: list[ScoredPaper] = []
        for paper, score, sim_row in zip(valid_papers, similarities, similarities):
            scored = ScoredPaper(
                paper=paper,
                score=float(score * 10),  # Scale to 0-10 range
                relevance_factors={
                    "corpus_similarity": float(score * 10),
                    "max_similarity": float(np.max(sim_row.cpu().numpy())),
                },
            )
            scored_papers.append(scored)

        # Sort by score (highest first)
        scored_papers.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"Top score: {scored_papers[0].score:.2f} ({scored_papers[0].paper_title})")

        return scored_papers


__all__ = ["SimilarityEngine"]