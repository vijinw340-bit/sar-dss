"""End-to-end API tests for the auth and mission flows."""
from datetime import datetime, timedelta


def _payload():
    return {
        "mission_name": "Integration Test Flight",
        "flight_number": "INT-101",
        "aircraft_name": "Dornier 228",
        "registration_number": "IN-TEST",
        "aircraft_type": "Fixed-wing",
        "pilot_name": "Capt. Test",
        "departure_airport": "VIDP",
        "destination_airport": "VABB",
        "lkp_latitude": 28.5,
        "lkp_longitude": 77.1,
        "altitude_ft": 6000,
        "ground_speed_kts": 140,
        "heading_deg": 200,
        "last_contact_time": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "fuel_remaining_hours": 3.0,
        "wind_speed_kts": 15,
        "wind_direction_deg": 250,
        "weather_conditions": "Clear",
        "visibility_nm": 10,
        "remarks": "Automated test",
        "lkp_accuracy": "medium",
        "is_route_known": False,
    }


def test_login_failure(client):
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_register_requires_admin(client, auth_headers):
    resp = client.post(
        "/api/v1/auth/register",
        headers=auth_headers,
        json={
            "username": "officer1",
            "email": "officer1@aai.in",
            "full_name": "SAR Officer One",
            "password": "Officer@123",
            "role": "sar_officer",
        },
    )
    assert resp.status_code == 201
    # Duplicate username rejected
    dup = client.post(
        "/api/v1/auth/register",
        headers=auth_headers,
        json={
            "username": "officer1",
            "email": "officer1b@aai.in",
            "full_name": "SAR Officer One",
            "password": "Officer@123",
        },
    )
    assert dup.status_code == 409


def test_mission_flow(client, auth_headers):
    created = client.post("/api/v1/missions", headers=auth_headers, json=_payload())
    assert created.status_code == 201
    m = created.json()
    assert m["search_radius_nm"] > 0
    assert m["search_area_sqnm"] > 0
    assert len(m["zones"]) == 3
    assert len(m["sectors"]) == 4
    assert any(p["recommended"] for p in m["patterns"])

    # Recalculation endpoint
    recalc = client.post(f"/api/v1/missions/{m['id']}/calculate", headers=auth_headers)
    assert recalc.status_code == 200

    # Analysis endpoint
    analysis = client.get(f"/api/v1/missions/{m['id']}/analysis", headers=auth_headers)
    assert analysis.status_code == 200
    assert analysis.json()["risk"]["score"] >= 0

    # Sector assignment
    sectors = client.get(f"/api/v1/missions/{m['id']}/sectors", headers=auth_headers).json()
    assert len(sectors) == 4
    sector_id = sectors[0]["id"]
    assign = client.patch(
        f"/api/v1/missions/sectors/{sector_id}",
        headers=auth_headers,
        json={"assigned_aircraft": "ALH Dhruv"},
    )
    assert assign.status_code == 200
    assert assign.json()["assigned_aircraft"] == "ALH Dhruv"

    # Status transition
    pause = client.patch(
        f"/api/v1/missions/{m['id']}",
        headers=auth_headers,
        json={"status": "completed"},
    )
    assert pause.status_code == 200
    assert pause.json()["status"] == "completed"

    # Delete requires admin
    delete = client.delete(f"/api/v1/missions/{m['id']}", headers=auth_headers)
    assert delete.status_code == 204


def test_mission_validation(client, auth_headers):
    bad = _payload()
    bad["lkp_latitude"] = 120.0  # out of range
    resp = client.post("/api/v1/missions", headers=auth_headers, json=bad)
    assert resp.status_code == 422
