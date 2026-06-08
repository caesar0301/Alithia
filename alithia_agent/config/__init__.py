"""Configuration module for alithia-agent.

JSON-based configuration with environment variable substitution.
Pydantic validation with fail-fast on missing required fields.
"""

from alithia_agent.config.loader import ConfigLoader, load_config
from alithia_agent.config.schema import (
    Config,
    ConfigError,
    EmailNotificationConfig,
    GemsConfig,
    GithubProfileConfig,
    GoogleScholarProfileConfig,
    LlmProfileConfig,
    PaperLensAgentConfig,
    PaperScoutAgentConfig,
    ResearcherProfileConfig,
    StorageConfig,
    SupabaseConfig,
    TurnstileConfig,
    XProfileConfig,
    ZoteroProfileConfig,
)

__all__ = [
    "ConfigLoader",
    "load_config",
    "Config",
    "ConfigError",
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
]
