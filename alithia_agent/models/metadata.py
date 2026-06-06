"""Metadata models for paper processing.

FileMetadata: PDF file system metadata
PaperMetadata: Extracted paper metadata
PaperContent: Structured paper content
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileMetadata(BaseModel):
    """PDF file system metadata.

    Used by PaperLens for local PDF tracking.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    file_path: Path  # Absolute path to file
    file_name: str  # Filename with extension
    file_size: int  # Size in bytes
    last_modified: datetime
    md5_hash: str | None = None  # Computed hash for dedup

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage (Path → str)."""
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "last_modified": self.last_modified.isoformat(),
            "md5_hash": self.md5_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileMetadata":
        """Deserialize from storage."""
        if "file_path" in data:
            data["file_path"] = Path(data["file_path"])
        if "last_modified" in data and isinstance(data["last_modified"], str):
            data["last_modified"] = datetime.fromisoformat(data["last_modified"])
        return cls(**data)


class PaperMetadata(BaseModel):
    """Extracted paper metadata.

    Used by PaperLens for parsed content metadata.
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1900, le=2100)
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    doi: str | None = None
    venue: str | None = None  # Journal/conference name

    def is_complete(self) -> bool:
        """Check if all essential fields are populated."""
        return bool(self.title and self.abstract and len(self.authors) > 0)


class PaperContent(BaseModel):
    """Structured paper content.

    Used by PaperLens for parsed PDF content.
    """

    model_config = ConfigDict(extra="allow")

    full_text: str  # Complete extracted text
    sections: dict[str, str] = Field(default_factory=dict)  # Section name → content
    references: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)  # Figure descriptions/captions
    tables: list[str] = Field(default_factory=list)  # Table descriptions

    @property
    def has_content(self) -> bool:
        """Check if any content was extracted."""
        return bool(self.full_text or self.sections)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return self.model_dump()


__all__ = [
    "FileMetadata",
    "PaperMetadata",
    "PaperContent",
]