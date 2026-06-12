"""PaperLens plugin for soothe framework.

PDF discovery and ranking agent for local paper analysis.
Registered via @plugin and @subagent decorators.
"""

from __future__ import annotations

import logging
from typing import Any

from soothe_sdk.plugin import plugin, subagent

from alithia_agent.plugins.paperlens.implementation import create_paperlens_subagent
from alithia_agent.plugins.paperlens.state import PaperLensRuntimeConfig

logger = logging.getLogger(__name__)

# Import events to register them with soothe's event system
from alithia_agent.plugins.paperlens import events as _events  # noqa: F401, E402

__all__ = [
    "PaperLensPlugin",
    "create_paperlens_subagent",
]


@plugin(
    name="paperlens",
    version="1.0.0",
    description="PDF discovery and ranking subagent for local paper analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "docling>=2.0.0",
        "sentence-transformers>=2.2.0",
    ],
    trust_level="standard",
)
class PaperLensPlugin:
    """PaperLens plugin for local PDF analysis.

    Provides a subagent that:
    1. Parses PDFs using Docling
    2. Enhances metadata using LLM when needed
    3. Calculates semantic similarity using sentence embeddings
    4. Returns ranked results with relevance scores
    """

    async def on_load(self, context: Any) -> None:
        """Validate dependencies are available.

        Args:
            context: Plugin context with logger and config.
        """
        context.logger.info("Loading PaperLens plugin v1.0.0")

        # Check for heavy dependencies
        try:
            import docling  # noqa: F401

            context.logger.debug("docling available")
        except ImportError:
            context.logger.warning("docling not installed. Install with: pip install docling")

        try:
            import sentence_transformers  # noqa: F401

            context.logger.debug("sentence-transformers available")
        except ImportError:
            context.logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        context.logger.info("PaperLens plugin loaded successfully")

    @subagent(
        name="paperlens",
        description=(
            "Discover relevant academic papers from PDF collections by "
            "semantic similarity matching. Use for local paper analysis, "
            "ranking PDFs by relevance to a research topic, and finding "
            "similar papers in your collection."
        ),
        triggers=[
            "rank papers",
            "analyze pdf",
            "similar papers",
            "local papers",
            "find relevant",
            "pdf analysis",
        ],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create PaperLens subagent.

        Args:
            model: LLM model (from soothe config).
            config: Soothe configuration.
            context: Plugin context with services.
            **kwargs: Additional args (alithia_config, user_id, query, pdf_path).

        Returns:
            Subagent dict with name, description, runnable.
        """
        # Extract alithia-specific config from kwargs
        alithia_config = kwargs.get("alithia_config")
        user_id = kwargs.get("user_id", "default")

        # Build runtime config from alithia config if available
        if alithia_config:
            from alithia_agent.config import Config

            try:
                full_config = Config(**alithia_config)
                runtime_config = PaperLensRuntimeConfig.build_runtime_config(full_config)
            except Exception as e:
                logger.warning(f"Could not build runtime config from alithia_config: {e}")
                runtime_config = PaperLensRuntimeConfig()
        else:
            runtime_config = PaperLensRuntimeConfig()

        logger.info(f"Creating PaperLens subagent for user {user_id}")

        return create_paperlens_subagent(
            config=runtime_config,
            llm=model,
            user_id=user_id,
        )
