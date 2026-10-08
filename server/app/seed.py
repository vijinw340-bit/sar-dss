"""Bootstrap script: create tables and seed the initial admin user + sample data."""
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models import ActivityLog, Aircraft, Mission, User
from app.services import intelligence, mission_engine


def ensure_admin() -> None:
    """Create the bootstrap admin account if it does not exist."""
    db = SessionLocal()
    try:
        existing = (
            db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        )
        if not existing:
            admin = User(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                full_name="SAR System Administrator",
                designation="SAR Mission Coordinator",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print(f"[seed] Created admin user '{settings.ADMIN_USERNAME}'")
        else:
            print("[seed] Admin user already present")
    finally:
        db.close()


def seed_aircraft_catalog() -> None:
    """Populate the aircraft catalog if empty."""
    db = SessionLocal()
    try:
        if db.query(Aircraft).count() > 0:
            return
        catalog = [
            Aircraft(name="ALH Dhruv", registration_number="ZP-2018", aircraft_type="Helicopter", operator="Indian Air Force"),
            Aircraft(name="Dornier 228", registration_number="IN-508", aircraft_type="Fixed-wing", operator="Indian Navy"),
            Aircraft(name="HAL Chetak", registration_number="ZP-1034", aircraft_type="Helicopter", operator="Indian Coast Guard"),
            Aircraft(name="C-130J Super Hercules", registration_number="KC-3801", aircraft_type="Fixed-wing", operator="Indian Air Force"),
            Aircraft(name="Beech King Air B350", registration_number="VT-SAR", aircraft_type="Fixed-wing", operator="AAI / DGCA SAR"),
        ]
        db.add_all(catalog)
        db.commit()
        print("[seed] Aircraft catalog seeded")
    finally:
        db.close()


def seed_demo_mission() -> None:
    """Create one realistic demo mission so the map is not empty on first run."""
    db = SessionLocal()
    try:
        if db.query(Mission).count() > 0:
            return
        admin = db.query(User).filter(User.role == "admin").first()
        mission = Mission(
            mission_name="AAI Flight 4120 - Sector Search",
            status="active",
            flight_number="AAI-4120",
            aircraft_name="Cessna 172 Skyhawk",
            registration_number="VT-AAI",
            aircraft_type="General Aviation",
            pilot_name="Capt. R. Sharma",
            departure_airport="Indira Gandhi Intl (VIDP)",
            destination_airport="Dehradun (VIDN)",
            lkp_latitude=28.9895,
            lkp_longitude=77.6748,
            altitude_ft=7500,
            ground_speed_kts=110,
            heading_deg=30,
            last_contact_time=datetime.utcnow() - timedelta(hours=2, minutes=40),
            fuel_remaining_hours=1.5,
            wind_speed_kts=18,
            wind_direction_deg=240,
            weather_conditions="Partly Cloudy",
            visibility_nm=8,
            remarks="Radar contact lost near Meerut FIR boundary. Transponder last observed at FL75.",
            lkp_accuracy="medium",
            is_route_known=True,
            created_by=admin.id if admin else None,
            started_at=datetime.utcnow(),
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)
        mission_engine.run_calculation_pipeline(db, mission, admin.id if admin else None)
        mission_engine.log_activity(
            db,
            mission,
            admin.id if admin else None,
            "mission_created",
            "Demo mission seeded on first run",
        )
        print("[seed] Demo mission created")
    finally:
        db.close()


def main() -> None:
    """Run all seed steps."""
    init_db()
    ensure_admin()
    seed_aircraft_catalog()
    seed_demo_mission()


if __name__ == "__main__":
    main()
