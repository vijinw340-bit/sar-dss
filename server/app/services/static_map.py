"""Static map generation by stitching anonymized relayed map tiles.

The legacy external static-map service (staticmap.openstreetmap.de) no longer
exists (dead DNS). Reports now build their map from a small grid of Esri street
tiles fetched through the configured image relay (see netroute.py image_session),
so the operator's identity never touches a public tile server directly.
"""
import io
import math

from PIL import Image

from app.services.netroute import egress

ESRI_STREETS = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
)
TILE_SIZE = 256
ZOOM_MIN = 8
ZOOM_MAX = 16


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple:
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def build_static_map(
    lat: float,
    lon: float,
    radius_nm: float,
    width: int = 840,
    height: int = 460,
) -> bytes:
    """Fetch an Esri street-tile grid via the image relay and stitch one PNG."""
    zoom = max(ZOOM_MIN, min(ZOOM_MAX, 13 - int(math.log2(max(radius_nm or 1.0, 1.0)))))
    cx, cy = _deg2num(lat, lon, zoom)
    cols = math.ceil(width / TILE_SIZE) + 1
    rows = math.ceil(height / TILE_SIZE) + 1
    x0 = cx - cols // 2
    y0 = cy - rows // 2
    canvas = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE))

    with egress.image_session() as client:
        for i in range(cols):
            for j in range(rows):
                url = ESRI_STREETS.format(z=zoom, y=y0 + j, x=x0 + i)
                try:
                    resp = client.get(url, timeout=egress.timeout)
                    if resp.status_code != 200:
                        continue
                    tile = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    canvas.paste(tile, (i * TILE_SIZE, j * TILE_SIZE))
                except Exception:
                    continue

    left = (cols * TILE_SIZE - width) // 2
    top = (rows * TILE_SIZE - height) // 2
    cropped = canvas.crop((left, top, left + width, top + height))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()