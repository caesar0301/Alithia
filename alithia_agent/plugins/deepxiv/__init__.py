"""DeepXiv plugin - academic paper search and progressive reading.

Provides access to arXiv, bioRxiv, medRxiv, and PubMed Central papers with
AI-generated TLDRs and section-level access for token-efficient reading.

Tools:
- deepxiv_search: Semantic paper search
- deepxiv_paper_brief: Quick summary (TLDR, keywords, citations)
- deepxiv_paper_metadata: Paper structure overview
- deepxiv_read_section: Read specific sections
- deepxiv_get_full_paper: Complete paper content
- deepxiv_trending: Trending papers by social signals
- deepxiv_websearch: Web search (higher token cost)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool

from alithia_agent.plugins.deepxiv.toolkit import DeepxivToolkit

logger = logging.getLogger(__name__)


class DeepxivPlugin:
    """DeepXiv plugin for academic paper operations.

    Provides tools for:
    - Semantic paper search across arXiv, bioRxiv, medRxiv, PMC
    - AI-generated TLDRs and summaries
    - Section-level paper reading for token efficiency
    - Trending papers based on social signals

    This is a thin wrapper around the DeepxivToolkit
    that provides plugin-compatible interface for alithia.
    """

    # Plugin metadata (for manual registration fallback)
    _plugin_manifest = type(
        "PluginManifest",
        (),
        {
            "name": "deepxiv",
            "version": "1.0.0",
            "description": "Academic paper search and progressive reading toolkit",
            "dependencies": ["langchain-core>=0.1.0", "deepxiv-sdk>=0.1.0"],
            "trust_level": "standard",
        },
    )()

    def __init__(self) -> None:
        """Initialize the plugin."""
        self._tools: list[BaseTool] = []

    async def on_load(self, context: Any) -> None:
        """Initialize the DeepXiv toolkit.

        Args:
            context: Plugin context with config and logger.
        """
        context.logger.info("Loading DeepXiv plugin v1.0.0")

        # Get config from context if available
        token: str | None = None
        timeout: int = 60
        max_retries: int = 3

        # Try to get config from context.config if available
        config = getattr(context, "config", None)
        if config and hasattr(config, "deepxiv"):
            deepxiv_config = config.deepxiv
            if deepxiv_config:
                token = getattr(deepxiv_config, "token", None)
                timeout = getattr(deepxiv_config, "timeout", 60)
                max_retries = getattr(deepxiv_config, "max_retries", 3)

        try:
            toolkit = DeepxivToolkit(
                token=token,
                timeout=timeout,
                max_retries=max_retries,
            )
            self._tools = toolkit.get_tools()
            context.logger.info(
                "Loaded %d DeepXiv tools (token=%s)",
                len(self._tools),
                "configured" if token else "auto-register",
            )
        except ImportError as e:
            context.logger.warning("deepxiv_sdk not installed, DeepXiv tools unavailable")
            context.logger.debug("Import error: %s", e)
            self._tools = []

    def get_tools(self) -> list[BaseTool]:
        """Get LangChain BaseTool instances.

        Returns:
            List of DeepXiv tool instances.
        """
        return self._tools


__all__ = ["DeepxivPlugin", "DeepxivToolkit"]
