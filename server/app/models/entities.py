"""ORM entity definitions.

Database tables: users, aircraft, missions, search_areas, search_patterns,
probability_zones, sectors, reports, weather_snapshots, activity_logs.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    """UTC now helper used as a default for timestamps."""
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    full_name = Column(String(128), nullable=False)
    designation = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="sar_officer", nullable=False)  # admin | sar_officer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    missions = relationship("Mission", back_populates="creator", lazy="selectin")


class Aircraft(Base):
    __tablename__ = "aircraft"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    registration_number = Column(String(32), unique=True, index=True, nullable=False)
    aircraft_type = Column(String(64), nullable=False)
    operator = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    mission_name = Column(String(128), nullable=False, index=True)
    status = Column(String(32), default="active", nullable=False, index=True)

    # Flight information
    flight_number = Column(String(32), nullable=True)
    aircraft_name = Column(String(128), nullable=True)
    registration_number = Column(String(32), nullable=True)
    aircraft_type = Column(String(64), nullable=True)
    pilot_name = Column(String(128), nullable=True)
    departure_airport = Column(String(128), nullable=True)
    destination_airport = Column(String(128), nullable=True)

    # Last known position / telemetry
    lkp_latitude = Column(Float, nullable=False)
    lkp_longitude = Column(Float, nullable=False)
    altitude_ft = Column(Float, default=0.0)
    ground_speed_kts = Column(Float, default=0.0)
    heading_deg = Column(Float, default=0.0)
    last_contact_time = Column(DateTime, nullable=False)
    fuel_remaining_hours = Column(Float, default=0.0)

    # Environment
    wind_speed_kts = Column(Float, default=0.0)
    wind_direction_deg = Column(Float, default=0.0)
    weather_conditions = Column(String(255), default="Clear")
    visibility_nm = Column(Float, default=10.0)
    remarks = Column(Text, nullable=True)

    # Search metadata / confidence
    lkp_accuracy = Column(String(16), default="medium")  # high | medium | low
    is_route_known = Column(Boolean, default=False)

    # Computed snapshot (cached calculation outputs)
    elapsed_hours = Column(Float, default=0.0)
    distance_nm = Column(Float, default=0.0)
    search_radius_nm = Column(Float, default=0.0)
    search_area_sqnm = Column(Float, default=0.0)
    uncertainty_nm = Column(Float, default=0.0)
    weather_impact = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    priority_rank = Column(Integer, default=0)
    predicted_latitude = Column(Float, nullable=True)
    predicted_longitude = Column(Float, nullable=True)
    desired_coverage_pct = Column(Float, default=0.0)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    creator = relationship("User", back_populates="missions", lazy="selectin")
    search_area = relationship(
        "SearchArea",
        back_populates="mission",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    patterns = relationship(
        "SearchPattern", back_populates="mission", cascade="all, delete-orphan"
    )
    zones = relationship(
        "ProbabilityZone", back_populates="mission", cascade="all, delete-orphan"
    )
    sectors = relationship(
        "Sector", back_populates="mission", cascade="all, delete-orphan"
    )
    reports = relationship(
        "Report", back_populates="mission", cascade="all, delete-orphan"
    )
    weather = relationship(
        "WeatherSnapshot", back_populates="mission", cascade="all, delete-orphan"
    )
    logs = relationship(
        "ActivityLog",
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SearchArea(Base):
    __tablename__ = "search_areas"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), unique=True, nullable=False)
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_nm = Column(Float, nullable=False)
    area_sqnm = Column(Float, nullable=False)
    polygon_geojson = Column(Text, nullable=False)
    track_spacing_nm = Column(Float, default=2.0)
    desired_coverage_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="search_area")


class SearchPattern(Base):
    __tablename__ = "search_patterns"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    pattern_type = Column(String(48), nullable=False)  # expanding_square | sector | parallel_track | creeping_line | track_line
    reason = Column(Text, nullable=True)
    recommended = Column(Boolean, default=False, nullable=False)
    params_json = Column(Text, default="{}")
    waypoints_geojson = Column(Text, nullable=False)
    track_spacing_nm = Column(Float, default=2.0)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="patterns")


class ProbabilityZone(Base):
    __tablename__ = "probability_zones"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    zone_level = Column(String(16), nullable=False)  # high | medium | low
    color = Column(String(16), nullable=False)
    min_radius_nm = Column(Float, default=0.0)
    max_radius_nm = Column(Float, default=0.0)
    probability_pct = Column(Float, default=0.0)
    polygon_geojson = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="zones")


class Sector(Base):
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    code = Column(String(8), nullable=False)  # A, B, C, D ...
    name = Column(String(64), nullable=False)
    color = Column(String(16), nullable=False)
    start_angle_deg = Column(Float, default=0.0)
    end_angle_deg = Column(Float, default=0.0)
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    area_sqnm = Column(Float, default=0.0)
    assigned_aircraft = Column(String(128), nullable=True)
    polygon_geojson = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="sectors")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    report_type = Column(String(16), default="pdf")
    title = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="reports")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=True)
    wind_speed_kts = Column(Float, nullable=True)
    wind_direction_deg = Column(Float, nullable=True)
    visibility_km = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    conditions = Column(String(255), nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    forecast_json = Column(Text, nullable=True)
    source = Column(String(64), default="openmeteo")
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="weather")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    mission = relationship("Mission", back_populates="logs")
