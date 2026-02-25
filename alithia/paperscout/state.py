"""
Agent state management for the Alithia research agent.
"""

from datetime import datetime
from operator import add
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from alithia.constants import (
    ALITHIA_MAX_PAPERS,
    ALITHIA_MAX_PAPERS_QUERIED,
    DEFAULT_ARXIV_QUERY,
    DEFAULT_SEND_EMAIL,
    DEFAULT_SEND_EMPTY,
)
from alithia.models.zotero_paper import ZoteroPaper
from alithia.researcher import ResearcherProfile

from .models import ArxivPaper, EmailContent, ScoredPaper


class PaperScoutConfig(BaseModel):
    """PaperScout agent configuration."""

    # User Profile
    user_profile: ResearcherProfile

    # Agent Config
    query: str = DEFAULT_ARXIV_QUERY
    max_papers: int = ALITHIA_MAX_PAPERS
    max_papers_queried: int = ALITHIA_MAX_PAPERS_QUERIED
    send_email: bool = DEFAULT_SEND_EMAIL
    send_empty: bool = DEFAULT_SEND_EMPTY
    ignore_patterns: List[str] = Field(default_factory=list)

    # Date Range (YYYY-MM-DD format, None defaults to yesterday)
    from_date: Optional[str] = None
    to_date: Optional[str] = None

    # Gap Scanner
    gap_scan_window_days: int = 7

    debug: bool = False


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with right overriding left."""
    return {**left, **right}


class AgentState(BaseModel):
    """Centralized state for the research agent workflow."""

    # Agent Config
    config: PaperScoutConfig

    # Discovery State
    discovered_papers: List[ArxivPaper] = Field(default_factory=list)
    zotero_corpus: List[ZoteroPaper] = Field(default_factory=list)

    # Assessment State
    scored_papers: List[ScoredPaper] = Field(default_factory=list)

    # Content State
    email_content: Optional[EmailContent] = None

    # System State
    current_step: str = "initializing"
    # Use Annotated with operator.add to accumulate error_log entries across nodes
    error_log: Annotated[List[str], add] = Field(default_factory=list)
    info_messages: Annotated[List[str], add] = Field(default_factory=list)
    # Use custom merge function to accumulate performance_metrics across nodes
    performance_metrics: Annotated[Dict[str, float], merge_dicts] = Field(default_factory=dict)

    # Debug State
    debug_mode: bool = False

    def add_error(self, error: str) -> None:
        """Add an error to the error log."""
        self.error_log.append(f"{datetime.now().isoformat()}: {error}")

    def update_metric(self, key: str, value: float) -> None:
        """Update a performance metric."""
        self.performance_metrics[key] = value

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state."""
        return {
            "current_step": self.current_step,
            "papers_discovered": len(self.discovered_papers),
            "papers_scored": len(self.scored_papers),
            "errors": len(self.error_log),
            "metrics": self.performance_metrics,
        }
