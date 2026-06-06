"""Shared data models for alithia-agent.

Pydantic v2 models for paper data, metadata, notifications, and scoring.
All models follow naming conventions from RFC-008.
"""

from alithia_agent.models.papers import (
    AcademicPaper,
    ArxivPaper,
    ZoteroPaper,
    ScoredPaper,
)
from alithia_agent.models.metadata import (
    FileMetadata,
    PaperMetadata,
    PaperContent,
)
from alithia_agent.models.notifications import (
    EmailContent,
    NotificationRecord,
    PaperLensQueryRecord,
)

__all__ = [
    # Paper types
    "AcademicPaper",
    "ArxivPaper",
    "ZoteroPaper",
    "ScoredPaper",
    # Metadata
    "FileMetadata",
    "PaperMetadata",
    "PaperContent",
    # Notifications
    "EmailContent",
    "NotificationRecord",
    "PaperLensQueryRecord",
]