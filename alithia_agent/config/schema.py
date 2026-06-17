"""Configuration schema definitions.

Pydantic models for configuration validation.
Aligned with existing alithia config structure.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alithia_agent.logging_config import DEFAULT_LOG_FILE


class ConfigError(Exception):
    """Configuration validation error."""

    def __init__(self, message: str, details: list[str] | None = None):
        self.message = message
        self.details = details or []
        super().__init__(self.format_message())

    def format_message(self) -> str:
        if self.details:
            return f"{self.message}\n" + "\n".join(f"  - {d}" for d in self.details)
        return self.message


# ============================================================
# Researcher Profile
# ============================================================


class LlmProfileConfig(BaseModel):
    """LLM settings within researcher profile."""

    model_config = ConfigDict(extra="forbid")

    openai_api_key: str | None = None
    openai_api_base: str | None = None
    model_name: str = "qwen-turbo-latest"


class ZoteroProfileConfig(BaseModel):
    """Zotero settings within researcher profile."""

    model_config = ConfigDict(extra="forbid")

    zotero_id: str
    zotero_key: str


class EmailNotificationConfig(BaseModel):
    """Email notification settings."""

    model_config = ConfigDict(extra="forbid")

    smtp_server: str
    smtp_port: int = Field(default=465, ge=1, le=65535)
    sender: str
    sender_password: str


class GithubProfileConfig(BaseModel):
    """GitHub settings."""

    model_config = ConfigDict(extra="forbid")

    github_username: str | None = None
    github_token: str | None = None


class GoogleScholarProfileConfig(BaseModel):
    """Google Scholar settings."""

    model_config = ConfigDict(extra="forbid")

    google_scholar_id: str | None = None
    google_scholar_token: str | None = None


class XProfileConfig(BaseModel):
    """X/Twitter settings."""

    model_config = ConfigDict(extra="forbid")

    x_username: str | None = None
    x_token: str | None = None


class GemsConfig(BaseModel):
    """Gems (custom research topics)."""

    model_config = ConfigDict(extra="allow")

    # Dynamic key-value pairs for custom topics


class ResearcherProfileConfig(BaseModel):
    """Researcher profile configuration."""

    model_config = ConfigDict(extra="allow")

    research_interests: list[str] = Field(default=["AI", "Machine Learning"])
    expertise_level: Literal["beginner", "intermediate", "advanced", "expert"] = "intermediate"
    language: str = "English"
    email: str | None = None
    llm: LlmProfileConfig | None = None
    zotero: ZoteroProfileConfig | None = None
    email_notification: EmailNotificationConfig | None = None
    github: GithubProfileConfig | None = None
    google_scholar: GoogleScholarProfileConfig | None = None
    x: XProfileConfig | None = None
    gems: GemsConfig | None = None


# ============================================================
# Storage
# ============================================================


class SupabaseConfig(BaseModel):
    """Supabase storage configuration."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    anon_key: str | None = None
    service_role_key: str | None = None


class StorageConfig(BaseModel):
    """Storage backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["sqlite", "postgres", "supabase"] = "sqlite"
    fallback_to_sqlite: bool = False
    sqlite_path: str = "data/alithia.db"
    user_id: str = "default_user"
    supabase: SupabaseConfig | None = None


# ============================================================
# Subagents
# ============================================================


class PaperScoutAgentConfig(BaseModel):
    """PaperScout agent configuration."""

    model_config = ConfigDict(extra="forbid")

    query: str = "cs.AI+cs.CV+cs.LG+cs.CL"
    max_papers: int = Field(default=25, ge=1, le=100)
    max_papers_queried: int = Field(default=500, ge=10, le=1000)
    send_email: bool = True
    send_empty: bool = False
    ignore_patterns: list[str] = Field(default_factory=list)
    big_bang: date | None = None

    # Date range settings
    lookback_days: int = Field(default=7, ge=1, le=30)
    gap_window_days: int = Field(default=7, ge=1, le=30)
    emailed_papers_retention_days: int = Field(default=30, ge=7, le=90)

    # LLM settings
    tldr_max_tokens: int = Field(default=150, ge=50, le=300)
    tldr_language: str = "English"


class PaperLensAgentConfig(BaseModel):
    """PaperLens agent configuration."""

    model_config = ConfigDict(extra="forbid")

    sbert_model: str = "all-MiniLM-L6-v2"
    force_gpu: bool = False
    top_n: int = Field(default=10, ge=1, le=50)

    # PDF processing
    pdf_extensions: list[str] = Field(default=["pdf"])
    recursive_scan: bool = True
    max_papers: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=8, ge=1, le=32)

    # LLM enhancement
    llm_enhance_metadata: bool = True
    llm_max_tokens: int = Field(default=500, ge=100, le=1000)

    # Output
    output_format: Literal["markdown", "json"] = "markdown"
    include_full_text: bool = False


# ============================================================
# Turnstile (CAPTCHA)
# ============================================================


class TurnstileConfig(BaseModel):
    """Cloudflare Turnstile configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    site_key: str = ""
    secret_key: str = ""


# ============================================================
# Daemon Scheduler
# ============================================================


class DaemonSchedulerConfig(BaseModel):
    """Daemon scheduler configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    hour: int = Field(default=23, ge=0, le=23, description="UTC hour for daily run")
    minute: int = Field(default=0, ge=0, le=59, description="UTC minute for daily run")
    timezone: str = "UTC"
    retry_window_days: int = Field(
        default=3, ge=1, le=7, description="Days to retry failed notifications"
    )
    max_retry_age_days: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Max age (days) to keep retrying unretrieved dates",
    )
    max_retries_per_run: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum unretrieved dates retried in each scheduler cycle",
    )
    backfill_on_startup: bool = Field(
        default=True,
        description="Retry unretrieved backlog days when the daemon starts",
    )
    startup_backfill_cap: int | None = Field(
        default=None,
        ge=0,
        le=90,
        description=(
            "Max backlog days to retry on startup. "
            "Defaults to max_retry_age_days when backfill_on_startup is enabled."
        ),
    )


class DaemonConfig(BaseModel):
    """Daemon process configuration."""

    model_config = ConfigDict(extra="forbid")

    scheduler: DaemonSchedulerConfig = Field(default_factory=DaemonSchedulerConfig)
    pid_file: str = "daemon.pid"
    log_file: str = DEFAULT_LOG_FILE
    big_bang: date | None = Field(
        default=None, description="Tracking start date, no scans before this"
    )


# ============================================================
# Root Config
# ============================================================


class Config(BaseModel):
    """Root configuration model."""

    model_config = ConfigDict(extra="allow")

    researcher_profile: ResearcherProfileConfig = Field(default_factory=ResearcherProfileConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    paperscout_agent: PaperScoutAgentConfig = Field(default_factory=PaperScoutAgentConfig)
    paperlens_agent: PaperLensAgentConfig = Field(default_factory=PaperLensAgentConfig)
    turnstile: TurnstileConfig = Field(default_factory=TurnstileConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)
    debug: bool = False

    @model_validator(mode="after")
    def validate_notification_dependencies(self) -> Config:
        """Validate email notification requires SMTP config."""
        if self.paperscout_agent.send_email:
            if not self.researcher_profile.email_notification:
                raise ValueError(
                    "researcher_profile.email_notification required when "
                    "paperscout_agent.send_email=True"
                )
        return self

    # Legacy aliases for backward compatibility
    @property
    def paperscout(self) -> PaperScoutAgentConfig:
        """Alias for paperscout_agent."""
        return self.paperscout_agent

    @property
    def paperlens(self) -> PaperLensAgentConfig:
        """Alias for paperlens_agent."""
        return self.paperlens_agent


__all__ = [
    "ConfigError",
    "Config",
    "ResearcherProfileConfig",
    "LlmProfileConfig",
    "ZoteroProfileConfig",
    "EmailNotificationConfig",
    "GithubProfileConfig",
    "GoogleScholarProfileConfig",
    "XProfileConfig",
    "GemsConfig",
    "StorageConfig",
    "SupabaseConfig",
    "PaperScoutAgentConfig",
    "PaperLensAgentConfig",
    "TurnstileConfig",
    "DaemonSchedulerConfig",
    "DaemonConfig",
]
