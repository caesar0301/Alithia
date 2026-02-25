"""
Paper data models for the Alithia research agent.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from cogents_core.utils import get_logger
from pydantic import BaseModel, Field

from alithia.models import ArxivPaper

logger = get_logger(__name__)


class ScoredPaper(BaseModel):
    """Represents a paper with relevance score."""

    paper: ArxivPaper
    score: float
    relevance_factors: Dict[str, float] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Update the paper's score after initialization."""
        self.paper.score = self.score


class EmailContent(BaseModel):
    """Represents the content for email delivery."""

    subject: str
    html_content: str
    papers: List[ScoredPaper]
    generated_at: datetime = Field(default_factory=datetime.now)

    def is_empty(self) -> bool:
        """Check if email has no papers."""
        return len(self.papers) == 0


class NotificationRecord(BaseModel):
    """Tracks a notification event for deduplication (PS-001)."""

    notification_id: Optional[str] = None
    user_id: str
    query_categories: str
    notification_date: date
    paper_count: int = 0
    status: Literal["pending", "sent", "failed"] = "pending"
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_storage_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "query_categories": self.query_categories,
            "notification_date": self.notification_date.isoformat(),
            "paper_count": self.paper_count,
            "status": self.status,
            "retry_count": self.retry_count,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
        }
