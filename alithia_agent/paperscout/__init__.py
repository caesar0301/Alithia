"""PaperScout subagent for ArXiv paper discovery and email notifications.

A soothe framework subagent that:
1. Validates Zotero/SMTP configuration
2. Fetches papers from ArXiv API
3. Analyzes user's Zotero library for relevance profiling
4. Ranks papers using FastEmbed embeddings
5. Sends email digest notifications
"""

from __future__ import annotations

import logging
from typing import Any

from soothe_sdk.plugin import plugin, subagent

from alithia_agent.paperscout.implementation import create_paperscout_subagent
from alithia_agent.paperscout.runner import PaperScoutRunResult, run_paperscout_for_dates
from alithia_agent.paperscout.state import (
    AgentState,
    PaperScoutConfig,  # Legacy alias
    PaperScoutRuntimeConfig,
    SmtpConfig,  # Legacy alias
    SmtpRuntimeConfig,
    ZoteroConfig,  # Legacy alias
    ZoteroRuntimeConfig,
    build_runtime_config,
)

logger = logging.getLogger(__name__)

# Import events to register them with soothe's event system
from alithia_agent.paperscout import events as _events  # noqa: F401, E402

__all__ = [
    "PaperScoutPlugin",
    "create_paperscout_subagent",
    "PaperScoutRunResult",
    "run_paperscout_for_dates",
    "PaperScoutRuntimeConfig",
    "PaperScoutConfig",
    "SmtpRuntimeConfig",
    "SmtpConfig",
    "ZoteroRuntimeConfig",
    "ZoteroConfig",
    "AgentState",
    "build_runtime_config",
]


@plugin(
    name="paperscout",
    version="1.0.0",
    description="ArXiv paper recommendation agent using Zotero library analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "arxiv>=2.0.0",
        "fastembed>=0.6.0",
        "pyzotero>=1.5.0",
        "scikit-learn>=1.0.0",
    ],
    trust_level="standard",
)
class PaperScoutPlugin:
    """PaperScout plugin for ArXiv paper recommendations.

    Provides a subagent that:
    1. Validates Zotero/SMTP configuration
    2. Fetches papers from ArXiv API
    3. Analyzes user's Zotero library for relevance profiling
    4. Ranks papers using sentence embeddings
    5. Sends email digest notifications
    """

    async def on_load(self, context: Any) -> None:
        """Validate dependencies are available.

        Args:
            context: Plugin context with logger and config.
        """
        context.logger.info("Loading PaperScout plugin v1.0.0")

        # Optional: Check for heavy dependencies
        try:
            import fastembed  # noqa: F401

            context.logger.debug("fastembed available")
        except ImportError:
            context.logger.warning("fastembed not installed. Install with: pip install fastembed")

        context.logger.info("PaperScout plugin loaded successfully")

    @subagent(
        name="paperscout",
        description=(
            "ArXiv paper recommendation agent that delivers personalized daily "
            "paper recommendations by analyzing your Zotero library and ranking "
            "newly published papers by relevance. Use for proactive paper discovery, "
            "daily research digest, and email notifications about new papers."
        ),
        triggers=[
            "new papers",
            "arxiv",
            "paper digest",
            "daily papers",
            "research papers",
            "find papers",
        ],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create PaperScout subagent.

        Args:
            model: LLM model (from soothe config).
            config: Soothe configuration.
            context: Plugin context with services.
            **kwargs: Additional args (alithia_config, store, user_id).

        Returns:
            Subagent dict with name, description, runnable.
        """
        # Extract alithia-specific config from kwargs
        alithia_config = kwargs.get("alithia_config")
        store = kwargs.get("store")
        user_id = kwargs.get("user_id", "default")

        # Build runtime config from alithia config if available
        if alithia_config:
            # Use the existing build_runtime_config from paperscout.state
            from alithia_agent.config import Config

            try:
                full_config = Config(**alithia_config)
                runtime_config = PaperScoutRuntimeConfig.build_runtime_config(full_config)
            except Exception as e:
                logger.warning(f"Could not build runtime config from alithia_config: {e}")
                runtime_config = PaperScoutRuntimeConfig()
        else:
            runtime_config = PaperScoutRuntimeConfig()

        from_date = kwargs.get("from_date")
        to_date = kwargs.get("to_date")
        source = kwargs.get("source", "manual")
        if from_date:
            runtime_config = runtime_config.with_scheduler_params(
                from_date=from_date,
                to_date=to_date or from_date,
                source=source,
            )

        logger.info(f"Creating PaperScout subagent for user {user_id}")

        return create_paperscout_subagent(
            config=runtime_config,
            store=store,
            user_id=user_id,
        )
