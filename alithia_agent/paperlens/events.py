"""PaperLens event types.

Events emitted during workflow execution for observability.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PaperLensStepEvent(BaseModel):
    """Workflow step progress event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperlens.step"] = "alithia.paperlens.step"
    step: str = ""
    status: str = ""


class PaperLensPaperParsedEvent(BaseModel):
    """PDF successfully parsed event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperlens.paper.parsed"] = "alithia.paperlens.paper.parsed"
    paper_title: str = ""
    file_name: str = ""


class PaperLensRankEvent(BaseModel):
    """Paper ranked event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperlens.paper.rank"] = "alithia.paperlens.paper.rank"
    rank: int = 0
    paper_title: str = ""
    score: float = 0.0


class PaperLensErrorEvent(BaseModel):
    """Error event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperlens.error"] = "alithia.paperlens.error"
    error_message: str = ""
    step: str = ""
    paper_id: str | None = None


class PaperLensCompleteEvent(BaseModel):
    """Workflow finished event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperlens.complete"] = "alithia.paperlens.complete"
    papers_count: int = 0


# Event type constants
PAPERLENS_STEP = "alithia.paperlens.step"
PAPERLENS_PAPER_PARSED = "alithia.paperlens.paper.parsed"
PAPERLENS_PAPER_RANK = "alithia.paperlens.paper.rank"
PAPERLENS_ERROR = "alithia.paperlens.error"
PAPERLENS_COMPLETE = "alithia.paperlens.complete"


__all__ = [
    "PaperLensStepEvent",
    "PaperLensPaperParsedEvent",
    "PaperLensRankEvent",
    "PaperLensErrorEvent",
    "PaperLensCompleteEvent",
    "PAPERLENS_STEP",
    "PAPERLENS_PAPER_PARSED",
    "PAPERLENS_PAPER_RANK",
    "PAPERLENS_ERROR",
    "PAPERLENS_COMPLETE",
]
