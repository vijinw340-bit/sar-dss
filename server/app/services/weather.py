"""Live weather integration (Open-Meteo, no API key required).

Returns current conditions and a short hourly forecast for a coordinate.
Wind speeds are converted from km/h to knots for aviation use.

Outbound requests exit via the configured VPN/proxy egress (see netroute.py).
"""
from typing import Optional

from app.services.netroute import egress

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
KMH_TO_KTS = 0.539957


async def fetch_weather(latitude: float, longitude: float) -> dict:
    """Fetch current + forecast weather from Open-Meteo."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,weather_code,surface_pressure,wind_speed_10m,"
            "wind_direction_10m,visibility"
        ),
        "hourly": "temperature_2m,precipitation,wind_speed_10m,visibility",
        "forecast_days": 1,
        "timezone": "auto",
    }
    async with egress.async_session() as client:
        resp = await client.get(
            OPENMETEO_URL,
            params=params,
            headers={"X-Return-Format": "text"},  # Jina-style relays return raw JSON
        )
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    conditions = weather_code_to_text(current.get("weather_code"))
    visibility_km = current.get("visibility")
    if visibility_km == 0 or visibility_km is None:
        # Visibility often missing; approximate from conditions
        visibility_km = 24.0 if conditions == "Clear" else 6.0

    forecast = []
    times = hourly.get("time", []) or []
    temps = hourly.get("temperature_2m", []) or []
    preci = hourly.get("precipitation", []) or []
    winds = hourly.get("wind_speed_10m", []) or []
    for i in range(min(6, len(times))):
        forecast.append({
            "time": times[i],
            "temperature_c": round(temps[i], 1) if i < len(temps) else None,
            "precipitation_mm": round(preci[i], 2) if i < len(preci) else 0.0,
            "wind_speed_kts": round((winds[i] or 0.0) * KMH_TO_KTS, 1) if i < len(winds) else 0.0,
        })

    return {
        "temperature_c": round(current.get("temperature_2m", 0.0), 1),
        "apparent_temperature_c": round(current.get("apparent_temperature", 0.0), 1),
        "humidity": round(current.get("relative_humidity_2m", 0.0), 0),
        "precipitation_mm": round(current.get("precipitation", 0.0), 2),
        "wind_speed_kts": round((current.get("wind_speed_10m") or 0.0) * KMH_TO_KTS, 1),
        "wind_direction_deg": round(current.get("wind_direction_10m", 0.0), 0),
        "pressure_hpa": round(current.get("surface_pressure", 0.0), 1),
        "visibility_km": round(visibility_km, 1),
        "conditions": conditions,
        "weather_code": current.get("weather_code"),
        "source": "openmeteo",
        "forecast": forecast,
    }


def weather_code_to_text(code: Optional[int]) -> str:
    """Map WMO weather codes to human-readable conditions."""
    if code is None:
        return "Clear"
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly Cloudy"
    if code == 3:
        return "Overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67):
        return "Rain"
    if code in (71, 73, 75, 77):
        return "Snow"
    if code in (80, 81, 82):
        return "Rain Showers"
    if code in (85, 86):
        return "Snow Showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"


async def snapshot_weather(latitude: float, longitude: float) -> dict:
    """Return a weather snapshot suitable for persistence (no forecast)."""
    try:
        data = await fetch_weather(latitude, longitude)
    except Exception:
        data = {
            "temperature_c": None, "apparent_temperature_c": None, "humidity": None,
            "precipitation_mm": None, "wind_speed_kts": None, "wind_direction_deg": None,
            "pressure_hpa": None, "visibility_km": None, "conditions": "Unknown",
            "weather_code": None, "source": "openmeteo", "forecast": [],
        }
    data.pop("forecast", None)
    data.pop("apparent_temperature_c", None)
    data.pop("weather_code", None)
    return data
