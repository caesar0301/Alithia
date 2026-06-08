"""PaperScout event types.

Events emitted during workflow execution for observability.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PaperScoutStepEvent(BaseModel):
    """Workflow step progress event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperscout.step"] = "alithia.paperscout.step"
    step: str = ""
    status: str = ""


class PaperScoutPaperFoundEvent(BaseModel):
    """New relevant paper discovered event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperscout.paper.found"] = "alithia.paperscout.paper.found"
    paper_title: str = ""
    arxiv_id: str = ""
    score: float = 0.0


class PaperScoutEmailSentEvent(BaseModel):
    """Email notification sent event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperscout.email.sent"] = "alithia.paperscout.email.sent"
    recipient: str = ""
    papers_count: int = 0


class PaperScoutErrorEvent(BaseModel):
    """Error event."""

    model_config = ConfigDict(extra="allow")

    type: Literal["alithia.paperscout.error"] = "alithia.paperscout.error"
    error_message: str = ""
    step: str = ""


# Event type constants
PAPERSCOUT_STEP = "alithia.paperscout.step"
PAPERSCOUT_PAPER_FOUND = "alithia.paperscout.paper.found"
PAPERSCOUT_EMAIL_SENT = "alithia.paperscout.email.sent"
PAPERSCOUT_ERROR = "alithia.paperscout.error"


__all__ = [
    "PaperScoutStepEvent",
    "PaperScoutPaperFoundEvent",
    "PaperScoutEmailSentEvent",
    "PaperScoutErrorEvent",
    "PAPERSCOUT_STEP",
    "PAPERSCOUT_PAPER_FOUND",
    "PAPERSCOUT_EMAIL_SENT",
    "PAPERSCOUT_ERROR",
]
