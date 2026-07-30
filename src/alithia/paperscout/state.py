"""PaperScout state and configuration models.

AgentState TypedDict for LangGraph workflow.
PaperScoutRuntimeConfig, SmtpRuntimeConfig, ZoteroRuntimeConfig for runtime parameters.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from alithia import ALITHIA_HOME
from alithia.models import ArxivPaper, EmailContent, ScoredPaper
from alithia.research_interests import ResearchInterest

if TYPE_CHECKING:
    from alithia.config.schema import Config


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
    query: str = Field(
        default="cs.AI+cs.CV+cs.LG+cs.CL",
        description="Original ArXiv query string",
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

    # Date range settings (for scheduler/daemon support)
    from_date: str | None = Field(
        default=None,
        description="Start date for paper query (YYYY-MM-DD), defaults to yesterday",
    )
    to_date: str | None = Field(
        default=None,
        description="End date for paper query (YYYY-MM-DD), defaults to from_date",
    )
    lookback_days: int = Field(default=7, ge=1, le=30)
    big_bang_date: date | None = None

    # Source tracking
    source: Literal["manual", "scheduler", "scheduler_retry", "gap_fill"] = Field(
        default="manual",
        description="Source of the run request",
    )

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

    # TLDR settings. Despite the name, this is a character budget for the
    # digest abstract shown in the TLDR row (a token budget anticipating a
    # future LLM summary). Default ~600 chars (~90 words); widen to 2000 so
    # users who want full abstracts can have them.
    tldr_max_tokens: int = Field(default=600, ge=50, le=2000)
    tldr_language: str = "English"

    # Research interests knowledge base (RFC-010). Directory of *.md files
    # under ALITHIA_HOME. Resolved here so nodes don't re-resolve ALITHIA_HOME.
    research_interests_dir: str | None = None

    def with_scheduler_params(
        self,
        *,
        from_date: str,
        to_date: str,
        source: Literal["manual", "scheduler", "scheduler_retry", "gap_fill"],
    ) -> PaperScoutRuntimeConfig:
        """Return a copy configured for scheduler/daemon date-range execution."""
        return self.model_copy(
            update={
                "from_date": from_date,
                "to_date": to_date,
                "source": source,
            }
        )

    @classmethod
    def build_runtime_config(cls, global_config: Config) -> PaperScoutRuntimeConfig:
        """Build runtime config from global alithia config.

        Args:
            global_config: The loaded alithia Config object.

        Returns:
            PaperScoutRuntimeConfig ready for agent execution.
        """

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

        return cls(
            arxiv_categories=categories,
            query=query,
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
            research_interests_dir=str(ALITHIA_HOME / "research_interests"),
        )


# Backward-compatible function wrapper for build_runtime_config
def build_runtime_config(global_config: Config) -> PaperScoutRuntimeConfig:
    """Build runtime config from global alithia config (backward-compatible wrapper).

    Args:
        global_config: The loaded alithia Config object.

    Returns:
        PaperScoutRuntimeConfig ready for agent execution.
    """
    return PaperScoutRuntimeConfig.build_runtime_config(global_config)


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

    # Research interests knowledge units loaded from research_interests_dir
    # (RFC-010). The unified knowledge base: hand-written units + Zotero items
    # synced into zotero/*.md. This is the ONLY corpus the reranker scores
    # against — the legacy zotero_papers slot was removed.
    research_interests: list[ResearchInterest]

    # Ranked papers
    scored_papers: list[ScoredPaper]

    # Email content
    email_content: EmailContent | None

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]


__all__ = [
    "SmtpRuntimeConfig",
    "ZoteroRuntimeConfig",
    "PaperScoutRuntimeConfig",
    "build_runtime_config",
    "AgentState",
]
