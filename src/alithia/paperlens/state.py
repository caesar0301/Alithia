"""PaperLens state and configuration models.

AgentState TypedDict for LangGraph workflow.
PaperLensRuntimeConfig for runtime parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field

from alithia.models import AcademicPaper, ScoredPaper

if TYPE_CHECKING:
    from alithia.config.schema import Config


class PaperLensRuntimeConfig(BaseModel):
    """PaperLens runtime configuration (derived from global config)."""

    model_config = ConfigDict(extra="forbid")

    # PDF processing
    pdf_extensions: list[str] = Field(default=["pdf"])
    recursive_scan: bool = Field(default=True)
    max_papers: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=8, ge=1, le=32)

    # Similarity
    sbert_model: str = "all-MiniLM-L6-v2"
    use_gpu: bool = Field(default=False)
    top_n: int = Field(default=10, ge=1, le=50)

    # LLM enhancement (injected from researcher_profile)
    llm_enhance_metadata: bool = True
    llm_max_tokens: int = Field(default=500, ge=100, le=1000)
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    llm_model: str = "qwen-turbo-latest"

    # Output
    output_format: Literal["markdown", "json"] = "markdown"
    include_full_text: bool = False

    @classmethod
    def build_runtime_config(cls, global_config: Config) -> PaperLensRuntimeConfig:
        """Build runtime config from global alithia config.

        Args:
            global_config: The loaded alithia Config object.

        Returns:
            PaperLensRuntimeConfig ready for agent execution.
        """

        cfg = global_config
        profile = cfg.researcher_profile

        return cls(
            pdf_extensions=cfg.paperlens_agent.pdf_extensions,
            recursive_scan=cfg.paperlens_agent.recursive_scan,
            max_papers=cfg.paperlens_agent.max_papers,
            batch_size=cfg.paperlens_agent.batch_size,
            sbert_model=cfg.paperlens_agent.sbert_model,
            use_gpu=cfg.paperlens_agent.force_gpu,
            top_n=cfg.paperlens_agent.top_n,
            llm_enhance_metadata=cfg.paperlens_agent.llm_enhance_metadata,
            llm_max_tokens=cfg.paperlens_agent.llm_max_tokens,
            llm_api_key=profile.llm.openai_api_key if profile.llm else None,
            llm_api_base=profile.llm.openai_api_base if profile.llm else None,
            llm_model=profile.llm.model_name if profile.llm else "qwen-turbo-latest",
            output_format=cfg.paperlens_agent.output_format,
            include_full_text=cfg.paperlens_agent.include_full_text,
        )


# Backward-compatible function wrapper for build_runtime_config
def build_runtime_config(global_config: Config) -> PaperLensRuntimeConfig:
    """Build runtime config from global alithia config (backward-compatible wrapper).

    Args:
        global_config: The loaded alithia Config object.

    Returns:
        PaperLensRuntimeConfig ready for agent execution.
    """
    return PaperLensRuntimeConfig.build_runtime_config(global_config)


class AgentState(TypedDict):
    """LangGraph agent state for PaperLens workflow.

    State flows through:
    validate_input → parse_pdfs → calculate_similarity → rank_results → generate_summary
    """

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperLensRuntimeConfig
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


# Legacy alias for backward compatibility
PaperLensConfig = PaperLensRuntimeConfig


__all__ = [
    "PaperLensRuntimeConfig",
    "build_runtime_config",
    "AgentState",
    # Legacy alias
    "PaperLensConfig",
]
