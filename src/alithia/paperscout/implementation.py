"""PaperScout LangGraph workflow implementation.

Creates and compiles the 6-node workflow graph.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from alithia.paperscout.nodes import make_nodes
from alithia.paperscout.state import AgentState, PaperScoutRuntimeConfig

logger = logging.getLogger(__name__)


def _default_agent_state(
    runtime_config: PaperScoutRuntimeConfig,
    user_id: str,
) -> AgentState:
    """Build a complete initial AgentState for graph invocation."""
    return {
        "messages": [],
        "config": runtime_config,
        "user_id": user_id,
        "discovered_papers": [],
        "research_interests": [],
        "scored_papers": [],
        "email_content": None,
        "errors": [],
        "info": [],
        "metrics": {},
    }


def _merge_input_state(
    input_state: Any,
    runtime_config: PaperScoutRuntimeConfig,
    user_id: str,
) -> AgentState:
    """Merge soothe/subagent input with required PaperScout state fields."""
    merged = _default_agent_state(runtime_config, user_id)
    if isinstance(input_state, dict):
        merged.update(input_state)  # type: ignore[typeddict-item]
    merged["config"] = runtime_config
    merged["user_id"] = user_id
    return merged


def _wrap_compiled_graph(
    compiled: Any,
    runtime_config: PaperScoutRuntimeConfig,
    user_id: str,
) -> Any:
    """Ensure graph invocations always include config in initial state."""

    class WrappedGraph:
        async def ainvoke(self, input_state: Any, *args: Any, **kwargs: Any) -> Any:
            return await compiled.ainvoke(
                _merge_input_state(input_state, runtime_config, user_id),
                *args,
                **kwargs,
            )

        async def astream(
            self,
            input_state: Any,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncIterator[Any]:
            async for chunk in compiled.astream(
                _merge_input_state(input_state, runtime_config, user_id),
                *args,
                **kwargs,
            ):
                yield chunk

        def __getattr__(self, name: str) -> Any:
            return getattr(compiled, name)

    return WrappedGraph()


def create_paperscout_graph(
    store: Any,
    user_id: str,
    config: PaperScoutRuntimeConfig,
) -> StateGraph:
    """Create the PaperScout workflow graph.

    Args:
        store: AsyncPersistStore for persistence.
        user_id: User identifier.
        config: PaperScout runtime configuration.

    Returns:
        LangGraph StateGraph (compile before execution).
    """
    # Config is injected via closure so soothe task invocations work without
    # pre-populating state["config"].
    nodes = make_nodes(store, user_id, config)

    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("profile_analysis", nodes["profile_analysis"])
    graph.add_node("data_collection", nodes["data_collection"])
    graph.add_node("relevance_assessment", nodes["relevance_assessment"])
    graph.add_node("content_generation", nodes["content_generation"])
    graph.add_node("persist_digest", nodes["persist_digest"])
    graph.add_node("communication", nodes["communication"])

    # Add edges (linear workflow)
    graph.add_edge(START, "profile_analysis")
    graph.add_edge("profile_analysis", "data_collection")
    graph.add_edge("data_collection", "relevance_assessment")
    graph.add_edge("relevance_assessment", "content_generation")
    graph.add_edge("content_generation", "persist_digest")
    graph.add_edge("persist_digest", "communication")
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
    graph = create_paperscout_graph(store, user_id, config)

    # Compile
    compiled = graph.compile()
    wrapped = _wrap_compiled_graph(compiled, config, user_id)

    logger.info(f"PaperScout subagent created for user {user_id}")

    return {
        "name": "paperscout",
        "description": (
            "ArXiv paper recommendation agent that delivers personalized daily "
            "paper recommendations by analyzing your Zotero library and ranking "
            "newly published papers by relevance."
        ),
        "runnable": wrapped,
        "config": config,
    }


__all__ = [
    "create_paperscout_graph",
    "create_paperscout_subagent",
]
