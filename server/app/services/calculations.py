"""Aviation search-area calculation engine.

Implements the standard SAR planning formulas used by ICAO / IAMSAR:
    Distance     = Ground Speed x Elapsed Time
    Search radius = distance + wind correction + navigation uncertainty
                    + pilot deviation   (scaled by weather severity)
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services import gis

# Uncertainty factors (fraction of distance + base terms)
NAV_UNCERTAINTY_BASE_NM = 2.0
NAV_UNCERTAINTY_FRAC = 0.05
PILOT_DEVIATION_FRAC = 0.10
WIND_DRIFT_FRAC = 0.60
MIN_SEARCH_RADIUS_NM = 5.0
SEVERE_WEATHER_EXPANSION = 1.6

SEVERE_WEATHER_KEYWORDS = (
    "storm", "thunder", "thunderstorm", "heavy rain", "torrential", "cyclone",
    "hurricane", "typhoon", "blizzard", "snow storm", "fog", "severe",
    "squall", "tornado", "dust storm", "icing", "gale", "freezing",
)


@dataclass
class CalculationResult:
    """Result of a full search-area calculation for a mission."""

    elapsed_hours: float = 0.0
    distance_nm: float = 0.0
    wind_correction_nm: float = 0.0
    navigation_uncertainty_nm: float = 0.0
    pilot_deviation_nm: float = 0.0
    uncertainty_nm: float = 0.0
    weather_impact: float = 0.0
    radius_nm: float = 0.0
    area_sqnm: float = 0.0
    predicted_lat: float | None = None
    predicted_lon: float | None = None
    track_spacing_nm: float = 2.0
    desired_coverage_pct: float = 0.0
    sectors_count: int = 4
    terrain_risk: float = 0.0
    weather_severity: str = "Good"
    probability: dict = field(default_factory=lambda: {
        "high": 0.55,
        "medium": 0.30,
        "low": 0.15,
    })


def weather_impact_score(
    weather_conditions: str, wind_speed_kts: float, visibility_nm: float
) -> float:
    """Compute a 0..1 weather severity / impact score."""
    score = 0.1
    text = (weather_conditions or "").lower()
    for kw in SEVERE_WEATHER_KEYWORDS:
        if kw in text:
            score += 0.18
    if wind_speed_kts >= 40:
        score += 0.15
    elif wind_speed_kts >= 25:
        score += 0.08
    if visibility_nm is not None and visibility_nm < 2:
        score += 0.15
    return min(1.0, score)


def weather_severity_label(score: float) -> str:
    """Human readable severity from a 0..1 impact score."""
    if score >= 0.75:
        return "Severe"
    if score >= 0.45:
        return "Deteriorating"
    if score >= 0.2:
        return "Moderate"
    return "Good"


def _safe_elapsed(last_contact: datetime) -> float:
    """Elapsed hours since last contact (never negative, never absurd)."""
    try:
        last_utc = last_contact.replace(tzinfo=timezone.utc)
    except TypeError:
        last_utc = last_contact
    now = datetime.now(timezone.utc)
    delta = now - last_utc
    hours = delta.total_seconds() / 3600.0
    return max(0.0, hours)


def calculate_mission(
    *,
    lkp_lat: float,
    lkp_lon: float,
    ground_speed_kts: float,
    heading_deg: float,
    last_contact_time: datetime,
    wind_speed_kts: float,
    wind_direction_deg: float,
    weather_conditions: str,
    visibility_nm: float,
    lkp_accuracy: str = "medium",
    is_route_known: bool = False,
    terrain_risk: float = 0.0,
    sectors_count: int = 4,
) -> CalculationResult:
    """Core calculation producing radius, area, predicted position and more."""
    res = CalculationResult()
    res.elapsed_hours = _safe_elapsed(last_contact_time)
    res.distance_nm = ground_speed_kts * res.elapsed_hours
    res.weather_impact = weather_impact_score(
        weather_conditions, wind_speed_kts, visibility_nm
    )
    res.weather_severity = weather_severity_label(res.weather_impact)

    # Uncertainty terms
    nav = NAV_UNCERTAINTY_BASE_NM + NAV_UNCERTAINTY_FRAC * res.distance_nm
    pilot = PILOT_DEVIATION_FRAC * res.distance_nm
    # Wind drift: air mass carries the aircraft; the perpendicular drift grows
    # with wind speed relative to aircraft speed.
    wind_drift = 0.0
    if ground_speed_kts > 0:
        ratio = min(1.0, wind_speed_kts / max(ground_speed_kts, 1.0))
        wind_drift = ratio * res.distance_nm * WIND_DRIFT_FRAC

    # LKP accuracy multiplier
    acc_mult = {"high": 0.6, "medium": 1.0, "low": 1.6}.get(lkp_accuracy, 1.0)

    # Weather expansion for severe conditions
    weather_mult = 1.0
    if res.weather_impact >= 0.75:
        weather_mult = SEVERE_WEATHER_EXPANSION
    elif res.weather_impact >= 0.45:
        weather_mult = 1.3

    res.wind_correction_nm = wind_drift * acc_mult * weather_mult
    res.navigation_uncertainty_nm = nav * acc_mult * weather_mult
    res.pilot_deviation_nm = pilot * acc_mult * weather_mult
    res.uncertainty_nm = (
        res.wind_correction_nm + res.navigation_uncertainty_nm + res.pilot_deviation_nm
    )

    res.radius_nm = max(
        MIN_SEARCH_RADIUS_NM,
        res.distance_nm + res.uncertainty_nm,
    )
    res.area_sqnm = gis.circle_area_sqnm(res.radius_nm)

    # Predicted position: fly along heading, then apply wind-drift offset.
    pred_lat, pred_lon = gis.destination(lkp_lat, lkp_lon, heading_deg, res.distance_nm)
    drift_dist = wind_drift
    if drift_dist > 0:
        pred_lat, pred_lon = gis.destination(
            pred_lat, pred_lon, wind_direction_deg, drift_dist
        )
    res.predicted_lat = pred_lat
    res.predicted_lon = pred_lon

    # Track spacing derived from visibility for efficient sweeping
    spacing = 2.0 * max(1.0, min(visibility_nm, 5.0))
    res.track_spacing_nm = round(spacing, 1)

    # Desired area coverage: fraction of the search area that can be swept in
    # one sortie with the available fuel given the pattern spacing.
    usable_time = max(0.5, res.elapsed_hours + (visibility_nm / 3.0))
    sweep_rate_sqnm_hr = ground_speed_kts * res.track_spacing_nm
    sweepable = sweep_rate_sqnm_hr * usable_time
    res.desired_coverage_pct = min(100.0, round((sweepable / max(res.area_sqnm, 0.001)) * 100.0, 1))

    # Terrain risk (0..1) supplied by the intelligence layer (0 = flat, 1 = rugged)
    res.terrain_risk = terrain_risk
    res.sectors_count = max(1, sectors_count)

    # Probability distribution concentrates around the predicted position.
    if lkp_accuracy == "high":
        res.probability = {"high": 0.62, "medium": 0.27, "low": 0.11}
    elif lkp_accuracy == "low":
        res.probability = {"high": 0.46, "medium": 0.32, "low": 0.22}
    else:
        res.probability = {"high": 0.55, "medium": 0.30, "low": 0.15}

    return res
