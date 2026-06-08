"""PaperScout LangGraph workflow implementation.

Creates and compiles the 5-node workflow graph.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from alithia_agent.paperscout.nodes import make_nodes
from alithia_agent.paperscout.state import AgentState, PaperScoutRuntimeConfig

logger = logging.getLogger(__name__)


def create_paperscout_graph(
    store: Any,
    user_id: str,
) -> StateGraph:
    """Create the PaperScout workflow graph.

    Args:
        store: AsyncPersistStore for persistence.
        user_id: User identifier.

    Returns:
        LangGraph StateGraph (compile before execution).
    """
    # Create nodes (config injected via state)
    nodes = make_nodes(store, user_id)

    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("profile_analysis", nodes["profile_analysis"])
    graph.add_node("data_collection", nodes["data_collection"])
    graph.add_node("relevance_assessment", nodes["relevance_assessment"])
    graph.add_node("content_generation", nodes["content_generation"])
    graph.add_node("communication", nodes["communication"])

    # Add edges (linear workflow)
    graph.add_edge(START, "profile_analysis")
    graph.add_edge("profile_analysis", "data_collection")
    graph.add_edge("data_collection", "relevance_assessment")
    graph.add_edge("relevance_assessment", "content_generation")
    graph.add_edge("content_generation", "communication")
    graph.add_edge("communication", END)

    logger.info("PaperScout workflow graph created")

    return graph


def create_paperscout_subagent(
    config: PaperScoutRuntimeConfig,
    store: Any,
    user_id: str = "default",
) -> dict[str, Any]:
    """Create PaperScout subagent.

    Args:
        config: PaperScout runtime configuration (with smtp and zotero attached).
        store: AsyncPersistStore.
        user_id: User identifier.

    Returns:
        Subagent dict with name, description, runnable, config.
    """
    # Create graph
    graph = create_paperscout_graph(store, user_id)

    # Compile
    compiled = graph.compile()

    logger.info(f"PaperScout subagent created for user {user_id}")

    return {
        "name": "paperscout",
        "description": (
            "ArXiv paper recommendation agent that delivers personalized daily "
            "paper recommendations by analyzing your Zotero library and ranking "
            "newly published papers by relevance."
        ),
        "runnable": compiled,
        "config": config,
    }


__all__ = [
    "create_paperscout_graph",
    "create_paperscout_subagent",
]
