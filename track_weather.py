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


_LOW_PRECIP_THRESHOLD = 20


def _adjust_for_low_precip(forecast: dict[str, Any]) -> dict[str, Any]:
    """Don't show rain/snow/storm when precipitation chance is very low."""
    precip = forecast.get("precipitation_probability")
    if precip is None or precip >= _LOW_PRECIP_THRESHOLD:
        return forecast
    out = dict(forecast)
    if out.get("icon") not in ("rain", "snow", "storm"):
        return out
    code = int(out.get("weather_code") or 0)
    if code in (0, 1, 2):
        out["icon"], out["label_sv"] = "partly", "Delvis molnigt"
    elif code == 3:
        out["icon"], out["label_sv"] = "cloud", "Mulet"
    elif code in (45, 48):
        out["icon"], out["label_sv"] = "fog", "Dimma"
    else:
        out["icon"], out["label_sv"] = "cloud", "Mulet"
    return out


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
    if precip is not None and precip >= _LOW_PRECIP_THRESHOLD:
        parts.append(f"{precip}% risk för nederbörd")
    elif precip is not None and precip > 0:
        parts.append(f"Låg risk för regn ({precip}%)")
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


_ICON_EMOJI = {
    "sun": "☀️",
    "partly": "⛅",
    "cloud": "☁️",
    "fog": "🌫️",
    "rain": "🌧️",
    "snow": "❄️",
    "storm": "⛈️",
}


def weather_icon_emoji(icon: str | None) -> str:
    return _ICON_EMOJI.get(icon or "", "🌤️")


def build_picks_weather_tips(
    weather: dict[str, Any] | None,
    *,
    series: str | None = None,
) -> list[str]:
    """Fantasy-oriented tips from race-day weather (strongest for outdoor MX)."""
    if not weather or not weather.get("available"):
        return []

    series_u = (series or "").upper()
    is_outdoor = series_u in ("MX", "WSX") or series_u == ""
    # SX is stadium — weather barely changes track; still show mild context for MX focus
    if series_u == "SX":
        return []

    tips: list[str] = []
    precip = weather.get("precipitation_probability")
    precip_i = int(precip) if precip is not None else None
    temp_max = weather.get("temp_max_c")
    temp_min = weather.get("temp_min_c")
    wind = weather.get("wind_kmh")
    icon = (weather.get("icon") or "").lower()
    label = weather.get("label_sv") or ""

    # --- Rain / mud ---
    if icon in ("rain", "storm") or (precip_i is not None and precip_i >= 55):
        tips.append(
            "Mud-/fukt-läge: prioritera förare som brukar klara slemmigt underlag — ren toppspeed väger mindre."
        )
        tips.append(
            "Start & holeshot blir ännu viktigare när sikt och grepp försämras."
        )
        tips.append(
            "Favoriter kan tappa — en wildcard på en ‘dirt rider’ kan skilja dig från fältet."
        )
    elif precip_i is not None and precip_i >= _LOW_PRECIP_THRESHOLD:
        tips.append(
            f"Regnrisk ~{precip_i}%: banan kan bli fuktig — ha en plan B om underlaget blir slemmigt."
        )
        tips.append(
            "Kolla vilka som gått bra i blött tidigare; form på torrt sand/hårdpack säger mindre."
        )

    # --- Heat / hard pack ---
    if temp_max is not None and temp_max >= 30 and (precip_i is None or precip_i < 30):
        tips.append(
            "Hett & torrt → ofta hårdare underlag: startrit och holeshot väger tungt."
        )
        tips.append(
            "Uthållighet i värme kan avgöra senare moto — undvik rena ‘sprinters’ i wildcard om racet är långt."
        )

    # --- Cold ---
    if temp_max is not None and temp_max <= 12:
        tips.append(
            "Kallt underlag: grepp och tidiga varv kan överraska — kolla vem som startar bra i kyla."
        )

    # --- Wind / dust ---
    if wind is not None and wind >= 40:
        tips.append(
            f"Blåsigt (~{wind} km/h): damm/sikt kan störa — stabila, konsekventa förare framför högrisk-outsiders."
        )
    elif wind is not None and wind >= 28 and icon in ("sun", "partly", "cloud"):
        tips.append(
            "Lite blåsigt: damm kan öka på torra banor — tidig position i fältet hjälper."
        )

    # --- Fog ---
    if icon == "fog":
        tips.append(
            "Dimma/sikt: tidig placering och lugn körning tidigt i race kan belönas mer än vanligt."
        )

    # --- Classic clear outdoor ---
    if (
        not tips
        and is_outdoor
        and icon in ("sun", "partly", "cloud")
        and (precip_i is None or precip_i < _LOW_PRECIP_THRESHOLD)
    ):
        tips.append(
            "Klassiskt outdoor-väder: banpreferens (sand/lera/hårdpack) och senaste form väger tungt."
        )
        tips.append(
            "Ingen extremväder-joker — lita mer på seriesform och banhistorik än på väderkaos."
        )

    # Cap to 3 tips so Bra att veta stays scannable
    return tips[:3]


def _resolve_weather_timezone(geo: dict[str, Any], comp) -> str:
    """Track-local timezone for Open-Meteo daily grids (not user display timezone)."""
    if geo.get("timezone"):
        return str(geo["timezone"])
    lon = float(geo.get("lon") or 0)
    lat = float(geo.get("lat") or 0)
    # Continental US — rough zones from longitude
    if -125 <= lon <= -66 and 24 <= lat <= 50:
        if lon >= -90:
            return "America/New_York"
        if lon >= -105:
            return "America/Chicago"
        return "America/Denver"
    comp_tz = (getattr(comp, "timezone", None) or "").strip()
    if comp_tz:
        return comp_tz
    return "America/New_York"


def get_weather_for_competition(comp) -> dict[str, Any]:
    """Cached race-day weather for a Competition ORM object."""
    unavailable = {"available": False}
    if comp is None or not getattr(comp, "event_date", None):
        return unavailable
    geo = resolve_track_geo(getattr(comp, "name", "") or "")
    if not geo:
        return unavailable
    tz = _resolve_weather_timezone(geo, comp)
    cache_key = f"{comp.id}:{comp.event_date}:{tz}"
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
        forecast = _adjust_for_low_precip(forecast)
        payload = build_weather_payload(forecast, geo["city"], comp.event_date)
        _WEATHER_CACHE[cache_key] = (now + _CACHE_TTL_SEC, payload)
        return payload
    except Exception as e:
        print(f"track_weather: fetch failed for {comp.name}: {e}")
        return unavailable
