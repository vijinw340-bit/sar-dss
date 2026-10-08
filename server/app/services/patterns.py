"""Search-pattern generation engine.

Implements the five standard SAR patterns used internationally:

  - Expanding Square   (best for high-confidence LKP)
  - Sector Search      (best for low confidence / uncertain)
  - Parallel Track     (best for very large areas)
  - Creeping Line      (best when a route/track is known)
  - Track Line         (follow the projected flight path)
"""
from typing import List, Tuple

from app.services import gis

# Allowed pattern keys
PATTERN_KEYS = (
    "expanding_square",
    "sector",
    "parallel_track",
    "creeping_line",
    "track_line",
)

PATTERN_LABELS = {
    "expanding_square": "Expanding Square",
    "sector": "Sector Search",
    "parallel_track": "Parallel Track",
    "creeping_line": "Creeping Line",
    "track_line": "Track Line",
}


def recommend_pattern(
    lkp_accuracy: str, is_route_known: bool, area_sqnm: float
) -> Tuple[str, str]:
    """Rule-based pattern recommendation (per IAMSAR planning guidance)."""
    if lkp_accuracy == "high":
        return "expanding_square", (
            "High-confidence LKP: an expanding square centred on the last known "
            "position is the most efficient way to saturate a compact area."
        )
    if is_route_known:
        return "creeping_line", (
            "The aircraft route is known: a creeping line search along the "
            "track maximises coverage of the probable flight corridor."
        )
    if area_sqnm >= 1500.0:
        return "parallel_track", (
            "Very large search area: parallel track lines provide systematic "
            "and complete coverage."
        )
    if lkp_accuracy == "low":
        return "sector", (
            "LKP confidence is low: a sector search radiating from the LKP "
            "finds targets whose drift direction is uncertain."
        )
    return "expanding_square", (
        "Balanced confidence: expanding square offers the best combination of "
        "simplicity and coverage efficiency."
    )


def expanding_square(
    center_lat: float,
    center_lon: float,
    spacing_nm: float,
    laps: int = 5,
) -> List[Tuple[float, float]]:
    """Waypoints of an expanding square spiral centred on a point."""
    pts = [(center_lat, center_lon)]
    east = north = 0.0
    # Leg lengths grow 1,1,2,2,3,3,4,4... times the spacing (N-S-E-W order).
    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # E, N, W, S
    lengths: List[int] = []
    for i in range(1, laps + 1):
        lengths.append(i)
        lengths.append(i)
    di = 0
    for length in lengths:
        de, dn = dirs[di % 4]
        for _ in range(length):
            east += de * spacing_nm
            north += dn * spacing_nm
            pts.append(gis.offset_meters_east_north(center_lat, center_lon, east, north))
        di += 1
    return pts


def sector_search(
    center_lat: float,
    center_lon: float,
    radius_nm: float,
    radial_lines: int = 8,
) -> List[Tuple[float, float]]:
    """Sector (VICTOR) search: outward/inward sweeps on evenly spaced radials."""
    pts: List[Tuple[float, float]] = []
    angle_step = 360.0 / max(2, radial_lines)
    for i in range(radial_lines):
        bearing = i * angle_step
        pts.append((center_lat, center_lon))
        pts.append(gis.destination(center_lat, center_lon, bearing, radius_nm))
    pts.append((center_lat, center_lon))
    return pts


def parallel_track(
    center_lat: float,
    center_lon: float,
    radius_nm: float,
    spacing_nm: float,
    track_angle_deg: float = 0.0,
) -> List[Tuple[float, float]]:
    """Parallel tracks sweeping a circular search area."""
    lines: List[List[Tuple[float, float]]] = []
    step = max(spacing_nm, 0.5)
    n_lines = max(1, int(math_ceil(2 * radius_nm / step)))
    perp_angle = (track_angle_deg + 90.0) % 360
    for i in range(-n_lines // 2, n_lines // 2 + 1):
        offset = i * step
        # Offset the centre perpendicular to the track direction.
        offset_pt = gis.destination(center_lat, center_lon, perp_angle, offset)
        start = gis.destination(offset_pt[0], offset_pt[1], track_angle_deg, -radius_nm)
        end = gis.destination(offset_pt[0], offset_pt[1], track_angle_deg, radius_nm)
        lines.append([start, end])
    return flatten_with_turnarounds(lines)


def creeping_line(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    spacing_nm: float,
    coverage_half_width_nm: float = 4.0,
) -> List[Tuple[float, float]]:
    """Creeping line along a known route with parallel legs offset to the side."""
    track = gis.bearing_between(start_lat, start_lon, end_lat, end_lon)
    track_len = gis.haversine_nm(start_lat, start_lon, end_lat, end_lon)
    perp = (track + 90.0) % 360
    n_legs = max(1, int(math_ceil((2 * coverage_half_width_nm) / max(spacing_nm, 0.5))))
    legs: List[List[Tuple[float, float]]] = []
    for i in range(-n_legs // 2, n_legs // 2 + 1):
        offset = i * spacing_nm
        pt_a = gis.destination(start_lat, start_lon, perp, offset)
        pt_b = gis.destination(end_lat, end_lon, perp, offset)
        legs.append([pt_a, pt_b])
    return flatten_with_turnarounds(legs)


def track_line(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> List[Tuple[float, float]]:
    """Track line: sweep the projected path, return leg offset to one side."""
    track = gis.bearing_between(start_lat, start_lon, end_lat, end_lon)
    track_len = gis.haversine_nm(start_lat, start_lon, end_lat, end_lon)
    if track_len < 0.1:
        return [(start_lat, start_lon), (end_lat, end_lon)]
    perp = (track + 90.0) % 360
    ret_a = gis.destination(end_lat, end_lon, perp, 1.5)
    ret_b = gis.destination(start_lat, start_lon, perp, 1.5)
    return [
        (start_lat, start_lon),
        (end_lat, end_lon),
        ret_a,
        ret_b,
        (start_lat, start_lon),
    ]


def flatten_with_turnarounds(lines: List[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """Snake lines into one polyline, reversing every other line for continuity."""
    flat: List[Tuple[float, float]] = []
    for idx, line in enumerate(lines):
        ordered = line if idx % 2 == 0 else list(reversed(line))
        if flat:
            flat.append(flat[-1])  # small turn at the end of the previous leg
        flat.extend(ordered)
    return flat


def generate_pattern(
    pattern_type: str,
    *,
    center_lat: float,
    center_lon: float,
    radius_nm: float,
    spacing_nm: float,
    predicted_lat: float,
    predicted_lon: float,
    lkp_lat: float,
    lkp_lon: float,
) -> List[Tuple[float, float]]:
    """Dispatch to the correct pattern generator."""
    if pattern_type == "expanding_square":
        return expanding_square(center_lat, center_lon, max(spacing_nm, 0.5))
    if pattern_type == "sector":
        return sector_search(center_lat, center_lon, radius_nm, radial_lines=8)
    if pattern_type == "parallel_track":
        return parallel_track(center_lat, center_lon, radius_nm, spacing_nm, 0.0)
    if pattern_type == "creeping_line":
        return creeping_line(lkp_lat, lkp_lon, predicted_lat, predicted_lon, spacing_nm)
    if pattern_type == "track_line":
        return track_line(lkp_lat, lkp_lon, predicted_lat, predicted_lon)
    return expanding_square(center_lat, center_lon, max(spacing_nm, 0.5))


def math_ceil(x: float) -> int:
    """Ceiling helper (avoids importing math inside hot loops)."""
    import math

    return math.ceil(x)
