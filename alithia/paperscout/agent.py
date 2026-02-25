"""
Main research agent implementation using LangGraph.
"""

import logging
from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph

from alithia.storage.base import StorageBackend

from .state import AgentState, PaperScoutConfig

logger = logging.getLogger(__name__)


class PaperScoutAgent:
    """
    LangGraph-based research agent for personalized ArXiv paper recommendations.
    Delivers daily paper recommendations from ArXiv to your inbox.
    """

    def __init__(self, storage: Optional[StorageBackend] = None, user_id: str = "default"):
        """
        Initialize the research agent.

        Args:
            storage: Injected storage backend (optional for backward compat)
            user_id: User identifier
        """
        self._storage = storage
        self._user_id = user_id
        self.workflow = self._create_workflow()

    def _create_workflow(self):
        """Create the LangGraph workflow."""
        from .nodes import make_nodes

        nodes = make_nodes(self._storage, self._user_id)

        workflow = StateGraph(AgentState)

        workflow.add_node("profile_analysis", nodes["profile_analysis"])
        workflow.add_node("data_collection", nodes["data_collection"])
        workflow.add_node("relevance_assessment", nodes["relevance_assessment"])
        workflow.add_node("content_generation", nodes["content_generation"])
        workflow.add_node("communication", nodes["communication"])

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
