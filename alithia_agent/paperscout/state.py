"""PaperScout state and configuration models.

AgentState TypedDict for LangGraph workflow.
PaperScoutConfig, SmtpConfig, ZoteroConfig for user-controlled parameters.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from alithia_agent.models import ArxivPaper, ZoteroPaper, ScoredPaper, EmailContent


class SmtpConfig(BaseModel):
    """SMTP server configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(default=587, ge=1, le=65535)
    user: str
    password: str
    use_tls: bool = True


class ZoteroConfig(BaseModel):
    """Zotero API configuration."""

    model_config = ConfigDict(extra="forbid")

    api_key: str
    library_id: str
    library_type: Literal["user", "group"] = "user"


class PaperScoutConfig(BaseModel):
    """PaperScout subagent configuration."""

    model_config = ConfigDict(extra="forbid")

    # ArXiv query settings
    arxiv_categories: list[str] = Field(
        default=["cs.AI", "cs.CV", "cs.LG", "cs.CL"],
        description="ArXiv categories to query",
    )
    max_papers: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum papers to include in digest",
    )
    max_papers_queried: int = Field(
        default=500,
        ge=10,
        le=1000,
        description="Maximum papers to query from ArXiv",
    )

    # Email settings
    send_email: bool = Field(default=True)
    send_empty: bool = Field(default=False)
    recipient_email: str | None = None

    # Date range settings
    lookback_days: int = Field(default=7, ge=1, le=30)
    big_bang_date: date | None = None

    # Notification settings
    gap_window_days: int = Field(default=7, ge=1, le=30)
    emailed_papers_retention_days: int = Field(default=30, ge=7, le=90)

    # Service configurations (injected)
    smtp: SmtpConfig | None = None
    zotero: ZoteroConfig | None = None

    # LLM settings
    tldr_max_tokens: int = Field(default=150, ge=50, le=300)
    tldr_language: str = "English"


class AgentState(TypedDict):
    """LangGraph agent state for PaperScout workflow.

    State flows through:
    profile_analysis → data_collection → relevance_assessment → content_generation → communication
    """

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperScoutConfig
    user_id: str

    # Discovered papers (from ArXiv)
    discovered_papers: list[ArxivPaper]

    # User corpus (from Zotero)
    zotero_papers: list[ZoteroPaper]

    # Ranked papers
    scored_papers: list[ScoredPaper]

    # Email content
    email_content: EmailContent | None

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]


__all__ = [
    "SmtpConfig",
    "ZoteroConfig",
    "PaperScoutConfig",
    "AgentState",
]