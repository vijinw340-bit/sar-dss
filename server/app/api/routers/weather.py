"""Weather endpoints: live conditions and persisted snapshots."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Mission, User, WeatherSnapshot
from app.schemas import WeatherSnapshotIn, WeatherSnapshotOut
from app.services import weather as weather_svc

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/live")
async def live_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: User = Depends(get_current_user),
):
    """Fetch live weather for a coordinate (Open-Meteo)."""
    try:
        return await weather_svc.fetch_weather(lat, lon)
    except Exception as exc:  # graceful degradation when offline
        return {
            "error": True,
            "detail": f"Weather service unavailable: {exc}",
            "wind_speed_kts": 0,
            "wind_direction_deg": 0,
            "conditions": "Unavailable",
            "visibility_km": None,
        }


@router.post("/snapshot", response_model=WeatherSnapshotOut, status_code=201)
async def create_snapshot(
    payload: WeatherSnapshotIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Fetch and persist a weather snapshot for a mission/LKP."""
    if payload.mission_id:
        mission = db.get(Mission, payload.mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
    data = await weather_svc.snapshot_weather(payload.latitude, payload.longitude)
    snapshot = WeatherSnapshot(
        mission_id=payload.mission_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        temperature_c=data.get("temperature_c"),
        wind_speed_kts=data.get("wind_speed_kts"),
        wind_direction_deg=data.get("wind_direction_deg"),
        visibility_km=data.get("visibility_km"),
        humidity=data.get("humidity"),
        pressure_hpa=data.get("pressure_hpa"),
        conditions=data.get("conditions"),
        precipitation_mm=data.get("precipitation_mm"),
        source=data.get("source", "openmeteo"),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
