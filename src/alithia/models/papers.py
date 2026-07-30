"""Paper data models.

Core paper types used across PaperScout and PaperLens:
- AcademicPaper: Generic paper representation
- ArxivPaper: ArXiv API paper
- ZoteroPaper: Zotero library paper
- ScoredPaper: Paper with relevance score
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AcademicPaper(BaseModel):
    """Generic academic paper representation.

    Used by PaperLens for parsed PDF papers.
    Shared base for paper interchange between subagents.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    # Core metadata
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    keywords: list[str] = Field(default_factory=list)

    # Identifiers
    doi: str | None = None
    arxiv_id: str | None = None

    # Content
    full_text: str | None = None
    sections: dict[str, str] = Field(default_factory=dict)
    figures: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)

    # Source tracking
    source: str = "unknown"  # "arxiv", "zotero", "pdf"
    source_url: str | None = None

    # Processing metadata
    similarity_score: float = Field(default=0.0, ge=0.0, le=10.0)
    parsed_at: datetime | None = None
    parsing_errors: list[str] = Field(default_factory=list)

    @property
    def display_title(self) -> str:
        """Human-readable title for display."""
        return self.title or "Untitled"

    @property
    def display_authors(self) -> str:
        """Human-readable author string."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al. ({len(self.authors)} authors)"

    def get_searchable_text(self) -> str:
        """Weighted combination for similarity matching.

        Title weighted 3x, abstract 2x, keywords + full text once.
        """
        parts = []

        # Title weighted 3x (most important)
        if self.title:
            parts.extend([self.title] * 3)

        # Abstract weighted 2x
        if self.abstract:
            parts.extend([self.abstract] * 2)

        # Keywords once
        if self.keywords:
            parts.append(" ".join(self.keywords))

        # Full text once
        if self.full_text:
            parts.append(self.full_text)

        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        data = self.model_dump()
        if self.parsed_at:
            data["parsed_at"] = self.parsed_at.isoformat()
        return data


class ArxivPaper(BaseModel):
    """Paper from ArXiv API.

    Used by PaperScout for fetched papers from ArXiv.
    """

    model_config = ConfigDict(extra="allow")

    # Core metadata
    title: str
    summary: str  # ArXiv uses "summary" not "abstract"
    authors: list[str] = Field(default_factory=list)

    # ArXiv-specific identifiers
    arxiv_id: str  # Primary identifier (e.g., "2401.12345")
    pdf_url: str
    published_date: datetime

    # Optional ArXiv fields
    categories: list[str] = Field(default_factory=list)
    journal_ref: str | None = None
    comments: str | None = None

    # PaperScout processing fields
    score: float = Field(default=0.0, ge=0.0, le=10.0)
    code_url: str | None = None  # PapersWithCode link
    affiliations: list[str] | None = None  # Author affiliations (if available)
    tldr: str | None = None  # Generated summary
    tex: str | None = None  # LaTeX content

    @property
    def abstract(self) -> str:
        """Alias for summary (compatibility with AcademicPaper)."""
        return self.summary

    @property
    def display_title(self) -> str:
        """Human-readable title."""
        return self.title

    @property
    def display_authors(self) -> str:
        """Human-readable author string."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    def to_academic_paper(self) -> AcademicPaper:
        """Convert to generic AcademicPaper."""
        return AcademicPaper(
            title=self.title,
            authors=self.authors,
            abstract=self.summary,
            year=self.published_date.year,
            arxiv_id=self.arxiv_id,
            full_text=None,
            source="arxiv",
            source_url=self.pdf_url,
            similarity_score=self.score,
        )

    def get_searchable_text(self) -> str:
        """Weighted combination for similarity matching."""
        parts = []

        if self.title:
            parts.extend([self.title] * 3)

        if self.summary:
            parts.extend([self.summary] * 2)

        return " ".join(parts)


class ZoteroPaper(BaseModel):
    """Paper from Zotero library.

    Used by PaperScout for corpus building.
    """

    model_config = ConfigDict(extra="allow")

    # Zotero-specific identifier
    zotero_item_key: str  # Zotero item ID

    # Core metadata
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None

    # Zotero-specific fields
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    date_added: datetime | None = None
    collection_paths: list[str] = Field(default_factory=list)
    item_type: str = "journalArticle"

    # Additional Zotero fields
    doi: str | None = None
    publication_title: str | None = None
    volume: str | None = None
    pages: str | None = None

    @property
    def display_title(self) -> str:
        """Human-readable title."""
        return self.title

    @property
    def display_authors(self) -> str:
        """Human-readable author string."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    def get_searchable_text(self) -> str:
        """For ranking corpus building."""
        parts = []

        if self.title:
            parts.extend([self.title] * 3)

        if self.abstract:
            parts.extend([self.abstract] * 2)

        if self.tags:
            parts.append(" ".join(self.tags))

        return " ".join(parts)


class ScoredPaper(BaseModel):
    """Paper with relevance score and breakdown.

    Used by both PaperScout and PaperLens for ranked results.
    """

    model_config = ConfigDict(extra="allow")

    paper: ArxivPaper | AcademicPaper  # Union of paper types
    score: float = Field(ge=0.0, le=10.0)
    rank: int | None = None  # Position in results (1 = top)

    # Score breakdown for analysis
    relevance_factors: dict[str, float] = Field(default_factory=dict)

    @property
    def display_score(self) -> str:
        """Human-readable score with stars."""
        if self.score >= 8.0:
            return "★★★★★"
        elif self.score >= 7.0:
            return "★★★★☆"
        elif self.score >= 6.0:
            return "★★★☆☆"
        elif self.score >= 5.0:
            return "★★☆☆☆"
        else:
            return "★☆☆☆☆"

    @property
    def paper_title(self) -> str:
        """Convenience accessor for paper title."""
        return self.paper.title or self.paper.display_title

    @property
    def paper_authors(self) -> str:
        """Convenience accessor for authors."""
        return self.paper.display_authors


__all__ = [
    "AcademicPaper",
    "ArxivPaper",
    "ZoteroPaper",
    "ScoredPaper",
]
