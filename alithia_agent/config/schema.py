"""Configuration schema definitions.

Pydantic models for configuration validation.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class StorageConfig(BaseModel):
    """Storage backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: str = "sqlite"
    path: str = "~/.alithia/alithia.db"
    user_id: str = "default"


class ZoteroConfig(BaseModel):
    """Zotero API configuration."""

    model_config = ConfigDict(extra="forbid")

    api_key: str
    library_id: str
    library_type: Literal["user", "group"] = "user"


class SmtpConfig(BaseModel):
    """SMTP server configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(default=587, ge=1, le=65535)
    user: str
    password: str
    use_tls: bool = True


class LlmConfig(BaseModel):
    """LLM provider configuration."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "openai"
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-4o-mini"
    max_tokens: int = Field(default=150, ge=50, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)


class PaperScoutConfig(BaseModel):
    """PaperScout subagent configuration."""

    model_config = ConfigDict(extra="forbid")

    # ArXiv query settings
    arxiv_categories: list[str] = Field(
        default=["cs.AI", "cs.CV", "cs.LG", "cs.CL"],
        min_length=1,
        description="ArXiv categories to query",
    )
    max_papers: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum papers in digest",
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

    # LLM settings
    tldr_max_tokens: int = Field(default=150, ge=50, le=300)
    tldr_language: str = "English"


class PaperLensConfig(BaseModel):
    """PaperLens subagent configuration."""

    model_config = ConfigDict(extra="forbid")

    # PDF processing
    pdf_extensions: list[str] = Field(default=["pdf"])
    recursive_scan: bool = Field(default=True)
    max_papers: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=8, ge=1, le=32)

    # Similarity
    sbert_model: str = "all-MiniLM-L6-v2"
    use_gpu: bool = Field(default=False)

    # LLM enhancement
    llm_enhance_metadata: bool = Field(default=True)
    llm_max_tokens: int = Field(default=500, ge=100, le=1000)

    # Output
    output_format: Literal["markdown", "json"] = "markdown"
    include_full_text: bool = Field(default=False)


class Config(BaseModel):
    """Root configuration model."""

    model_config = ConfigDict(extra="allow")

    storage: StorageConfig = Field(default_factory=StorageConfig)
    zotero: ZoteroConfig | None = None
    smtp: SmtpConfig | None = None
    llm: LlmConfig | None = None
    paperscout: PaperScoutConfig = Field(default_factory=PaperScoutConfig)
    paperlens: PaperLensConfig = Field(default_factory=PaperLensConfig)

    @model_validator(mode="after")
    def validate_paperscout_dependencies(self) -> "Config":
        """PaperScout requires zotero and smtp if send_email=True."""
        if self.paperscout.send_email:
            if not self.smtp:
                raise ValueError("smtp config required when paperscout.send_email=True")
        return self


__all__ = [
    "ConfigError",
    "Config",
    "StorageConfig",
    "ZoteroConfig",
    "SmtpConfig",
    "LlmConfig",
    "PaperScoutConfig",
    "PaperLensConfig",
]