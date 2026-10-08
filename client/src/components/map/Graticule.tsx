import L from "leaflet";
import { useEffect } from "react";
import { useMap } from "react-leaflet";

/**
 * Latitude/longitude graticule overlay rendered on a canvas GridLayer.
 * Draws degree lines across the visible map for professional GIS feel.
 */

class GraticuleLayer extends L.GridLayer {
  private color: string;
  private leafletMap: L.Map;

  constructor(map: L.Map, color: string) {
    super({ opacity: 1, tileSize: 256 });
    this.leafletMap = map;
    this.color = color;
  }

  createTile(coords: L.Coords, done: L.DoneCallback) {
    const size = this.getTileSize();
    const tile = document.createElement("canvas");
    tile.width = size.x;
    tile.height = size.y;
    const ctx = tile.getContext("2d");
    if (!ctx) {
      done(undefined, tile);
      return tile;
    }

    const nwPoint = coords.scaleBy(size);
    const sePoint = nwPoint.add(size);
    const nw = this.leafletMap.unproject(nwPoint, coords.z);
    const se = this.leafletMap.unproject(sePoint, coords.z);

    ctx.strokeStyle = this.color;
    ctx.lineWidth = 0.6;
    ctx.font = "9px Inter, sans-serif";
    ctx.fillStyle = this.color;

    const spanLng = Math.abs(nw.lng - se.lng);
    const step = spanLng > 4 ? 2 : spanLng > 1.5 ? 1 : spanLng > 0.4 ? 0.5 : 0.1;
    for (let lng = Math.floor(nw.lng / step) * step; lng <= se.lng; lng += step) {
      const x = this.leafletMap.project([(nw.lat + se.lat) / 2, lng], coords.z).x - nwPoint.x;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size.y);
      ctx.stroke();
      ctx.fillText(`${Math.abs(lng).toFixed(step < 1 ? 1 : 0)}°${lng < 0 ? "W" : "E"}`, x + 3, 10);
    }
    for (let lat = Math.floor(se.lat / step) * step; lat <= nw.lat; lat += step) {
      const y = this.leafletMap.project([lat, (nw.lng + se.lng) / 2], coords.z).y - nwPoint.y;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size.x, y);
      ctx.stroke();
      ctx.fillText(`${Math.abs(lat).toFixed(step < 1 ? 1 : 0)}°${lat < 0 ? "S" : "N"}`, 3, y + 10);
    }
    done(undefined, tile);
    return tile;
  }
}

export function Graticule({ color = "rgba(255,255,255,0.22)" }: { color?: string }) {
  const map = useMap();

  useEffect(() => {
    const grid = new GraticuleLayer(map, color);
    grid.addTo(map);
    return () => {
      map.removeLayer(grid);
    };
  }, [map, color]);

  return null;
}
