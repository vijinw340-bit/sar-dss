"""Search-area sector division.

Divides the search circle into N equal angular sectors (A, B, C, D ...) so SAR
coordinators can assign search aircraft to specific slices of the area.
"""
from typing import List, Tuple

from app.services import gis

SECTOR_COLORS = [
    "#2563eb",
    "#16a34a",
    "#9333ea",
    "#dc2626",
    "#d97706",
    "#0891b2",
    "#db2777",
    "#4d7c0f",
    "#1d4ed8",
    "#b45309",
]


def generate_sectors(
    center_lat: float,
    center_lon: float,
    radius_nm: float,
    count: int = 4,
    start_angle_deg: float = 0.0,
    segments_per_sector: int = 8,
) -> List[dict]:
    """Return a list of sector dicts: code, name, color, angles, polygon, area."""
    count = max(1, min(10, count))
    step = 360.0 / count
    sectors = []
    for i in range(count):
        a_start = (start_angle_deg + i * step) % 360
        a_end = (a_start + step) % 360
        # Wedge polygon: center -> arc points -> back to center.
        arc = gis.circle_polygon(center_lat, center_lon, radius_nm, segments_per_sector)
        wedge = [(center_lat, center_lon)]
        for j in range(segments_per_sector):
            ang = a_start + (a_end - a_start) * (j / segments_per_sector)
            wedge.append(gis.destination(center_lat, center_lon, ang, radius_nm))
        wedge.append((center_lat, center_lon))
        area = gis.spherical_polygon_area_sqnm(wedge)
        sectors.append(
            {
                "code": chr(ord("A") + i),
                "name": f"Sector {chr(ord('A') + i)}",
                "color": SECTOR_COLORS[i % len(SECTOR_COLORS)],
                "start_angle_deg": round(a_start, 2),
                "end_angle_deg": round(a_end, 2),
                "center_latitude": center_lat,
                "center_longitude": center_lon,
                "area_sqnm": round(area, 2),
                "assigned_aircraft": None,
                "polygon_geojson": gis.polygon_geojson(wedge),
            }
        )
    return sectors
