import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from noesium.core.utils import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class ArxivPaper(BaseModel):
    """Represents an ArXiv paper with all relevant metadata."""

    title: str
    summary: str
    authors: List[str]
    arxiv_id: str
    pdf_url: str
    code_url: Optional[str] = None
    affiliations: Optional[List[str]] = None
    tldr: Optional[str] = None
    score: Optional[float] = None
    published_date: Optional[datetime] = None
    tex: Optional[Dict[str, str]] = None  # Store extracted LaTeX content
    arxiv_result: Optional[Any] = Field(
        default=None, exclude=True
    )  # Store original arxiv.Result object for source access

    @classmethod
    def from_arxiv_result(cls, paper_result) -> "ArxivPaper":
        """Create ArxivPaper from arxiv.Result object."""
        arxiv_id = re.sub(r"v\d+$", "", paper_result.get_short_id())

        # Validate that we have essential fields
        if not paper_result.title or not paper_result.summary:
            logger.warning(f"Skipping paper with missing title or summary: {arxiv_id}")
            return None

        return cls(
            title=paper_result.title.strip(),
            summary=paper_result.summary.strip(),
            authors=[author.name for author in paper_result.authors],
            arxiv_id=arxiv_id,
            pdf_url=paper_result.pdf_url,
            published_date=paper_result.published,
            arxiv_result=paper_result,  # Store the original result object
        )

    def download_source(self, dirpath: str) -> str:
        """Download source files for the paper."""
        if self.arxiv_result is None:
            raise AttributeError("Cannot download source: no arxiv_result available")
        return self.arxiv_result.download_source(dirpath=dirpath)
