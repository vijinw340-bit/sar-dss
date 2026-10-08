"""Mission computation pipeline.

Orchestrates the full GIS calculation for a mission and persists the results:
search area, all five search patterns (one marked recommended), probability
zones and search sectors. Also logs the activity.
"""
import json

from sqlalchemy.orm import Session

from app.models import (
    ActivityLog,
    Mission,
    ProbabilityZone,
    SearchArea,
    SearchPattern,
    Sector,
)
from app.services import calculations, intelligence, patterns, probability, sectors as sector_svc
from app.services.gis import circle_polygon, polygon_geojson


def log_activity(
    db: Session,
    mission: Mission | None,
    user_id: int | None,
    action: str,
    description: str,
) -> ActivityLog:
    """Persist an activity-log entry."""
    entry = ActivityLog(
        mission_id=mission.id if mission else None,
        user_id=user_id,
        action=action,
        description=description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def run_calculation_pipeline(db: Session, mission: Mission, user_id: int | None) -> Mission:
    """Recompute and persist all mission search outputs."""
    terrain = intelligence.terrain_roughness(mission)
    res = calculations.calculate_mission(
        lkp_lat=mission.lkp_latitude,
        lkp_lon=mission.lkp_longitude,
        ground_speed_kts=mission.ground_speed_kts,
        heading_deg=mission.heading_deg,
        last_contact_time=mission.last_contact_time,
        wind_speed_kts=mission.wind_speed_kts,
        wind_direction_deg=mission.wind_direction_deg,
        weather_conditions=mission.weather_conditions,
        visibility_nm=mission.visibility_nm,
        lkp_accuracy=mission.lkp_accuracy,
        is_route_known=mission.is_route_known,
        terrain_risk=terrain,
        sectors_count=4,
    )

    # --- snapshot computed fields onto mission ---------------------------------
    mission.elapsed_hours = res.elapsed_hours
    mission.distance_nm = res.distance_nm
    mission.search_radius_nm = res.radius_nm
    mission.search_area_sqnm = res.area_sqnm
    mission.uncertainty_nm = res.uncertainty_nm
    mission.weather_impact = res.weather_impact
    mission.predicted_latitude = res.predicted_lat
    mission.predicted_longitude = res.predicted_lon
    mission.desired_coverage_pct = res.desired_coverage_pct
    risk = intelligence.risk_analysis(mission)
    mission.risk_score = risk["score"]

    # --- clear previous derived records ---------------------------------------
    db.query(SearchArea).filter(SearchArea.mission_id == mission.id).delete(
        synchronize_session=False
    )
    db.query(SearchPattern).filter(SearchPattern.mission_id == mission.id).delete(
        synchronize_session=False
    )
    db.query(ProbabilityZone).filter(ProbabilityZone.mission_id == mission.id).delete(
        synchronize_session=False
    )
    db.query(Sector).filter(Sector.mission_id == mission.id).delete(
        synchronize_session=False
    )
    # Expire stale relationship caches so SQLAlchemy will not try to reconcile
    # (and null out FK columns of) previously loaded derived objects.
    db.expire(mission, ["search_area", "patterns", "zones", "sectors"])
    db.flush()

    # --- search area -----------------------------------------------------------
    center_poly = circle_polygon(mission.lkp_latitude, mission.lkp_longitude, res.radius_nm)
    area = SearchArea(
        mission_id=mission.id,
        center_latitude=mission.lkp_latitude,
        center_longitude=mission.lkp_longitude,
        radius_nm=res.radius_nm,
        area_sqnm=res.area_sqnm,
        polygon_geojson=json.dumps(polygon_geojson(center_poly)),
        track_spacing_nm=res.track_spacing_nm,
        desired_coverage_pct=res.desired_coverage_pct,
    )
    db.add(area)

    # --- patterns --------------------------------------------------------------
    rec_type, reason = patterns.recommend_pattern(
        mission.lkp_accuracy, mission.is_route_known, res.area_sqnm
    )
    for key in patterns.PATTERN_KEYS:
        wp = patterns.generate_pattern(
            key,
            center_lat=mission.lkp_latitude,
            center_lon=mission.lkp_longitude,
            radius_nm=res.radius_nm,
            spacing_nm=res.track_spacing_nm,
            predicted_lat=res.predicted_lat or mission.lkp_latitude,
            predicted_lon=res.predicted_lon or mission.lkp_longitude,
            lkp_lat=mission.lkp_latitude,
            lkp_lon=mission.lkp_longitude,
        )
        db.add(
            SearchPattern(
                mission_id=mission.id,
                pattern_type=key,
                reason=reason if key == rec_type else None,
                recommended=(key == rec_type),
                params_json=json.dumps(
                    {
                        "spacing_nm": res.track_spacing_nm,
                        "radius_nm": res.radius_nm,
                        "label": patterns.PATTERN_LABELS[key],
                    }
                ),
                waypoints_geojson=json.dumps(gis_polyline(wp)),
                track_spacing_nm=res.track_spacing_nm,
            )
        )

    # --- probability zones -------------------------------------------------------
    weights = probability.confidence_weights(
        lkp_accuracy=mission.lkp_accuracy,
        elapsed_hours=res.elapsed_hours,
        wind_speed_kts=mission.wind_speed_kts,
    )
    for level, color, min_r, max_r, pct, polygon in probability.generate_zones(
        mission.lkp_latitude, mission.lkp_longitude, res.radius_nm, weights
    ):
        db.add(
            ProbabilityZone(
                mission_id=mission.id,
                zone_level=level,
                color=color,
                min_radius_nm=min_r,
                max_radius_nm=max_r,
                probability_pct=pct,
                polygon_geojson=json.dumps(polygon),
            )
        )

    # --- sectors ------------------------------------------------------------------
    for sec in sector_svc.generate_sectors(
        mission.lkp_latitude, mission.lkp_longitude, res.radius_nm, count=4
    ):
        db.add(
            Sector(
                mission_id=mission.id,
                code=sec["code"],
                name=sec["name"],
                color=sec["color"],
                start_angle_deg=sec["start_angle_deg"],
                end_angle_deg=sec["end_angle_deg"],
                center_latitude=sec["center_latitude"],
                center_longitude=sec["center_longitude"],
                area_sqnm=sec["area_sqnm"],
                assigned_aircraft=sec["assigned_aircraft"],
                polygon_geojson=json.dumps(sec["polygon_geojson"]),
            )
        )

    db.commit()
    db.refresh(mission)
    log_activity(
        db,
        mission,
        user_id,
        "calculation",
        f"Search area recalculated: radius {res.radius_nm:.1f} nm, area {res.area_sqnm:,.1f} nm²",
    )
    return mission


def gis_polyline(points) -> dict:
    """Build a GeoJSON LineString from pattern waypoints."""
    return {
        "type": "LineString",
        "coordinates": [[round(lon, 6), round(lat, 6)] for lat, lon in points],
    }
