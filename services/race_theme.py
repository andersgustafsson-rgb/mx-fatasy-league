"""Special visual themes for race picks (Military Appreciation, etc.)."""
from __future__ import annotations

from typing import Any

# Official MAD weekends by (year, series, competition name).
MILITARY_APPRECIATION_RACES = frozenset(
    {
        (2027, "SX", "Seattle"),
    }
)

# St. Jude / Love Moto Stop Cancer (AMA SX Glendale).
ST_JUDE_LOVE_MOTO_RACES = frozenset(
    {
        (2027, "SX", "Glendale"),
    }
)

_MONTHS_EN = (
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
)
_MONTHS_EN_SHORT = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)
_COAST_LABEL = {
    "west": "250SX West",
    "east": "250SX East",
    "showdown": "East/West Showdown",
    "both": "250SX both coasts",
}


def _competition_year(competition: Any) -> int | None:
    ed = getattr(competition, "event_date", None)
    if ed is not None and getattr(ed, "year", None):
        return int(ed.year)
    series = getattr(competition, "series_ref", None)
    year = getattr(series, "year", None) if series is not None else None
    return int(year) if year else None


def _sx_calendar_race(competition: Any) -> dict[str, Any] | None:
    series = (getattr(competition, "series", None) or "").strip().upper()
    year = _competition_year(competition)
    name = (getattr(competition, "name", None) or "").strip()
    if series != "SX" or not year or int(year) < 2027:
        return None
    try:
        from ama_2027_calendar import get_sx_2027_race_info

        return get_sx_2027_race_info(name)
    except Exception:
        return None


def is_military_appreciation_race(competition: Any) -> bool:
    """True for AMA SX Military Appreciation Day weekends."""
    if competition is None:
        return False
    name = (getattr(competition, "name", None) or "").strip()
    if "military appreciation" in name.lower():
        return True

    series = (getattr(competition, "series", None) or "").strip().upper()
    year = _competition_year(competition)
    if year and series and (year, series, name) in MILITARY_APPRECIATION_RACES:
        return True

    race = _sx_calendar_race(competition)
    return bool(race and race.get("is_military_appreciation"))


def _race_theme_dates(competition: Any) -> tuple[str, str, str]:
    name = (getattr(competition, "name", None) or "").strip()
    ed = getattr(competition, "event_date", None)
    date_short = ""
    date_long = ""
    if ed is not None and getattr(ed, "month", None):
        month_i = int(ed.month) - 1
        date_short = f"{int(ed.day)} {_MONTHS_EN_SHORT[month_i]} {int(ed.year)}"
        date_long = f"{int(ed.day)} {_MONTHS_EN[month_i]} {int(ed.year)}"
    return name, date_short, date_long


def _race_theme_base(competition: Any) -> dict[str, Any]:
    name, date_short, date_long = _race_theme_dates(competition)
    year = _competition_year(competition)
    coast = (getattr(competition, "coast_250", None) or "").strip().lower()
    round_n = None
    venue = ""
    race = _sx_calendar_race(competition)
    if race:
        round_n = race.get("round")
        venue = race.get("venue") or ""
        coast = (race.get("coast_250") or coast or "").strip().lower()
    return {
        "city": name.upper(),
        "year": year,
        "round": round_n,
        "coast": coast,
        "coast_label": _COAST_LABEL.get(coast, ""),
        "venue": venue,
        "date_short": date_short,
        "date_long": date_long,
    }


def is_st_jude_love_moto_race(competition: Any) -> bool:
    """True for AMA SX St. Jude / Love Moto Stop Cancer weekends (Glendale)."""
    if competition is None:
        return False
    name = (getattr(competition, "name", None) or "").strip()
    if "st. jude" in name.lower() or "love moto" in name.lower():
        return True
    series = (getattr(competition, "series", None) or "").strip().upper()
    year = _competition_year(competition)
    if year and series and (year, series, name) in ST_JUDE_LOVE_MOTO_RACES:
        return True
    race = _sx_calendar_race(competition)
    return bool(race and race.get("is_st_jude_love_moto"))


def military_theme_meta(competition: Any) -> dict[str, Any]:
    """Copy + round/coast labels for the Military Appreciation Day hero."""
    meta = _race_theme_base(competition)
    meta["motto"] = "HONOR · COURAGE"
    return meta


def st_jude_theme_meta(competition: Any) -> dict[str, Any]:
    """Copy + labels for St. Jude Love Moto hero."""
    meta = _race_theme_base(competition)
    meta["motto"] = "LOVE MOTO · STOP CANCER"
    venue = meta.get("venue") or ""
    if venue and "," in venue:
        meta["venue_short"] = venue.split(",")[0].strip()
    else:
        meta["venue_short"] = venue
    return meta


def race_card_marks(competition: Any) -> dict[str, bool]:
    """Icons for series schedule cards: Triple Crown, East/West, Military Appreciation."""
    series = (getattr(competition, "series", None) or "").strip().upper()
    if series != "SX":
        return {"triple_crown": False, "showdown": False, "military": False, "st_jude": False}
    race = _sx_calendar_race(competition)
    coast = (
        (race.get("coast_250") if race else None)
        or getattr(competition, "coast_250", None)
        or ""
    )
    coast = str(coast).strip().lower()
    triple = bool(race.get("is_triple_crown")) if race else False
    if not triple:
        triple = bool(getattr(competition, "is_triple_crown", False))
    return {
        "triple_crown": triple,
        "showdown": coast in ("showdown", "both"),
        "military": is_military_appreciation_race(competition),
        "st_jude": is_st_jude_love_moto_race(competition),
    }
