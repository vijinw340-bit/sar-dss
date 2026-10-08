-- =====================================================================
-- SAR-DSS - Full PostgreSQL / PostGIS schema reference
--
-- The application creates these tables automatically via SQLAlchemy on
-- startup. This file documents the production schema including the
-- PostGIS geometry columns that the application adds automatically on
-- PostgreSQL (see app/core/database.py ensure_postgis_geometry).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    email           VARCHAR(128) NOT NULL UNIQUE,
    full_name       VARCHAR(128) NOT NULL,
    designation     VARCHAR(128),
    phone           VARCHAR(32),
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(32)  NOT NULL DEFAULT 'sar_officer',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_email    ON users (email);

-- ---------------------------------------------------------------------
-- aircraft
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aircraft (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    registration_number VARCHAR(32)  NOT NULL UNIQUE,
    aircraft_type       VARCHAR(64)  NOT NULL,
    operator            VARCHAR(128),
    created_at          TIMESTAMP
);

-- ---------------------------------------------------------------------
-- missions
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS missions (
    id                    SERIAL PRIMARY KEY,
    mission_name          VARCHAR(128) NOT NULL,
    status                VARCHAR(32)  NOT NULL DEFAULT 'active',
    flight_number         VARCHAR(32),
    aircraft_name         VARCHAR(128),
    registration_number   VARCHAR(32),
    aircraft_type         VARCHAR(64),
    pilot_name            VARCHAR(128),
    departure_airport     VARCHAR(128),
    destination_airport   VARCHAR(128),
    lkp_latitude          DOUBLE PRECISION NOT NULL,
    lkp_longitude         DOUBLE PRECISION NOT NULL,
    altitude_ft           DOUBLE PRECISION DEFAULT 0,
    ground_speed_kts      DOUBLE PRECISION DEFAULT 0,
    heading_deg           DOUBLE PRECISION DEFAULT 0,
    last_contact_time     TIMESTAMP NOT NULL,
    fuel_remaining_hours  DOUBLE PRECISION DEFAULT 0,
    wind_speed_kts        DOUBLE PRECISION DEFAULT 0,
    wind_direction_deg    DOUBLE PRECISION DEFAULT 0,
    weather_conditions    VARCHAR(255) DEFAULT 'Clear',
    visibility_nm         DOUBLE PRECISION DEFAULT 10,
    remarks               TEXT,
    lkp_accuracy          VARCHAR(16) DEFAULT 'medium',
    is_route_known        BOOLEAN DEFAULT FALSE,
    elapsed_hours         DOUBLE PRECISION DEFAULT 0,
    distance_nm           DOUBLE PRECISION DEFAULT 0,
    search_radius_nm      DOUBLE PRECISION DEFAULT 0,
    search_area_sqnm      DOUBLE PRECISION DEFAULT 0,
    uncertainty_nm        DOUBLE PRECISION DEFAULT 0,
    weather_impact        DOUBLE PRECISION DEFAULT 0,
    risk_score            DOUBLE PRECISION DEFAULT 0,
    priority_rank         INTEGER DEFAULT 0,
    predicted_latitude    DOUBLE PRECISION,
    predicted_longitude   DOUBLE PRECISION,
    desired_coverage_pct  DOUBLE PRECISION DEFAULT 0,
    created_by            INTEGER REFERENCES users(id),
    created_at            TIMESTAMP,
    updated_at            TIMESTAMP,
    started_at            TIMESTAMP,
    completed_at          TIMESTAMP,
    geom_lkp              geometry(Point,4326),
    geom_predicted        geometry(Point,4326)
);
CREATE INDEX IF NOT EXISTS ix_missions_status        ON missions (status);
CREATE INDEX IF NOT EXISTS ix_missions_mission_name  ON missions (mission_name);
CREATE INDEX IF NOT EXISTS ix_missions_geom_lkp      ON missions USING GIST (geom_lkp);

-- ---------------------------------------------------------------------
-- search_areas
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_areas (
    id                 SERIAL PRIMARY KEY,
    mission_id         INTEGER NOT NULL UNIQUE REFERENCES missions(id) ON DELETE CASCADE,
    center_latitude    DOUBLE PRECISION NOT NULL,
    center_longitude   DOUBLE PRECISION NOT NULL,
    radius_nm          DOUBLE PRECISION NOT NULL,
    area_sqnm          DOUBLE PRECISION NOT NULL,
    polygon_geojson    TEXT NOT NULL,
    track_spacing_nm   DOUBLE PRECISION DEFAULT 2,
    desired_coverage_pct DOUBLE PRECISION DEFAULT 0,
    created_at         TIMESTAMP,
    geom               geometry(Polygon,4326)
);
CREATE INDEX IF NOT EXISTS ix_search_areas_geom ON search_areas USING GIST (geom);

-- ---------------------------------------------------------------------
-- search_patterns
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_patterns (
    id                SERIAL PRIMARY KEY,
    mission_id        INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    pattern_type      VARCHAR(48) NOT NULL,
    reason            TEXT,
    recommended       BOOLEAN NOT NULL DEFAULT FALSE,
    params_json       TEXT DEFAULT '{}',
    waypoints_geojson TEXT NOT NULL,
    track_spacing_nm  DOUBLE PRECISION DEFAULT 2,
    created_at        TIMESTAMP,
    geom              geometry(LineString,4326)
);

-- ---------------------------------------------------------------------
-- probability_zones
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS probability_zones (
    id                SERIAL PRIMARY KEY,
    mission_id        INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    zone_level        VARCHAR(16) NOT NULL,
    color             VARCHAR(16) NOT NULL,
    min_radius_nm     DOUBLE PRECISION DEFAULT 0,
    max_radius_nm     DOUBLE PRECISION DEFAULT 0,
    probability_pct   DOUBLE PRECISION DEFAULT 0,
    polygon_geojson   TEXT NOT NULL,
    created_at        TIMESTAMP,
    geom              geometry(Polygon,4326)
);

-- ---------------------------------------------------------------------
-- sectors
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sectors (
    id               SERIAL PRIMARY KEY,
    mission_id       INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    code             VARCHAR(8) NOT NULL,
    name             VARCHAR(64) NOT NULL,
    color            VARCHAR(16) NOT NULL,
    start_angle_deg  DOUBLE PRECISION DEFAULT 0,
    end_angle_deg    DOUBLE PRECISION DEFAULT 0,
    center_latitude  DOUBLE PRECISION NOT NULL,
    center_longitude DOUBLE PRECISION NOT NULL,
    area_sqnm        DOUBLE PRECISION DEFAULT 0,
    assigned_aircraft VARCHAR(128),
    polygon_geojson  TEXT NOT NULL,
    created_at       TIMESTAMP,
    geom             geometry(Polygon,4326)
);

-- ---------------------------------------------------------------------
-- reports
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id           SERIAL PRIMARY KEY,
    mission_id   INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    report_type  VARCHAR(16) DEFAULT 'pdf',
    title        VARCHAR(255) NOT NULL,
    file_path    VARCHAR(512) NOT NULL,
    generated_by INTEGER REFERENCES users(id),
    created_at   TIMESTAMP
);

-- ---------------------------------------------------------------------
-- weather_snapshots
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_snapshots (
    id                 SERIAL PRIMARY KEY,
    mission_id         INTEGER REFERENCES missions(id) ON DELETE CASCADE,
    latitude           DOUBLE PRECISION NOT NULL,
    longitude          DOUBLE PRECISION NOT NULL,
    temperature_c      DOUBLE PRECISION,
    wind_speed_kts     DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    visibility_km      DOUBLE PRECISION,
    humidity           DOUBLE PRECISION,
    pressure_hpa       DOUBLE PRECISION,
    conditions         VARCHAR(255),
    precipitation_mm   DOUBLE PRECISION,
    forecast_json      TEXT,
    source             VARCHAR(64) DEFAULT 'openmeteo',
    created_at         TIMESTAMP
);

-- ---------------------------------------------------------------------
-- activity_logs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_logs (
    id          SERIAL PRIMARY KEY,
    mission_id  INTEGER REFERENCES missions(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id),
    action      VARCHAR(64) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_activity_logs_created_at ON activity_logs (created_at);
