"""
GET /api/overview — Dashboard overview data.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Request

from alithia.dashboard.models import OverviewResponse, ServiceStatus

router = APIRouter(prefix="/api", tags=["overview"])

_ALL_SERVICES = [
    ("zotero", lambda rp: bool(rp.get("zotero"))),
    ("google_scholar", lambda rp: bool(rp.get("google_scholar") or rp.get("googlescholarconnection"))),
    ("github", lambda rp: bool(rp.get("github", {}).get("github_username"))),
    ("email", lambda rp: bool(rp.get("email_notification", {}).get("smtp_server"))),
    ("llm", lambda rp: bool(rp.get("llm", {}).get("openai_api_key"))),
]


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

    rp = config.get("researcher_profile", {})
    services = []
    for name, is_configured in _ALL_SERVICES:
        configured = is_configured(rp)
        last = storage.get_last_sync(user_id, name) if name in ("zotero", "google_scholar") else None
        if configured:
            if last:
                status = "ok" if last.get("status") == "success" else "pending"
            else:
                status = "ok"
        else:
            status = "not_configured"
        services.append(
            ServiceStatus(
                name=name,
                configured=configured,
                last_synced=last.get("completed_at") if last else None,
                status=status,
            )
        )

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
