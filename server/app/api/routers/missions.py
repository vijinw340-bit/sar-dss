"""Mission CRUD, calculation pipeline and intelligence endpoints."""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models import Mission, Sector, User
from app.schemas import (
    MissionCreate,
    MissionListItem,
    MissionOut,
    MissionUpdate,
    SectorOut,
    SectorUpdate,
)
from app.services import intelligence, mission_engine

router = APIRouter(prefix="/missions", tags=["Missions"])


def _get_mission_or_404(db: Session, mission_id: int) -> Mission:
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.get("", response_model=list[MissionListItem])
def list_missions(
    search: Optional[str] = Query(default=None),
    mission_status: Optional[str] = Query(default=None, alias="status"),
    aircraft: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List missions with optional search + filter parameters."""
    q = db.query(Mission)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Mission.mission_name.ilike(like))
            | (Mission.flight_number.ilike(like))
            | (Mission.registration_number.ilike(like))
            | (Mission.pilot_name.ilike(like))
        )
    if mission_status:
        q = q.filter(Mission.status == mission_status)
    if aircraft:
        q = q.filter(
            (Mission.aircraft_name.ilike(f"%{aircraft}%"))
            | (Mission.aircraft_type.ilike(f"%{aircraft}%"))
        )
    if from_date:
        q = q.filter(Mission.last_contact_time >= from_date)
    if to_date:
        q = q.filter(Mission.last_contact_time <= to_date)
    return q.order_by(Mission.created_at.desc()).all()


@router.post("", response_model=MissionOut, status_code=status.HTTP_201_CREATED)
def create_mission(
    payload: MissionCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Create a mission and run the full GIS calculation pipeline."""
    mission = Mission(
        **payload.model_dump(),
        status="active",
        created_by=current.id,
        started_at=datetime.utcnow(),
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    mission_engine.log_activity(
        db, mission, current.id, "mission_created", f"Mission '{mission.mission_name}' created"
    )
    return mission_engine.run_calculation_pipeline(db, mission, current.id)


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return a mission with all derived GIS outputs."""
    return _get_mission_or_404(db, mission_id)


@router.patch("/{mission_id}", response_model=MissionOut)
def update_mission(
    mission_id: int,
    payload: MissionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Partially update a mission. Status transitions log a timeline entry."""
    mission = _get_mission_or_404(db, mission_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] != mission.status:
        mission_engine.log_activity(
            db,
            mission,
            current.id,
            f"status_{data['status']}",
            f"Mission status changed to {data['status']}",
        )
    if data.get("status") == "completed" and mission.completed_at is None:
        mission.completed_at = datetime.utcnow()
    for field, value in data.items():
        setattr(mission, field, value)
    db.commit()
    db.refresh(mission)
    return mission


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a mission (admin only)."""
    mission = _get_mission_or_404(db, mission_id)
    db.delete(mission)
    db.commit()
    return Response(status_code=204)


@router.post("/{mission_id}/calculate", response_model=MissionOut)
def recalculate_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Re-run the search-area / probability / pattern / sector calculations."""
    mission = _get_mission_or_404(db, mission_id)
    return mission_engine.run_calculation_pipeline(db, mission, current.id)


@router.get("/{mission_id}/search-area")
def get_search_area(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the search-area GeoJSON polygon."""
    mission = _get_mission_or_404(db, mission_id)
    if not mission.search_area:
        raise HTTPException(status_code=404, detail="No search area computed yet")
    import json

    return {
        "polygon": json.loads(mission.search_area.polygon_geojson),
        "center": [mission.search_area.center_latitude, mission.search_area.center_longitude],
        "radius_nm": mission.search_area.radius_nm,
        "area_sqnm": mission.search_area.area_sqnm,
        "desired_coverage_pct": mission.search_area.desired_coverage_pct,
    }


@router.get("/{mission_id}/pattern")
def get_pattern(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all generated patterns and which one is recommended."""
    mission = _get_mission_or_404(db, mission_id)
    import json

    return [
        {
            "pattern_type": p.pattern_type,
            "recommended": p.recommended,
            "reason": p.reason,
            "params": json.loads(p.params_json or "{}"),
            "waypoints": json.loads(p.waypoints_geojson),
            "track_spacing_nm": p.track_spacing_nm,
        }
        for p in mission.patterns
    ]


@router.get("/{mission_id}/probability")
def get_probability(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return probability zone polygons with cumulative probabilities."""
    mission = _get_mission_or_404(db, mission_id)
    import json

    return [
        {
            "zone_level": z.zone_level,
            "color": z.color,
            "min_radius_nm": z.min_radius_nm,
            "max_radius_nm": z.max_radius_nm,
            "probability_pct": z.probability_pct,
            "polygon": json.loads(z.polygon_geojson),
        }
        for z in mission.zones
    ]


@router.get("/{mission_id}/sectors", response_model=list[SectorOut])
def get_sectors(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all sectors for a mission."""
    mission = _get_mission_or_404(db, mission_id)
    return mission.sectors


@router.patch("/sectors/{sector_id}", response_model=SectorOut)
def assign_sector(
    sector_id: int,
    payload: SectorUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Assign a search aircraft to a sector."""
    sector = db.get(Sector, sector_id)
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    sector.assigned_aircraft = payload.assigned_aircraft
    db.commit()
    db.refresh(sector)
    mission_engine.log_activity(
        db,
        sector.mission,
        current.id,
        "sector_assign",
        f"Aircraft '{payload.assigned_aircraft}' assigned to {sector.name}",
    )
    return sector


@router.get("/{mission_id}/analysis")
def analyze_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Full intelligence analysis: risk, prediction, weather, simulation."""
    mission = _get_mission_or_404(db, mission_id)
    return intelligence.summarize_analysis(mission)


@router.get("/{mission_id}/simulation")
def simulate_mission(
    mission_id: int,
    hours: int = Query(default=6, ge=1, le=48),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Simulate search-area growth over the next N hours."""
    mission = _get_mission_or_404(db, mission_id)
    return intelligence.simulate_area_growth(mission, hours_ahead=hours)


def _mission_csv_row(m: Mission) -> list:
    return [
        m.id,
        m.mission_name,
        m.status,
        m.flight_number or "",
        m.aircraft_name or "",
        m.registration_number or "",
        m.aircraft_type or "",
        m.pilot_name or "",
        m.departure_airport or "",
        m.destination_airport or "",
        round(m.lkp_latitude, 6),
        round(m.lkp_longitude, 6),
        round(m.altitude_ft or 0, 0),
        round(m.ground_speed_kts or 0, 1),
        round(m.heading_deg or 0, 1),
        m.last_contact_time.isoformat() if m.last_contact_time else "",
        round(m.fuel_remaining_hours or 0, 1),
        round(m.elapsed_hours or 0, 2),
        round(m.distance_nm or 0, 2),
        round(m.search_radius_nm or 0, 2),
        round(m.search_area_sqnm or 0, 2),
        round(m.uncertainty_nm or 0, 2),
        round(m.risk_score or 0, 1),
        m.weather_conditions or "",
        round(m.wind_speed_kts or 0, 1),
        round(m.wind_direction_deg or 0, 1),
        m.created_at.isoformat() if m.created_at else "",
        m.completed_at.isoformat() if m.completed_at else "",
    ]


CSV_HEADERS = [
    "mission_id", "mission_name", "status", "flight_number", "aircraft_name",
    "registration_number", "aircraft_type", "pilot_name", "departure_airport",
    "destination_airport", "lkp_latitude", "lkp_longitude", "altitude_ft",
    "ground_speed_kts", "heading_deg", "last_contact_time", "fuel_remaining_hours",
    "elapsed_hours", "distance_nm", "search_radius_nm", "search_area_sqnm",
    "uncertainty_nm", "risk_score", "weather_conditions", "wind_speed_kts",
    "wind_direction_deg", "created_at", "completed_at",
]


def _csv_response(rows: list[list], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    writer.writerows(rows)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{mission_id}/export/csv")
def export_mission_csv(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Export a single mission as CSV."""
    mission = _get_mission_or_404(db, mission_id)
    return _csv_response(
        [_mission_csv_row(mission)],
        f"mission_{mission_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv",
    )


@router.get("/export/csv")
def export_all_csv(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Export all missions as CSV."""
    missions = db.query(Mission).order_by(Mission.created_at.desc()).all()
    return _csv_response(
        [_mission_csv_row(m) for m in missions],
        f"sar_dss_missions_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
    )
