"""OmniResearch LangGraph workflow implementation.

Creates and compiles the workflow graph for pattern-based research.

RFC Reference: RFC-010 Section 5.1
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from alithia_agent.omr.nodes import bootstrap_node, collection_node, evidence_node
from alithia_agent.omr.state import AgentState, OmrRuntimeConfig, default_agent_state

logger = logging.getLogger(__name__)


def create_omr_graph(config: OmrRuntimeConfig, user_id: str) -> StateGraph:
    """Create OmniResearch workflow graph.

    Core pipeline: bootstrap → pattern_router → collection → evidence

    Args:
        config: OmrRuntimeConfig with research settings.
        user_id: User identifier.

    Returns:
        LangGraph StateGraph (compile before execution).
    """
    # Create graph with AgentState
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("bootstrap", bootstrap_node)
    graph.add_node("collection", collection_node)
    graph.add_node("evidence", evidence_node)

    # Add edges (core pipeline)
    graph.add_edge(START, "bootstrap")
    graph.add_edge("bootstrap", "collection")
    graph.add_edge("collection", "evidence")
    graph.add_edge("evidence", END)

    logger.info("OmniResearch workflow graph created")

    return graph


def _wrap_compiled_graph(
    compiled: Any,
    runtime_config: OmrRuntimeConfig,
    user_id: str,
) -> Any:
    """Ensure graph invocations include config in initial state."""

    class WrappedGraph:
        async def ainvoke(self, input_state: Any, *args: Any, **kwargs: Any) -> Any:
            merged = default_agent_state(runtime_config, user_id)
            if isinstance(input_state, dict):
                merged.update(input_state)
            # CRITICAL: Always set config after merge to guarantee it exists
            merged["config"] = runtime_config
            merged["user_id"] = user_id
            return await compiled.ainvoke(merged, *args, **kwargs)

        async def astream(
            self,
            input_state: Any,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[Any]:
            merged = default_agent_state(runtime_config, user_id)
            if isinstance(input_state, dict):
                merged.update(input_state)
            # CRITICAL: Always set config after merge to guarantee it exists
            merged["config"] = runtime_config
            merged["user_id"] = user_id
            async for chunk in compiled.astream(merged, *args, **kwargs):
                yield chunk

        def with_config(self, config: Any = None, **kwargs: Any) -> Any:
            """Return a new WrappedGraph with config applied to underlying compiled graph."""
            # Apply config to compiled, keep same wrapper behavior
            new_compiled = compiled.with_config(config, **kwargs)
            return _wrap_compiled_graph(new_compiled, runtime_config, user_id)

        def __getattr__(self, name: str) -> Any:
            return getattr(compiled, name)

    return WrappedGraph()


def create_omr_subagent(
    config: OmrRuntimeConfig,
    user_id: str = "default",
) -> dict[str, Any]:
    """Create OmniResearch subagent.

    Args:
        config: OmrRuntimeConfig with research settings.
        user_id: User identifier.

    Returns:
        Subagent dict with name, description, runnable.
    """
    # Create graph
    graph = create_omr_graph(config, user_id)

    # Compile
    compiled = graph.compile()
    wrapped = _wrap_compiled_graph(compiled, config, user_id)

    logger.info(f"OmniResearch subagent created for user {user_id}")

    return {
        "name": "omr",
        "description": (
            "Structured research workflow with pattern-based routing. "
            "Supports Evidence-First, Idea-First, Decision-First, "
            "Experiment-First, and Rapid-Prototype patterns."
        ),
        "runnable": wrapped,
        "config": config,
    }


__all__ = [
    "create_omr_graph",
    "create_omr_subagent",
]
