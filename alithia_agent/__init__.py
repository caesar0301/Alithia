"""Alithia Agent - CLI research assistant for paper discovery and analysis.

A pure CLI version of alithia built on the soothe framework, providing:
- PaperScout: ArXiv paper discovery with email notifications
- PaperLens: Local PDF analysis with similarity ranking

Usage:
    python -m alithia_agent --subagent paperscout
    python -m alithia_agent --subagent paperlens --query "transformers" --pdf-path ~/papers

Environment:
    SOOTHE_HOME: Set to ~/.alithia/soothe/ for soothe framework integration
    ALITHIA_HOME: Set to ~/.alithia/ for alithia-specific storage
    ALITHIA_HF_CACHE: Set to ~/.cache/alithia/models/huggingface for embedding models
"""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.0.0"

# Set SOOTHE_HOME to ~/.alithia/soothe/ before any soothe imports
# This ensures soothe framework uses our dedicated directory
ALITHIA_HOME = Path(os.environ.get("ALITHIA_HOME", str(Path.home() / ".alithia")))
SOOTHE_HOME = ALITHIA_HOME / "soothe"

# Set environment variable for soothe framework
os.environ["SOOTHE_HOME"] = str(SOOTHE_HOME)

# Ensure directories exist
ALITHIA_HOME.mkdir(parents=True, exist_ok=True)
SOOTHE_HOME.mkdir(parents=True, exist_ok=True)

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
    # Constants
    "ALITHIA_HOME",
    "SOOTHE_HOME",
    # Models
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