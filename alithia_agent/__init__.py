"""Alithia Agent - CLI research assistant for paper discovery and analysis.

A pure CLI version of alithia built on the soothe framework, providing:
- PaperScout: ArXiv paper discovery with email notifications
- PaperLens: Local PDF analysis with similarity ranking

Usage:
    python -m alithia_agent --subagent paperscout
    python -m alithia_agent --subagent paperlens --query "transformers" --pdf-path ~/papers
"""

__version__ = "1.0.0"

from alithia_agent.models import (
    AcademicPaper,
    ArxivPaper,
    ZoteroPaper,
    ScoredPaper,
    FileMetadata,
    PaperMetadata,
    PaperContent,
    EmailContent,
    NotificationRecord,
)

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
]