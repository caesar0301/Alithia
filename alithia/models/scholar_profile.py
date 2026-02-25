"""
Google Scholar profile and publication models.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScholarPublication(BaseModel):
    """A single publication from Google Scholar."""

    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    citation_count: int = 0
    venue: Optional[str] = None
    url: Optional[str] = None
    scholar_id: Optional[str] = None

    def to_storage_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "citation_count": self.citation_count,
            "venue": self.venue,
            "url": self.url,
            "scholar_article_id": self.scholar_id,
        }

    @classmethod
    def from_storage_dict(cls, row: Dict[str, Any]) -> "ScholarPublication":
        authors = row.get("authors", [])
        if isinstance(authors, str):
            authors = json.loads(authors)
        return cls(
            title=row.get("title", ""),
            authors=authors,
            year=row.get("year"),
            citation_count=row.get("citation_count", 0),
            venue=row.get("venue"),
            url=row.get("url"),
            scholar_id=row.get("scholar_article_id"),
        )


class ScholarProfile(BaseModel):
    """Normalized Google Scholar researcher profile."""

    scholar_user_id: str
    name: str
    affiliation: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    total_citations: int = 0
    publications: List[ScholarPublication] = Field(default_factory=list)
    fetched_at: Optional[datetime] = None

    def to_storage_dict(self) -> Dict[str, Any]:
        return {
            "scholar_user_id": self.scholar_user_id,
            "name": self.name,
            "affiliation": self.affiliation,
            "interests": self.interests,
            "h_index": self.h_index,
            "i10_index": self.i10_index,
            "total_citations": self.total_citations,
            "last_synced": self.fetched_at.isoformat() if self.fetched_at else datetime.utcnow().isoformat(),
        }

    @classmethod
    def from_storage_dict(cls, row: Dict[str, Any]) -> "ScholarProfile":
        interests = row.get("interests", [])
        if isinstance(interests, str):
            interests = json.loads(interests)

        fetched_at = row.get("last_synced")
        if isinstance(fetched_at, str) and fetched_at:
            try:
                fetched_at = datetime.fromisoformat(fetched_at)
            except (ValueError, TypeError):
                fetched_at = None

        return cls(
            scholar_user_id=row.get("scholar_user_id", ""),
            name=row.get("name", ""),
            affiliation=row.get("affiliation"),
            interests=interests,
            h_index=row.get("h_index"),
            i10_index=row.get("i10_index"),
            total_citations=row.get("total_citations", 0),
            fetched_at=fetched_at,
        )
