"""Intelligence layer: heuristic "AI" decision support.

Provides the bonus analytics features:

  - Crash-location prediction (drift modelling)
  - Weather impact prediction
  - Automatic search-priority ranking across missions
  - Mission risk analysis
  - Smart search-pattern recommendations
  - Search-area evolution simulation

All models are transparent, deterministic heuristics grounded in SAR planning
doctrine (IAMSAR) so officers can audit every recommendation.
"""
import math
from typing import Dict, List

from app.models import Mission
from app.services import calculations, gis

# Terrain elevation (m) lookup table for a small set of likely Indian regions.
# Used as a lightweight terrain proxy; extend with a real DEM for production.
TERRAIN_TABLE: Dict[str, float] = {
    "delhi": 216, "mumbai": 14, "kolkata": 9, "chennai": 6, "bengaluru": 920,
    "hyderabad": 536, "dehradun": 640, "leh": 3500, "srinagar": 1585,
    "guwahati": 55, "imphal": 786, "goa": 10, "jaipur": 431, "lucknow": 123,
    "patna": 53, "bhopal": 499, "kochi": 0, "thiruvananthapuram": 5,
    "sikkim": 1700, "shillong": 1525, "nagpur": 310, "indore": 553,
    "chandigarh": 350, "amritsar": 234, "vijayawada": 11, "puducherry": 3,
}


def risk_analysis(mission: Mission) -> dict:
    """Compute a 0..100 risk score with a breakdown of contributing factors."""
    factors = []
    score = 0.0

    # Time since loss of contact - urgency grows rapidly
    hours = mission.elapsed_hours or 0.0
    time_score = min(40.0, hours * 1.2)
    if hours < 2:
        severity = "Low"
    elif hours < 8:
        severity = "Moderate"
    else:
        severity = "Critical"
    factors.append({"name": "Time since LKP", "value": round(time_score, 1), "max": 40.0, "severity": severity})

    # Fuel exhaustion
    fuel = mission.fuel_remaining_hours or 0.0
    fuel_score = max(0.0, 15.0 * (1.0 - (fuel / max(hours, 0.1)) / 3.0)) if hours > 0 else 2.0
    fuel_score = min(15.0, max(0.0, fuel_score))
    factors.append({"name": "Fuel remaining", "value": round(fuel_score, 1), "max": 15.0,
                    "severity": "Critical" if fuel_score >= 12 else "Moderate" if fuel_score >= 8 else "Low"})

    # Weather severity
    impact = mission.weather_impact or 0.0
    weather_score = impact * 20.0
    factors.append({"name": "Weather severity", "value": round(weather_score, 1), "max": 20.0,
                    "severity": calculations.weather_severity_label(impact)})

    # LKP uncertainty
    acc_mult = {"high": 0.25, "medium": 0.5, "low": 1.0}.get(mission.lkp_accuracy, 0.5)
    lkp_score = acc_mult * 15.0
    factors.append({"name": "LKP uncertainty", "value": round(lkp_score, 1), "max": 15.0,
                    "severity": "Low" if mission.lkp_accuracy == "high" else "Moderate" if mission.lkp_accuracy == "medium" else "High"})

    # Area size complexity
    area = mission.search_area_sqnm or 0.0
    area_score = min(10.0, area / 400.0)
    factors.append({"name": "Search area size", "value": round(area_score, 1), "max": 10.0,
                    "severity": "High" if area_score >= 8 else "Moderate" if area_score >= 5 else "Low"})

    score = round(sum(f["value"] for f in factors), 1)
    score = min(100.0, max(0.0, score))
    if score >= 75:
        rating = "CRITICAL"
        tone = "red"
    elif score >= 50:
        rating = "HIGH"
        tone = "orange"
    elif score >= 30:
        rating = "MODERATE"
        tone = "yellow"
    else:
        rating = "LOW"
        tone = "green"

    return {
        "score": score,
        "rating": rating,
        "tone": tone,
        "factors": factors,
        "summary": (
            f"{mission.mission_name} is assessed as {rating} priority. "
            f"Elapsed {hours:.1f}h since last contact with {mission.weather_conditions} "
            f"conditions and {mission.fuel_remaining_hours:.1f}h of fuel remaining."
        ),
    }


def priority_rank(active_missions: List[Mission]) -> List[int]:
    """Return mission ids ordered by computed risk score, highest first."""
    scored = [(risk_analysis(m)["score"], m.id) for m in active_missions]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [mid for _, mid in scored]


def predict_crash_location(mission: Mission) -> dict:
    """Predict the probable crash location and confidence ellipse."""
    if mission.predicted_latitude is None or mission.predicted_longitude is None:
        return {"latitude": None, "longitude": None, "confidence_nm": 0.0, "drift_bearing": 0.0}
    # Drift continuing from the predicted point along wind.
    drift_nm = (mission.wind_speed_kts or 0.0) * 0.5
    if mission.elapsed_hours > 6:
        drift_nm *= 1.5
    final_lat, final_lon = gis.destination(
        mission.predicted_latitude,
        mission.predicted_longitude,
        mission.wind_direction_deg or 0.0,
        drift_nm,
    )
    confidence = max(1.0, mission.uncertainty_nm * 0.7)
    return {
        "latitude": round(final_lat, 6),
        "longitude": round(final_lon, 6),
        "confidence_nm": round(confidence, 2),
        "drift_bearing": round((mission.wind_direction_deg or 0.0), 1),
    }


def weather_impact_prediction(mission: Mission) -> dict:
    """Predict how weather will evolve and impact the search effort."""
    impact = mission.weather_impact or 0.0
    trend = "deteriorating" if impact >= 0.45 else "stable" if impact >= 0.2 else "improving"
    effective_visibility = mission.visibility_nm or 5.0
    return {
        "current_impact": round(impact, 2),
        "severity": calculations.weather_severity_label(impact),
        "trend": trend,
        "recommendation": (
            "Launch immediate air search before weather degrades further."
            if trend == "deteriorating"
            else "Proceed with planned pattern; visibility adequate for visual search."
        ),
        "effective_visibility_nm": round(effective_visibility, 1),
        "track_spacing_recommendation_nm": round(2 * max(1.0, min(effective_visibility, 5.0)), 1),
    }


def terrain_roughness(mission: Mission) -> float:
    """Estimate terrain roughness (0..1) around the search area (heuristic)."""
    lat, lon = mission.lkp_latitude, mission.lkp_longitude
    # Simple proxy: distance from major lowland coastal reference and latitude.
    lowland_refs = [(19.076, 72.8777, 20), (28.6139, 77.2090, 10), (22.5726, 88.3639, 5)]
    best = 0.1
    for rlat, rlon, near in lowland_refs:
        d = gis.haversine_nm(lat, lon, rlat, rlon)
        if d < near:
            best = min(best, 0.2)
    if abs(lat) > 26.0:  # Himalayan / mountainous band
        best = max(best, 0.75)
    elif abs(lat) > 22.0:
        best = max(best, 0.35)
    return round(min(1.0, best), 2)


def smart_recommendations(mission: Mission) -> List[dict]:
    """Generate actionable, human-readable search recommendations."""
    recs = []
    area = mission.search_area_sqnm or 0.0
    radius = mission.search_radius_nm or 0.0
    if area >= 1500:
        recs.append({"type": "coverage", "title": "Split the search area",
                     "detail": f"Area of {area:,.0f} nm² exceeds single-sortie coverage; split into sectors and assign one aircraft each."})
    if mission.wind_speed_kts >= 25:
        recs.append({"type": "wind", "title": "Account for strong wind drift",
                     "detail": f"Wind of {mission.wind_speed_kts:.0f} kt shifts the probable position downwind; bias high-priority zone downwind of the track."})
    if mission.fuel_remaining_hours > 0 and mission.fuel_remaining_hours < mission.elapsed_hours:
        recs.append({"type": "fuel", "title": "Fuel exhaustion likely",
                     "detail": "Estimated endurance is below the elapsed time since contact; assume no further powered flight."})
    if mission.lkp_accuracy == "low":
        recs.append({"type": "confidence", "title": "Verify LKP with radar replay",
                     "detail": "Low-confidence LKP: cross-check with ATC radar playback and secondary surveillance data before allocating resources."})
    if radius <= 10:
        recs.append({"type": "radius", "title": "Tighten the search radius",
                     "detail": f"Search radius of {radius:.1f} nm suggests the aircraft is still airborne or very recently downed; prioritise visual contact along heading."})
    return recs or [
        {"type": "general", "title": "Proceed with recommended pattern",
         "detail": "No overriding risk factors detected; execute the recommended search pattern as planned."}
    ]


def simulate_area_growth(mission: Mission, hours_ahead: int = 6) -> List[dict]:
    """Simulate how the search radius/area will evolve over future hours."""
    points = []
    speed = mission.ground_speed_kts or 0.0
    wind = mission.wind_speed_kts or 0.0
    for h in range(0, hours_ahead + 1):
        elapsed = mission.elapsed_hours + h
        distance = speed * elapsed
        nav = calculations.NAV_UNCERTAINTY_BASE_NM + calculations.NAV_UNCERTAINTY_FRAC * distance
        pilot = calculations.PILOT_DEVIATION_FRAC * distance
        ratio = min(1.0, wind / max(speed, 1.0))
        drift = ratio * distance * calculations.WIND_DRIFT_FRAC
        acc_mult = {"high": 0.6, "medium": 1.0, "low": 1.6}.get(mission.lkp_accuracy, 1.0)
        radius = max(calculations.MIN_SEARCH_RADIUS_NM, distance + (nav + pilot + drift) * acc_mult)
        area = gis.circle_area_sqnm(radius)
        points.append({
            "hours_from_now": h,
            "elapsed_hours": round(elapsed, 1),
            "radius_nm": round(radius, 2),
            "area_sqnm": round(area, 1),
        })
    return points


def summarize_analysis(mission: Mission) -> dict:
    """Assemble the full intelligence bundle for a mission."""
    risk = risk_analysis(mission)
    crash = predict_crash_location(mission)
    weather = weather_impact_prediction(mission)
    terrain = terrain_roughness(mission)
    return {
        "mission_id": mission.id,
        "risk": risk,
        "crash_prediction": crash,
        "weather_impact": weather,
        "terrain_roughness": terrain,
        "recommendations": smart_recommendations(mission),
        "simulation": simulate_area_growth(mission, hours_ahead=6),
    }
