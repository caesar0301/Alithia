"""Notification and history models.

EmailContent: Email digest content
NotificationRecord: Record of sent notification
PaperLensQueryRecord: Query history tracking
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from alithia.models.papers import AcademicPaper, ArxivPaper


class EmailContent(BaseModel):
    """Email digest content.

    Used by PaperScout for email generation.
    """

    model_config = ConfigDict(extra="allow")

    subject: str
    html_body: str
    text_body: str | None = None  # Plain text fallback
    papers: list[ArxivPaper | AcademicPaper] = Field(default_factory=list)

    digest_date: str | None = None  # YYYY/MM/DD format

    @property
    def papers_count(self) -> int:
        """Number of papers in digest."""
        return len(self.papers)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "subject": self.subject,
            "html_body": self.html_body,
            "text_body": self.text_body,
            "papers": [p.model_dump() for p in self.papers],
            "digest_date": self.digest_date,
        }


class NotificationRecord(BaseModel):
    """Record of sent notification.

    Used by PaperScout for notification tracking.
    Stored in paperscout_notifications table.
    """

    model_config = ConfigDict(extra="allow")

    date: date  # Notification date
    papers_count: int
    recipient: str  # Email recipient
    arxiv_ids: list[str] = Field(default_factory=list)  # Papers included
    sent_at: datetime  # Timestamp

    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationRecord:
        """Deserialize from storage."""
        if "date" in data and isinstance(data["date"], str):
            data["date"] = date.fromisoformat(data["date"])
        if "sent_at" in data and isinstance(data["sent_at"], str):
            data["sent_at"] = datetime.fromisoformat(data["sent_at"])
        return cls(**data)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "user_id": self.user_id,
            "query": self.query,
            "pdf_path": self.pdf_path,
            "papers_count": self.papers_count,
            "top_score": self.top_score,
            "queried_at": self.queried_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperLensQueryRecord:
        """Deserialize from storage."""
        if "queried_at" in data and isinstance(data["queried_at"], str):
            data["queried_at"] = datetime.fromisoformat(data["queried_at"])
        return cls(**data)


__all__ = [
    "EmailContent",
    "NotificationRecord",
    "PaperLensQueryRecord",
]
