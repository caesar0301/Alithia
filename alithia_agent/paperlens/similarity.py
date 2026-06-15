"""Similarity engine for PaperLens.

FastEmbed ONNX embeddings for semantic similarity matching.
"""

from __future__ import annotations

import logging
import os

import numpy as np

from alithia_agent.models import AcademicPaper, ScoredPaper

logger = logging.getLogger(__name__)

# Default embedding model (same as soothe for consistency)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_cache_dir() -> str:
    """Get Alithia's embedding model cache directory.

    Priority:
    1. ALITHIA_EMBEDDING_CACHE env var (for Docker builds)
    2. Default: ~/.cache/alithia/models/embeddings
    """
    env_cache = os.environ.get("ALITHIA_EMBEDDING_CACHE")
    if env_cache:
        return env_cache
    return os.path.join(os.path.expanduser("~"), ".cache", "alithia", "models", "embeddings")


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector.
        vec2: Second embedding vector.

    Returns:
        Similarity score in range [0, 1].
    """
    if vec1 is None or vec2 is None:
        return 0.0

    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


class SimilarityEngine:
    """FastEmbed similarity engine.

    Encodes query and papers, computes cosine similarity.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        cache_dir: str | None = None,
    ):
        """Initialize similarity engine.

        Args:
            model_name: FastEmbed model name.
            cache_dir: Directory for caching models.
        """
        self.model_name = model_name
        self.cache_dir = cache_dir or get_embedding_cache_dir()

        # Set HF mirror for reliable downloads (especially in China)
        if "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        # Load model
        try:
            from fastembed import TextEmbedding

            logger.info(f"Loading FastEmbed model: {model_name}")
            self.model = TextEmbedding(model_name=model_name, cache_dir=self.cache_dir)
            logger.info("FastEmbed model loaded successfully")
        except ImportError as e:
            raise ImportError("fastembed not installed. Install with: pip install fastembed") from e

    def encode(self, texts: list[str]) -> list[np.ndarray]:
        """Encode texts to embedding vectors.

        Args:
            texts: List of text strings to encode.

        Returns:
            List of embedding vectors (numpy arrays).
        """
        if not texts:
            return []
        embeddings = list(self.model.embed(texts))
        return [np.array(emb) for emb in embeddings]

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
                ScoredPaper(paper=paper, score=5.0, relevance_factors={"default": 5.0})
                for paper in papers
            ]

        logger.info(f"Calculating similarity for {len(papers)} papers")

        # Encode query
        query_embeddings = self.encode([query])
        if not query_embeddings:
            logger.warning("Failed to encode query")
            return []
        query_embedding = query_embeddings[0]

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
        paper_embeddings = self.encode(paper_texts)

        # Calculate cosine similarities
        similarities = []
        for paper_emb in paper_embeddings:
            sim = cosine_similarity(query_embedding, paper_emb)
            similarities.append(sim)

        # Create ScoredPaper objects
        scored_papers: list[ScoredPaper] = []
        for paper, sim in zip(valid_papers, similarities):
            scored = ScoredPaper(
                paper=paper,
                score=float(sim * 10),  # Scale to 0-10 range
                relevance_factors={
                    "corpus_similarity": float(sim * 10),
                    "raw_similarity": float(sim),
                },
            )
            scored_papers.append(scored)

        # Sort by score (highest first)
        scored_papers.sort(key=lambda x: x.score, reverse=True)

        if scored_papers:
            logger.info(f"Top score: {scored_papers[0].score:.2f} ({scored_papers[0].paper_title})")

        return scored_papers


__all__ = ["SimilarityEngine", "get_embedding_cache_dir", "EMBEDDING_MODEL_NAME"]
