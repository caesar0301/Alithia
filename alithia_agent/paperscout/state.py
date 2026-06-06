"""PaperScout state and configuration models.

AgentState TypedDict for LangGraph workflow.
PaperScoutRuntimeConfig, SmtpRuntimeConfig, ZoteroRuntimeConfig for runtime parameters.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from alithia_agent.models import ArxivPaper, ZoteroPaper, ScoredPaper, EmailContent


class SmtpRuntimeConfig(BaseModel):
    """SMTP server configuration for runtime."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(default=587, ge=1, le=65535)
    user: str
    password: str
    use_tls: bool = True


class ZoteroRuntimeConfig(BaseModel):
    """Zotero API configuration for runtime."""

    model_config = ConfigDict(extra="forbid")

    api_key: str
    library_id: str
    library_type: Literal["user", "group"] = "user"


class PaperScoutRuntimeConfig(BaseModel):
    """PaperScout runtime configuration (derived from global config)."""

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

    # Service configurations (injected from researcher_profile)
    smtp: SmtpRuntimeConfig | None = None
    zotero: ZoteroRuntimeConfig | None = None

    # LLM settings (injected from researcher_profile)
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    llm_model: str = "qwen-turbo-latest"

    # TLDR settings
    tldr_max_tokens: int = Field(default=150, ge=50, le=300)
    tldr_language: str = "English"


def build_runtime_config(global_config: "Config") -> PaperScoutRuntimeConfig:
    """Build runtime config from global alithia config.

    Args:
        global_config: The loaded alithia Config object.

    Returns:
        PaperScoutRuntimeConfig ready for agent execution.
    """
    from alithia_agent.config import Config

    cfg = global_config
    profile = cfg.researcher_profile

    # Build SMTP config from email_notification
    smtp = None
    if profile.email_notification:
        smtp = SmtpRuntimeConfig(
            host=profile.email_notification.smtp_server,
            port=profile.email_notification.smtp_port,
            user=profile.email_notification.sender,
            password=profile.email_notification.sender_password,
            use_tls=profile.email_notification.smtp_port != 25,
        )

    # Build Zotero config
    zotero = None
    if profile.zotero:
        zotero = ZoteroRuntimeConfig(
            api_key=profile.zotero.zotero_key,
            library_id=profile.zotero.zotero_id,
            library_type="user",
        )

    # Parse query string into categories
    query = cfg.paperscout_agent.query or "cs.AI+cs.CV+cs.LG+cs.CL"
    categories = query.replace("+", ",").split(",") if "+" in query else query.split(",")

    return PaperScoutRuntimeConfig(
        arxiv_categories=categories,
        max_papers=cfg.paperscout_agent.max_papers,
        max_papers_queried=cfg.paperscout_agent.max_papers_queried,
        send_email=cfg.paperscout_agent.send_email,
        send_empty=cfg.paperscout_agent.send_empty,
        recipient_email=profile.email,
        lookback_days=cfg.paperscout_agent.lookback_days,
        big_bang_date=cfg.paperscout_agent.big_bang,
        gap_window_days=cfg.paperscout_agent.gap_window_days,
        emailed_papers_retention_days=cfg.paperscout_agent.emailed_papers_retention_days,
        smtp=smtp,
        zotero=zotero,
        llm_api_key=profile.llm.openai_api_key if profile.llm else None,
        llm_api_base=profile.llm.openai_api_base if profile.llm else None,
        llm_model=profile.llm.model_name if profile.llm else "qwen-turbo-latest",
        tldr_max_tokens=cfg.paperscout_agent.tldr_max_tokens,
        tldr_language=cfg.paperscout_agent.tldr_language,
    )


class AgentState(TypedDict):
    """LangGraph agent state for PaperScout workflow.

    State flows through:
    profile_analysis → data_collection → relevance_assessment → content_generation → communication
    """

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperScoutRuntimeConfig
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


# Legacy aliases for backward compatibility
SmtpConfig = SmtpRuntimeConfig
ZoteroConfig = ZoteroRuntimeConfig
PaperScoutConfig = PaperScoutRuntimeConfig


__all__ = [
    "SmtpRuntimeConfig",
    "ZoteroRuntimeConfig",
    "PaperScoutRuntimeConfig",
    "build_runtime_config",
    "AgentState",
    # Legacy aliases
    "SmtpConfig",
    "ZoteroConfig",
    "PaperScoutConfig",
]