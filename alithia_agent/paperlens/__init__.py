"""PaperLens subagent for PDF discovery and ranking.

A soothe framework subagent that:
1. Parses PDFs using Docling with IBM Granite VLM
2. Enhances metadata using LLM when needed
3. Calculates semantic similarity using FastEmbed embeddings
4. Returns ranked results with relevance scores
"""

from __future__ import annotations

import logging
from typing import Any

from soothe_sdk.plugin import plugin, subagent

from alithia_agent.paperlens.implementation import create_paperlens_subagent
from alithia_agent.paperlens.state import (
    AgentState,
    PaperLensConfig,  # Legacy alias
    PaperLensRuntimeConfig,
    build_runtime_config,
)

logger = logging.getLogger(__name__)

# Import events to register them with soothe's event system
from alithia_agent.paperlens import events as _events  # noqa: F401, E402

__all__ = [
    "PaperLensPlugin",
    "create_paperlens_subagent",
    "PaperLensRuntimeConfig",
    "PaperLensConfig",
    "AgentState",
    "build_runtime_config",
]


@plugin(
    name="paperlens",
    version="1.0.0",
    description="PDF discovery and ranking subagent for local paper analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "docling>=2.0.0",
        "fastembed>=0.6.0",
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
            import fastembed  # noqa: F401

            context.logger.debug("fastembed available")
        except ImportError:
            context.logger.warning("fastembed not installed. Install with: pip install fastembed")

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
        from alithia_agent.runtime_resolve import resolve_alithia_runtime

        full_config, _store, user_id = resolve_alithia_runtime(
            alithia_config=kwargs.get("alithia_config"),
            store=kwargs.get("store"),
            user_id=kwargs.get("user_id"),
        )
        try:
            runtime_config = PaperLensRuntimeConfig.build_runtime_config(full_config)
        except Exception as e:
            logger.warning("Could not build PaperLens runtime config: %s", e)
            runtime_config = PaperLensRuntimeConfig()

        logger.info("Creating PaperLens subagent for user %s", user_id)

        return create_paperlens_subagent(
            config=runtime_config,
            llm=model,
            user_id=user_id,
        )
