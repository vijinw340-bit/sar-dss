"""GIS math engine: spherical navigation primitives used across SAR-DSS.

All distances are in nautical miles, angles in degrees, coordinates in WGS84.
"""
import math
from typing import List, Tuple

# Earth mean radius in nautical miles (1 nm = 1852 m, R = 6371 km).
EARTH_RADIUS_NM = 3440.065
DEG_PER_RAD = 180.0 / math.pi
NM_PER_DEG_LAT = 60.0  # one degree of latitude ≈ 60 nm


def to_rad(deg: float) -> float:
    return math.radians(deg)


def to_deg(rad: float) -> float:
    return math.degrees(rad)


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in nautical miles."""
    d_lat = to_rad(lat2 - lat1)
    d_lon = to_rad(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_NM * c


def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (degrees, 0..360) from point 1 toward point 2."""
    lat1_r, lat2_r = to_rad(lat1), to_rad(lat2)
    d_lon = to_rad(lon2 - lon1)
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    return (to_deg(math.atan2(y, x)) + 360) % 360


def destination(
    lat: float, lon: float, bearing_deg: float, distance_nm: float
) -> Tuple[float, float]:
    """Return (lat, lon) after moving a distance along a bearing."""
    d = distance_nm / EARTH_RADIUS_NM
    b = to_rad(bearing_deg)
    lat1, lon1 = to_rad(lat), to_rad(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b)
    )
    lon2 = lon1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return to_deg(lat2), ((to_deg(lon2) + 540) % 360) - 180


def offset_meters_east_north(
    lat: float, lon: float, east_nm: float, north_nm: float
) -> Tuple[float, float]:
    """Approximate offset in nm applied to a coordinate (local tangent plane)."""
    new_lat = lat + north_nm / NM_PER_DEG_LAT
    new_lon = lon + east_nm / (NM_PER_DEG_LAT * math.cos(to_rad(lat)))
    return new_lat, new_lon


def circle_polygon(
    center_lat: float, center_lon: float, radius_nm: float, segments: int = 64
) -> List[Tuple[float, float]]:
    """Vertex list (lat, lon) of a circle polygon on the sphere."""
    pts = []
    for i in range(segments):
        bearing = i * (360.0 / segments)
        pts.append(destination(center_lat, center_lon, bearing, radius_nm))
    return pts


def spherical_angle_at(apex: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Interior spherical angle (radians) at `apex` between points a and b."""
    b1 = bearing_between(apex[0], apex[1], a[0], a[1])
    b2 = bearing_between(apex[0], apex[1], b[0], b[1])
    diff = abs(b1 - b2) % 360
    if diff > 180:
        diff = 360 - diff
    return to_rad(diff)


def spherical_polygon_area_sqnm(points: List[Tuple[float, float]]) -> float:
    """Area of a spherical polygon (naval formula) in square nautical miles."""
    if len(points) < 3:
        return 0.0
    n = len(points)
    total = 0.0
    for i in range(n):
        apex = points[i]
        a = points[(i - 1) % n]
        b = points[(i + 1) % n]
        total += spherical_angle_at(apex, a, b)
    excess = abs(total - (n - 2) * math.pi)
    return excess * EARTH_RADIUS_NM * EARTH_RADIUS_NM


def circle_area_sqnm(radius_nm: float) -> float:
    """Area of a circle of given radius in square nautical miles."""
    return math.pi * radius_nm * radius_nm


def polyline_geojson(points: List[Tuple[float, float]]) -> dict:
    """GeoJSON LineString from a list of (lat, lon) points."""
    return {
        "type": "LineString",
        "coordinates": [[round(lon, 6), round(lat, 6)] for lat, lon in points],
    }


def polygon_geojson(points: List[Tuple[float, float]]) -> dict:
    """GeoJSON Polygon (closed) from a list of (lat, lon) points."""
    coords = [[round(lon, 6), round(lat, 6)] for lat, lon in points]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def point_geojson(lat: float, lon: float) -> dict:
    """GeoJSON Point."""
    return {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}


def parse_geojson(raw: str) -> dict:
    """Parse a stored GeoJSON string (safe fallback to {})."""
    import json

    try:
        return json.loads(raw)
    except Exception:
        return {}


def mean_bearing(angles_deg: List[float]) -> float:
    """Circular mean of a list of bearings in degrees."""
    x = sum(math.cos(to_rad(a)) for a in angles_deg)
    y = sum(math.sin(to_rad(a)) for a in angles_deg)
    if x == 0 and y == 0:
        return 0.0
    return (to_deg(math.atan2(y, x)) + 360) % 360
