-- =====================================================================
-- SAR-DSS - Optional seed / analytical objects (PostGIS)
--
-- These objects are idempotent and safe to run after the application has
-- provisioned its tables. Sample missions are seeded by the application
-- itself (python -m app.seed) so their computed values are consistent.
-- =====================================================================

-- Live view of active search missions for operational dashboards.
CREATE OR REPLACE VIEW v_active_missions AS
SELECT
    m.id,
    m.mission_name,
    m.status,
    m.lkp_latitude,
    m.lkp_longitude,
    m.search_radius_nm,
    m.search_area_sqnm,
    m.risk_score,
    m.ground_speed_kts,
    m.heading_deg,
    ST_DistanceSphere(
        m.geom_lkp,
        ST_SetSRID(ST_MakePoint(m.predicted_longitude, m.predicted_latitude), 4326)
    ) / 1852.0 AS predicted_offset_nm,
    sa.geom AS search_polygon
FROM missions m
LEFT JOIN search_areas sa ON sa.mission_id = m.id
WHERE m.status IN ('active', 'paused');

-- Count of sectors with / without assigned aircraft per active mission.
CREATE OR REPLACE VIEW v_sector_coverage AS
SELECT
    m.id AS mission_id,
    m.mission_name,
    COUNT(s.id)                 AS total_sectors,
    COUNT(s.assigned_aircraft)  AS assigned_sectors,
    ROUND(100.0 * COUNT(s.assigned_aircraft) / NULLIF(COUNT(s.id), 0), 1) AS coverage_pct
FROM missions m
LEFT JOIN sectors s ON s.mission_id = m.id
WHERE m.status IN ('active', 'paused')
GROUP BY m.id, m.mission_name;
