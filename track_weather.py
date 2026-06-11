"""Race-day weather via Open-Meteo (free, no API key)."""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Optional

import requests

# lat, lon, city label, optional timezone override
TRACK_GEO: dict[str, dict[str, Any]] = {
    # Supercross
    "Anaheim 1": {"lat": 33.8366, "lon": -117.9143, "city": "Anaheim, CA"},
    "Anaheim 2": {"lat": 33.8366, "lon": -117.9143, "city": "Anaheim, CA"},
    "San Diego": {"lat": 32.7157, "lon": -117.1611, "city": "San Diego, CA"},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "city": "San Francisco, CA"},
    "Seattle": {"lat": 47.6062, "lon": -122.3321, "city": "Seattle, WA"},
    "Denver": {"lat": 39.7392, "lon": -104.9903, "city": "Denver, CO"},
    "Salt Lake City": {"lat": 40.7608, "lon": -111.8910, "city": "Salt Lake City, UT"},
    "Glendale": {"lat": 33.5387, "lon": -112.1860, "city": "Glendale, AZ"},
    "Houston": {"lat": 29.7604, "lon": -95.3698, "city": "Houston, TX"},
    "Arlington": {"lat": 32.7357, "lon": -97.1081, "city": "Arlington, TX"},
    "St. Louis": {"lat": 38.6270, "lon": -90.1994, "city": "St. Louis, MO"},
    "Nashville": {"lat": 36.1627, "lon": -86.7816, "city": "Nashville, TN"},
    "Birmingham": {"lat": 33.5207, "lon": -86.8025, "city": "Birmingham, AL"},
    "Daytona": {"lat": 29.2108, "lon": -81.0228, "city": "Daytona Beach, FL"},
    "Tampa": {"lat": 27.9506, "lon": -82.4572, "city": "Tampa, FL"},
    "Indianapolis": {"lat": 39.7684, "lon": -86.1581, "city": "Indianapolis, IN"},
    "Detroit": {"lat": 42.3314, "lon": -83.0458, "city": "Detroit, MI"},
    "Cleveland": {"lat": 41.4993, "lon": -81.6944, "city": "Cleveland, OH"},
    "Philadelphia": {"lat": 39.9526, "lon": -75.1652, "city": "Philadelphia, PA"},
    "East Rutherford": {"lat": 40.8128, "lon": -74.0742, "city": "East Rutherford, NJ"},
    "Foxborough": {"lat": 42.0909, "lon": -71.2643, "city": "Foxborough, MA"},
    "Minneapolis": {"lat": 44.9778, "lon": -93.2650, "city": "Minneapolis, MN"},
    "Atlanta": {"lat": 33.7490, "lon": -84.3880, "city": "Atlanta, GA"},
    "Las Vegas": {"lat": 36.1699, "lon": -115.1398, "city": "Las Vegas, NV"},
    # Pro Motocross
    "Fox Raceway National": {"lat": 33.3653, "lon": -117.2290, "city": "Pala, CA"},
    "Hangtown Classic": {"lat": 38.5816, "lon": -121.4944, "city": "Sacramento, CA"},
    "Thunder Valley National": {"lat": 39.7392, "lon": -105.1781, "city": "Lakewood, CO"},
    "High Point National": {"lat": 40.7859, "lon": -80.1442, "city": "Mt. Morris, PA"},
    "RedBud National": {"lat": 41.8273, "lon": -86.3611, "city": "Buchanan, MI"},
    "Southwick National": {"lat": 42.0548, "lon": -72.7704, "city": "Southwick, MA"},
    "Spring Creek National": {"lat": 44.2911, "lon": -94.4611, "city": "Millville, MN"},
    "Washougal National": {"lat": 45.5826, "lon": -122.3534, "city": "Washougal, WA"},
    "Unadilla National": {"lat": 42.6251, "lon": -75.3324, "city": "New Berlin, NY"},
    "Budds Creek National": {"lat": 38.4432, "lon": -76.7439, "city": "Mechanicsville, MD"},
    "Ironman National": {"lat": 40.0417, "lon": -86.8745, "city": "Crawfordsville, IN"},
    # WSX
    "Buenos Aires City GP": {"lat": -34.6037, "lon": -58.3816, "city": "Buenos Aires"},
    "Canadian GP": {"lat": 49.2827, "lon": -123.1207, "city": "Vancouver"},
    "Australian GP": {"lat": -28.0167, "lon": 153.4000, "city": "Gold Coast"},
    "Swedish GP": {"lat": 59.3293, "lon": 18.0686, "city": "Stockholm"},
    "South African GP": {"lat": -33.9249, "lon": 18.4241, "city": "Cape Town"},
}

_WEATHER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SEC = 45 * 60


def _normalize_track_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def resolve_track_geo(track_name: str) -> Optional[dict[str, Any]]:
    """Map competition name to coordinates and city label."""
    name = (track_name or "").strip()
    if not name:
        return None
    if name in TRACK_GEO:
        return dict(TRACK_GEO[name])
    slug = _normalize_track_key(name)
    for key, geo in TRACK_GEO.items():
        key_slug = _normalize_track_key(key)
        if slug == key_slug or slug in key_slug or key_slug in slug:
            return dict(geo)
    base = name.lower().replace(" national", "").replace(" classic", "").strip()
    for key, geo in TRACK_GEO.items():
        key_base = key.lower().replace(" national", "").replace(" classic", "").strip()
        if base == key_base or base in key_base or key_base in base:
            return dict(geo)
    return None


def wmo_to_display(code: int) -> tuple[str, str]:
    """WMO weather code -> (icon_key, Swedish label)."""
    if code == 0:
        return "sun", "Klart"
    if code in (1, 2):
        return "partly", "Delvis molnigt"
    if code == 3:
        return "cloud", "Mulet"
    if code in (45, 48):
        return "fog", "Dimma"
    if code in (51, 53, 55, 56, 57):
        return "rain", "Duggregn"
    if code in (61, 63, 65, 66, 67):
        return "rain", "Regn"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow", "Snö"
    if code in (80, 81, 82):
        return "rain", "Skurar"
    if code in (95, 96, 99):
        return "storm", "Åska"
    return "partly", "Varierande"


def fetch_race_day_forecast(
    lat: float,
    lon: float,
    event_date: date,
    timezone: str,
) -> Optional[dict[str, Any]]:
    """Daily forecast for a single race date from Open-Meteo."""
    date_str = event_date.isoformat()
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,wind_speed_10m_max"
            ),
            "timezone": timezone,
            "start_date": date_str,
            "end_date": date_str,
        },
        timeout=8,
    )
    resp.raise_for_status()
    daily = (resp.json() or {}).get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return None
    idx = 0
    for i, t in enumerate(times):
        if t == date_str:
            idx = i
            break
    code = int((daily.get("weather_code") or [0])[idx])
    icon, label_sv = wmo_to_display(code)
    temp_max = (daily.get("temperature_2m_max") or [None])[idx]
    temp_min = (daily.get("temperature_2m_min") or [None])[idx]
    precip = (daily.get("precipitation_probability_max") or [None])[idx]
    wind = (daily.get("wind_speed_10m_max") or [None])[idx]
    return {
        "weather_code": code,
        "icon": icon,
        "label_sv": label_sv,
        "temp_max_c": round(temp_max) if temp_max is not None else None,
        "temp_min_c": round(temp_min) if temp_min is not None else None,
        "precipitation_probability": int(precip) if precip is not None else None,
        "wind_kmh": round(wind) if wind is not None else None,
    }


def build_weather_payload(
    forecast: dict[str, Any],
    city: str,
    event_date: date,
) -> dict[str, Any]:
    """Client-facing weather object for race day."""
    temp_max = forecast.get("temp_max_c")
    temp_min = forecast.get("temp_min_c")
    label = forecast.get("label_sv") or ""
    precip = forecast.get("precipitation_probability")
    parts = [f"Race day · {city}"]
    if temp_max is not None:
        if temp_min is not None and temp_min != temp_max:
            parts.append(f"{temp_min}–{temp_max}°C")
        else:
            parts.append(f"{temp_max}°C")
    parts.append(label)
    if precip is not None and precip > 0:
        parts.append(f"{precip}% regn")
    return {
        "available": True,
        "city": city,
        "event_date": event_date.isoformat(),
        "icon": forecast.get("icon") or "partly",
        "label_sv": label,
        "temp_max_c": temp_max,
        "temp_min_c": temp_min,
        "precipitation_probability": precip,
        "wind_kmh": forecast.get("wind_kmh"),
        "summary_sv": " · ".join(parts),
    }


def get_weather_for_competition(comp) -> dict[str, Any]:
    """Cached race-day weather for a Competition ORM object."""
    unavailable = {"available": False}
    if comp is None or not getattr(comp, "event_date", None):
        return unavailable
    geo = resolve_track_geo(getattr(comp, "name", "") or "")
    if not geo:
        return unavailable
    tz = (
        getattr(comp, "timezone", None)
        or geo.get("timezone")
        or "America/New_York"
    )
    cache_key = f"{comp.id}:{comp.event_date}"
    now = time.time()
    cached = _WEATHER_CACHE.get(cache_key)
    if cached and now < cached[0]:
        return cached[1]
    try:
        forecast = fetch_race_day_forecast(
            geo["lat"],
            geo["lon"],
            comp.event_date,
            tz,
        )
        if not forecast:
            return unavailable
        payload = build_weather_payload(forecast, geo["city"], comp.event_date)
        _WEATHER_CACHE[cache_key] = (now + _CACHE_TTL_SEC, payload)
        return payload
    except Exception as e:
        print(f"track_weather: fetch failed for {comp.name}: {e}")
        return unavailable
