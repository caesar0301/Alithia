"""Alithia Agent - CLI research assistant for paper discovery and analysis.

A CLI host built on soothe-nano, providing:
- PaperScout: ArXiv paper discovery with email notifications
- PaperLens: Local PDF analysis with similarity ranking

Usage:
    alithia-agent "Find new papers about transformers"
    alithia-agent --subagent paperscout "Check for new papers"
    alithia-agent daemon start

Environment:
    SOOTHE_HOME: Set to ~/.alithia/soothe/ for soothe-nano runtime
    ALITHIA_HOME: Set to ~/.alithia/ for alithia-specific storage
    ALITHIA_HF_CACHE: Set to ~/.cache/alithia/models/huggingface for embedding models
"""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "0.3.1"

# Set SOOTHE_HOME to ~/.alithia/soothe/ before any soothe-nano imports
ALITHIA_HOME = Path(os.environ.get("ALITHIA_HOME", str(Path.home() / ".alithia")))
SOOTHE_HOME = ALITHIA_HOME / "soothe"

os.environ["SOOTHE_HOME"] = str(SOOTHE_HOME)

ALITHIA_HOME.mkdir(parents=True, exist_ok=True)
SOOTHE_HOME.mkdir(parents=True, exist_ok=True)

from alithia_agent.models import (  # noqa: E402
    AcademicPaper,
    ArxivPaper,
    EmailContent,
    FileMetadata,
    NotificationRecord,
    PaperContent,
    PaperMetadata,
    ScoredPaper,
    ZoteroPaper,
)

__all__ = [
    "ALITHIA_HOME",
    "SOOTHE_HOME",
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
