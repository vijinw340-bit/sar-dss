"""Dashboard statistics, activity feed, mission overview and notifications."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import ActivityLog, Mission, User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Aggregated statistics for the dashboard cards."""
    total = db.query(Mission).count()
    active = db.query(Mission).filter(Mission.status == "active").count()
    paused = db.query(Mission).filter(Mission.status == "paused").count()
    completed = db.query(Mission).filter(Mission.status == "completed").count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    missing_today = (
        db.query(Mission)
        .filter(Mission.last_contact_time >= today_start)
        .count()
    )

    active_missions = (
        db.query(Mission)
        .filter(Mission.status.in_(["active", "paused"]))
        .order_by(Mission.risk_score.desc())
        .all()
    )
    high_risk = sum(1 for m in active_missions if m.risk_score >= 50)
    total_area = sum(m.search_area_sqnm or 0 for m in active_missions)

    return {
        "total_missions": total,
        "active_missions": active,
        "paused_missions": paused,
        "completed_missions": completed,
        "aircraft_missing_today": missing_today,
        "high_risk_missions": high_risk,
        "active_search_area_sqnm": round(total_area, 1),
    }


@router.get("/activities")
def recent_activities(
    limit: int = 12,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Most recent activity feed entries."""
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [
        {
            "id": log.id,
            "action": log.action,
            "description": log.description,
            "mission_id": log.mission_id,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/missions-overview")
def missions_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Mission data for the live dashboard map."""
    missions = (
        db.query(Mission)
        .filter(Mission.status.in_(["active", "paused"]))
        .order_by(Mission.risk_score.desc())
        .all()
    )
    return [
        {
            "id": m.id,
            "mission_name": m.mission_name,
            "status": m.status,
            "lkp_latitude": m.lkp_latitude,
            "lkp_longitude": m.lkp_longitude,
            "predicted_latitude": m.predicted_latitude,
            "predicted_longitude": m.predicted_longitude,
            "search_radius_nm": m.search_radius_nm,
            "search_area_sqnm": m.search_area_sqnm,
            "risk_score": m.risk_score,
            "heading_deg": m.heading_deg,
            "ground_speed_kts": m.ground_speed_kts,
            "elapsed_hours": m.elapsed_hours,
            "weather_conditions": m.weather_conditions,
            "last_contact_time": m.last_contact_time,
        }
        for m in missions
    ]


@router.get("/notifications")
def notifications(
    hours: int = 48,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """System notifications derived from active missions."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    missions = (
        db.query(Mission)
        .filter(Mission.last_contact_time >= cutoff)
        .order_by(Mission.risk_score.desc())
        .all()
    )
    items = []
    for m in missions[:10]:
        if m.risk_score >= 75:
            items.append({
                "level": "critical",
                "message": f"{m.mission_name}: CRITICAL risk ({m.risk_score:.0f}/100). Immediate response required.",
            })
        elif m.risk_score >= 50:
            items.append({
                "level": "warning",
                "message": f"{m.mission_name}: High risk ({m.risk_score:.0f}/100). Review search allocation.",
            })
        elif m.fuel_remaining_hours is not None and 0 < m.fuel_remaining_hours < m.elapsed_hours:
            items.append({
                "level": "warning",
                "message": f"{m.mission_name}: Fuel endurance likely exhausted.",
            })
    if not items:
        items.append({"level": "info", "message": "No critical notifications."})
    return items
