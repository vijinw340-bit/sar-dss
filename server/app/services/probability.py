"""Probability zone generation.

The search area is divided into concentric bands around the predicted position
using a simplified bivariate-normal probability model:

    High   (red)     inner band    -> largest cumulative probability
    Medium (orange)  middle band
    Low    (yellow)  outer band

Weights reflect heading certainty, wind magnitude, elapsed time and LKP accuracy.
"""
from typing import List, Tuple

from app.services import gis

ZONE_SPECS = [
    {"level": "high", "color": "#ef4444", "inner": 0.0, "outer": 0.35},
    {"level": "medium", "color": "#f97316", "inner": 0.35, "outer": 0.70},
    {"level": "low", "color": "#eab308", "inner": 0.70, "outer": 1.00},
]


def compute_zone_probabilities(radius_nm: float, weights: dict) -> dict:
    """Scale the base band distribution using mission confidence weights."""
    base = {"high": weights.get("high", 0.55), "medium": weights.get("medium", 0.30), "low": weights.get("low", 0.15)}
    total = sum(base.values()) or 1.0
    return {k: round(v / total * 100.0, 1) for k, v in base.items()}


def confidence_weights(*, lkp_accuracy: str, elapsed_hours: float, wind_speed_kts: float) -> dict:
    """Blend LKP accuracy, elapsed time and wind into probability weights."""
    high = {"high": 0.62, "medium": 0.55, "low": 0.46}[lkp_accuracy]
    # Longer elapsed time spreads the distribution toward the outer band.
    time_spread = min(0.25, elapsed_hours * 0.01)
    wind_spread = min(0.15, wind_speed_kts * 0.003)
    return {
        "high": round(max(0.30, high - time_spread - wind_spread), 3),
        "medium": 0.30,
        "low": round(min(0.35, 0.20 + time_spread + wind_spread), 3),
    }


def generate_zones(
    center_lat: float,
    center_lon: float,
    radius_nm: float,
    weights: dict,
    segments: int = 64,
) -> List[Tuple[str, str, float, float, float, dict]]:
    """Return zone tuples (level, color, min_r, max_r, prob_pct, polygon)."""
    zones = []
    probs = compute_zone_probabilities(radius_nm, weights)
    for spec in ZONE_SPECS:
        min_r = spec["inner"] * radius_nm
        max_r = spec["outer"] * radius_nm
        # Each band is an annulus: inner circle hole + outer ring.
        outer = gis.circle_polygon(center_lat, center_lon, max_r, segments)
        if min_r <= 0.5:
            polygon = gis.polygon_geojson(outer)
        else:
            inner = gis.circle_polygon(center_lat, center_lon, min_r, segments)
            outer.reverse()
            ring = outer + inner
            polygon = {
                "type": "Polygon",
                "coordinates": [
                    [[round(lon, 6), round(lat, 6)] for lat, lon in ring],
                ],
            }
        zones.append(
            (
                spec["level"],
                spec["color"],
                round(min_r, 3),
                round(max_r, 3),
                probs[spec["level"]],
                polygon,
            )
        )
    return zones
