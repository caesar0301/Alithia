# RFC-008-data-models: Shared Data Model Contracts

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-29
**Depends on**: RFC-002-world-view, RFC-010-research-interests-knowledge
**Supersedes**: ---
**Stage**: Core
**Kind**: Implementation Interface Design

---

## 1. Abstract

Alithia-agent subagents share common data models for papers, scores, and related metadata. This RFC defines the Python type contracts for these shared models: Pydantic BaseModel definitions, field specifications, method contracts, and naming conventions. These models form the data interchange layer between subagents, storage, and output formatting.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Shared paper models (AcademicPaper, ArxivPaper, ZoteroPaper, ResearchInterest)
* Score model (ScoredPaper)
* Metadata models (FileMetadata, PaperMetadata, PaperContent)
* Email/notification models (EmailContent, NotificationRecord)
* Method contracts (e.g., `get_searchable_text()`)
* Naming conventions for model fields
* Model configuration (extra fields handling)

### 2.2 Non-Goals

This RFC does **not** define:

* Storage serialization format (see RFC-004-storage-layer)
* Workflow-specific state models (see RFC-001, RFC-003)
* Configuration models (see RFC-001, RFC-003)
* Event models (see RFC-007-plugin-integration)
* Output formatting (see RFC-005-cli-interface)

---

## 3. Background & Motivation

PaperScout and PaperLens both work with paper data but from different sources:
- **PaperScout**: ArXiv API + Zotero library
- **PaperLens**: User-provided PDFs

Shared models enable:
- Consistent paper representation across subagents
- Reusable ranking/scoring logic
- Standardized output formatting
- Interoperable storage serialization

---

## 4. Design Principles

1. **Pydantic v2**: All models use Pydantic BaseModel with v2 syntax
2. **Shared core**: Common fields shared across paper types
3. **Type-specific extensions**: Each paper type has source-specific fields
4. **Method contracts**: Key methods defined by contract (e.g., searchable text)
5. **Extra field policy**: `extra="allow"` for extensibility, `extra="forbid"` for configs

---

## 5. Core Paper Models

### 5.1 AcademicPaper (Generic Paper)

```python
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AcademicPaper(BaseModel):
    """Generic academic paper representation.
    
    Used by PaperLens for parsed PDF papers.
    Shared base for paper interchange.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    # Core metadata
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    keywords: list[str] = Field(default_factory=list)

    # Identifiers
    doi: str | None = None
    arxiv_id: str | None = None  # Populated for ArXiv papers

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
        """Weighted combination of title, abstract, keywords, full text.
        
        MUST be implemented for similarity matching.
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
```

### 5.2 ArxivPaper (ArXiv Source)

```python
class ArxivPaper(BaseModel):
    """Paper from ArXiv API.
    
    Used by PaperScout for fetched papers.
    """

    model_config = ConfigDict(extra="allow")

    # Core metadata (same as AcademicPaper)
    title: str
    summary: str  # ArXiv uses "summary" not "abstract"
    authors: list[str]

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
```

### 5.3 ZoteroPaper (Zotero Source)

```python
class ZoteroPaper(BaseModel):
    """Paper from Zotero library.
    
    Used by PaperScout for corpus building.
    """

    model_config = ConfigDict(extra="allow")

    # Zotero-specific identifier
    zotero_item_key: str  # Zotero item ID

    # Core metadata
    title: str
    authors: list[str]
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
```

### 5.4 ResearchInterest (Knowledge Unit)

> Defined in full in [RFC-010-research-interests-knowledge](RFC-010-research-interests-knowledge.md) §6.1. Summarized here as a shared data-model contract.

```python
class ResearchInterest(BaseModel):
    """One knowledge unit parsed from a research_interests/*.md file.

    Used by PaperScout as a primary relevance-corpus unit. May be hand-written
    (source="manual") or Zotero-synced (source="zotero"). Both origins are
    treated uniformly by the matcher.
    """

    model_config = ConfigDict(extra="allow")

    title: str
    source: Literal["manual", "zotero"] = "manual"
    weight: float = Field(default=1.0, ge=0.0)  # multiplier on this unit's similarity
    arxiv_categories: list[str] = Field(default_factory=list)  # informational, not fetch
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    date_added: date | None = None  # recency key for time-decay
    zotero_item_key: str | None = None  # provenance for zotero-synced units
    body: str = ""  # raw markdown body (frontmatter stripped), set by loader

    def get_searchable_text(self) -> str:
        """Text fed to the embedder: notes + body + tags (RFC-010 §5.4)."""
        parts: list[str] = []
        if self.notes:
            parts.append(self.notes)
        if self.body:
            parts.append(self.body)
        if self.tags:
            parts.append(" ".join(self.tags))
        return " ".join(parts)
```

---

## 6. Score Model

### 6.1 ScoredPaper

```python
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
```

---

## 7. Metadata Models

### 7.1 FileMetadata

```python
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

    def to_dict(self) -> dict:
        """Serialize for storage (Path → str)."""
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "last_modified": self.last_modified.isoformat(),
            "md5_hash": self.md5_hash,
        }
```

### 7.2 PaperMetadata

```python
class PaperMetadata(BaseModel):
    """Extracted paper metadata.
    
    Used by PaperLens for parsed content.
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None  # Publication year (4-digit)
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    doi: str | None = None
    venue: str | None = None  # Journal/conference name

    def is_complete(self) -> bool:
        """Check if all essential fields are populated."""
        return bool(self.title and self.abstract and len(self.authors) > 0)
```

### 7.3 PaperContent

```python
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
```

---

## 8. Email/Notification Models

### 8.1 EmailContent

```python
class EmailContent(BaseModel):
    """Email digest content.
    
    Used by PaperScout for email generation.
    """

    model_config = ConfigDict(extra="allow")

    subject: str
    html_body: str
    text_body: str | None = None  # Plain text fallback
    papers: list[ArxivPaper]  # Papers included in digest

    digest_date: str | None = None  # YYYY/MM/DD format

    @property
    def papers_count(self) -> int:
        """Number of papers in digest."""
        return len(self.papers)
```

### 8.2 NotificationRecord

```python
class NotificationRecord(BaseModel):
    """Record of sent notification.
    
    Used by PaperScout for notification tracking.
    Stored in paperscout_notifications table.
    """

    model_config = ConfigDict(extra="allow")

    date: date  # Notification date
    papers_count: int
    recipient: str  # Email recipient
    arxiv_ids: list[str]  # Papers included
    sent_at: datetime  # Timestamp

    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "date": self.date.isoformat(),
            "papers_count": self.papers_count,
            "recipient": self.recipient,
            "arxiv_ids": self.arxiv_ids,
            "sent_at": self.sent_at.isoformat(),
            "success": self.success,
            "error_message": self.error_message,
        }
```

---

## 9. Query/History Models

### 9.1 PaperLensQueryRecord

```python
class PaperLensQueryRecord(BaseModel):
    """Record of PaperLens query for history.
    
    Used by PaperLens for query tracking.
    Stored in paperlens_query_history table.
    """

    model_config = ConfigDict(extra="allow")

    user_id: str
    query: str  # Research topic/question
    pdf_path: str  # Directory or file analyzed
    papers_count: int  # Papers found
    top_score: float  # Best similarity score
    queried_at: datetime

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "user_id": self.user_id,
            "query": self.query,
            "pdf_path": self.pdf_path,
            "papers_count": self.papers_count,
            "top_score": self.top_score,
            "queried_at": self.queried_at.isoformat(),
        }
```

---

## 10. Naming Conventions

### 10.1 Field Naming Rules

| Rule | Example |
|------|---------|
| snake_case for fields | `arxiv_id`, `published_date` |
| No abbreviations except common | `url`, `doi`, `pdf` are OK; avoid `usr`, `cnt` |
| Boolean prefixes: `is_`, `has_`, `send_` | `is_complete`, `has_content`, `send_email` |
| Count suffix: `_count` | `papers_count`, `authors_count` |
| Timestamp suffix: `_at` | `sent_at`, `parsed_at`, `queried_at` |
| Date suffix: `_date` | `published_date`, `digest_date` |
| List plural nouns | `authors`, `papers`, `tags` (not `author_list`) |

### 10.2 Method Naming Rules

| Pattern | Purpose | Example |
|---------|---------|---------|
| `get_*()` | Computed value | `get_searchable_text()` |
| `to_*()` | Conversion | `to_dict()`, `to_academic_paper()` |
| `is_*()` | Boolean check | `is_complete()` |
| `has_*()` | Presence check | `has_content()` |
| `display_*` | Human-readable property | `display_title`, `display_authors` |

---

## 11. Model Configuration

### 11.1 ConfigDict Options

| Model Type | Config | Reason |
|------------|--------|--------|
| Data models | `extra="allow"` | Extensibility for unknown fields |
| Config models | `extra="forbid"` | Strict validation |
| Path-containing | `arbitrary_types_allowed=True` | Path is not JSON-serializable by default |

### 11.2 Field Constraints

```python
# Score fields
score: float = Field(ge=0.0, le=10.0)  # Range [0, 10]

# Count fields
max_papers: int = Field(ge=1, le=100)  # Range [1, 100]

# Year fields
year: int = Field(ge=1900, le=2100)  # Reasonable year range
```

---

## 12. Serialization

### 12.1 to_dict Pattern

```python
def to_dict(self) -> dict:
    """Serialize model for storage.
    
    Handles non-JSON types:
    - Path → str
    - datetime → ISO string
    - date → ISO string
    """
    data = self.model_dump()
    
    # Convert Path fields
    for field in ["file_path", "pdf_path"]:
        if field in data and isinstance(data[field], Path):
            data[field] = str(data[field])
    
    # Convert datetime fields
    for field in ["sent_at", "parsed_at", "queried_at", "published_date"]:
        if field in data and isinstance(data[field], datetime):
            data[field] = data[field].isoformat()
    
    # Convert date fields
    for field in ["date", "published_date"]:
        if field in data and isinstance(data[field], date):
            data[field] = data[field].isoformat()
    
    return data
```

### 12.2 from_dict Pattern

```python
@classmethod
def from_dict(cls, data: dict) -> "ModelClass":
    """Deserialize from storage.
    
    Handles non-JSON types:
    - str → Path
    - ISO string → datetime/date
    """
    # Pydantic handles most conversions automatically
    # via type annotations on fields
    return cls(**data)
```

---

## 13. Module Structure

### 13.1 Model Module Layout

```python
# models/__init__.py
"""Shared data models for alithia-agent."""

from .papers import AcademicPaper, ArxivPaper, ZoteroPaper, ScoredPaper
from .metadata import FileMetadata, PaperMetadata, PaperContent
from .notifications import EmailContent, NotificationRecord, PaperLensQueryRecord

__all__ = [
    "AcademicPaper",
    "ArxivPaper",
    "ZoteroPaper",
    "ScoredPaper",
    "FileMetadata",
    "PaperMetadata",
    "PaperContent",
    "EmailContent",
    "NotificationRecord",
    "PaperLensQueryRecord",
]
```

---

## 14. Dependencies

### 14.1 Required Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `pydantic` | BaseModel, validation | >=2.0 |
| `datetime` | Date/time types | stdlib |
| `pathlib` | Path type | stdlib |

---

## 15. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Implements Paper/Score abstractions |
| RFC-001-paperlens-workflow | Uses AcademicPaper, FileMetadata, PaperMetadata, PaperContent |
| RFC-003-paperscout-workflow | Uses ArxivPaper, ZoteroPaper, ResearchInterest, EmailContent, NotificationRecord |
| RFC-004-storage-layer | Defines serialization to_dict/from_dict |
| RFC-010-research-interests-knowledge | Defines the full ResearchInterest model and its Markdown format (§5.4 cross-references it) |

---

## 16. Open Questions

None. Pydantic v2 is the chosen model framework.

---

## 17. Conclusion

Alithia-agent shared data models provide:

1. **Core paper types**: AcademicPaper (generic), ArxivPaper (ArXiv), ZoteroPaper (Zotero)
2. **Score model**: ScoredPaper with relevance breakdown
3. **Metadata models**: FileMetadata, PaperMetadata, PaperContent
4. **Notification models**: EmailContent, NotificationRecord
5. **Method contracts**: `get_searchable_text()`, `to_dict()`, `is_complete()`
6. **Naming conventions**: snake_case fields, `_at` timestamps, `_count` totals

> **Shared Pydantic models enable consistent paper representation across PaperScout and PaperLens — with standardized serialization for storage and human-readable display properties for output.**