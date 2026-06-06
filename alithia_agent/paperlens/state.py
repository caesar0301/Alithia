"""PaperLens state and configuration models.

AgentState TypedDict for LangGraph workflow.
PaperLensConfig for user-controlled parameters.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from alithia_agent.models import AcademicPaper, ScoredPaper


class PaperLensConfig(BaseModel):
    """PaperLens subagent configuration."""

    model_config = ConfigDict(extra="forbid")

    # PDF processing
    pdf_extensions: list[str] = Field(default=["pdf"])
    recursive_scan: bool = Field(default=True)
    max_papers: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=8, ge=1, le=32)

    # Similarity
    sbert_model: str = "all-MiniLM-L6-v2"
    use_gpu: bool = Field(default=False)

    # LLM enhancement
    llm_enhance_metadata: bool = Field(default=True)
    llm_max_tokens: int = Field(default=500, ge=100, le=1000)

    # Output
    output_format: Literal["markdown", "json"] = "markdown"
    include_full_text: bool = Field(default=False)


class AgentState(TypedDict):
    """LangGraph agent state for PaperLens workflow.

    State flows through: validate_input → parse_pdfs → calculate_similarity → rank_results → generate_summary
    """

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperLensConfig
    user_id: str

    # Input
    query: str  # Research topic/question
    pdf_path: str  # Directory or file path

    # Intermediate results
    parsed_papers: list[AcademicPaper]  # After parse_pdfs
    papers_with_scores: list[ScoredPaper]  # After calculate_similarity
    ranked_papers: list[ScoredPaper]  # After rank_results

    # Output
    response_content: str  # Formatted summary

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]


__all__ = [
    "PaperLensConfig",
    "AgentState",
]