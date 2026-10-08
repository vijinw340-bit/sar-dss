"""Server-side map tile relay.

Browsers load Leaflet tiles directly from public tile servers, leaking the
operator's IP. Pointing the frontend at these routes instead anonymizes *every*
tile request by relaying it through the server's VPN/proxy egress (netroute.py).

``relay`` mode routes tiles through an image CDN relay (``OUTBOUND_IMAGE_RELAY_URL``,
e.g. https://wsrv.nl) so the anonymous third party fetches from public tile
servers (Esri basemaps) - passing policy filters that block proxy services.
"""
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.config import settings
from app.services.netroute import _wrap_relay_url, egress

router = APIRouter(prefix="/tiles", tags=["Tiles"])

_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/{svc}/MapServer/tile/{z}/{y}/{x}"

# provider -> upstream URL template (Leaflet {s}/{z}/{x}/{y}/{r} tokens)
# All point at Esri basemaps because public tile servers (OSM family) block
# image-proxy bots, while server.arcgisonline.com relays cleanly.
TILE_PROVIDERS = {
    "streets": _ESRI.replace("{svc}", "World_Street_Map"),
    "terrain": _ESRI.replace("{svc}", "World_Topo_Map"),
    "dark": _ESRI.replace("{svc}", "World_Street_Map"),
    "satellite": _ESRI.replace("{svc}", "World_Imagery"),
}

# wsrv transform params that restyle the "dark" provider (greyscale + dimmed).
DARK_FILTER = "&filt=greyscale&bri=-40"

MAX_ZOOM = 19
MAX_TILE = 40_000  # tile indices past this are almost certainly abuse (GeoJSON overlap)


@router.get("/{provider}/{z}/{x}/{y}.png")
async def tile(
    provider: str,
    z: int,
    x: int,
    y: int,
    s: str = Query(default="a", pattern="^[a-c]$"),
    r: str = Query(default="", pattern="^(@2x)?$"),
):
    """Fetch a tile from the upstream provider through an anonymized egress."""
    template = TILE_PROVIDERS.get(provider)
    if template is None:
        raise HTTPException(status_code=404, detail="Unknown tile provider")
    if not (0 <= z <= MAX_ZOOM) or x < 0 or y < 0 or x > MAX_TILE or y > MAX_TILE:
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    url = template.format(s=s, z=z, x=x, y=y, r=r)
    headers = {
        "User-Agent": "SAR-DSS/1.0 private tile relay",
        "Accept": "image/png,*/*;q=0.8",
    }
    try:
        if egress.mode == "relay" and egress.image_relay_url:
            # direct to the image relay so we can append per-provider transforms
            relay_url = _wrap_relay_url(
                egress.image_relay_url, url, settings.OUTBOUND_IMAGE_RELAY_FORMAT
            )
            if provider == "dark":
                relay_url += DARK_FILTER
            async with httpx.AsyncClient(verify=False, timeout=egress.timeout, follow_redirects=True) as client:
                resp = await client.get(relay_url, headers=headers)
        else:
            async with egress.async_session() as client:
                resp = await client.get(url, headers=headers, timeout=egress.timeout)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream tile error: HTTP {resp.status_code}")
        return Response(
            content=resp.content,
            media_type=resp.headers.get("content-type", "image/png"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tile relay unavailable: {exc}") from exc