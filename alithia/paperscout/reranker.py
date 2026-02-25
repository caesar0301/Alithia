"""
Paper recommendation and reranking utilities.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np

from alithia.models.zotero_paper import ZoteroPaper

from .models import ArxivPaper, ScoredPaper

logger = logging.getLogger(__name__)


class PaperReranker:
    """
    Paper reranking system with multiple strategies.

    Supports:
    - Sentence Transformer embeddings (recommended, default)
    - FlashRank reranking (optional, requires flashrank)

    Features:
    - Time-decay weighting for corpus recency
    - Batch processing for efficiency
    - Error handling and fallback scoring
    """

    def __init__(
        self,
        papers: List[ArxivPaper],
        corpus: Union[List[ZoteroPaper], List[Dict[str, Any]]],
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize the reranker.

        Args:
            papers: List of papers to rank
            corpus: User's research corpus (ZoteroPaper list or legacy raw dicts)
            cache_dir: Directory for caching models
        """
        self.papers = papers
        self.corpus = corpus
        self.cache_dir = cache_dir or "/tmp/alithia_models"

        if not self.papers:
            logger.warning("No papers provided for reranking")
        if not self.corpus:
            logger.warning("Empty corpus provided for reranking")

    def rerank_flashrank(self, model_name: str = "ms-marco-MiniLM-L-12-v2") -> List[ScoredPaper]:
        """
        Rerank papers based on relevance to user's research corpus.

        Args:
            papers: List of papers to score
            corpus: User's Zotero corpus for comparison
            model_name: FlashRank model to use (default: ms-marco-MiniLM-L-12-v2)

        Returns:
            List of scored papers sorted by relevance
        """
        try:
            from flashrank import Ranker, RerankRequest
        except ImportError:
            raise ImportError("FlashRank is not installed. Please install it using `pip install flashrank`.")

        if not self.papers or not self.corpus:
            return [ScoredPaper(paper=paper, score=0.0) for paper in self.papers]

        # Initialize FlashRank ranker
        ranker = Ranker(model_name=model_name, cache_dir="/tmp/flashrank_cache")

        # Sort corpus by date (newest first)
        sorted_corpus = sorted(
            self.corpus, key=lambda x: datetime.strptime(x["data"]["dateAdded"], "%Y-%m-%dT%H:%M:%SZ"), reverse=True
        )

        # Calculate time decay weights
        time_decay_weight = 1 / (1 + np.log10(np.arange(len(sorted_corpus)) + 1))
        time_decay_weight = time_decay_weight / time_decay_weight.sum()

        # Prepare corpus abstracts as passages
        corpus_passages = [{"text": paper["data"]["abstractNote"]} for paper in sorted_corpus]

        # Score each paper against the entire corpus
        scored_papers = []
        for paper in self.papers:
            # Create rerank request for this paper against all corpus passages
            rerank_request = RerankRequest(query=paper.summary, passages=corpus_passages)

            # Get reranking results
            results = ranker.rerank(rerank_request)

            # Create a mapping from text to corpus index
            text_to_idx = {paper["data"]["abstractNote"]: idx for idx, paper in enumerate(sorted_corpus)}

            # Calculate weighted score based on corpus relevance and time decay
            weighted_scores = []
            for result in results:
                relevance_score = result["score"]
                # Find which corpus paper this result corresponds to
                idx = text_to_idx[result["text"]]
                weighted_score = relevance_score * time_decay_weight[idx]
                weighted_scores.append(weighted_score)

            # Sum weighted scores and scale
            final_score = sum(weighted_scores) * 10

            scored_paper = ScoredPaper(
                paper=paper,
                score=float(final_score),
                relevance_factors={"corpus_similarity": float(final_score), "corpus_size": len(self.corpus)},
            )
            scored_papers.append(scored_paper)

        # Sort by score (highest first)
        scored_papers.sort(key=lambda x: x.score, reverse=True)

        return scored_papers

    def rerank_sentence_transformer(
        self, model_name: str = "avsolatorio/GIST-small-Embedding-v0", batch_size: int = 32, show_progress: bool = False
    ) -> List[ScoredPaper]:
        """
        Rerank papers using sentence transformers.

        Args:
            model_name: Sentence transformer model to use
            batch_size: Batch size for encoding
            show_progress: Show progress bar during encoding

        Returns:
            List of scored papers sorted by relevance
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "SentenceTransformer is not installed. Please install it using `pip install sentence-transformers`."
            )

        if not self.papers:
            logger.warning("No papers to rerank")
            return []

        if not self.corpus:
            logger.warning("Empty corpus, returning papers with default scores")
            return [ScoredPaper(paper=paper, score=5.0, relevance_factors={"default": 5.0}) for paper in self.papers]

        try:
            logger.info(f"Loading sentence transformer model: {model_name}")
            encoder = SentenceTransformer(model_name, cache_folder=self.cache_dir)

            # Sort corpus by date (newest first), handling both ZoteroPaper and dicts
            sorted_corpus = []
            for item in self.corpus:
                try:
                    if isinstance(item, ZoteroPaper):
                        if item.date_added:
                            sorted_corpus.append(item)
                    else:
                        date_str = item.get("data", {}).get("dateAdded", "")
                        if date_str:
                            sorted_corpus.append(item)
                except Exception as e:
                    logger.warning(f"Error processing corpus item: {e}")
                    continue

            def _get_date(item):
                if isinstance(item, ZoteroPaper):
                    return item.date_added or datetime.min
                return datetime.strptime(item["data"]["dateAdded"], "%Y-%m-%dT%H:%M:%SZ")

            sorted_corpus.sort(key=_get_date, reverse=True)

            if not sorted_corpus:
                logger.warning("No valid corpus items after filtering")
                return [
                    ScoredPaper(paper=paper, score=5.0, relevance_factors={"fallback": 5.0}) for paper in self.papers
                ]

            time_decay_weight = 1 / (1 + np.log10(np.arange(len(sorted_corpus)) + 1))
            time_decay_weight = time_decay_weight / time_decay_weight.sum()

            # Extract and validate corpus texts (ZoteroPaper or raw dict)
            corpus_texts = []
            valid_corpus_indices = []
            for idx, paper in enumerate(sorted_corpus):
                if isinstance(paper, ZoteroPaper):
                    abstract = paper.abstract
                else:
                    abstract = paper.get("data", {}).get("abstractNote", "")
                if abstract and len(abstract.strip()) > 0:
                    corpus_texts.append(abstract)
                    valid_corpus_indices.append(idx)

            if not corpus_texts:
                logger.warning("No valid abstracts in corpus")
                return [
                    ScoredPaper(paper=paper, score=5.0, relevance_factors={"no_corpus_text": 5.0})
                    for paper in self.papers
                ]

            # Update time decay weights for valid corpus items only
            time_decay_weight = time_decay_weight[valid_corpus_indices]
            time_decay_weight = time_decay_weight / time_decay_weight.sum()

            logger.info(f"Encoding {len(corpus_texts)} corpus abstracts")
            corpus_embeddings = encoder.encode(
                corpus_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_tensor=False,
                normalize_embeddings=True,  # Normalize for cosine similarity
            )

            # Extract and validate paper texts
            paper_texts = []
            valid_papers = []
            for paper in self.papers:
                if paper.summary and len(paper.summary.strip()) > 0:
                    paper_texts.append(paper.summary)
                    valid_papers.append(paper)
                else:
                    logger.warning(f"Paper {paper.arxiv_id} has no summary, skipping")

            if not paper_texts:
                logger.warning("No valid paper summaries to rank")
                return []

            logger.info(f"Encoding {len(paper_texts)} paper summaries")
            paper_embeddings = encoder.encode(
                paper_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_tensor=False,
                normalize_embeddings=True,
            )

            # Calculate similarity scores (cosine similarity with normalized embeddings)
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity(paper_embeddings, corpus_embeddings)

            # Calculate weighted scores with time decay
            scores = (similarities * time_decay_weight).sum(axis=1) * 10

            # Create scored papers
            scored_papers = []
            for paper, score, sim_vector in zip(valid_papers, scores, similarities):
                scored_paper = ScoredPaper(
                    paper=paper,
                    score=float(score),
                    relevance_factors={
                        "corpus_similarity": float(score),
                        "corpus_size": len(corpus_texts),
                        "max_similarity": float(sim_vector.max()),
                        "mean_similarity": float(sim_vector.mean()),
                    },
                )
                scored_papers.append(scored_paper)

            # Sort by score (highest first)
            scored_papers.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"Successfully reranked {len(scored_papers)} papers")
            return scored_papers

        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            # Fallback to basic scoring
            logger.info("Using fallback scoring")
            return [
                ScoredPaper(paper=paper, score=5.0, relevance_factors={"error_fallback": 5.0}) for paper in self.papers
            ]
