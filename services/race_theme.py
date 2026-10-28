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


def is_paris_sx_race(competition: Any) -> bool:
    """True for Paris Supercross weekend competitions (lördag/söndag)."""
    if competition is None:
        return False
    series = (getattr(competition, "series", None) or "").strip().upper()
    if series == "PARIS":
        return True
    try:
        from paris_fantasy import paris_is_weekend_comp

        return bool(paris_is_weekend_comp(competition))
    except Exception:
        name = (getattr(competition, "name", None) or "").strip().lower()
        return "paris supercross" in name or name.startswith("paris")


def paris_theme_meta(competition: Any) -> dict[str, Any]:
    """Copy for Paris SX race-picks hero (Eiffel / night theme)."""
    name, date_short, date_long = _race_theme_dates(competition)
    year = _competition_year(competition)
    phase = (getattr(competition, "phase", None) or "").strip().lower()
    name_l = name.lower()
    is_saturday = phase == "paris_sat" or "lördag" in name_l or "saturday" in name_l
    is_sunday = phase == "paris_sun" or "söndag" in name_l or "sunday" in name_l
    if is_sunday:
        evening_sv = "Söndag"
        evening_en = "Sunday"
        evening_tag = "NIGHT 2"
    else:
        evening_sv = "Lördag"
        evening_en = "Saturday"
        evening_tag = "NIGHT 1"
        is_saturday = True
    return {
        "city": "PARIS",
        "title": name or "Paris Supercross",
        "year": year,
        "date_short": date_short,
        "date_long": date_long,
        "is_saturday": is_saturday,
        "is_sunday": is_sunday,
        "evening_sv": evening_sv,
        "evening_en": evening_en,
        "evening_tag": evening_tag,
        "motto": "VILLE LUMIÈRE · SUPERCROSS",
        "venue": "Plenitude Arena",
        "venue_short": "Plenitude Arena",
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


def sx_format_kind(competition: Any) -> str | None:
    """
    SX race-picks hero variant (after Military / St. Jude specials).
    Returns: triple_showdown, showdown, triple_crown, coast_west, coast_east, or None.
    """
    series = (getattr(competition, "series", None) or "").strip().upper()
    if series != "SX":
        return None
    if is_military_appreciation_race(competition) or is_st_jude_love_moto_race(competition):
        return None
    marks = race_card_marks(competition)
    coast = (
        (getattr(competition, "coast_250", None) or "").strip().lower()
    )
    race = _sx_calendar_race(competition)
    if race:
        coast = (race.get("coast_250") or coast or "").strip().lower()
    if marks.get("triple_crown") and marks.get("showdown"):
        return "triple_showdown"
    if marks.get("showdown"):
        return "showdown"
    if marks.get("triple_crown"):
        return "triple_crown"
    if coast == "west":
        return "coast_west"
    if coast == "east":
        return "coast_east"
    return None


SX_EAST_WEST_SHOWDOWN_BADGE = "images/sx_east_west_showdown_badge.png"


def is_sx_east_west_showdown(competition: Any) -> bool:
    """True for SX rounds where 250 East and West both race (incl. St. Jude Glendale)."""
    series = (getattr(competition, "series", None) or "").strip().upper()
    if series != "SX":
        return False
    return bool(race_card_marks(competition).get("showdown"))


# Full composite hero (no HTML overlay) — image contains all typography.
_SX_PICKS_HERO_IMAGES: dict[str, str] = {
    "Anaheim 2": "images/sx_tc_anaheim2_hero.jpg",
}

# Background only — UI text/badges rendered in sx_format_stage.html.
_SX_PICKS_HERO_BACKGROUNDS: dict[str, tuple[str, int, int]] = {
    # path, width, height (for aspect-ratio box — full image visible, no crop)
    "Arlington": ("images/sx_tc_arlington_bg.jpg", 1024, 369),
}

# Art behind the format plaque (copy + badges on top; composed = city/crowns in the image).
_SX_PICKS_HERO_PLAQUE_BACKGROUNDS: dict[str, tuple[str, int, int, bool]] = {
    "Foxborough": ("images/sx_tc_foxborough_hero.jpg", 1024, 369, True),
}

_SX_PICKS_HERO_IMAGE_ASPECT: dict[str, tuple[int, int]] = {
    "Anaheim 2": (1024, 397),
}


def sx_format_hero_image(competition: Any) -> str | None:
    """Static path for full composite race-picks hero."""
    name = (getattr(competition, "name") or "").strip()
    return _SX_PICKS_HERO_IMAGES.get(name)


def sx_format_hero_background(competition: Any) -> str | None:
    """Static path for background plate; copy and badges come from templates."""
    name = (getattr(competition, "name") or "").strip()
    entry = _SX_PICKS_HERO_BACKGROUNDS.get(name)
    if not entry:
        return None
    return entry[0]


def sx_format_theme_meta(competition: Any) -> dict[str, Any]:
    """Labels for SX format heroes (Triple Crown, Showdown, coast)."""
    meta = _race_theme_base(competition)
    kind = sx_format_kind(competition)
    meta["format"] = kind
    venue = meta.get("venue") or ""
    if venue and "," in venue:
        meta["venue_short"] = venue.split(",")[0].strip()
    else:
        meta["venue_short"] = venue
    hero = sx_format_hero_image(competition)
    if hero:
        meta["hero_image"] = hero
    bg_entry = _SX_PICKS_HERO_BACKGROUNDS.get(
        (getattr(competition, "name") or "").strip()
    )
    if bg_entry and not hero:
        path, aw, ah = bg_entry
        meta["hero_background"] = path
        meta["hero_aspect_w"] = aw
        meta["hero_aspect_h"] = ah
    plaque_entry = _SX_PICKS_HERO_PLAQUE_BACKGROUNDS.get(
        (getattr(competition, "name") or "").strip()
    )
    if plaque_entry and not hero and not bg_entry:
        path, aw, ah, composed = plaque_entry
        meta["hero_plaque_background"] = path
        meta["hero_plaque_composed"] = composed
        meta["hero_aspect_w"] = aw
        meta["hero_aspect_h"] = ah
    aspect = _SX_PICKS_HERO_IMAGE_ASPECT.get(
        (getattr(competition, "name") or "").strip()
    )
    if aspect and hero:
        meta["hero_aspect_w"], meta["hero_aspect_h"] = aspect
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
