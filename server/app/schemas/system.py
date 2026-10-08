"""System / auth / utility schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str


class LoginRequest(BaseModel):
    """Username/email + password login payload."""

    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=6, max_length=255)


class TokenOut(BaseModel):
    """JWT response."""

    access_token: str
    token_type: str = "bearer"
    user: UserBrief


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=6, max_length=255)
    role: str = Field(default="sar_officer")
    designation: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    designation: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    # Admin-only credential rotation (handled explicitly in the router:
    # username is uniqueness-checked, password is bcrypt-hashed).
    username: Optional[str] = Field(default=None, min_length=3, max_length=64)
    password: Optional[str] = Field(default=None, min_length=8, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    designation: Optional[str]
    phone: Optional[str]
    role: str
    is_active: bool
    created_at: datetime


class AircraftCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    registration_number: str = Field(min_length=2, max_length=32)
    aircraft_type: str = Field(min_length=2, max_length=64)
    operator: Optional[str] = Field(default=None, max_length=128)


class AircraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    registration_number: str
    aircraft_type: str
    operator: Optional[str]


class SectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_id: int
    code: str
    name: str
    color: str
    start_angle_deg: float
    end_angle_deg: float
    center_latitude: float
    center_longitude: float
    area_sqnm: float
    assigned_aircraft: Optional[str]
    polygon_geojson: str


class SectorUpdate(BaseModel):
    assigned_aircraft: Optional[str] = Field(default=None, max_length=128)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_id: int
    report_type: str
    title: str
    created_at: datetime


class WeatherSnapshotIn(BaseModel):
    mission_id: Optional[int] = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class WeatherSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float
    longitude: float
    temperature_c: Optional[float]
    wind_speed_kts: Optional[float]
    wind_direction_deg: Optional[float]
    visibility_km: Optional[float]
    humidity: Optional[float]
    pressure_hpa: Optional[float]
    conditions: Optional[str]
    precipitation_mm: Optional[float]
    source: str
    created_at: datetime


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_id: Optional[int]
    user_id: Optional[int]
    action: str
    description: Optional[str]
    created_at: datetime
