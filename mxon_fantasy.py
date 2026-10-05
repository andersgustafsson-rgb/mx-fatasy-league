"""Motocross of Nations (MXoN) fantasy — seed data, ensure helpers, nation scoring."""
from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Any

from models import (
    Competition,
    CompetitionImage,
    CompetitionScore,
    FinishedSeriesStats,
    MxonClassPick,
    MxonClassResult,
    MxonCompetitionOut,
    MxonNation,
    MxonNationPick,
    MxonNationResult,
    MxonTeamEntry,
    Series,
    db,
)

# Speedweek / FIM provisional entry list (Ernée 2026), Sep 2026.
# USA MXGP: Julien Beaumer replaces Chance Hymas (post pre-entry update).
# Official FIM entry list Ernée 2026 (32 nations).
# `no` = plate numbers (MXGP, MX2, OPEN).
MXON_2026_ERNEE_TEAMS: list[dict[str, Any]] = [
    {"code": "AUS", "name": "Australia", "mxgp": "Jed Beaton", "mx2": "Alex Larwood", "open": "Aaron Tanti", "no": (1, 2, 3)},
    {"code": "USA", "name": "United States", "mxgp": "Julien Beaumer", "mx2": "Levi Kitchen", "open": "Cooper Webb", "no": (4, 5, 6)},
    {"code": "FRA", "name": "France", "mxgp": "Romain Febvre", "mx2": "Mathis Valin", "open": "Tom Vialle", "no": (7, 8, 9)},
    {"code": "BEL", "name": "Belgium", "mxgp": "Lucas Coenen", "mx2": "Sacha Coenen", "open": "Liam Everts", "no": (10, 11, 12)},
    # Gajser out → Pancar MXGP, Osek OPEN
    {"code": "SLO", "name": "Slovenia", "mxgp": "Jan Pancar", "mx2": "Jaka Peklaj", "open": "Lukas Osek", "no": (13, 14, 15)},
    {"code": "ITA", "name": "Italy", "mxgp": "Andrea Adamo", "mx2": "Ferruccio Zanchi", "open": "Alberto Forato", "no": (16, 17, 18)},
    {"code": "SWE", "name": "Sweden", "mxgp": "Isak Gifting", "mx2": "Alve Callemo", "open": "Alvin Östlund", "no": (19, 20, 21)},
    {"code": "SUI", "name": "Switzerland", "mxgp": "Valentin Guillod", "mx2": "Jeremy Seewer", "open": "Kevin Brumann", "no": (22, 23, 24)},
    {"code": "LAT", "name": "Latvia", "mxgp": "Karlis Alberts Reisulis", "mx2": "Janis Martins Reisulis", "open": "Pauls Jonass", "no": (25, 26, 27)},
    {"code": "ESP", "name": "Spain", "mxgp": "Jorge Prado", "mx2": "Guillem Farres", "open": "Francisco Garcia", "no": (28, 29, 30)},
    {"code": "JPN", "name": "Japan", "mxgp": "Kainosuke Oshiro", "mx2": "Haruki Yokoyama", "open": "Yuki Okura", "no": (31, 32, 33)},
    {"code": "BRA", "name": "Brazil", "mxgp": "Fabio Santos", "mx2": "Guilherme Bresolin", "open": "Enzo Lopes", "no": (34, 35, 36)},
    {"code": "EST", "name": "Estonia", "mxgp": "Jorgen-Matthias Talviku", "mx2": "Sebastian Leok", "open": "Kaarel Tilk", "no": (37, 38, 39)},
    {"code": "RSA", "name": "South Africa", "mxgp": "Slade Smith", "mx2": "Camden McLellan", "open": "Trey Cox", "no": (40, 41, 42)},
    {"code": "GER", "name": "Germany", "mxgp": "Tom Koch", "mx2": "Valentin Kees", "open": "Noah Ludwig", "no": (43, 44, 45)},
    {"code": "GBR", "name": "Great Britain", "mxgp": "Taylor Hammal", "mx2": "Ben Mustoe", "open": "Ben Watson", "no": (46, 47, 48)},
    {"code": "NOR", "name": "Norway", "mxgp": "Leander Thunshelle", "mx2": "Pelle Gundersen", "open": "Sander Agard-Michelsen", "no": (52, 53, 54)},
    {"code": "NED", "name": "Netherlands", "mxgp": "Roan van de Moosdijk", "mx2": "Glenn Coldenhoff", "open": "Jeffrey Herlings", "no": (55, 56, 57)},
    {"code": "DEN", "name": "Denmark", "mxgp": "Mads Fredsoe", "mx2": "Nicolai Skovbjerg", "open": "Mikkel Haarup", "no": (58, 59, 60)},
    {"code": "AUT", "name": "Austria", "mxgp": "Michael Kratzer", "mx2": "Ricardo Bauer", "open": "Michael Sandner", "no": (61, 62, 63)},
    {"code": "CAN", "name": "Canada", "mxgp": "Tanner Ward", "mx2": "Dylan Rempel", "open": "Dylan Wright", "no": (64, 65, 66)},
    {"code": "FIN", "name": "Finland", "mxgp": "Emil Weckman", "mx2": "Saku Mansikkamäki", "open": "Jere Haavisto", "no": (67, 68, 69)},
    {"code": "IRL", "name": "Ireland", "mxgp": "Lennox Belfast", "mx2": "Glenn McCormick", "open": "Jason Meara", "no": (85, 86, 87)},
    {"code": "LAM", "name": "FIM Latin America", "mxgp": "Joaquin Poli", "mx2": "Carlos Badiali", "open": "Fabricio Chacon", "no": (88, 89, 90)},
    {"code": "MAR", "name": "Morocco", "mxgp": "Maxime Simon", "mx2": "Saad Soulimani", "open": "Noam Jayal", "no": (91, 92, 93)},
    {"code": "MEX", "name": "Mexico", "mxgp": "Jorge Israel Rubalcava", "mx2": "Fernando Velazquez", "open": "Erick Ismael Vasquez Diaz", "no": (97, 98, 99)},
    {"code": "ISL", "name": "Iceland", "mxgp": "Ingvar Sverrir Einarsson", "mx2": "Eric Mani Gudmundsson", "open": "Tristan Berg Arason", "no": (100, 101, 102)},
    {"code": "UKR", "name": "Ukraine", "mxgp": "Roman Morozov", "mx2": "Ostap Andrukh", "open": "Mykhailo Vasko", "no": (103, 104, 105)},
    {"code": "CZE", "name": "Czech Republic", "mxgp": "Petr Rathousky", "mx2": "David Widerwill", "open": "Vaclav Kovar", "no": (115, 116, 117)},
    {"code": "CRO", "name": "Croatia", "mxgp": "Matija Kelava", "mx2": "Simun Ivandic", "open": "Matej Jaros", "no": (118, 119, 120)},
    {"code": "SVK", "name": "Slovakia", "mxgp": "Tomas Kohut", "mx2": "Jaroslav Katrinak", "open": "Pavol Repcak", "no": (121, 122, 123)},
    {"code": "LTU", "name": "Lithuania", "mxgp": "Domantas Jazdauskas", "mx2": "Marius Adomaitis", "open": "Erlandas Mackonis", "no": (124, 125, 126)},
]

# Motorsport codes → ISO 3166-1 alpha-2 for flag emoji
_CODE_TO_ALPHA2 = {
    "AUS": "AU",
    "USA": "US",
    "FRA": "FR",
    "BEL": "BE",
    "SLO": "SI",
    "ITA": "IT",
    "SWE": "SE",
    "SUI": "CH",
    "LAT": "LV",
    "ESP": "ES",
    "JPN": "JP",
    "BRA": "BR",
    "EST": "EE",
    "RSA": "ZA",
    "GER": "DE",
    "GBR": "GB",
    "NOR": "NO",
    "NED": "NL",
    "DEN": "DK",
    "AUT": "AT",
    "CAN": "CA",
    "FIN": "FI",
    "CHI": "CL",
    "IRL": "IE",
    "MAR": "MA",
    "MEX": "MX",
    "ISL": "IS",
    "UKR": "UA",
    "CZE": "CZ",
    "CRO": "HR",
    "SVK": "SK",
    "LTU": "LT",
}

COMP_NAME = "MXoN Ernée 2026"
# Tippa / CompetitionImage: flygfoto av banan. Serie-kort: samma (CSS).
TRACK_IMAGE_REL = "images/mxon/ernee_trackmap.jpg"
TRACK_IMAGE_STATIC = TRACK_IMAGE_REL
AERIAL_IMAGE_REL = "images/mxon/ernee_aerial.jpg"

# Weekend: fre 2 okt parade · lör 3 okt kval · sön 4 okt Race 1–3.
# tippa-lock styrs av event_date + start_time (−2h) → måste vara LÖRDAG (kval),
# annars kan man tippa efter att ha sett kvalresultat.
MXON_QUAL_DATE = date(2026, 10, 3)
MXON_RACE_DATE = date(2026, 10, 4)
# Officiellt program Motoclub Ernée 2026 (lokal tid Europe/Paris):
#   Lör: MXGP Qual 14:30 · MX2 Qual 15:30 · OPEN Qual 16:30
#   Sön: Race 1 13:10 · Race 2 14:40 · Race 3 16:08
# (Racer X TV-listan är USA-tid — använd inte den för tippa-deadline.)
MXON_QUAL_START = time(14, 30)
MXON_RACE1_START = time(13, 10)


def _set_competition_start_time(comp: Competition, value: time) -> None:
    """Best-effort persist of start_time (property setter + raw SQL when column exists)."""
    hhmmss = value.strftime("%H:%M:%S")
    try:
        comp.start_time = value
    except Exception:
        pass
    try:
        db.session.execute(db.text("SELECT start_time FROM competitions LIMIT 1"))
        db.session.execute(
            db.text("UPDATE competitions SET start_time = :start_time WHERE id = :id"),
            {"start_time": hhmmss, "id": comp.id},
        )
    except Exception:
        # Local DB may lack start_time; MXON schedule fallback in main covers lock.
        pass

MXON_CLASS_KEYS = ("mxgp", "mx2", "open")
MXON_CLASS_LABELS = {"mxgp": "MXGP", "mx2": "MX2", "open": "OPEN"}
# Poäng per rätt klassfavorit (förare som vinner klassen)
CLASS_FAVORITE_POINTS = 15


def rider_seat_for_nation(nation_id: int, class_name: str) -> dict[str, Any]:
    """Return {rider_name, rider_number, is_tba} for a nation's class seat."""
    key = (class_name or "").lower()
    entry = MxonTeamEntry.query.filter_by(nation_id=nation_id, class_name=key).first()
    if not entry:
        return {"rider_name": "TBA", "rider_number": None, "is_tba": True}
    is_tba = bool(entry.is_tba) or not (entry.rider_name or "").strip()
    return {
        "rider_name": "TBA" if is_tba else (entry.rider_name or "").strip(),
        "rider_number": entry.rider_number,
        "is_tba": is_tba,
    }


def format_mxon_rider_label(seat: dict[str, Any] | None, *, with_number: bool = True) -> str:
    """Display label like '#19 Isak Gifting' or 'TBA'."""
    if not seat:
        return "TBA"
    name = "TBA" if seat.get("is_tba") else (seat.get("rider_name") or "TBA")
    num = seat.get("rider_number")
    if with_number and num is not None:
        return f"#{num} {name}"
    return name


def class_rider_label(nation_id: int, class_name: str) -> str:
    return format_mxon_rider_label(rider_seat_for_nation(nation_id, class_name))


def _ensure_mxon_team_rider_number_column() -> None:
    """Best-effort ADD COLUMN so prod works before/without alembic migrate."""
    try:
        url = str(db.engine.url)
        if "sqlite" in url:
            rows = db.session.execute(db.text("PRAGMA table_info(mxon_team_entries)")).fetchall()
            cols = {r[1] for r in rows}
            if "rider_number" not in cols:
                db.session.execute(
                    db.text("ALTER TABLE mxon_team_entries ADD COLUMN rider_number INTEGER")
                )
                db.session.commit()
        else:
            db.session.execute(
                db.text(
                    "ALTER TABLE mxon_team_entries "
                    "ADD COLUMN IF NOT EXISTS rider_number INTEGER"
                )
            )
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def flag_emoji_for_code(code: str) -> str:
    if (code or "").upper() == "LAM":
        return "🌎"
    alpha2 = _CODE_TO_ALPHA2.get((code or "").upper())
    if not alpha2 or len(alpha2) != 2:
        return "🏳️"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in alpha2.upper())


def alpha2_for_code(code: str) -> str | None:
    c = (code or "").upper()
    if c == "LAM":
        return None
    return _CODE_TO_ALPHA2.get(c)


def flag_image_url(code: str) -> str:
    """PNG flag URL — emoji flags render as 'SE'/'US' on Windows."""
    c = (code or "").upper()
    if c == "LAM":
        return "/static/images/mxon/flags/lam.svg"
    alpha2 = alpha2_for_code(c)
    if not alpha2:
        return "/static/images/mxon/flags/unknown.svg"
    local = f"/static/images/mxon/flags/{alpha2.lower()}.png"
    # Prefer local cache when present; CDN as absolute fallback path used by seed downloader
    return local


def list_active_nations() -> list:
    return (
        MxonNation.query.filter_by(is_active=True)
        .order_by(MxonNation.sort_order.asc(), MxonNation.name.asc())
        .all()
    )


def _ensure_mxon_competition_outs_table() -> None:
    """Best-effort create table so prod works before/without alembic migrate."""
    try:
        MxonCompetitionOut.__table__.create(bind=db.engine, checkfirst=True)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def get_mxon_outs(competition_id: int) -> list[dict[str, Any]]:
    """Return OUT rows for a competition (nation and/or seat)."""
    _ensure_mxon_competition_outs_table()
    rows = (
        MxonCompetitionOut.query.filter_by(competition_id=int(competition_id))
        .order_by(MxonCompetitionOut.nation_id.asc(), MxonCompetitionOut.class_name.asc())
        .all()
    )
    out = []
    for r in rows:
        n = r.nation or MxonNation.query.get(r.nation_id)
        cls = (r.class_name or "*").lower()
        seat = None
        if cls in MXON_CLASS_KEYS:
            seat = rider_seat_for_nation(int(r.nation_id), cls)
        out.append(
            {
                "id": r.id,
                "competition_id": r.competition_id,
                "nation_id": r.nation_id,
                "code": n.code if n else None,
                "name": n.name if n else None,
                "flag_url": flag_image_url(n.code) if n else None,
                "class_name": cls,
                "class_label": "Hela nationen" if cls == "*" else MXON_CLASS_LABELS.get(cls, cls.upper()),
                "rider_name": (seat or {}).get("rider_name"),
                "rider_number": (seat or {}).get("rider_number"),
            }
        )
    return out


def mxon_out_sets(competition_id: int) -> tuple[set[int], set[tuple[int, str]]]:
    """Return (nation_ids_out, seat_outs as (nation_id, class_key))."""
    _ensure_mxon_competition_outs_table()
    nation_out: set[int] = set()
    seat_out: set[tuple[int, str]] = set()
    for r in MxonCompetitionOut.query.filter_by(competition_id=int(competition_id)).all():
        cls = (r.class_name or "*").lower()
        if cls == "*":
            nation_out.add(int(r.nation_id))
        elif cls in MXON_CLASS_KEYS:
            seat_out.add((int(r.nation_id), cls))
    return nation_out, seat_out


def set_mxon_out(
    competition_id: int,
    nation_id: int,
    class_name: str | None = "*",
    *,
    status: str = "OUT",
) -> dict[str, Any]:
    """Set or clear OUT. class_name '*' = whole nation; mxgp|mx2|open = seat."""
    _ensure_mxon_competition_outs_table()
    cls = (class_name or "*").strip().lower()
    if cls in ("nation", "all", "team", ""):
        cls = "*"
    if cls != "*" and cls not in MXON_CLASS_KEYS:
        raise ValueError("invalid_class")
    nation = MxonNation.query.get(int(nation_id))
    if not nation:
        raise ValueError("nation_not_found")

    status_u = (status or "OUT").upper()
    existing = MxonCompetitionOut.query.filter_by(
        competition_id=int(competition_id),
        nation_id=int(nation_id),
        class_name=cls,
    ).first()

    if status_u == "CLEAR":
        deleted = 0
        if existing:
            db.session.delete(existing)
            deleted = 1
        # Clearing whole nation also clears seat-level OUTs for that nation
        if cls == "*":
            deleted += (
                MxonCompetitionOut.query.filter_by(
                    competition_id=int(competition_id),
                    nation_id=int(nation_id),
                )
                .filter(MxonCompetitionOut.class_name != "*")
                .delete(synchronize_session=False)
            )
        db.session.commit()
        return {"ok": True, "cleared": deleted, "class_name": cls}

    if not existing:
        db.session.add(
            MxonCompetitionOut(
                competition_id=int(competition_id),
                nation_id=int(nation_id),
                class_name=cls,
            )
        )
    # If marking whole nation OUT, remove redundant seat rows
    if cls == "*":
        MxonCompetitionOut.query.filter_by(
            competition_id=int(competition_id),
            nation_id=int(nation_id),
        ).filter(MxonCompetitionOut.class_name != "*").delete(synchronize_session=False)
    db.session.commit()
    return {"ok": True, "class_name": cls, "nation_id": int(nation_id)}


def apply_mxon_outs_to_nations(
    nations: list[dict[str, Any]],
    competition_id: int,
    *,
    hide_nation_out: bool = True,
) -> list[dict[str, Any]]:
    """Annotate lineup seats with is_out; optionally drop fully OUT nations."""
    nation_out, seat_out = mxon_out_sets(competition_id)
    filtered: list[dict[str, Any]] = []
    for d in nations:
        nid = int(d.get("id") or 0)
        whole = nid in nation_out
        if hide_nation_out and whole:
            continue
        d = dict(d)
        d["is_out"] = whole
        lineup = dict(d.get("lineup") or {})
        for key in MXON_CLASS_KEYS:
            seat = dict(lineup.get(key) or {})
            seat["is_out"] = whole or ((nid, key) in seat_out)
            lineup[key] = seat
        d["lineup"] = lineup
        filtered.append(d)
    return filtered


def nation_dict(n: MxonNation, *, include_lineup: bool = True) -> dict:
    code = n.code or ""
    payload: dict[str, Any] = {
        "id": n.id,
        "code": code,
        "name": n.name,
        "flag_emoji": n.flag_emoji or flag_emoji_for_code(code),
        "flag_url": flag_image_url(code),
        "alpha2": alpha2_for_code(code),
        "sort_order": n.sort_order,
    }
    if include_lineup:
        lineup = {}
        for e in MxonTeamEntry.query.filter_by(nation_id=n.id).all():
            lineup[e.class_name] = {
                "rider_name": e.rider_name,
                "rider_number": e.rider_number,
                "is_tba": bool(e.is_tba),
                "rider_id": e.rider_id,
            }
        payload["lineup"] = lineup
    return payload


def ensure_mxon_2026(*, attach_track_image: bool = True) -> dict:
    """Upsert MXON Series + Ernée competition + 32 nations + official lineups."""
    _ensure_mxon_team_rider_number_column()
    _ensure_mxon_competition_outs_table()
    created_series = False
    mxon = Series.query.filter(
        Series.year == 2026,
        Series.name.in_(("MXON", "MXoN")),
    ).first()
    if not mxon:
        mxon = Series(
            name="MXON",
            year=2026,
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 4),
            is_active=True,
            points_system="standard",
        )
        db.session.add(mxon)
        db.session.flush()
        created_series = True
    else:
        mxon.name = "MXON"
        mxon.start_date = date(2026, 10, 2)
        mxon.end_date = date(2026, 10, 4)
        # Don't reopen an archived season
        already_archived = (
            FinishedSeriesStats.query.filter_by(series_id=int(mxon.id)).first() is not None
        )
        if already_archived:
            mxon.is_active = False
        elif mxon.is_active is None:
            mxon.is_active = True
        # else: keep current is_active (admin may have closed it)

    created_comp = False
    updated_comp = False
    comp = Competition.query.filter_by(name=COMP_NAME, series_id=mxon.id).first()
    if comp is None:
        orphan = Competition.query.filter_by(name=COMP_NAME, series="MXON", series_id=None).first()
        if orphan:
            comp = orphan
            updated_comp = True
        else:
            # Also match alternate naming
            orphan2 = (
                Competition.query.filter(Competition.series == "MXON")
                .filter(Competition.name.ilike("%ern%"))
                .first()
            )
            if orphan2:
                comp = orphan2
                updated_comp = True
            else:
                comp = Competition(
                    name=COMP_NAME,
                    event_date=MXON_QUAL_DATE,
                    series="MXON",
                    series_id=mxon.id,
                )
                db.session.add(comp)
                created_comp = True
    else:
        updated_comp = True

    comp.name = COMP_NAME
    comp.series = "MXON"
    comp.series_id = mxon.id
    # Lock-dag = lördag kval (inte söndagens Race 1)
    comp.event_date = MXON_QUAL_DATE
    if hasattr(comp, "timezone"):
        comp.timezone = "Europe/Paris"
    db.session.flush()
    # MXGP Qual 14:30 lokal → picks deadline 12:30 (samma −2h-regel som övriga serier)
    _set_competition_start_time(comp, MXON_QUAL_START)

    nations_created = 0
    nations_updated = 0
    entries_upserted = 0
    for i, team in enumerate(MXON_2026_ERNEE_TEAMS):
        code = team["code"].upper()
        nation = MxonNation.query.filter_by(code=code).first()
        if not nation:
            nation = MxonNation(
                code=code,
                name=team["name"],
                flag_emoji=flag_emoji_for_code(code),
                sort_order=i,
                is_active=True,
            )
            db.session.add(nation)
            db.session.flush()
            nations_created += 1
        else:
            nation.name = team["name"]
            nation.flag_emoji = flag_emoji_for_code(code)
            nation.sort_order = i
            nation.is_active = True
            nations_updated += 1

        for cls_i, cls_key in enumerate(("mxgp", "mx2", "open")):
            rider_name = (team.get(cls_key) or "").strip() or "TBA"
            is_tba = rider_name.upper() == "TBA"
            numbers = team.get("no") or (None, None, None)
            rider_number = None
            try:
                rider_number = int(numbers[cls_i]) if numbers[cls_i] is not None else None
            except (TypeError, ValueError, IndexError):
                rider_number = None
            entry = MxonTeamEntry.query.filter_by(nation_id=nation.id, class_name=cls_key).first()
            if not entry:
                entry = MxonTeamEntry(
                    nation_id=nation.id,
                    class_name=cls_key,
                    rider_name=None if is_tba else rider_name,
                    rider_number=rider_number,
                    is_tba=is_tba,
                )
                db.session.add(entry)
            else:
                entry.rider_name = None if is_tba else rider_name
                entry.rider_number = rider_number
                entry.is_tba = is_tba
            entries_upserted += 1

    # Deactivate nations no longer on the official entry list (e.g. Chile).
    active_codes = {t["code"].upper() for t in MXON_2026_ERNEE_TEAMS}
    nations_deactivated = 0
    for nation in MxonNation.query.all():
        code = (nation.code or "").upper()
        if code and code not in active_codes and nation.is_active:
            nation.is_active = False
            nations_deactivated += 1

    image_attached = False
    if attach_track_image:
        image_attached = _ensure_ernee_track_image(comp)

    db.session.commit()
    info = {
        "series_id": mxon.id,
        "competition_id": comp.id,
        "created_series": created_series,
        "created_competition": created_comp,
        "updated_competition": updated_comp,
        "nations_created": nations_created,
        "nations_updated": nations_updated,
        "nations_deactivated": nations_deactivated,
        "entries_upserted": entries_upserted,
        "track_image": image_attached,
        "nation_count": len(MXON_2026_ERNEE_TEAMS),
    }
    print(
        f"[MXON-SEED] OK series_id={mxon.id} comp_id={comp.id} "
        f"nations={nations_created}+{nations_updated} deactivated={nations_deactivated} "
        f"entries={entries_upserted}"
    )
    return info


def _ensure_ernee_track_image(comp: Competition) -> bool:
    """Attach CompetitionImage pointing at the Ernée aerial track photo."""
    root = Path(__file__).resolve().parent
    abs_path = root / "static" / TRACK_IMAGE_REL
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    url = TRACK_IMAGE_STATIC
    existing = (
        CompetitionImage.query.filter_by(competition_id=comp.id)
        .filter(CompetitionImage.image_url.contains("mxon"))
        .first()
    )
    if existing:
        existing.image_url = url
        existing.sort_order = 0
        return abs_path.is_file()

    # Avoid wiping other images — only add if none for this comp
    any_img = CompetitionImage.query.filter_by(competition_id=comp.id).first()
    if any_img is None:
        db.session.add(
            CompetitionImage(competition_id=comp.id, image_url=url, sort_order=0)
        )
    return abs_path.is_file()


def calculate_nation_pick_points(predicted_position: int, actual_position: int | None) -> int:
    """Same proximity scale as tippa topp-6: 25/18/13/9/6/(3)."""
    if actual_position is None:
        return 0
    if predicted_position == actual_position:
        return 25
    diff = abs(int(predicted_position) - int(actual_position))
    if diff == 1:
        return 18
    if diff == 2:
        return 13
    if diff == 3:
        return 9
    if diff == 4:
        return 6
    return 3


def get_user_nation_picks(user_id: int, competition_id: int) -> list[dict]:
    rows = (
        MxonNationPick.query.filter_by(user_id=user_id, competition_id=competition_id)
        .order_by(MxonNationPick.position.asc())
        .all()
    )
    out = []
    for p in rows:
        n = p.nation or MxonNation.query.get(p.nation_id)
        code = n.code if n else ""
        out.append(
            {
                "position": p.position,
                "nation_id": p.nation_id,
                "code": code or None,
                "name": n.name if n else None,
                "flag_emoji": (n.flag_emoji if n else None) or flag_emoji_for_code(code),
                "flag_url": flag_image_url(code) if code else None,
            }
        )
    return out


def save_user_nation_picks(
    user_id: int,
    competition_id: int,
    nation_ids: list[int],
) -> list[dict]:
    """Replace user's top-5. nation_ids must be exactly 5 unique active nation ids."""
    if len(nation_ids) != 5:
        raise ValueError("exactly_5_nations_required")
    if len(set(nation_ids)) != 5:
        raise ValueError("duplicate_nations")
    active_ids = {n.id for n in list_active_nations()}
    nation_out, _seat_out = mxon_out_sets(int(competition_id))
    for nid in nation_ids:
        if int(nid) not in active_ids:
            raise ValueError(f"invalid_nation:{nid}")
        if int(nid) in nation_out:
            raise ValueError(f"nation_out:{nid}")

    MxonNationPick.query.filter_by(user_id=user_id, competition_id=competition_id).delete()
    for pos, nid in enumerate(nation_ids, start=1):
        db.session.add(
            MxonNationPick(
                user_id=user_id,
                competition_id=competition_id,
                position=pos,
                nation_id=int(nid),
            )
        )
    db.session.commit()
    return get_user_nation_picks(user_id, competition_id)


def get_user_class_picks(user_id: int, competition_id: int) -> dict[str, dict]:
    """Return {mxgp|mx2|open: {nation_id, code, name, flag_url, rider_name}}."""
    rows = MxonClassPick.query.filter_by(
        user_id=user_id, competition_id=competition_id
    ).all()
    out: dict[str, dict] = {}
    for p in rows:
        key = (p.class_name or "").lower()
        if key not in MXON_CLASS_KEYS:
            continue
        n = p.nation or MxonNation.query.get(p.nation_id)
        code = n.code if n else ""
        seat = rider_seat_for_nation(int(p.nation_id), key)
        out[key] = {
            "class_name": key,
            "nation_id": p.nation_id,
            "code": code or None,
            "name": n.name if n else None,
            "flag_url": flag_image_url(code) if code else None,
            "rider_name": seat["rider_name"],
            "rider_number": seat.get("rider_number"),
            "is_tba": seat["is_tba"],
        }
    return out


def mxon_has_official_results(competition_id: int) -> bool:
    """True when nation classification has been entered for scoring."""
    return (
        MxonNationResult.query.filter_by(competition_id=int(competition_id)).first()
        is not None
    )


def _nation_public_row(nation: MxonNation | None, nation_id: int | None = None) -> dict[str, Any]:
    n = nation
    if n is None and nation_id is not None:
        n = MxonNation.query.get(int(nation_id))
    code = (n.code if n else "") or ""
    return {
        "nation_id": int(n.id) if n else int(nation_id or 0),
        "code": code or None,
        "name": (n.name if n else None) or code or "?",
        "flag_emoji": (n.flag_emoji if n else None) or flag_emoji_for_code(code),
        "flag_url": flag_image_url(code) if code else None,
    }


def build_mxon_crowd_summary(competition_id: int) -> dict[str, Any]:
    """Field favorites: most tipped nation per slot 1–5 + class favorites."""
    from collections import defaultdict

    cid = int(competition_id)
    slot_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    class_counts: dict[str, dict[int, int]] = {
        k: defaultdict(int) for k in MXON_CLASS_KEYS
    }

    nation_user_ids = {
        int(uid)
        for (uid,) in db.session.query(MxonNationPick.user_id)
        .filter_by(competition_id=cid)
        .distinct()
        .all()
        if uid is not None
    }
    class_user_ids = {
        int(uid)
        for (uid,) in db.session.query(MxonClassPick.user_id)
        .filter_by(competition_id=cid)
        .distinct()
        .all()
        if uid is not None
    }
    n_users = len(nation_user_ids | class_user_ids)

    for p in MxonNationPick.query.filter_by(competition_id=cid).all():
        try:
            pos = int(p.position)
            nid = int(p.nation_id)
        except (TypeError, ValueError):
            continue
        if 1 <= pos <= 5:
            slot_counts[pos][nid] += 1

    for p in MxonClassPick.query.filter_by(competition_id=cid).all():
        key = (p.class_name or "").lower()
        if key not in MXON_CLASS_KEYS:
            continue
        try:
            class_counts[key][int(p.nation_id)] += 1
        except (TypeError, ValueError):
            continue

    all_nids: set[int] = set()
    for counter in slot_counts.values():
        all_nids.update(int(nid) for nid in counter)
    for counter in class_counts.values():
        all_nids.update(int(nid) for nid in counter)
    nations_by_id: dict[int, MxonNation] = {}
    if all_nids:
        nations_by_id = {
            int(n.id): n
            for n in MxonNation.query.filter(MxonNation.id.in_(all_nids)).all()
        }

    def top_nations(counter: dict[int, int], topn: int = 5) -> list[dict[str, Any]]:
        tot = sum(counter.values())
        if tot <= 0:
            return []
        items = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        out: list[dict[str, Any]] = []
        for nid, c in items[:topn]:
            row = _nation_public_row(nations_by_id.get(nid), nid)
            row["count"] = c
            row["pct"] = round(100.0 * c / tot, 1)
            out.append(row)
        return out

    slots = {str(pos): top_nations(dict(slot_counts.get(pos, {}))) for pos in range(1, 6)}
    class_favorites = {
        key: top_nations(dict(class_counts[key]), topn=5) for key in MXON_CLASS_KEYS
    }
    # Attach rider seat label for class favorites
    for key, rows in class_favorites.items():
        for row in rows:
            seat = rider_seat_for_nation(int(row["nation_id"]), key)
            row["rider_name"] = seat.get("rider_name")
            row["rider_number"] = seat.get("rider_number")

    return {
        "kind": "mxon",
        "n_lineups": len(nation_user_ids),
        "n_users_with_snapshots_or_picks": n_users,
        "slots_nations": slots,
        "class_favorites": class_favorites,
        # Keep empty SX-shaped keys so older clients don't crash
        "slots_450": {},
        "slots_250": {},
        "holeshot_450": [],
        "holeshot_250": [],
        "wildcard_top": [],
    }


def list_other_users_mxon_picks(
    competition_id: int, *, exclude_user_id: int | None = None
) -> list[dict[str, Any]]:
    """Per-user MXoN tippa for 'Se andras picks' after deadline."""
    from models import User

    cid = int(competition_id)
    q = (
        db.session.query(MxonNationPick.user_id)
        .filter_by(competition_id=cid)
        .distinct()
    )
    class_q = (
        db.session.query(MxonClassPick.user_id)
        .filter_by(competition_id=cid)
        .distinct()
    )
    user_ids = {int(uid) for (uid,) in q.all() if uid is not None}
    user_ids |= {int(uid) for (uid,) in class_q.all() if uid is not None}
    if exclude_user_id is not None:
        user_ids.discard(int(exclude_user_id))

    users = {
        int(u.id): u
        for u in User.query.filter(User.id.in_(user_ids or [0])).all()
    }
    out: list[dict[str, Any]] = []
    for uid in sorted(user_ids, key=lambda i: (users.get(i).username or "").lower() if users.get(i) else ""):
        user = users.get(uid)
        if not user:
            continue
        nations = get_user_nation_picks(uid, cid)
        classes = get_user_class_picks(uid, cid)
        if not nations and not classes:
            continue
        out.append(
            {
                "username": user.username,
                "display_name": getattr(user, "display_name", None) or user.username,
                "is_mxon": True,
                "is_wsx": False,
                "nations": nations,
                "classes": classes,
                "picks_450": [],
                "picks_250": [],
                "holeshot_450": None,
                "holeshot_250": None,
                "wildcard": None,
            }
        )
    return out


def save_user_class_picks(
    user_id: int,
    competition_id: int,
    class_nation_ids: dict[str, int],
) -> dict[str, dict]:
    """Replace class favorites. Expects keys mxgp/mx2/open → nation_id."""
    active_ids = {n.id for n in list_active_nations()}
    nation_out, seat_out = mxon_out_sets(int(competition_id))
    cleaned: dict[str, int] = {}
    for key in MXON_CLASS_KEYS:
        raw = class_nation_ids.get(key)
        if raw is None or raw == "":
            raise ValueError(f"missing_class:{key}")
        nid = int(raw)
        if nid not in active_ids:
            raise ValueError(f"invalid_nation:{nid}")
        if nid in nation_out or (nid, key) in seat_out:
            raise ValueError(f"seat_out:{key}:{nid}")
        cleaned[key] = nid

    MxonClassPick.query.filter_by(user_id=user_id, competition_id=competition_id).delete()
    for key, nid in cleaned.items():
        db.session.add(
            MxonClassPick(
                user_id=user_id,
                competition_id=competition_id,
                class_name=key,
                nation_id=nid,
            )
        )
    db.session.commit()
    return get_user_class_picks(user_id, competition_id)


def set_class_results(competition_id: int, class_nation_ids: dict[str, int]) -> int:
    """Set winning nation per class. Keys: mxgp/mx2/open."""
    active_ids = {n.id for n in list_active_nations()}
    cleaned: dict[str, int] = {}
    for key in MXON_CLASS_KEYS:
        raw = class_nation_ids.get(key)
        if raw is None or raw == "":
            raise ValueError(f"missing_class:{key}")
        nid = int(raw)
        if nid not in active_ids:
            raise ValueError(f"invalid_nation:{nid}")
        cleaned[key] = nid

    MxonClassResult.query.filter_by(competition_id=competition_id).delete()
    for key, nid in cleaned.items():
        db.session.add(
            MxonClassResult(
                competition_id=competition_id,
                class_name=key,
                nation_id=nid,
            )
        )
    db.session.commit()
    return len(cleaned)


def get_class_results(competition_id: int) -> dict[str, dict]:
    rows = MxonClassResult.query.filter_by(competition_id=competition_id).all()
    out: dict[str, dict] = {}
    for r in rows:
        key = (r.class_name or "").lower()
        n = r.nation or MxonNation.query.get(r.nation_id)
        code = n.code if n else ""
        seat = rider_seat_for_nation(int(r.nation_id), key)
        out[key] = {
            "class_name": key,
            "nation_id": r.nation_id,
            "code": code or None,
            "name": n.name if n else None,
            "rider_name": seat["rider_name"],
            "rider_number": seat.get("rider_number"),
            "is_tba": seat["is_tba"],
        }
    return out


def set_nation_results(competition_id: int, ordered_nation_ids: list[int]) -> int:
    """Replace official nation order (1..n) for a competition. Returns count."""
    if not ordered_nation_ids:
        raise ValueError("empty_results")
    if len(set(ordered_nation_ids)) != len(ordered_nation_ids):
        raise ValueError("duplicate_nations")
    MxonNationResult.query.filter_by(competition_id=competition_id).delete()
    for pos, nid in enumerate(ordered_nation_ids, start=1):
        db.session.add(
            MxonNationResult(
                competition_id=competition_id,
                position=pos,
                nation_id=int(nid),
            )
        )
    db.session.commit()
    return len(ordered_nation_ids)


def calculate_mxon_scores(competition_id: int) -> dict:
    """Score nation tippa + klassfavoriter → CompetitionScore."""
    results = MxonNationResult.query.filter_by(competition_id=competition_id).all()
    actual_by_nation = {int(r.nation_id): int(r.position) for r in results}
    if not actual_by_nation:
        return {"scored_users": 0, "error": "no_results"}

    class_winners = {
        (r.class_name or "").lower(): int(r.nation_id)
        for r in MxonClassResult.query.filter_by(competition_id=competition_id).all()
        if (r.class_name or "").lower() in MXON_CLASS_KEYS
    }

    pick_user_ids = {
        int(uid)
        for (uid,) in db.session.query(MxonNationPick.user_id)
        .filter_by(competition_id=competition_id)
        .distinct()
        .all()
    }
    class_user_ids = {
        int(uid)
        for (uid,) in db.session.query(MxonClassPick.user_id)
        .filter_by(competition_id=competition_id)
        .distinct()
        .all()
    }
    pick_user_ids |= class_user_ids

    scored = 0
    for uid in pick_user_ids:
        picks = MxonNationPick.query.filter_by(
            user_id=uid, competition_id=competition_id
        ).all()
        race_points = 0
        for p in picks:
            actual = actual_by_nation.get(int(p.nation_id))
            race_points += calculate_nation_pick_points(int(p.position), actual)

        class_points = 0
        class_picks = MxonClassPick.query.filter_by(
            user_id=uid, competition_id=competition_id
        ).all()
        for cp in class_picks:
            key = (cp.class_name or "").lower()
            winner = class_winners.get(key)
            if winner is not None and int(cp.nation_id) == winner:
                class_points += CLASS_FAVORITE_POINTS

        score = CompetitionScore.query.filter_by(
            user_id=uid, competition_id=competition_id
        ).first()
        if not score:
            score = CompetitionScore(
                user_id=uid,
                competition_id=competition_id,
                total_points=0,
                race_points=0,
                holeshot_points=0,
                wildcard_points=0,
            )
            db.session.add(score)
        score.race_points = int(race_points)
        # Klassfavoriter lagras i holeshot_points (ingen holeshot i MXoN)
        score.holeshot_points = int(class_points)
        score.wildcard_points = 0
        score.total_points = int(race_points) + int(class_points)
        scored += 1

    db.session.commit()
    return {
        "scored_users": scored,
        "result_nations": len(actual_by_nation),
        "class_winners": len(class_winners),
        "class_points_each": CLASS_FAVORITE_POINTS,
    }


def build_mxon_results_detail(user_id: int, competition_id: int) -> dict:
    """Structured MXoN score breakdown for Mina poäng detail modal (same shape as AMA)."""
    comp = Competition.query.get(int(competition_id))
    results = MxonNationResult.query.filter_by(competition_id=int(competition_id)).all()
    actual_by_nation = {int(r.nation_id): int(r.position) for r in results}
    nation_by_id: dict[int, MxonNation] = {}
    for r in results:
        n = r.nation or MxonNation.query.get(r.nation_id)
        if n:
            nation_by_id[int(n.id)] = n

    picks = (
        MxonNationPick.query.filter_by(
            user_id=int(user_id), competition_id=int(competition_id)
        )
        .order_by(MxonNationPick.position.asc())
        .all()
    )
    nation_rows: list[dict] = []
    race_points = 0
    for p in picks:
        nid = int(p.nation_id)
        n = p.nation or nation_by_id.get(nid) or MxonNation.query.get(nid)
        code = (n.code if n else "") or ""
        name = (n.name if n else None) or f"Nation #{nid}"
        pred = int(p.position)
        actual = actual_by_nation.get(nid)
        points = calculate_nation_pick_points(pred, actual)
        race_points += points
        if actual is None:
            status = "miss"
            hint = "Nationen finns inte i resultatet → 0p"
            diff = 0
            actual_out = 0
        else:
            diff = abs(pred - int(actual))
            actual_out = int(actual)
            if points == 25:
                status = "perfect"
                hint = "Exakt rätt plats → +25p"
            elif points > 0:
                status = "close"
                hint = f"{diff} {'plats' if diff == 1 else 'platser'} fel → +{points}p"
            else:
                status = "miss"
                hint = "Utanför poängzonen → 0p"
        nation_rows.append(
            {
                "kind": "pick",
                "status": status,
                "rider_name": name,
                "flag_url": flag_image_url(code) if code else None,
                "code": code or None,
                "predicted": pred,
                "actual": actual_out,
                "points": int(points),
                "diff": int(diff),
                "hint": hint,
            }
        )

    class_winners = get_class_results(int(competition_id))
    class_picks = get_user_class_picks(int(user_id), int(competition_id))
    class_rows: list[dict] = []
    class_points = 0
    for key in MXON_CLASS_KEYS:
        label = MXON_CLASS_LABELS.get(key, key.upper())
        picked = class_picks.get(key)
        winner = class_winners.get(key)
        if not picked and not winner:
            continue
        picked_name = (picked or {}).get("name") or "—"
        picked_rider = (picked or {}).get("rider_name") or ""
        if picked_rider and picked_rider != "—":
            picked_display = f"{picked_name} ({picked_rider})"
        else:
            picked_display = picked_name
        actual_name = (winner or {}).get("name") or ""
        actual_rider = (winner or {}).get("rider_name") or ""
        if actual_name and actual_rider and actual_rider != "—":
            actual_display = f"{actual_name} ({actual_rider})"
        else:
            actual_display = actual_name
        ok = bool(
            picked
            and winner
            and int(picked.get("nation_id") or 0) == int(winner.get("nation_id") or 0)
        )
        pts = CLASS_FAVORITE_POINTS if ok else 0
        class_points += pts
        class_rows.append(
            {
                "kind": "class_favorite",
                "status": "correct" if ok else "wrong",
                "label": label,
                "picked_name": picked_display,
                "rider_name": picked_display,
                "actual_name": actual_display,
                "points": int(pts),
                "hint": (
                    f"Rätt klassfavorit → +{CLASS_FAVORITE_POINTS}p"
                    if ok
                    else f"Fel klassfavorit → 0p (rätt: {actual_display or '—'})"
                ),
            }
        )

    total = int(race_points) + int(class_points)
    return {
        "ok": True,
        "kind": "mxon",
        "competition": {
            "id": int(competition_id),
            "name": comp.name if comp else None,
            "series": (comp.series if comp else None) or "MXON",
            "event_date": comp.event_date.isoformat() if comp and comp.event_date else None,
        },
        "total": total,
        "summary": {
            "race_points": int(race_points),
            "holeshot_points": int(class_points),
            "wildcard_points": 0,
        },
        "sections": {
            "picks_450": nation_rows,
            "picks_250": [],
            "holeshot": class_rows,
            "wildcard": [],
            "other": [],
        },
        "labels": {
            "primary": "Nationer (topp 5)",
            "secondary": "",
        },
        "breakdown": [],
    }


def mxon_competitions_for_year(year: int = 2026) -> list[Competition]:
    series = Series.query.filter(
        Series.year == int(year),
        Series.name.in_(("MXON", "MXoN")),
    ).first()
    q = Competition.query.filter(Competition.series == "MXON")
    if series:
        q = q.filter(
            db.or_(
                Competition.series_id == series.id,
                Competition.series_id.is_(None),
            )
        )
    comps = q.all()
    comps.sort(key=lambda c: (c.event_date is None, c.event_date or date.max, int(c.id)))
    return comps


def mxon_nation_podium_for_series(series_id: int, *, limit: int = 3) -> list[dict]:
    """Top N official nations for finished-series display (flags + place)."""
    series = Series.query.get(int(series_id))
    if not series:
        return []
    comps = (
        Competition.query.filter(
            Competition.series == "MXON",
            db.or_(
                Competition.series_id == int(series_id),
                Competition.series_id.is_(None),
            ),
        )
        .order_by(Competition.event_date.desc().nullslast())
        .all()
    )
    if not comps:
        return []
    cid = int(comps[0].id)
    rows = (
        MxonNationResult.query.filter_by(competition_id=cid)
        .order_by(MxonNationResult.position.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    out: list[dict] = []
    for r in rows:
        n = r.nation or MxonNation.query.get(r.nation_id)
        code = (n.code if n else "") or ""
        out.append(
            {
                "place": int(r.position),
                "rank": int(r.position),
                "code": code.upper(),
                "name": (n.name if n else code) or "?",
                "flag_url": flag_image_url(code) if code else None,
                "display_name": (n.name if n else code) or "?",
                "total_points": None,
            }
        )
    return out


def mxon_class_winners_for_series(series_id: int) -> list[dict]:
    series = Series.query.get(int(series_id))
    if not series:
        return []
    comps = (
        Competition.query.filter(
            Competition.series == "MXON",
            db.or_(
                Competition.series_id == int(series_id),
                Competition.series_id.is_(None),
            ),
        )
        .order_by(Competition.event_date.desc().nullslast())
        .all()
    )
    if not comps:
        return []
    cr = get_class_results(int(comps[0].id))
    out = []
    for key, label in (("mxgp", "MXGP"), ("mx2", "MX2"), ("open", "OPEN")):
        row = cr.get(key) or {}
        if not row:
            continue
        out.append(
            {
                "class": label,
                "code": (row.get("code") or "").upper(),
                "name": row.get("name") or row.get("code") or "?",
                "rider_name": row.get("rider_name") or "—",
                "flag_url": flag_image_url(row.get("code") or "") if row.get("code") else None,
            }
        )
    return out


def fantasy_mxon_leaderboard_for_year(year: int = 2026) -> list[dict]:
    """MXoN tippa leaderboard from CompetitionScore, with FinishedSeriesStats fallback."""
    from collections import defaultdict

    from models import SeasonTeam, User

    comps = mxon_competitions_for_year(int(year))
    season_ids = [int(c.id) for c in comps]

    totals: dict[int, int] = defaultdict(int)
    if season_ids:
        by_uc: dict[tuple[int, int], CompetitionScore] = {}
        for s in CompetitionScore.query.filter(
            CompetitionScore.competition_id.in_(season_ids)
        ).all():
            k = (int(s.user_id), int(s.competition_id))
            prev = by_uc.get(k)
            if prev is None or int(s.score_id or 0) > int(prev.score_id or 0):
                by_uc[k] = s
        for s in by_uc.values():
            totals[int(s.user_id)] += int(s.total_points or 0)

    # After archive (or if scores were wiped): fall back to Fantasy-arkiv rows
    if not totals:
        mxon = Series.query.filter(
            Series.year == int(year),
            Series.name.in_(("MXON", "MXoN")),
        ).first()
        if mxon:
            for row in FinishedSeriesStats.query.filter_by(series_id=int(mxon.id)).all():
                totals[int(row.user_id)] = int(row.total_points or 0)

    if not totals:
        return []

    uids = list(totals.keys())
    users = {u.id: u for u in User.query.filter(User.id.in_(uids)).all()}
    teams = {
        int(t.user_id): t.team_name
        for t in SeasonTeam.query.filter(SeasonTeam.user_id.in_(uids)).all()
    }
    ranked = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
    out = []
    for i, (uid, pts) in enumerate(ranked, 1):
        u = users.get(uid)
        dn = getattr(u, "display_name", None) or (u.username if u else "?")
        out.append(
            {
                "user_id": uid,
                "username": u.username if u else "?",
                "display_name": dn,
                "team_name": teams.get(uid),
                "rank": i,
                "delta": 0,
                "total_points": int(pts),
            }
        )
    return out


def build_mxon_crowd_ranking(competition_id: int) -> dict[str, Any]:
    """
    Crowd consensus for MXoN tippa — ranked nations + class favorites.
    Includes strength_pct (share of tip weight / class votes) — no tipper counts.
    Nation rank weight: #1=5 … #5=1 across all tippers.
    """
    from collections import defaultdict

    comp_id = int(competition_id)
    comp = Competition.query.get(comp_id)
    if not comp or (comp.series or "").upper() != "MXON":
        return {"ok": False, "error": "not_mxon"}

    try:
        from services.picks_lock import is_picks_locked

        locked = bool(is_picks_locked(comp))
    except Exception:
        locked = False

    weight = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
    scores: dict[int, float] = defaultdict(float)
    for p in MxonNationPick.query.filter_by(competition_id=comp_id).all():
        pos = int(p.position or 0)
        w = weight.get(pos)
        if w:
            scores[int(p.nation_id)] += w

    nation_ids = list(scores.keys())
    nations = (
        {n.id: n for n in MxonNation.query.filter(MxonNation.id.in_(nation_ids)).all()}
        if nation_ids
        else {}
    )
    total_all = float(sum(scores.values())) or 1.0
    ranked_nations = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    # Show top 10 for the board; % only on tip-style top 5 (share of all tip weight).
    nations_out = []
    for i, (nid, score) in enumerate(ranked_nations[:10], 1):
        n = nations.get(nid)
        if not n:
            continue
        code = (n.code or "").strip()
        row = {
            "rank": i,
            "nation_id": nid,
            "code": code or None,
            "name": n.name,
            "flag_url": flag_image_url(code) if code else None,
            "flag_emoji": n.flag_emoji,
        }
        if i <= 5:
            row["strength_pct"] = int(round(100.0 * float(score) / total_all))
        nations_out.append(row)

    class_counts: dict[str, dict[int, int]] = {
        k: defaultdict(int) for k in MXON_CLASS_KEYS
    }
    for p in MxonClassPick.query.filter_by(competition_id=comp_id).all():
        key = (p.class_name or "").strip().lower()
        if key not in class_counts:
            continue
        class_counts[key][int(p.nation_id)] += 1

    classes_out: dict[str, dict | None] = {}
    for key in MXON_CLASS_KEYS:
        counts = class_counts[key]
        if not counts:
            classes_out[key] = None
            continue
        top_nid, top_votes = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0]
        class_total = int(sum(counts.values())) or 1
        n = MxonNation.query.get(top_nid)
        code = (n.code if n else "") or ""
        seat = rider_seat_for_nation(int(top_nid), key) if n else {}
        classes_out[key] = {
            "class_name": key,
            "class_label": MXON_CLASS_LABELS.get(key, key.upper()),
            "nation_id": top_nid,
            "code": code or None,
            "name": n.name if n else None,
            "flag_url": flag_image_url(code) if code else None,
            "rider_name": (seat or {}).get("rider_name"),
            "rider_number": (seat or {}).get("rider_number"),
            "is_tba": bool((seat or {}).get("is_tba")),
            "strength_pct": int(round(100.0 * int(top_votes) / class_total)),
        }

    return {
        "ok": True,
        "kind": "mxon_crowd",
        "competition": {
            "id": comp.id,
            "name": comp.name,
            "series": "MXON",
            "event_date": comp.event_date.isoformat() if comp.event_date else None,
        },
        "picks_locked": locked,
        "has_tips": bool(nations_out) or any(classes_out.values()),
        "nations": nations_out,
        "classes": classes_out,
        "method": (
            "Topp 10 nationer efter tippvikt (#1=5p … #5=1p). "
            "% visas för tipparnas topp 5 (andel av all tippvikt). "
            "Klass-% = andel av tippen på favoriten. Inte odds."
        ),
    }
