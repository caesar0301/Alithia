"""
POST /api/agents/run, GET /api/agents/tasks — Agent execution endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from alithia.dashboard.models import BackgroundTask, RunAgentRequest, SyncRequest
from alithia.dashboard.turnstile import verify_turnstile

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/run", response_model=BackgroundTask, dependencies=[Depends(verify_turnstile)])
async def run_agent(request: Request, body: RunAgentRequest):
    dispatcher = request.app.state.agent_dispatcher
    task = await dispatcher.dispatch(body)
    return task


@router.post("/sync", response_model=BackgroundTask, dependencies=[Depends(verify_turnstile)])
async def trigger_sync(request: Request, body: SyncRequest):
    dispatcher = request.app.state.agent_dispatcher
    req = RunAgentRequest(
        agent_type="sync",
        parameters={"connector": body.connector, "force_full": body.force_full},
    )
    task = await dispatcher.dispatch(req)
    return task


@router.get("/tasks", response_model=list[BackgroundTask])
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    task_manager = request.app.state.task_manager
    return task_manager.get_tasks(status=status, limit=limit)


@router.get("/tasks/{task_id}", response_model=BackgroundTask)
async def get_task(request: Request, task_id: str):
    task_manager = request.app.state.task_manager
    task = task_manager.get_task(task_id)
    if task is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Task not found")
    return task
