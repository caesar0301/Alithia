"""OmniResearch subagent for structured research workflows.

A soothe framework subagent that:
1. Bootstraps research workspaces under {soothe_workspace}/omr-output/
2. Routes to appropriate research patterns (Evidence-First, etc.)
3. Collects materials from multiple sources
4. Extracts evidence with minimal parsing
5. Maintains skill tree state for progress tracking

RFC Reference: RFC-011
"""

from __future__ import annotations

import logging
from typing import Any

from soothe_sdk.plugin import plugin, subagent

from alithia import SOOTHE_HOME
from alithia.omr.events import (
    OmrErrorEvent,
    OmrEvidenceExtractedEvent,
    OmrMaterialCollectedEvent,
    OmrStepEvent,
)
from alithia.omr.implementation import create_omr_subagent
from alithia.omr.state import (
    DEFAULT_TREE_STATE,
    AgentState,
    OmrRuntimeConfig,
    default_agent_state,
)

logger = logging.getLogger(__name__)

__all__ = [
    "OmniResearchPlugin",
    "create_omr_subagent",
    "OmrRuntimeConfig",
    "AgentState",
    "DEFAULT_TREE_STATE",
    "default_agent_state",
    "OmrStepEvent",
    "OmrMaterialCollectedEvent",
    "OmrEvidenceExtractedEvent",
    "OmrErrorEvent",
]


@plugin(
    name="omr",
    version="1.0.0",
    description="OmniResearch structured workflow with pattern routing",
    dependencies=[
        "langgraph>=0.2.0",
        "arxiv>=2.0.0",
        "pdfplumber>=0.10.0",
        "httpx>=0.25.0",
        "html2text>=2020.1.16",
    ],
    trust_level="standard",
)
class OmniResearchPlugin:
    """OmniResearch plugin for structured research workflows.

    Provides a subagent that:
    1. Creates research workspaces with directory structure
    2. Routes user requests to appropriate patterns
    3. Collects materials from ArXiv, GitHub, HuggingFace, Web
    4. Extracts evidence and generates research brief
    5. Tracks progress via skill tree state
    """

    async def on_load(self, context: Any) -> None:
        """Validate dependencies are available.

        Args:
            context: Plugin context with logger and config.
        """
        context.logger.info("Loading OmniResearch plugin v1.0.0")

        # Check for dependencies
        try:
            import arxiv  # noqa: F401

            context.logger.debug("arxiv SDK available")
        except ImportError:
            context.logger.warning("arxiv not installed. Install with: pip install arxiv")

        try:
            import httpx  # noqa: F401

            context.logger.debug("httpx available")
        except ImportError:
            context.logger.warning("httpx not installed. Install with: pip install httpx")

        try:
            import html2text  # noqa: F401

            context.logger.debug("html2text available")
        except ImportError:
            context.logger.warning("html2text not installed. Install with: pip install html2text")

        context.logger.info("OmniResearch plugin loaded successfully")

    @subagent(
        name="omr",
        description=(
            "Structured research workflow that guides evidence-bound, traceable research "
            "with pattern-based flexibility. Supports Evidence-First, Idea-First, "
            "Decision-First, Experiment-First, and Rapid-Prototype patterns. "
            "Use for systematic literature reviews, hypothesis validation, and research projects. "
            "Output workspace: {soothe_workspace}/omr-output/{project-id}/"
        ),
        triggers=[
            "research",
            "omni",
            "omr",
            "start research",
            "literature review",
            "systematic review",
            "workflow",
            "collect papers",
            "bootstrap workspace",
        ],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create OmniResearch subagent.

        Args:
            model: LLM model (from soothe config).
            config: Soothe configuration.
            context: Plugin context with services.
            **kwargs: Additional args (alithia_config, user_id, research_topic).

        Returns:
            Subagent dict with name, description, runnable.
        """
        alithia_config = kwargs.get("alithia_config")
        user_id = kwargs.get("user_id", "default")
        research_topic = kwargs.get("research_topic", kwargs.get("query", ""))

        # Build runtime config
        if alithia_config:
            from alithia.config import Config

            try:
                full_config = Config(**alithia_config)
                runtime_config = OmrRuntimeConfig.build_runtime_config(
                    full_config, research_topic, SOOTHE_HOME
                )
            except Exception as e:
                logger.warning(f"Could not build runtime config from alithia_config: {e}")
                runtime_config = OmrRuntimeConfig(
                    workspace_base=SOOTHE_HOME / "omr-output",
                    research_topic=research_topic,
                    pattern="evidence-first",
                )
        else:
            # Fallback: use soothe default workspace
            runtime_config = OmrRuntimeConfig(
                workspace_base=SOOTHE_HOME / "omr-output",
                research_topic=research_topic,
                pattern="evidence-first",
            )

        logger.info(f"Creating OmniResearch subagent for user {user_id}")

        return create_omr_subagent(config=runtime_config, user_id=user_id)
