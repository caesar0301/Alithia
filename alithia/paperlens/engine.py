"""
PaperLens - Research Paper Discovery Tool

Given a research topic and a directory of PDF papers, finds the most relevant papers
using semantic similarity matching.
"""

import hashlib
import sys
from pathlib import Path
from typing import List, Optional

from noesium.core.utils import get_logger

from alithia.paperlens.paper_ocr.docling import DoclingOcr
from alithia.storage.base import StorageBackend

logger = get_logger(__name__)

try:
    pass
except ImportError:
    logger.error("docling is not installed. Install with: pip install 'alithia[paperlens]'")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    logger.error("sentence-transformers is not installed. Install with: pip install 'alithia[extra]'")
    sys.exit(1)

from alithia.paperlens.models import (
    AcademicPaper,
    FileMetadata,
    PaperContent,
    PaperMetadata,
)


class PaperLensEngine:
    """Core engine for paper analysis and ranking."""

    def __init__(
        self,
        sbert_model: str = "all-MiniLM-L6-v2",
        force_gpu: bool = False,
        llm=None,
        storage: Optional[StorageBackend] = None,
        user_id: str = "default_user",
    ):
        """
        Initialize the PaperLens engine.

        Args:
            sbert_model: Name of the sentence-transformer model to use.
                       Default is 'all-MiniLM-L6-v2' which is fast and efficient.
            force_gpu: Force GPU usage even if CUDA compatibility issues are detected.
            llm: Optional LLM client for enhanced metadata extraction.
            storage: Optional storage backend for caching parsed papers.
            user_id: User identifier for storage isolation.

        Note:
            This engine uses IBM Granite Docling 258M model for PDF parsing and layout analysis.
        """
        import os

        import torch

        # Handle GPU/CPU device selection
        if force_gpu:
            logger.info("Force GPU mode enabled")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                logger.warning("GPU requested but CUDA not available, falling back to CPU")
        else:
            # Default behavior: use CPU to avoid CUDA compatibility issues
            device = "cpu"
            os.environ["CUDA_VISIBLE_DEVICES"] = ""

        logger.info(f"Loading sentence transformer model: {sbert_model} (device: {device})")
        self.model = SentenceTransformer(sbert_model, device=device)

        self.llm = llm
        self.ocr = DoclingOcr(llm=self.llm)
        self.storage = storage
        self.user_id = user_id

        if self.storage:
            logger.info("Storage backend enabled for paper caching")

        logger.info(f"PaperLens engine initialized (device: {device})")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of a file."""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def _cached_paper_to_model(self, cached_data: dict, pdf_path: Path) -> AcademicPaper:
        """Convert cached paper data back to AcademicPaper model."""
        from datetime import datetime

        file_stats = pdf_path.stat()

        file_metadata = FileMetadata(
            file_path=pdf_path,
            file_name=pdf_path.name,
            file_size=file_stats.st_size,
            last_modified=datetime.fromtimestamp(file_stats.st_mtime),
            md5_hash=cached_data.get("file_hash"),
        )

        paper_metadata = PaperMetadata(
            title=cached_data.get("title"),
            authors=cached_data.get("authors", []),
            abstract=cached_data.get("abstract"),
        )

        paper_content = PaperContent(
            full_text=cached_data.get("full_text", ""),
            sections=cached_data.get("sections", {}),
            figures=cached_data.get("figures", []),
            tables=cached_data.get("tables", []),
        )

        return AcademicPaper(
            file_metadata=file_metadata,
            paper_metadata=paper_metadata,
            content=paper_content,
            parse_timestamp=datetime.fromisoformat(cached_data.get("parsed_at")),
        )

    def parse_file(self, pdf_path: Path) -> AcademicPaper:
        """
        Parse a single PDF file with caching support.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Parsed AcademicPaper object or None if parsing fails
        """
        # Check cache if storage is available
        if self.storage:
            try:
                file_hash = self._compute_file_hash(pdf_path)
                cached_paper = self.storage.get_parsed_paper(self.user_id, file_hash)

                if cached_paper:
                    logger.info(f"Using cached paper for {pdf_path.name}")
                    return self._cached_paper_to_model(cached_paper, pdf_path)
            except Exception as e:
                logger.warning(f"Failed to check cache for {pdf_path.name}: {e}")

        # Parse the PDF
        paper = self.ocr.parse_file(pdf_path)

        # Cache the result if storage is available
        if paper and self.storage:
            try:
                file_hash = self._compute_file_hash(pdf_path)
                paper_data = {
                    "file_path": str(paper.file_metadata.file_path),
                    "file_name": paper.file_metadata.file_name,
                    "file_hash": file_hash,
                    "title": paper.paper_metadata.title,
                    "authors": paper.paper_metadata.authors,
                    "abstract": paper.paper_metadata.abstract,
                    "full_text": paper.content.full_text,
                    "sections": paper.content.sections,
                    "figures": paper.content.figures,
                    "tables": paper.content.tables,
                }

                self.storage.cache_parsed_paper(self.user_id, paper_data)
                logger.info(f"Cached parsed paper {pdf_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cache parsed paper {pdf_path.name}: {e}")

        return paper

    def scan_pdf_directory(self, directory: Path, recursive: bool = True) -> List[AcademicPaper]:
        """
        Scan a directory for PDF files and parse them.

        Args:
            directory: Directory containing PDF files
            recursive: Whether to search subdirectories

        Returns:
            List of successfully parsed AcademicPaper objects
        """
        logger.info(f"Scanning directory: {directory}")

        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return []

        if not directory.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return []

        # Find all PDF files
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(directory.glob(pattern))
        logger.info(f"Found {len(pdf_files)} PDF files")

        # Parse each PDF
        papers = []
        for pdf_path in pdf_files:
            paper = self.ocr.parse_file(pdf_path)
            if paper:
                papers.append(paper)

        logger.info(f"Successfully parsed {len(papers)} out of {len(pdf_files)} PDFs")
        return papers

    def calculate_similarity(self, research_topic: str, papers: List[AcademicPaper]) -> List[AcademicPaper]:
        """
        Calculate similarity scores between research topic and papers.

        Args:
            research_topic: The research topic string
            papers: List of AcademicPaper objects

        Returns:
            List of papers with updated similarity scores
        """
        if not papers:
            logger.warning("No papers to calculate similarity for")
            return papers

        logger.info(f"Calculating similarity for {len(papers)} papers")

        # Encode the research topic
        topic_embedding = self.model.encode(research_topic, convert_to_tensor=True)

        # Encode all paper texts
        paper_texts = [paper.get_searchable_text() for paper in papers]

        # Batch encode for efficiency
        logger.info("Encoding paper contents...")
        paper_embeddings = self.model.encode(paper_texts, convert_to_tensor=True, show_progress_bar=True)

        # Calculate cosine similarity
        from sentence_transformers import util

        similarities = util.cos_sim(topic_embedding, paper_embeddings)[0]

        # Update similarity scores
        for paper, score in zip(papers, similarities):
            paper.similarity_score = float(score)

        return papers

    def rank_papers(self, papers: List[AcademicPaper], top_n: int = 10) -> List[AcademicPaper]:
        """
        Rank papers by similarity score.

        Args:
            papers: List of AcademicPaper objects
            top_n: Number of top papers to return

        Returns:
            Sorted list of top N papers
        """
        sorted_papers = sorted(papers, key=lambda p: p.similarity_score, reverse=True)
        return sorted_papers[:top_n]
