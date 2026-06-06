"""PaperLens LangGraph workflow implementation.

Creates and compiles the 5-node workflow graph.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from alithia_agent.paperlens.state import AgentState, PaperLensConfig
from alithia_agent.paperlens.nodes import make_nodes

logger = logging.getLogger(__name__)


def create_paperlens_graph(
    config: PaperLensConfig,
    llm: Any | None = None,
) -> StateGraph:
    """Create the PaperLens workflow graph.

    Args:
        config: PaperLens configuration.
        llm: Optional LLM client for metadata enhancement.

    Returns:
        LangGraph StateGraph (compile before execution).
    """
    # Create nodes
    nodes = make_nodes(config, llm)

    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("validate_input", nodes["validate_input"])
    graph.add_node("parse_pdfs", nodes["parse_pdfs"])
    graph.add_node("calculate_similarity", nodes["calculate_similarity"])
    graph.add_node("rank_results", nodes["rank_results"])
    graph.add_node("generate_summary", nodes["generate_summary"])

    # Add edges (linear workflow)
    graph.add_edge(START, "validate_input")
    graph.add_edge("validate_input", "parse_pdfs")
    graph.add_edge("parse_pdfs", "calculate_similarity")
    graph.add_edge("calculate_similarity", "rank_results")
    graph.add_edge("rank_results", "generate_summary")
    graph.add_edge("generate_summary", END)

    logger.info("PaperLens workflow graph created")

    return graph


def create_paperlens_subagent(
    config: PaperLensConfig,
    llm: Any | None = None,
    user_id: str = "default",
) -> dict[str, Any]:
    """Create PaperLens subagent.

    Args:
        config: PaperLens configuration.
        llm: Optional LLM client.
        user_id: User identifier.

    Returns:
        Subagent dict with name, description, runnable, config.
    """
    # Create graph
    graph = create_paperlens_graph(config, llm)

    # Compile
    compiled = graph.compile()

    logger.info(f"PaperLens subagent created for user {user_id}")

    return {
        "name": "paperlens",
        "description": (
            "Discover relevant academic papers from PDF collections by "
            "semantic similarity matching. Use for local paper analysis."
        ),
        "runnable": compiled,
        "config": config,
    }


__all__ = [
    "create_paperlens_graph",
    "create_paperlens_subagent",
]