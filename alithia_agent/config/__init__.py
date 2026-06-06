"""Configuration module for alithia-agent.

JSON-based configuration with environment variable substitution.
Pydantic validation with fail-fast on missing required fields.
"""

from alithia_agent.config.loader import ConfigLoader
from alithia_agent.config.schema import (
    Config,
    StorageConfig,
    ZoteroConfig,
    SmtpConfig,
    LlmConfig,
    PaperScoutConfig,
    PaperLensConfig,
)

__all__ = [
    "ConfigLoader",
    "Config",
    "StorageConfig",
    "ZoteroConfig",
    "SmtpConfig",
    "LlmConfig",
    "PaperScoutConfig",
    "PaperLensConfig",
]