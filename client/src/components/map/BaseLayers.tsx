import { TileLayer } from "react-leaflet";

/**
 * Base tile layers. All tiles are relayed through the SAR-DSS backend
 * (`/api/v1/tiles/<provider>/...`) so every map request exits via the
 * server's VPN/proxy egress instead of the operator's browser IP.
 * See server/app/services/netroute.py for egress configuration.
 */
const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

export function StreetLayer() {
  return (
    <TileLayer
      url={`${API_BASE}/tiles/streets/{z}/{x}/{y}.png?s={s}`}
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      maxZoom={19}
      subdomains={["a", "b", "c"]}
    />
  );
}

export function SatelliteLayer() {
  return (
    <TileLayer
      url={`${API_BASE}/tiles/satellite/{z}/{y}/{x}.png`}
      attribution="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
      maxZoom={19}
    />
  );
}

export function TerrainLayer() {
  return (
    <TileLayer
      url={`${API_BASE}/tiles/terrain/{z}/{x}/{y}.png?s={s}`}
      attribution='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors, SRTM'
      maxZoom={17}
      subdomains={["a", "b", "c"]}
    />
  );
}

export function DarkLayer() {
  return (
    <TileLayer
      url={`${API_BASE}/tiles/dark/{z}/{x}/{y}.png?s={s}&r={r}`}
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
      maxZoom={19}
      subdomains={["a", "b", "c"]}
      detectRetina={true}
    />
  );
}
