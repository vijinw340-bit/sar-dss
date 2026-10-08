"""Unit tests for the GIS calculation and pattern engines."""
import math
from datetime import datetime, timedelta

import pytest

from app.services import calculations, gis, patterns, probability, sectors


def test_haversine_distance():
    # Approx distance Delhi -> Mumbai is ~620 nm
    d = gis.haversine_nm(28.6139, 77.2090, 19.0760, 72.8777)
    assert 590 < d < 700


def test_destination_roundtrip():
    lat, lon = 28.5, 77.0
    dist = 120.0
    bearing = 45.0
    lat2, lon2 = gis.destination(lat, lon, bearing, dist)
    back = gis.haversine_nm(lat, lon, lat2, lon2)
    assert abs(back - dist) < 0.5


def test_radius_at_least_distance_plus_uncertainty():
    last = datetime.utcnow() - timedelta(hours=1)
    res = calculations.calculate_mission(
        lkp_lat=28.6, lkp_lon=77.2, ground_speed_kts=120, heading_deg=45,
        last_contact_time=last, wind_speed_kts=10, wind_direction_deg=270,
        weather_conditions="Clear", visibility_nm=8, lkp_accuracy="medium",
    )
    assert res.distance_nm == pytest_close(120.0, 1.0)
    assert res.radius_nm >= res.distance_nm + res.uncertainty_nm - 0.01
    assert res.radius_nm >= calculations.MIN_SEARCH_RADIUS_NM


def test_severe_weather_expands_radius():
    last = datetime.utcnow() - timedelta(hours=2)
    base = calculations.calculate_mission(
        lkp_lat=28.6, lkp_lon=77.2, ground_speed_kts=100, heading_deg=90,
        last_contact_time=last, wind_speed_kts=10, wind_direction_deg=0,
        weather_conditions="Clear", visibility_nm=10, lkp_accuracy="medium",
    )
    severe = calculations.calculate_mission(
        lkp_lat=28.6, lkp_lon=77.2, ground_speed_kts=100, heading_deg=90,
        last_contact_time=last, wind_speed_kts=45, wind_direction_deg=0,
        weather_conditions="Thunderstorm heavy rain", visibility_nm=0.5,
        lkp_accuracy="medium",
    )
    assert severe.radius_nm > base.radius_nm
    assert severe.weather_impact > 0.5


def test_predicted_position_drift():
    last = datetime.utcnow() - timedelta(hours=1)
    res = calculations.calculate_mission(
        lkp_lat=0.0, lkp_lon=0.0, ground_speed_kts=120, heading_deg=0,
        last_contact_time=last, wind_speed_kts=30, wind_direction_deg=90,
        weather_conditions="Clear", visibility_nm=8,
    )
    # With a strong crosswind, predicted lon should drift east (+x).
    assert res.predicted_lon is not None
    assert res.predicted_lat is not None
    assert res.predicted_lon > 0.0


def test_pattern_recommendation_rules():
    assert patterns.recommend_pattern("high", False, 100.0)[0] == "expanding_square"
    assert patterns.recommend_pattern("medium", True, 100.0)[0] == "creeping_line"
    assert patterns.recommend_pattern("medium", False, 5000.0)[0] == "parallel_track"
    assert patterns.recommend_pattern("low", False, 100.0)[0] == "sector"


def test_generators_produce_valid_geometries():
    center = (28.6, 77.2)
    square = patterns.expanding_square(*center, spacing_nm=2.0, laps=3)
    assert len(square) > 10
    sec = patterns.sector_search(*center, radius_nm=30.0, radial_lines=8)
    assert len(sec) > 5
    par = patterns.parallel_track(*center, radius_nm=30.0, spacing_nm=3.0)
    assert len(par) > 4
    cre = patterns.creeping_line(28.5, 77.0, 29.0, 77.5, spacing_nm=2.0)
    assert len(cre) > 4
    tl = patterns.track_line(28.5, 77.0, 29.0, 77.5)
    assert len(tl) >= 3


def test_probability_zones_cover_search_area():
    weights = probability.confidence_weights(
        lkp_accuracy="medium", elapsed_hours=2, wind_speed_kts=15
    )
    zones = probability.generate_zones(28.6, 77.2, 50.0, weights)
    assert len(zones) == 3
    levels = [z[0] for z in zones]
    assert levels == ["high", "medium", "low"]
    total = sum(z[4] for z in zones)
    assert math.isclose(total, 100.0, abs_tol=1.0)
    # High zone max radius equals medium zone min radius (touching bands).
    assert zones[0][3] == pytest_close(zones[1][2], 0.001)


def test_sectors_divide_circle():
    secs = sectors.generate_sectors(28.6, 77.2, 40.0, count=4)
    assert len(secs) == 4
    assert [s["code"] for s in secs] == ["A", "B", "C", "D"]
    for s in secs:
        assert s["area_sqnm"] > 0
        # Angular width handles wrap-around (e.g. 270 -> 0)
        width = (s["end_angle_deg"] - s["start_angle_deg"]) % 360
        assert width == 90.0


def pytest_close(a: float, b: float, tol: float = 0.001):
    return pytest.approx(a, abs=tol)
