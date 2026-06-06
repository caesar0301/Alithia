"""PaperLens subagent for PDF discovery and ranking.

A soothe framework subagent that:
1. Parses PDFs using Docling with IBM Granite VLM
2. Enhances metadata using LLM when needed
3. Calculates semantic similarity using sentence embeddings
4. Returns ranked results with relevance scores
"""

from alithia_agent.paperlens.implementation import create_paperlens_subagent
from alithia_agent.paperlens.state import PaperLensConfig, AgentState

__all__ = [
    "create_paperlens_subagent",
    "PaperLensConfig",
    "AgentState",
]