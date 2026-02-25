"""
Main research agent implementation using LangGraph.
"""

import logging
from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph

from alithia.storage.base import StorageBackend

from .state import AgentState, PaperScoutConfig

logger = logging.getLogger(__name__)

NODE_PROGRESS: Dict[str, float] = {
    "profile_analysis": 0.10,
    "data_collection": 0.30,
    "relevance_assessment": 0.55,
    "content_generation": 0.80,
    "communication": 0.95,
}


def _describe_result(name: str, result: dict) -> str:
    """Generate a human-readable milestone from a node's return value."""
    step = result.get("current_step", "")

    if name == "profile_analysis":
        if "error" in step:
            return "Profile validation failed"
        return "Profile validated"

    if name == "data_collection":
        papers = result.get("discovered_papers", [])
        if papers:
            return f"Collected {len(papers)} papers from ArXiv"
        return "No new papers to process"

    if name == "relevance_assessment":
        scored = result.get("scored_papers", [])
        if scored:
            return f"Ranked {len(scored)} papers by relevance"
        return "No papers to rank"

    if name == "content_generation":
        if result.get("email_content"):
            return "Generated summaries & recommendations"
        if "error" in step:
            return "Content generation failed"
        return "No content to generate"

    if name == "communication":
        if "error" in step:
            return "Email delivery failed"
        return "Workflow complete"

    return step or name


class PaperScoutAgent:
    """
    LangGraph-based research agent for personalized ArXiv paper recommendations.
    Delivers daily paper recommendations from ArXiv to your inbox.
    """

    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        user_id: str = "default",
        on_step: Optional[Callable[[float, str], None]] = None,
    ):
        """
        Initialize the research agent.

        Args:
            storage: Injected storage backend (optional for backward compat)
            user_id: User identifier
            on_step: Optional callback(progress, label) called after each major node
        """
        self._storage = storage
        self._user_id = user_id
        self._on_step = on_step
        self.workflow = self._create_workflow()

    def _wrap_node(self, fn: Callable, name: str) -> Callable:
        """Wrap a node to report a descriptive milestone after execution."""
        progress = NODE_PROGRESS[name]
        callback = self._on_step

        def wrapped(state):
            result = fn(state)
            if callback:
                try:
                    message = _describe_result(name, result)
                    callback(progress, message)
                except Exception:
                    pass
            return result

        return wrapped

    def _create_workflow(self):
        """Create the LangGraph workflow."""
        from .nodes import make_nodes

        nodes = make_nodes(self._storage, self._user_id)

        workflow = StateGraph(AgentState)

        for name, fn in nodes.items():
            if self._on_step and name in NODE_PROGRESS:
                workflow.add_node(name, self._wrap_node(fn, name))
            else:
                workflow.add_node(name, fn)

        workflow.add_edge("profile_analysis", "data_collection")
        workflow.add_edge("data_collection", "relevance_assessment")
        workflow.add_edge("relevance_assessment", "content_generation")
        workflow.add_edge("content_generation", "communication")

        workflow.set_entry_point("profile_analysis")
        workflow.set_finish_point("communication")

        return workflow.compile()

    def run(self, config: PaperScoutConfig) -> Dict[str, Any]:
        """
        Run the research agent with given configuration.

        Args:
            config: PaperScoutConfig object with all necessary parameters

        Returns:
            Final state dictionary with results
        """
        logger.info("Starting research agent workflow...")

        initial_state = AgentState(config=config, debug_mode=getattr(config, "debug", False))

        try:
            final_state = self.workflow.invoke(initial_state)

            if hasattr(final_state, "get_summary"):
                summary = final_state.get_summary()
                papers_sent = len(final_state.scored_papers)
                errors = final_state.error_log
            else:
                summary = {
                    "current_step": final_state.get("current_step", "unknown"),
                    "papers_discovered": len(final_state.get("discovered_papers", [])),
                    "papers_scored": len(final_state.get("scored_papers", [])),
                    "errors": len(final_state.get("error_log", [])),
                    "metrics": final_state.get("performance_metrics", {}),
                }
                papers_sent = len(final_state.get("scored_papers", []))
                errors = final_state.get("error_log", [])

            logger.info(f"Workflow completed: {summary}")

            return {
                "success": True,
                "summary": summary,
                "papers_sent": papers_sent,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return {"success": False, "error": str(e), "errors": initial_state.error_log}

    def get_workflow_info(self) -> Dict[str, Any]:
        return {
            "name": "Alithia Research Agent",
            "description": "A personalized arXiv recommendation agent.",
            "nodes": [
                "profile_analysis",
                "data_collection",
                "relevance_assessment",
                "content_generation",
                "communication",
            ],
            "entry_point": "profile_analysis",
            "exit_point": "communication",
        }
