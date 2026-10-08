import L from "leaflet";
import { useEffect, useMemo } from "react";
import {
  Circle,
  LayersControl,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  Tooltip,
  useMap,
} from "react-leaflet";
import { DarkLayer, SatelliteLayer, StreetLayer, TerrainLayer } from "./BaseLayers";
import { Graticule } from "./Graticule";
import { AIRPORTS, haversineNm } from "./airports";

const { BaseLayer, Overlay } = LayersControl;

/** Rotated aircraft divIcon marker. */
export function makePlaneIcon(headingDeg: number, color = "#ffffff") {
  return L.divIcon({
    className: "aircraft-marker",
    html: `<div style="transform: rotate(${headingDeg}deg)">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>
        </svg>
      </div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

/** Pulsing red LKP marker. */
export function makeLkpIcon() {
  return L.divIcon({
    className: "lkp-marker-pulse",
    html: `<div style="width:18px;height:18px;border-radius:50%;background:#ef4444;border:3px solid #fff;box-shadow:0 0 12px rgba(239,68,68,.9)"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function FlyTo({ center, radiusNm }: { center: [number, number]; radiusNm: number }) {
  const map = useMap();
  useEffect(() => {
    if (!center[0] || !center[1]) return;
    const zoom = Math.max(5, Math.min(11, 13 - Math.log2(Math.max(radiusNm, 1))));
    map.flyTo(center, zoom, { duration: 1.2 });
  }, [center, radiusNm, map]);
  return null;
}

export interface ZoneDisplay {
  color: string;
  level: string;
  probabilityPct: number;
  polygon: [number, number][];
}

export interface SectorDisplay {
  color: string;
  name: string;
  polygon: [number, number][];
}

interface MissionMapProps {
  center: [number, number];
  radiusNm?: number;
  searchPolygon?: [number, number][];
  zones?: ZoneDisplay[];
  sectors?: SectorDisplay[];
  patternWaypoints?: [number, number][];
  predicted?: [number, number] | null;
  heading?: number;
  showZones?: boolean;
  showPattern?: boolean;
  showSectors?: boolean;
  showRadius?: boolean;
  showGrid?: boolean;
  showAirports?: boolean;
  showNearbyAirports?: boolean;
  height?: string | number;
  missionName?: string;
  flightNumber?: string;
  aircraftName?: string;
}

export function MissionMap({
  center,
  radiusNm = 0,
  searchPolygon,
  zones,
  sectors,
  patternWaypoints,
  predicted,
  heading = 0,
  showZones = true,
  showPattern = true,
  showSectors = true,
  showRadius = true,
  showGrid = false,
  showAirports = false,
  showNearbyAirports = false,
  height = "100%",
  missionName,
  flightNumber,
  aircraftName,
}: MissionMapProps) {
  const isDefaultView = !center[0] && !center[1];
  const mapCenter: [number, number] = isDefaultView ? [22.5, 79.0] : center;
  const initialZoom = isDefaultView ? 5 : 8;

  const nearbyAirports = useMemo(() => {
    if (!showNearbyAirports && !showAirports) return [];
    if (isDefaultView) return AIRPORTS.slice(0, 12);
    return AIRPORTS.map((a) => ({ ...a, dist: haversineNm(center[0], center[1], a.lat, a.lon) }))
      .sort((a, b) => a.dist - b.dist)
      .filter((a) => a.dist <= Math.max(radiusNm * 1.6, 60))
      .slice(0, 12);
  }, [showNearbyAirports, showAirports, isDefaultView, center, radiusNm]);

  const planeIcon = useMemo(() => makePlaneIcon(heading), [heading]);
  const lkpIcon = useMemo(() => makeLkpIcon(), []);

  return (
    <MapContainer
      center={mapCenter}
      zoom={initialZoom}
      style={{ height, width: "100%", borderRadius: "0.75rem" }}
      className="z-0"
      zoomControl={true}
    >
      {!isDefaultView && <FlyTo center={center} radiusNm={radiusNm || 1} />}

      <LayersControl position="topright">
        <BaseLayer checked name="Street">
          <StreetLayer />
        </BaseLayer>
        <BaseLayer name="Satellite">
          <SatelliteLayer />
        </BaseLayer>
        <BaseLayer name="Terrain">
          <TerrainLayer />
        </BaseLayer>
        <BaseLayer name="Dark">
          <DarkLayer />
        </BaseLayer>

        {showRadius && radiusNm > 0 && !isDefaultView && (
          <Overlay checked name="Search radius">
            <Circle
              center={center}
              radius={radiusNm * 1852}
              pathOptions={{ color: "#1d4ed8", weight: 2, dashArray: "6 6", fillColor: "#1d4ed8", fillOpacity: 0.06 }}
            />
          </Overlay>
        )}

        {showZones && zones && zones.length > 0 && !isDefaultView && (
          <Overlay checked name="Probability zones">
            {zones.map((z, i) => (
              <Polyline
                key={`zone-${z.level}-${i}`}
                positions={z.polygon}
                pathOptions={{ color: z.color, weight: 1.5, fillColor: z.color, fillOpacity: 0.28 }}
              >
                <Tooltip direction="center" sticky>
                  {z.level.toUpperCase()} · {z.probabilityPct}%
                </Tooltip>
              </Polyline>
            ))}
          </Overlay>
        )}

        {showSectors && sectors && sectors.length > 0 && !isDefaultView && (
          <Overlay checked name="Sectors">
            {sectors.map((s, i) => (
              <Polyline
                key={`sector-${i}`}
                positions={s.polygon}
                pathOptions={{ color: s.color, weight: 2, fillColor: s.color, fillOpacity: 0.12, dashArray: "8 4" }}
              >
                <Tooltip direction="center" sticky>
                  {s.name}
                </Tooltip>
              </Polyline>
            ))}
          </Overlay>
        )}

        {showPattern && patternWaypoints && patternWaypoints.length > 0 && !isDefaultView && (
          <Overlay checked name="Search pattern">
            <Polyline
              positions={patternWaypoints}
              pathOptions={{ color: "#f97316", weight: 3, opacity: 0.95 }}
            >
              <Tooltip direction="top" sticky>
                Recommended search pattern
              </Tooltip>
            </Polyline>
          </Overlay>
        )}

        {showGrid && (
          <Overlay checked name="Grid coordinates">
            <Graticule />
          </Overlay>
        )}

        {(showNearbyAirports || showAirports) && (
          <Overlay checked name="Airports">
            {nearbyAirports.map((a) => (
              <Marker
                key={a.code}
                position={[a.lat, a.lon]}
                icon={L.divIcon({
                  className: "",
                  html: `<div style="transform:translate(-50%,-50%)">
                    <div style="display:flex;align-items:center;gap:2px;background:rgba(15,42,74,.85);color:#fff;font-size:10px;font-weight:700;padding:2px 6px;border-radius:6px;border:1px solid rgba(255,255,255,.5)">
                      ✈ ${a.code}
                    </div></div>`,
                  iconSize: [0, 0],
                })}
              >
                <Popup>{a.name}</Popup>
              </Marker>
            ))}
          </Overlay>
        )}
      </LayersControl>

      {/* Static overlay layers (always rendered) */}
      {searchPolygon && searchPolygon.length > 0 && !isDefaultView && (
        <Polyline
          positions={searchPolygon}
          pathOptions={{ color: "#0f2a4a", weight: 2.5, fillColor: "#1d4ed8", fillOpacity: 0.05 }}
        />
      )}

      {!isDefaultView && (
        <>
          <Marker position={center} icon={lkpIcon}>
            <Popup>
              <strong>Last Known Position</strong>
              <br />
              {center[0].toFixed(5)}, {center[1].toFixed(5)}
            </Popup>
          </Marker>

          <Marker position={center} icon={planeIcon}>
            <Popup>
              <strong>{missionName || "Mission"}</strong>
              {flightNumber && (
                <>
                  <br />
                  Flight {flightNumber}
                </>
              )}
              {aircraftName && (
                <>
                  <br />
                  {aircraftName}
                </>
              )}
              <br />
              Heading {Math.round(heading)}° · {Math.round(radiusNm)} nm radius
            </Popup>
          </Marker>

          {predicted && (
            <Marker
              position={predicted}
              icon={L.divIcon({
                className: "",
                html: `<div style="transform:translate(-50%,-50%)">
                  <div style="width:14px;height:14px;transform:rotate(45deg);background:#dc2626;border:2px solid #fff"></div></div>`,
                iconSize: [0, 0],
              })}
            >
              <Tooltip direction="top" sticky>
                Predicted position
              </Tooltip>
            </Marker>
          )}
        </>
      )}
    </MapContainer>
  );
}
