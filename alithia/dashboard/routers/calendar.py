"""
GET /api/calendar — Notification calendar heatmap data.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Query, Request

from alithia.dashboard.models import CalendarDay, CalendarMonth

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/calendar", response_model=list[CalendarMonth])
async def get_calendar(
    request: Request,
    months: int = Query(3, ge=1, le=12, description="How many months back"),
):
    storage = request.app.state.storage
    user_id = request.app.state.user_id
    config = request.app.state.config

    ps_settings = config.get("paperscout_agent", config.get("arxrec", {}))
    query = ps_settings.get("query", "")

    # big_bang: the earliest date paperscout tracks; dates before it are not "missing"
    bb_str = ps_settings.get("big_bang")
    big_bang = date.fromisoformat(bb_str) if bb_str else None

    today = date.today()
    start = today.replace(day=1) - timedelta(days=30 * (months - 1))
    start = start.replace(day=1)

    if big_bang and start < big_bang:
        start = big_bang

    records = storage.get_notification_records_range(user_id, query, start, today)
    record_map = {}
    for r in records:
        nd = r.get("notification_date", "")
        record_map[nd] = r

    result = []
    current = start
    month_days = []
    cur_year, cur_month = current.year, current.month

    while current <= today:
        if current.year != cur_year or current.month != cur_month:
            if month_days:
                result.append(CalendarMonth(year=cur_year, month=cur_month, days=month_days))
            month_days = []
            cur_year, cur_month = current.year, current.month

        key = current.isoformat()
        rec = record_map.get(key)
        if rec:
            day = CalendarDay(
                date=key,
                paper_count=rec.get("paper_count", 0),
                status=rec.get("status", "missing"),
            )
        else:
            day = CalendarDay(date=key, paper_count=0, status="missing")

        month_days.append(day)
        current += timedelta(days=1)

    if month_days:
        result.append(CalendarMonth(year=cur_year, month=cur_month, days=month_days))

    return result
