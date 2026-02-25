"""
User profile and configuration models for the Alithia research agent.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .connection import (
    EmailConnection,
    GithubConnection,
    GoogleScholarConnection,
    LLMConnection,
    XConnection,
    ZoteroConnection,
)

logger = logging.getLogger(__name__)


class ResearcherProfile(BaseModel):
    """Represents a user's research profile and preferences."""

    # Basic profile
    research_interests: List[str] = Field(default_factory=list)
    expertise_level: str = "intermediate"
    language: str = "English"
    email: str

    # Connected services
    llm: LLMConnection
    zotero: ZoteroConnection
    email_notification: EmailConnection
    github: Optional[GithubConnection] = None
    google_scholar: Optional[GoogleScholarConnection] = None
    x: Optional[XConnection] = None

    # Gems
    gems: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ResearcherProfile":
        """Create ResearcherProfile from configuration dictionary."""

        # Extract researcher_profile section
        profile_config = config.get("researcher_profile", {})

        if not _validate(profile_config):
            raise ValueError("Invalid configuration")

        # Helper function to safely create optional connections
        def safe_create_connection(connection_class, config_key):
            config_data = profile_config.get(connection_class.__name__.lower(), {})
            if config_data:
                try:
                    return connection_class(**config_data)
                except Exception:
                    logger.warning(f"Failed to create {connection_class.__name__}, skipping")
                    return None
            return None

        return cls(
            research_interests=profile_config.get("research_interests", []),
            expertise_level=profile_config.get("expertise_level", "intermediate"),
            language=profile_config.get("language", "English"),
            email=profile_config.get("email", ""),
            llm=LLMConnection(**profile_config.get("llm", {})),
            zotero=ZoteroConnection(**profile_config.get("zotero", {})),
            email_notification=EmailConnection(**profile_config.get("email_notification", {})),
            github=GithubConnection(**profile_config.get("github", {})) if profile_config.get("github") else None,
            google_scholar=_build_scholar_connection(profile_config.get("google_scholar")),
            x=XConnection(**profile_config.get("x", {})) if profile_config.get("x") else None,
            gems=profile_config.get("gems", {}),
        )


def _build_scholar_connection(raw: Any) -> Optional[GoogleScholarConnection]:
    """Build GoogleScholarConnection handling both old and new field names."""
    if not raw:
        return None
    try:
        data = dict(raw)
        if "google_scholar_id" in data and "scholar_id" not in data:
            data["scholar_id"] = data.pop("google_scholar_id")
        if "google_scholar_token" in data and "serpapi_key" not in data:
            data["serpapi_key"] = data.pop("google_scholar_token")
        data.pop("google_scholar_token", None)
        data.pop("google_scholar_id", None)
        return GoogleScholarConnection(**data)
    except Exception:
        logger.warning("Failed to create GoogleScholarConnection, skipping")
        return None


def _validate(config: dict) -> bool:
    """
    Validate configuration has all required fields.

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "llm",
        "zotero",
        "email_notification",
    ]

    missing = [field for field in required_fields if field not in config or not config[field]]

    if missing:
        logger.error(f"Missing required configuration: {', '.join(missing)}")
        return False

    return True
