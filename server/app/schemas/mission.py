"""Pydantic schemas for mission-related payloads."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_MISSION_STATUSES = {"draft", "active", "paused", "completed", "cancelled"}
VALID_ACCURACY = {"high", "medium", "low"}


class MissionCreate(BaseModel):
    """Payload used to create a new SAR mission and trigger calculations."""

    mission_name: str = Field(min_length=3, max_length=128)
    flight_number: Optional[str] = Field(default=None, max_length=32)
    aircraft_name: Optional[str] = Field(default=None, max_length=128)
    registration_number: Optional[str] = Field(default=None, max_length=32)
    aircraft_type: Optional[str] = Field(default=None, max_length=64)
    pilot_name: Optional[str] = Field(default=None, max_length=128)
    departure_airport: Optional[str] = Field(default=None, max_length=128)
    destination_airport: Optional[str] = Field(default=None, max_length=128)

    lkp_latitude: float = Field(ge=-90.0, le=90.0)
    lkp_longitude: float = Field(ge=-180.0, le=180.0)
    altitude_ft: float = Field(default=0.0, ge=-500, le=100000)
    ground_speed_kts: float = Field(default=0.0, ge=0.0, le=2000.0)
    heading_deg: float = Field(default=0.0, ge=0.0, le=360.0)
    last_contact_time: datetime
    fuel_remaining_hours: float = Field(default=0.0, ge=0.0, le=200.0)

    wind_speed_kts: float = Field(default=0.0, ge=0.0, le=400.0)
    wind_direction_deg: float = Field(default=0.0, ge=0.0, le=360.0)
    weather_conditions: str = Field(default="Clear", max_length=255)
    visibility_nm: float = Field(default=10.0, ge=0.0, le=100.0)
    remarks: Optional[str] = Field(default=None, max_length=5000)

    lkp_accuracy: str = Field(default="medium")
    is_route_known: bool = False

    @field_validator("lkp_accuracy")
    @classmethod
    def validate_accuracy(cls, v: str) -> str:
        if v not in VALID_ACCURACY:
            raise ValueError(f"lkp_accuracy must be one of {sorted(VALID_ACCURACY)}")
        return v


class MissionUpdate(BaseModel):
    """Payload for partial mission updates."""

    mission_name: Optional[str] = Field(default=None, min_length=3, max_length=128)
    status: Optional[str] = None
    pilot_name: Optional[str] = Field(default=None, max_length=128)
    remarks: Optional[str] = Field(default=None, max_length=5000)
    ground_speed_kts: Optional[float] = Field(default=None, ge=0.0, le=2000.0)
    heading_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    wind_speed_kts: Optional[float] = Field(default=None, ge=0.0, le=400.0)
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    weather_conditions: Optional[str] = Field(default=None, max_length=255)
    visibility_nm: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    lkp_accuracy: Optional[str] = None
    is_route_known: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MISSION_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_MISSION_STATUSES)}")
        return v

    @field_validator("lkp_accuracy")
    @classmethod
    def validate_accuracy(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ACCURACY:
            raise ValueError(f"lkp_accuracy must be one of {sorted(VALID_ACCURACY)}")
        return v


class SectorBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    color: str
    assigned_aircraft: Optional[str] = None


class SearchAreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    center_latitude: float
    center_longitude: float
    radius_nm: float
    area_sqnm: float
    polygon_geojson: str
    track_spacing_nm: float
    desired_coverage_pct: float


class SearchPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pattern_type: str
    reason: Optional[str]
    recommended: bool
    params_json: str
    waypoints_geojson: str
    track_spacing_nm: float


class ProbabilityZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_level: str
    color: str
    min_radius_nm: float
    max_radius_nm: float
    probability_pct: float
    polygon_geojson: str


class MissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_name: str
    status: str
    flight_number: Optional[str]
    aircraft_name: Optional[str]
    registration_number: Optional[str]
    aircraft_type: Optional[str]
    pilot_name: Optional[str]
    departure_airport: Optional[str]
    destination_airport: Optional[str]
    lkp_latitude: float
    lkp_longitude: float
    altitude_ft: float
    ground_speed_kts: float
    heading_deg: float
    last_contact_time: datetime
    fuel_remaining_hours: float
    wind_speed_kts: float
    wind_direction_deg: float
    weather_conditions: str
    visibility_nm: float
    remarks: Optional[str]
    lkp_accuracy: str
    is_route_known: bool
    elapsed_hours: float
    distance_nm: float
    search_radius_nm: float
    search_area_sqnm: float
    uncertainty_nm: float
    weather_impact: float
    risk_score: float
    priority_rank: int
    predicted_latitude: Optional[float]
    predicted_longitude: Optional[float]
    desired_coverage_pct: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    search_area: Optional[SearchAreaOut] = None
    patterns: list[SearchPatternOut] = []
    zones: list[ProbabilityZoneOut] = []
    sectors: list[SectorBrief] = []
    logs: list["ActivityLogOut"] = []


from app.schemas.system import ActivityLogOut  # noqa: E402

MissionOut.model_rebuild()


class MissionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_name: str
    status: str
    flight_number: Optional[str]
    aircraft_name: Optional[str]
    registration_number: Optional[str]
    aircraft_type: Optional[str]
    pilot_name: Optional[str]
    lkp_latitude: float
    lkp_longitude: float
    last_contact_time: datetime
    elapsed_hours: float
    distance_nm: float
    search_radius_nm: float
    search_area_sqnm: float
    risk_score: float
    priority_rank: int
    weather_conditions: str
    created_at: datetime
    completed_at: Optional[datetime]
    creator: Optional["UserBrief"] = None

    @property
    def _skip(self) -> None:  # placeholder to avoid unused import lint noise
        return None


from app.schemas.system import UserBrief  # noqa: E402

MissionListItem.model_rebuild()
