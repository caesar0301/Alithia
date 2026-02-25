"""
GET /api/overview — Dashboard overview data.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Request

from alithia.dashboard.models import OverviewResponse, ServiceStatus

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(request: Request):
    storage = request.app.state.storage
    user_id = request.app.state.user_id
    config = request.app.state.config
    task_manager = request.app.state.task_manager

    ps_settings = config.get("paperscout_agent", config.get("arxrec", {}))
    query = ps_settings.get("query", "")

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    assessed = storage.get_assessed_papers(user_id, query, thirty_days_ago, today)
    emailed = storage.get_emailed_papers(user_id, days_back=30)
    notifications = storage.get_notification_records_range(user_id, query, thirty_days_ago, today)
    sent_count = sum(1 for n in notifications if n.get("status") == "sent")

    zotero_papers = storage.get_zotero_papers(user_id, max_age_hours=9999)
    zotero_count = len(zotero_papers) if zotero_papers else 0

    scholar_pubs = storage.get_scholar_publications(user_id, limit=9999)

    # Build service statuses
    services = []
    for name in ["zotero", "google_scholar"]:
        last = storage.get_last_sync(user_id, name)
        configured = False
        if name == "zotero":
            configured = bool(config.get("researcher_profile", {}).get("zotero"))
        elif name == "google_scholar":
            configured = bool(config.get("researcher_profile", {}).get("googlescholarconnection"))
        status = "not_configured"
        if configured:
            status = "ok" if last and last.get("status") == "success" else "pending"
        services.append(ServiceStatus(
            name=name,
            configured=configured,
            last_synced=last.get("completed_at") if last else None,
            status=status,
        ))

    recent_tasks = task_manager.get_tasks(limit=5)

    return OverviewResponse(
        total_papers_assessed=len(assessed),
        total_papers_emailed=len(emailed),
        total_notifications_sent=sent_count,
        zotero_papers_cached=zotero_count,
        scholar_publications=len(scholar_pubs),
        services=services,
        recent_tasks=recent_tasks,
    )
