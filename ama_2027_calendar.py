"""Official AMA / SMX 2027 calendar (released calendar graphic).

Upserts Series + competitions for year=2027 without touching 2026 rows
(match on series_id + name).
"""
from __future__ import annotations

from datetime import date, datetime, time as dt_time
from typing import Any, Callable

# Supercross 2027 — stadium calendar (coast_250 best-effort until East/West published)
SX_2027: list[dict[str, Any]] = [
    {
        "name": "Anaheim 1",
        "date": "2027-01-09",
        "round": 1,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "Angel Stadium, Anaheim, CA",
        "timezone_label": "PT",
        "blurb": "Säsongsöppnare i Angel Stadium — SX:s klassiska startarena i södra Kalifornien. 250 West kör här.",
        "highlights": ["Säsongsöppnare", "250 West", "Klassisk SX-arena"],
    },
    {
        "name": "San Diego",
        "date": "2027-01-16",
        "round": 2,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "Snapdragon Stadium, San Diego, CA",
        "timezone_label": "PT",
        "blurb": "Runda 2 i Snapdragon Stadium (ca 35 000 platser), hemmaarena för SDSU Aztecs. San Diego har kört SX sedan 1980; Snapdragon tog över 2023.",
        "highlights": ["250 West", "Snapdragon Stadium", "Early-season West"],
    },
    {
        "name": "Anaheim 2",
        "date": "2027-01-23",
        "round": 3,
        "coast_250": "west",
        "is_triple_crown": True,
        "venue": "Angel Stadium, Anaheim, CA",
        "timezone_label": "PT",
        "blurb": "Andra Anaheim-besöket — Triple Crown (tre mains, poäng summeras). Ofta en av säsongens mest dramatiska kvällar.",
        "highlights": ["Triple Crown", "250 West", "Tre mains"],
    },
    {
        "name": "San Antonio",
        "date": "2027-01-30",
        "round": 4,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "Alamodome, San Antonio, TX",
        "timezone_label": "CT",
        "blurb": "Första SX-besöket någonsin i Alamodome. Ny Texas-arena på schemat efter många år med Houston/Arlington.",
        "highlights": ["Debut 2027", "Alamodome", "250 West"],
    },
    {
        "name": "Tampa",
        "date": "2027-02-06",
        "round": 5,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "Raymond James Stadium, Tampa, FL",
        "timezone_label": "ET",
        "blurb": "Återkomst till Raymond James Stadium (Buccaneers). Florida-runda där 250 East tar över efter West-starten.",
        "highlights": ["250 East", "Återkomst", "Raymond James"],
    },
    {
        "name": "Glendale",
        "date": "2027-02-13",
        "round": 6,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "State Farm Stadium, Glendale, AZ",
        "timezone_label": "MST",
        "blurb": "Arizona-runda i State Farm Stadium (Cardinals). Ökenvärme, högt tempo och klassisk West-stopp.",
        "highlights": ["250 West", "State Farm Stadium", "Arizona"],
    },
    {
        "name": "Detroit",
        "date": "2027-02-20",
        "round": 7,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "Ford Field, Detroit, MI",
        "timezone_label": "ET",
        "blurb": "Inomhus på Ford Field (Lions). Tidigarelagt 2027 — Midwestern-runda med typiskt tekniskt underlag.",
        "highlights": ["250 East", "Ford Field", "Inomhus"],
    },
    {
        "name": "Arlington",
        "date": "2027-02-27",
        "round": 8,
        "coast_250": "showdown",
        "is_triple_crown": False,
        "venue": "AT&T Stadium, Arlington, TX",
        "timezone_label": "CT",
        "blurb": "East/West Showdown i AT&T Stadium (Cowboys). Båda 250-coasts kör samma natt — extra kaos i tippat.",
        "highlights": ["East/West Showdown", "AT&T Stadium", "Båda coasts"],
    },
    {
        "name": "Daytona",
        "date": "2027-03-06",
        "round": 9,
        "coast_250": "east",
        "is_triple_crown": True,
        "venue": "Daytona International Speedway, Daytona Beach, FL",
        "timezone_label": "ET",
        "blurb": "Triple Crown på Daytona International Speedway — unikt underlag och layout. Banbild publiceras ofta senare än övriga rundor.",
        "highlights": ["Triple Crown", "Daytona Speedway", "250 East"],
    },
    {
        "name": "Indianapolis",
        "date": "2027-03-13",
        "round": 10,
        "coast_250": "showdown",
        "is_triple_crown": False,
        "venue": "Lucas Oil Stadium, Indianapolis, IN",
        "timezone_label": "ET",
        "blurb": "East/West Showdown i Lucas Oil Stadium. Inomhus, tät bana och ofta avgörande för 250-ställningen.",
        "highlights": ["East/West Showdown", "Lucas Oil Stadium", "Inomhus"],
    },
    {
        "name": "Seattle",
        "date": "2027-03-20",
        "round": 11,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "Lumen Field, Seattle, WA",
        "timezone_label": "PT",
        "blurb": "Lumen Field (Seahawks) — SX i Seattle sedan 1978 (Kingdome-eran). Flyttat senare i schemat 2027.",
        "highlights": ["250 West", "Lumen Field", "Historisk SX-marknad"],
    },
    {
        "name": "Foxborough",
        "date": "2027-04-03",
        "round": 12,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "Gillette Stadium, Foxborough, MA",
        "timezone_label": "ET",
        "blurb": "Återkomst till Gillette Stadium (Patriots). Start på den östkustsvängen i april.",
        "highlights": ["250 East", "Gillette Stadium", "Återkomst"],
    },
    {
        "name": "Baltimore",
        "date": "2027-04-10",
        "round": 13,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "M&T Bank Stadium, Baltimore, MD",
        "timezone_label": "ET",
        "blurb": "Första SX någonsin i Baltimore / M&T Bank Stadium (Ravens). Första stadium-SX i DMV på 44 år. FanFest + kval från ca 08:00 lokal tid.",
        "highlights": ["Debut 2027", "M&T Bank Stadium", "250 East"],
    },
    {
        "name": "East Rutherford",
        "date": "2027-04-17",
        "round": 14,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "MetLife Stadium, East Rutherford, NJ",
        "timezone_label": "ET",
        "blurb": "MetLife Stadium (Giants/Jets) i New York-metro. Storöstkust-publik och sen-säsongs intensitet.",
        "highlights": ["250 East", "MetLife Stadium", "NY/NJ"],
    },
    {
        "name": "Pittsburgh",
        "date": "2027-04-24",
        "round": 15,
        "coast_250": "east",
        "is_triple_crown": False,
        "venue": "Acrisure Stadium, Pittsburgh, PA",
        "timezone_label": "ET",
        "blurb": "Acrisure Stadium (Steelers) — modern comeback till Pittsburgh (tidigare Three Rivers 1978/1983).",
        "highlights": ["250 East", "Acrisure Stadium", "Pittsburgh-comeback"],
    },
    {
        "name": "Denver",
        "date": "2027-05-08",
        "round": 16,
        "coast_250": "showdown",
        "is_triple_crown": False,
        "venue": "Empower Field at Mile High, Denver, CO",
        "timezone_label": "MT",
        "blurb": "East/West Showdown på mile-high höjd i Empower Field. Tunn luft = motor/kondition blir extra viktigt.",
        "highlights": ["East/West Showdown", "Mile High", "Höjd ~1600 m"],
    },
    {
        "name": "Salt Lake City",
        "date": "2027-05-15",
        "round": 17,
        "coast_250": "west",
        "is_triple_crown": False,
        "venue": "Rice-Eccles Stadium, Salt Lake City, UT",
        "timezone_label": "MT",
        "blurb": "SX-finalen i Rice-Eccles Stadium. Titlar avgörs ofta här innan sommarens Pro Motocross tar vid.",
        "highlights": ["SX-final", "250 West", "Rice-Eccles"],
    },
]

# Short venue blurbs for Pro Motocross 2027 (shown on series schedule click-through)
MX_2027_INFO: dict[str, dict[str, Any]] = {
    "Fox Raceway National": {
        "blurb": "Memorial Day-öppnare i Pala, CA — sandig/hårdpackad bana som sätter tonen för outdoorsäsongen.",
        "highlights": ["MX-öppnare", "Pala, CA", "Memorial Day"],
    },
    "Hangtown Classic": {
        "blurb": "Klassisk Hangtown utanför Sacramento — en av de mest traditionsrika nationals.",
        "highlights": ["Hangtown", "Sacramento", "Classic"],
    },
    "Thunder Valley National": {
        "blurb": "Thunder Valley i Colorado — höjd, branta sektioner och ofta spektakulära whoops.",
        "highlights": ["Lakewood, CO", "Höjd", "Thunder Valley"],
    },
    "High Point National": {
        "blurb": "Father’s Day-weekend i Mount Morris, PA — klassisk East Coast-national.",
        "highlights": ["Father’s Day", "Mount Morris, PA"],
    },
    "RedBud National": {
        "blurb": "Independence Day på RedBud — en av MX:s mest ikoniska banor (LaRocco’s Leap m.m.).",
        "highlights": ["4th of July", "Buchanan, MI", "Ikonisk"],
    },
    "Southwick National": {
        "blurb": "Sandbanan i Southwick, MA — specialister på sand får ofta övertaget.",
        "highlights": ["Sand", "Southwick, MA"],
    },
    "Spring Creek National": {
        "blurb": "Spring Creek i Millville, MN — kuperad Midwestern-bana mitt i sommaren.",
        "highlights": ["Millville, MN", "Kuperat"],
    },
    "Washougal National": {
        "blurb": "Washougal i Washington — Pacific Northwest, tekniskt och ofta blött underlag.",
        "highlights": ["Washougal, WA", "PNW"],
    },
    "Unadilla National": {
        "blurb": "Unadilla i New Berlin, NY — en av de äldsta och mest respekterade nationals.",
        "highlights": ["Unadilla", "New Berlin, NY"],
    },
    "Budds Creek National": {
        "blurb": "Budds Creek i Maryland — sen-säsongs national innan Ironman.",
        "highlights": ["Mechanicsville, MD", "Budds Creek"],
    },
    "Ironman National": {
        "blurb": "MX-finalen på Ironman Raceway, Crawfordsville — sista poängen innan SMX-playoffs.",
        "highlights": ["MX-final", "Crawfordsville, IN"],
    },
}


def get_sx_2027_race_info(name: str) -> dict[str, Any] | None:
    key = (name or "").strip()
    for race in SX_2027:
        if race["name"] == key:
            return race
    return None


def competition_public_info(competition, series_year: int | None = None) -> dict[str, Any]:
    """Public blurbs/tags for series schedule click-through."""
    name = (getattr(competition, "name", None) or "").strip()
    year = series_year
    if year is None:
        ed = getattr(competition, "event_date", None)
        year = ed.year if ed is not None else None
    series = (getattr(competition, "series", None) or "").strip().upper()

    info: dict[str, Any] = {
        "blurb": "",
        "highlights": [],
        "round": None,
        "coast_label": "",
        "format_label": "",
        "timezone_label": "",
    }

    if series == "SX" and year and int(year) >= 2027:
        race = get_sx_2027_race_info(name)
        if race:
            coast = (race.get("coast_250") or "").lower()
            coast_label = {
                "west": "250 West",
                "east": "250 East",
                "showdown": "East/West Showdown",
                "both": "250 båda coasts",
            }.get(coast, "")
            fmt = "Triple Crown" if race.get("is_triple_crown") else "Standard (1 main)"
            info.update(
                {
                    "blurb": race.get("blurb") or "",
                    "highlights": list(race.get("highlights") or []),
                    "round": race.get("round"),
                    "coast_label": coast_label,
                    "format_label": fmt,
                    "timezone_label": race.get("timezone_label") or "",
                }
            )
            return info

    if series == "MX" and year and int(year) >= 2027:
        mx = MX_2027_INFO.get(name) or {}
        if mx:
            info["blurb"] = mx.get("blurb") or ""
            info["highlights"] = list(mx.get("highlights") or [])
            return info

    return info

MX_2027: list[dict[str, Any]] = [
    {"name": "Fox Raceway National", "date": "2027-05-29", "location": "Pala, CA"},
    {"name": "Hangtown Classic", "date": "2027-06-05", "location": "Sacramento, CA"},
    {"name": "Thunder Valley National", "date": "2027-06-12", "location": "Lakewood, CO"},
    {"name": "High Point National", "date": "2027-06-19", "location": "Mount Morris, PA"},
    {"name": "RedBud National", "date": "2027-07-03", "location": "Buchanan, MI"},
    {"name": "Southwick National", "date": "2027-07-10", "location": "Southwick, MA"},
    {"name": "Spring Creek National", "date": "2027-07-17", "location": "Millville, MN"},
    {"name": "Washougal National", "date": "2027-07-24", "location": "Washougal, WA"},
    {"name": "Unadilla National", "date": "2027-08-14", "location": "New Berlin, NY"},
    {"name": "Budds Creek National", "date": "2027-08-21", "location": "Mechanicsville, MD"},
    {"name": "Ironman National", "date": "2027-08-28", "location": "Crawfordsville, IN"},
]

# Venues TBD on the released graphic
SMX_2027: list[dict[str, Any]] = [
    {"name": "SMX Playoff 1", "date": "2027-09-11", "phase": "playoff1", "multiplier": 1.0},
    {"name": "SMX Playoff 2", "date": "2027-09-18", "phase": "playoff2", "multiplier": 2.0},
    {"name": "SMX Final", "date": "2027-09-25", "phase": "final", "multiplier": 3.0},
]

SMX_RACE_META_2027: dict[str, dict[str, Any]] = {
    "SMX Playoff 1": {
        "venue": "TBD",
        "city": "TBD",
        "timezone": "America/New_York",
        "start_time": (15, 0),
        "first_quali": (12, 50),
        "gate_label": "TBD",
    },
    "SMX Playoff 2": {
        "venue": "TBD",
        "city": "TBD",
        "timezone": "America/Los_Angeles",
        "start_time": (16, 0),
        "first_quali": (9, 50),
        "gate_label": "TBD",
    },
    "SMX Final": {
        "venue": "TBD",
        "city": "TBD",
        "timezone": "America/Chicago",
        "start_time": (18, 0),
        "first_quali": (12, 0),
        "gate_label": "TBD",
    },
}


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _ensure_series(Series, *, name: str, year: int, start: date, end: date) -> tuple[Any, bool]:
    rows = Series.query.filter_by(name=name, year=year).order_by(Series.id.asc()).all()
    created = False
    from models import db

    if not rows:
        row = Series(
            name=name,
            year=year,
            start_date=start,
            end_date=end,
            is_active=True,
            points_system="standard",
        )
        db.session.add(row)
        db.session.flush()
        created = True
        return row, created

    row = rows[0]
    row.start_date = start
    row.end_date = end
    row.is_active = True
    # Drop empty duplicate series rows created by double-init races
    for dup in rows[1:]:
        from models import Competition

        if Competition.query.filter_by(series_id=dup.id).count() == 0:
            db.session.delete(dup)
    return row, created


def ensure_ama_2027_calendar(
    *,
    get_timezone_for_track: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Create/update AMA SX + MX + SMX Finals for 2027. Idempotent."""
    from models import Competition, Series, db

    tz_fn = get_timezone_for_track or (lambda _n: "America/New_York")

    created_series: list[str] = []
    created_comps = 0
    updated_comps = 0

    sx_series, sx_new = _ensure_series(
        Series,
        name="Supercross",
        year=2027,
        start=_parse_date(SX_2027[0]["date"]),
        end=_parse_date(SX_2027[-1]["date"]),
    )
    if sx_new:
        created_series.append("Supercross 2027")

    mx_series, mx_new = _ensure_series(
        Series,
        name="Motocross",
        year=2027,
        start=_parse_date(MX_2027[0]["date"]),
        end=_parse_date(MX_2027[-1]["date"]),
    )
    if mx_new:
        created_series.append("Motocross 2027")

    smx_series, smx_new = _ensure_series(
        Series,
        name="SMX Finals",
        year=2027,
        start=_parse_date(SMX_2027[0]["date"]),
        end=_parse_date(SMX_2027[-1]["date"]),
    )
    if smx_new:
        created_series.append("SMX Finals 2027")

    def upsert_sx_mx(race: dict, *, series_row, series_code: str, coast: str | None) -> None:
        nonlocal created_comps, updated_comps
        target = _parse_date(race["date"])
        existing = Competition.query.filter_by(
            name=race["name"], series_id=series_row.id
        ).first()
        if not existing:
            # Avoid stealing a 2026 row that shares the short name
            existing = (
                Competition.query.filter(
                    Competition.name == race["name"],
                    Competition.series == series_code,
                    Competition.event_date >= date(2027, 1, 1),
                    Competition.event_date <= date(2027, 12, 31),
                ).first()
            )
        tz = tz_fn(race["name"])
        if existing:
            existing.series_id = series_row.id
            existing.series = series_code
            existing.event_date = target
            existing.phase = "regular"
            existing.point_multiplier = 1.0
            existing.timezone = tz
            if coast is not None:
                existing.coast_250 = coast
            if "is_triple_crown" in race:
                existing.is_triple_crown = 1 if race.get("is_triple_crown") else 0
            updated_comps += 1
            return
        db.session.add(
            Competition(
                name=race["name"],
                event_date=target,
                series=series_code,
                point_multiplier=1.0,
                is_triple_crown=1 if race.get("is_triple_crown") else 0,
                coast_250=coast,
                timezone=tz,
                series_id=series_row.id,
                phase="regular",
                is_qualifying=False,
            )
        )
        created_comps += 1

    for race in SX_2027:
        upsert_sx_mx(
            race,
            series_row=sx_series,
            series_code="SX",
            coast=race.get("coast_250"),
        )

    for race in MX_2027:
        upsert_sx_mx(
            race,
            series_row=mx_series,
            series_code="MX",
            coast="both",
        )

    for race in SMX_2027:
        meta = SMX_RACE_META_2027.get(race["name"]) or {}
        st = meta.get("start_time")
        start_time_val = dt_time(st[0], st[1]) if st else None
        target = _parse_date(race["date"])
        existing = Competition.query.filter_by(
            name=race["name"], series_id=smx_series.id
        ).first()
        if not existing:
            existing = (
                Competition.query.filter(
                    Competition.name == race["name"],
                    Competition.series == "SMX",
                    Competition.event_date >= date(2027, 1, 1),
                    Competition.event_date <= date(2027, 12, 31),
                ).first()
            )
        if existing:
            existing.series_id = smx_series.id
            existing.series = "SMX"
            existing.event_date = target
            existing.phase = race["phase"]
            existing.point_multiplier = race["multiplier"]
            existing.timezone = meta.get("timezone") or existing.timezone or "America/New_York"
            if start_time_val:
                existing.start_time = start_time_val
            updated_comps += 1
        else:
            db.session.add(
                Competition(
                    name=race["name"],
                    event_date=target,
                    series="SMX",
                    point_multiplier=race["multiplier"],
                    is_triple_crown=0,
                    coast_250=None,
                    timezone=meta.get("timezone") or "America/New_York",
                    start_time=start_time_val,
                    series_id=smx_series.id,
                    phase=race["phase"],
                    is_qualifying=False,
                )
            )
            created_comps += 1

    db.session.commit()

    # Prior AMA year is Fantasy-arkiv only once 2027 calendar exists
    deactivated = []
    for name in ("Supercross", "Motocross", "SMX Finals"):
        older = Series.query.filter_by(name=name, year=2026).first()
        if older and older.is_active:
            older.is_active = False
            deactivated.append(name)
    if deactivated:
        db.session.commit()

    summary = {
        "ok": True,
        "series_created": created_series,
        "competitions_created": created_comps,
        "competitions_updated": updated_comps,
        "sx": len(SX_2027),
        "mx": len(MX_2027),
        "smx": len(SMX_2027),
        "deactivated_2026": deactivated,
    }
    print(
        f"[AMA-2027] series+={len(created_series)} comps+={created_comps} "
        f"comps~={updated_comps} (SX {len(SX_2027)} / MX {len(MX_2027)} / SMX {len(SMX_2027)})"
        + (f" deactivated_2026={deactivated}" if deactivated else "")
    )
    return summary
