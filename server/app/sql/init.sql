-- =====================================================================
-- SAR-DSS - Database initialisation (runs automatically on first boot)
-- Enables PostGIS. The application provisions its tables via SQLAlchemy
-- on startup; the full DDL reference is available in schema_postgres.sql
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

COMMENT ON EXTENSION postgis IS 'PostGIS geometry/geography support for SAR-DSS spatial queries';
