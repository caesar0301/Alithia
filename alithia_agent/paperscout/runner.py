"""Direct PaperScout workflow runner for scheduler/daemon use.

Bypasses soothe's StrangeLoop orchestration and runs the LangGraph workflow
with explicit date-range parameters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from alithia_agent.config.schema import Config
from alithia_agent.paperscout.implementation import create_paperscout_graph
from alithia_agent.paperscout.state import AgentState, PaperScoutRuntimeConfig

logger = logging.getLogger(__name__)

RunStatus = Literal["sent", "empty", "failed"]


@dataclass(frozen=True)
class PaperScoutRunResult:
    """Result of a direct PaperScout workflow execution."""

    paper_count: int
    status: RunStatus
    errors: list[str]
    metrics: dict[str, Any]


def build_scheduler_config(
    global_config: Config,
    *,
    from_date: str,
    to_date: str,
    source: Literal["scheduler", "scheduler_retry", "gap_fill", "manual"],
) -> PaperScoutRuntimeConfig:
    """Build PaperScout runtime config with explicit scheduler date range."""
    runtime_config = PaperScoutRuntimeConfig.build_runtime_config(global_config)
    return runtime_config.with_scheduler_params(
        from_date=from_date,
        to_date=to_date,
        source=source,
    )


def _initial_state(
    runtime_config: PaperScoutRuntimeConfig,
    user_id: str,
) -> AgentState:
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


def _resolve_status(paper_count: int, errors: list[str]) -> RunStatus:
    if errors:
        return "failed"
    if paper_count > 0:
        return "sent"
    return "empty"


async def run_paperscout_for_dates(
    global_config: Config,
    store: Any,
    user_id: str,
    *,
    from_date: str,
    to_date: str,
    source: Literal["scheduler", "scheduler_retry", "gap_fill", "manual"],
) -> PaperScoutRunResult:
    """Run PaperScout workflow for an explicit date range.

    Args:
        global_config: Loaded alithia configuration.
        store: AsyncPersistStore-compatible storage (load/save).
        user_id: User identifier.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        source: Run source tag for metrics and notification records.

    Returns:
        PaperScoutRunResult with paper_count, terminal status, and errors.
    """
    runtime_config = build_scheduler_config(
        global_config,
        from_date=from_date,
        to_date=to_date,
        source=source,
    )

    graph = create_paperscout_graph(store, user_id, runtime_config)
    compiled = graph.compile()
    initial_state = _initial_state(runtime_config, user_id)

    logger.info(
        "Running PaperScout workflow: %s to %s (source=%s, user=%s)",
        from_date,
        to_date,
        source,
        user_id,
    )

    try:
        result = await compiled.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("PaperScout workflow failed for %s to %s", from_date, to_date)
        return PaperScoutRunResult(
            paper_count=0,
            status="failed",
            errors=[str(exc)],
            metrics={},
        )

    errors = list(result.get("errors") or [])
    metrics = dict(result.get("metrics") or {})
    paper_count = int(metrics.get("paper_count", 0))

    status = _resolve_status(paper_count, errors)
    logger.info(
        "PaperScout workflow finished: %s to %s, papers=%d, status=%s",
        from_date,
        to_date,
        paper_count,
        status,
    )

    return PaperScoutRunResult(
        paper_count=paper_count,
        status=status,
        errors=errors,
        metrics=metrics,
    )


__all__ = [
    "PaperScoutRunResult",
    "RunStatus",
    "build_scheduler_config",
    "run_paperscout_for_dates",
]
