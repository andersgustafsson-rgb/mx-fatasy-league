"""Motocross of Nations (MXoN) fantasy — seed data, ensure helpers, nation scoring."""
from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Any

from models import (
    Competition,
    CompetitionImage,
    CompetitionScore,
    MxonClassPick,
    MxonClassResult,
    MxonNation,
    MxonNationPick,
    MxonNationResult,
    MxonTeamEntry,
    Series,
    db,
)

# Speedweek / FIM provisional entry list (Ernée 2026), Sep 2026.
# TBA seats marked with rider name "TBA" / is_tba=True.
MXON_2026_ERNEE_TEAMS: list[dict[str, Any]] = [
    {"code": "AUS", "name": "Australia", "mxgp": "Jed Beaton", "mx2": "Alex Larwood", "open": "Aaron Tanti"},
    {"code": "USA", "name": "United States", "mxgp": "Chance Hymas", "mx2": "Levi Kitchen", "open": "Cooper Webb"},
    {"code": "FRA", "name": "France", "mxgp": "Romain Febvre", "mx2": "Mathis Valin", "open": "Tom Vialle"},
    {"code": "BEL", "name": "Belgium", "mxgp": "Lucas Coenen", "mx2": "Sacha Coenen", "open": "Liam Everts"},
    {"code": "SLO", "name": "Slovenia", "mxgp": "Tim Gajser", "mx2": "Jaka Peklaj", "open": "Jan Pancar"},
    {"code": "ITA", "name": "Italy", "mxgp": "Andrea Adamo", "mx2": "Ferruccio Zanchi", "open": "Andrea Bonacorsi"},
    {"code": "SWE", "name": "Sweden", "mxgp": "Isak Gifting", "mx2": "Alve Callemo", "open": "Alvin Östlund"},
    {"code": "SUI", "name": "Switzerland", "mxgp": "Valentin Guillod", "mx2": "Jeremy Seewer", "open": "Kevin Brumann"},
    {"code": "LAT", "name": "Latvia", "mxgp": "Karlis Alberts Reisulis", "mx2": "Janis Martins Reisulis", "open": "Pauls Jonass"},
    {"code": "ESP", "name": "Spain", "mxgp": "Jorge Prado", "mx2": "Guillem Farres", "open": "Ruben Fernandez"},
    {"code": "JPN", "name": "Japan", "mxgp": "Kainosuke Oshiro", "mx2": "Haruki Yokoyama", "open": "Yuki Okura"},
    {"code": "BRA", "name": "Brazil", "mxgp": "Fabio Santos", "mx2": "TBA", "open": "Enzo Lopes"},
    {"code": "EST", "name": "Estonia", "mxgp": "Jorgen-Matthias Talviku", "mx2": "Sebastian Leok", "open": "Harri Kullas"},
    {"code": "RSA", "name": "South Africa", "mxgp": "Tristan Purdon", "mx2": "Camden McLellan", "open": "Slade Smith"},
    {"code": "GER", "name": "Germany", "mxgp": "Tom Koch", "mx2": "Valentin Kees", "open": "Noah Ludwig"},
    {"code": "GBR", "name": "Great Britain", "mxgp": "Taylor Hammal", "mx2": "Ben Mustoe", "open": "Ben Watson"},
    {"code": "NOR", "name": "Norway", "mxgp": "Kevin Horgmo", "mx2": "Pelle Gundersen", "open": "Hakon Osterhagen"},
    {"code": "NED", "name": "Netherlands", "mxgp": "TBA", "mx2": "Roan van de Moosdijk", "open": "Jeffrey Herlings"},
    {"code": "DEN", "name": "Denmark", "mxgp": "Mads Fredsoe", "mx2": "Nicolai Skovbjerg", "open": "Mikkel Haarup"},
    {"code": "AUT", "name": "Austria", "mxgp": "Michael Kratzer", "mx2": "Ricardo Bauer", "open": "Michael Sandner"},
    {"code": "CAN", "name": "Canada", "mxgp": "Tanner Ward", "mx2": "Dylan Rempel", "open": "Dylan Wright"},
    {"code": "FIN", "name": "Finland", "mxgp": "Emil Weckman", "mx2": "Saku Mansikkamäki", "open": "Jere Haavisto"},
    {"code": "CHI", "name": "Chile", "mxgp": "Benjamin Garib", "mx2": "Nicolas Israel", "open": "Cesar Paine Diaz"},
    {"code": "IRL", "name": "Ireland", "mxgp": "Lennox Cambridge", "mx2": "Glenn McCormick", "open": "Jason Meara"},
    {"code": "LAM", "name": "FIM Latin America", "mxgp": "Joaquin Poli", "mx2": "Carlos Badiali", "open": "Fabricio Chacon"},
    {"code": "MAR", "name": "Morocco", "mxgp": "Maxime Simon", "mx2": "Saad Soulimani", "open": "Noam Jayal"},
    {"code": "MEX", "name": "Mexico", "mxgp": "Jorge Israel Rubalcava", "mx2": "Fernando Velazquez", "open": "Erick Ismael Vasquez Diaz"},
    {"code": "ISL", "name": "Iceland", "mxgp": "Ingvar Sverrir Einarsson", "mx2": "Eric Mani Gudmundsson", "open": "Tristan Berg Arason"},
    {"code": "UKR", "name": "Ukraine", "mxgp": "Roman Morozov", "mx2": "Vasyl Kurosh", "open": "Mykhailo Vasko"},
    {"code": "CZE", "name": "Czech Republic", "mxgp": "Petr Rathousky", "mx2": "Julius Mikula", "open": "Vaclav Kovar"},
    {"code": "CRO", "name": "Croatia", "mxgp": "Matija Kelava", "mx2": "Simun Ivandic", "open": "Matej Jaros"},
    {"code": "SVK", "name": "Slovakia", "mxgp": "Tomas Kohut", "mx2": "Jaroslav Katrinak", "open": "Pavol Repcak"},
    {"code": "LTU", "name": "Lithuania", "mxgp": "Domantas Jazdauskas", "mx2": "Marius Adomaitis", "open": "Erlandas Mackonis"},
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
# Tippa / CompetitionImage: banlayout. Serie-kort: aerial (CSS), separat fil.
TRACK_IMAGE_REL = "images/mxon/ernee_layout.png"
TRACK_IMAGE_STATIC = TRACK_IMAGE_REL
AERIAL_IMAGE_REL = "images/mxon/ernee_aerial.jpg"

# Weekend: fre 2 okt parade · lör 3 okt kval · sön 4 okt Race 1–3.
# tippa-lock styrs av event_date + start_time (−2h) → måste vara LÖRDAG (kval),
# annars kan man tippa efter att ha sett kvalresultat.
MXON_QUAL_DATE = date(2026, 10, 3)
MXON_RACE_DATE = date(2026, 10, 4)
# Provisional (samma som Ernée 2023): första MXGP Qual Heat 14:30 lokal tid
MXON_QUAL_START = time(14, 30)


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
    """Return {rider_name, is_tba} for a nation's class seat."""
    key = (class_name or "").lower()
    entry = MxonTeamEntry.query.filter_by(nation_id=nation_id, class_name=key).first()
    if not entry:
        return {"rider_name": "TBA", "is_tba": True}
    is_tba = bool(entry.is_tba) or not (entry.rider_name or "").strip()
    return {
        "rider_name": "TBA" if is_tba else (entry.rider_name or "").strip(),
        "is_tba": is_tba,
    }


def class_rider_label(nation_id: int, class_name: str) -> str:
    return rider_seat_for_nation(nation_id, class_name)["rider_name"]


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
                "is_tba": bool(e.is_tba),
                "rider_id": e.rider_id,
            }
        payload["lineup"] = lineup
    return payload


def ensure_mxon_2026(*, attach_track_image: bool = True) -> dict:
    """Upsert MXON Series + Ernée competition + 33 nations + provisional lineups."""
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
        mxon.is_active = True

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
    # MXGP Qual ~14:30 → picks deadline 12:30 lokal (samma −2h-regel som övriga serier)
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

        for cls_key in ("mxgp", "mx2", "open"):
            rider_name = (team.get(cls_key) or "").strip() or "TBA"
            is_tba = rider_name.upper() == "TBA"
            entry = MxonTeamEntry.query.filter_by(nation_id=nation.id, class_name=cls_key).first()
            if not entry:
                entry = MxonTeamEntry(
                    nation_id=nation.id,
                    class_name=cls_key,
                    rider_name=None if is_tba else rider_name,
                    is_tba=is_tba,
                )
                db.session.add(entry)
            else:
                entry.rider_name = None if is_tba else rider_name
                entry.is_tba = is_tba
            entries_upserted += 1

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
        "entries_upserted": entries_upserted,
        "track_image": image_attached,
        "nation_count": len(MXON_2026_ERNEE_TEAMS),
    }
    print(
        f"[MXON-SEED] OK series_id={mxon.id} comp_id={comp.id} "
        f"nations={nations_created}+{nations_updated} entries={entries_upserted}"
    )
    return info


def _ensure_ernee_track_image(comp: Competition) -> bool:
    """Attach CompetitionImage pointing at static/images/mxon/ernee_2026.jpg."""
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
    for nid in nation_ids:
        if int(nid) not in active_ids:
            raise ValueError(f"invalid_nation:{nid}")

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
            "is_tba": seat["is_tba"],
        }
    return out


def save_user_class_picks(
    user_id: int,
    competition_id: int,
    class_nation_ids: dict[str, int],
) -> dict[str, dict]:
    """Replace class favorites. Expects keys mxgp/mx2/open → nation_id."""
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


def fantasy_mxon_leaderboard_for_year(year: int = 2026) -> list[dict]:
    """Simple MXoN tippa leaderboard from CompetitionScore totals."""
    from models import SeasonTeam, User

    comps = mxon_competitions_for_year(int(year))
    season_ids = [int(c.id) for c in comps]
    if not season_ids:
        return []

    from collections import defaultdict

    by_uc: dict[tuple[int, int], CompetitionScore] = {}
    for s in CompetitionScore.query.filter(
        CompetitionScore.competition_id.in_(season_ids)
    ).all():
        k = (int(s.user_id), int(s.competition_id))
        prev = by_uc.get(k)
        if prev is None or int(s.score_id or 0) > int(prev.score_id or 0):
            by_uc[k] = s
    totals: dict[int, int] = defaultdict(int)
    for s in by_uc.values():
        totals[int(s.user_id)] += int(s.total_points or 0)
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
