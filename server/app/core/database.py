"""Database engine, session factory and declarative base.

Supports both PostgreSQL (production) and SQLite (local development / tests).
Spatial coordinates are stored as plain floats plus GeoJSON text columns so the
application layer works identically on both engines. PostGIS geometry columns
are provisioned separately via server/app/sql/init.sql for advanced spatial
queries on PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

def _normalize_url(url: str) -> str:
    """Map generic postgres URLs to the installed psycopg v3 dialect.

    Hosted providers (Railway, Render, Neon...) expose DATABASE_URL as
    ``postgres://`` or ``postgresql://``. SQLAlchemy would then try the
    psycopg2 driver, which is not installed - rewrite to ``psycopg`` v3.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
    return url


DATABASE_URL = _normalize_url(settings.DATABASE_URL)

# SQLite needs check_same_thread disabled when used across threads.
connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Imported models must be registered first."""
    from app import models  # noqa: F401  (ensure models are imported)

    Base.metadata.create_all(bind=engine)
    ensure_postgis_geometry()


def ensure_postgis_geometry() -> None:
    """Add PostGIS geometry columns on PostgreSQL (skipped on SQLite).

    Keeps the ORM portable while still provisioning real spatial columns
    for advanced spatial queries on production deployments.
    """
    if not engine.url.get_backend_name().startswith("postgres"):
        return
    # PostGIS is optional: hosted Postgres often lacks the extension.
    # The app runs fully on plain float/GeoJSON columns; spatial columns
    # are a bonus. Never let this fail application startup.
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    except Exception as exc:  # noqa: BLE001 - portability over strictness
        print(f"[db] PostGIS unavailable, skipping spatial columns: {exc}")
        return
    from sqlalchemy import text

    alters = [
        (
            "missions", "geom_lkp", "geometry(Point,4326)",
            "ST_SetSRID(ST_MakePoint(lkp_longitude, lkp_latitude), 4326)",
        ),
        (
            "missions", "geom_predicted", "geometry(Point,4326)",
            "ST_SetSRID(ST_MakePoint(predicted_longitude, predicted_latitude), 4326)",
        ),
        (
            "search_areas", "geom", "geometry(Polygon,4326)",
            "ST_SetSRID(ST_GeomFromGeoJSON(polygon_geojson), 4326)",
        ),
        (
            "probability_zones", "geom", "geometry(Polygon,4326)",
            "ST_SetSRID(ST_GeomFromGeoJSON(polygon_geojson), 4326)",
        ),
        (
            "sectors", "geom", "geometry(Polygon,4326)",
            "ST_SetSRID(ST_GeomFromGeoJSON(polygon_geojson), 4326)",
        ),
        (
            "search_patterns", "geom", "geometry(LineString,4326)",
            "ST_SetSRID(ST_GeomFromGeoJSON(waypoints_geojson), 4326)",
        ),
    ]
    with engine.begin() as conn:
        for table, col, gtype, expr in alters:
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {gtype}"
                )
            )
            conn.execute(
                text(
                    f"UPDATE {table} SET {col} = {expr} "
                    f"WHERE {col} IS NULL AND {expr} IS NOT NULL"
                )
            )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_missions_geom_lkp "
                "ON missions USING GIST (geom_lkp)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_search_areas_geom "
                "ON search_areas USING GIST (geom)"
            )
        )
