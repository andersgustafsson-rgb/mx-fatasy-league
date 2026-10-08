"""WSX (World Supercross) tippa-only series scaffold.

Extracted from main.py (refactor skiva 8) — same behaviour, thinner main.

Canadian GP 2026 ran; remaining 2026 rounds cancelled. Seeds stay idempotent
for history, tippa grids, and admin re-seed.
"""
from __future__ import annotations

from models import (
    Competition,
    CompetitionResult,
    CompetitionRiderStatus,
    HoleshotPick,
    HoleshotResult,
    RacePick,
    Rider,
    SeasonTeamRider,
    Series,
    WildcardPick,
    db,
    rider_query_for_list_ui,
)
from services.results_import import (
    _WSX_NAME_ALIASES,
    _canonical_wsx_rider_name,
)


SERIES_CODE = "WSX"
CLASS_SX1 = "wsx_sx1"
CLASS_SX2 = "wsx_sx2"


def _invalidate_series_status_cache() -> None:
    """Clear homepage series-card cache without importing main at module load."""
    try:
        from services.series_status import invalidate_series_status_cache

        invalidate_series_status_cache()
    except Exception:
        pass


def _wsx_portrait_rel_for_seed(name: str | None) -> str | None:
    """Bind rider.image_url during roster seed; lazy so Flask app need not exist yet."""
    try:
        from main import _wsx_static_portrait_rel

        return _wsx_static_portrait_rel(name)
    except Exception:
        return None


def ensure_wsx_series_and_competitions():
    """Skapa WSX 2025 och dess 5 tävlingar om de inte redan finns (historik)."""
    from datetime import date as _date
    from datetime import time as _time

    wsx = Series.query.filter_by(name='WSX', year=2025).first()
    if not wsx:
        wsx = Series(
            name='WSX', year=2025,
            start_date=_date(2025, 11, 8),
            end_date=_date(2025, 12, 13),
            is_active=False, points_system='standard'
        )
        db.session.add(wsx)
        db.session.flush()
        comps = [
            ('Buenos Aires City GP', _date(2025, 11, 8), 'America/Argentina/Buenos_Aires', '13:00'),
            ('Canadian GP', _date(2025, 11, 15), 'America/Los_Angeles', None),
            ('Australian GP', _date(2025, 11, 29), 'Australia/Brisbane', None),
            ('Swedish GP', _date(2025, 12, 6), 'Europe/Stockholm', '17:00'),
            ('South African GP', _date(2025, 12, 13), 'Africa/Johannesburg', None),
        ]
        for n, d, tz, start_hhmm in comps:
            # Bind to this series_id so we never steal 2026 rows with same display name
            comp = Competition.query.filter_by(name=n, series_id=wsx.id).first()
            if comp is None:
                comp = Competition(name=n, event_date=d, series='WSX', series_id=wsx.id)
                db.session.add(comp)
            if hasattr(comp, 'timezone'):
                comp.timezone = tz
            if start_hhmm and hasattr(comp, 'start_time'):
                try:
                    hh, mm = map(int, start_hhmm.split(':'))
                    comp.start_time = _time(hour=hh, minute=mm)
                except Exception:
                    pass
        db.session.commit()
        print("[WSX-SEED] WSX 2025-serie och 5 tävlingar skapade!")
    else:
        try:
            comp = Competition.query.filter_by(name='Buenos Aires City GP', series_id=wsx.id).first()
            if comp:
                if hasattr(comp, 'timezone'):
                    comp.timezone = 'America/Argentina/Buenos_Aires'
                if hasattr(comp, 'start_time'):
                    comp.start_time = _time(hour=13, minute=0)
                db.session.commit()
        except Exception as e:
            print(f"[WSX-SEED] Failed to update BA 2025 start time: {e}")
        print("[WSX-SEED] WSX 2025-serie fanns redan!")


def ensure_wsx_2026(*, deactivate_2025: bool = True) -> dict:
    """Upsert WSX 2026 Series + GPs (official calendar from worldsupercrosschampionship.com).

    Oct 2026: remaining season cancelled after Canadian GP only — soft-cancel those rounds
    and close the series window so homepage tippa no longer advertises WSX as upcoming.
    """
    from datetime import date as _date
    from datetime import time as _time

    created_series = False
    wsx = Series.query.filter_by(name='WSX', year=2026).first()
    if not wsx:
        wsx = Series(
            name='WSX',
            year=2026,
            start_date=_date(2026, 8, 8),
            end_date=_date(2026, 8, 8),
            is_active=False,
            points_system='standard',
        )
        db.session.add(wsx)
        db.session.flush()
        created_series = True
    else:
        wsx.start_date = _date(2026, 8, 8)
        # Season ended after Canadian GP (remaining rounds cancelled Oct 2026).
        wsx.end_date = _date(2026, 8, 8)
        wsx.is_active = False

    if deactivate_2025:
        old = Series.query.filter_by(name='WSX', year=2025).first()
        if old and old.is_active:
            old.is_active = False

    # name, date|None, timezone, start_time HH:MM local (track/show start when known)
    comps_spec = [
        ('Canadian GP', _date(2026, 8, 8), 'America/Edmonton', '19:30'),  # Calgary / McMahon — only round that ran
        ('British GP', _date(2026, 10, 10), 'Europe/London', None),  # Birmingham — cancelled
        ('Buenos Aires City GP', _date(2026, 10, 24), 'America/Argentina/Buenos_Aires', None),  # cancelled
        ('Australian GP', _date(2026, 11, 21), 'Australia/Brisbane', None),  # Gold Coast — cancelled
        ('South African GP', None, 'Africa/Johannesburg', None),  # cancelled (city/date was TBA)
        ('New Zealand GP', _date(2026, 12, 5), 'Pacific/Auckland', None),  # Christchurch — cancelled
    ]
    cancelled_rounds = frozenset(
        {
            "British GP",
            "Buenos Aires City GP",
            "Australian GP",
            "South African GP",
            "New Zealand GP",
        }
    )

    created_comps = 0
    updated_comps = 0
    cancelled_comps = 0
    comp_ids = []
    for n, d, tz, start_hhmm in comps_spec:
        comp = Competition.query.filter_by(name=n, series_id=wsx.id).first()
        if comp is None:
            # Prefer a free-standing WSX row with same name and no series_id (legacy)
            orphan = (
                Competition.query.filter_by(name=n, series='WSX', series_id=None).first()
            )
            if orphan:
                comp = orphan
                comp.series_id = wsx.id
                updated_comps += 1
            else:
                comp = Competition(name=n, event_date=d, series='WSX', series_id=wsx.id)
                db.session.add(comp)
                created_comps += 1
        else:
            updated_comps += 1

        comp.series = 'WSX'
        comp.series_id = wsx.id
        if d is not None:
            comp.event_date = d
        if hasattr(comp, 'timezone') and tz:
            comp.timezone = tz
        if start_hhmm and hasattr(comp, 'start_time'):
            try:
                hh, mm = map(int, start_hhmm.split(':'))
                # Flush so setter has an id on brand-new rows
                db.session.flush()
                comp.start_time = _time(hour=hh, minute=mm)
            except Exception:
                pass
        if n in cancelled_rounds:
            if not getattr(comp, "is_cancelled", False):
                cancelled_comps += 1
            comp.is_cancelled = True
        elif n == "Canadian GP":
            comp.is_cancelled = False
        db.session.flush()
        comp_ids.append(comp.id)

    db.session.commit()
    # Homepage series cards are cached — force refresh after calendar change.
    _invalidate_series_status_cache()
    info = {
        "series_id": wsx.id,
        "year": 2026,
        "created_series": created_series,
        "created_competitions": created_comps,
        "updated_competitions": updated_comps,
        "cancelled_competitions": cancelled_comps,
        "competition_ids": comp_ids,
        "rounds": [c[0] for c in comps_spec],
        "season_concluded": True,
    }
    print(
        f"[WSX-SEED] WSX 2026 OK series_id={wsx.id} created={created_comps} "
        f"updated={updated_comps} cancelled={cancelled_comps} (season ended after Canadian GP)"
    )
    return info


# Official 2026 championship + round entry list (MX1Onboard / WSX Calgary cards, Jul 2026).
# Tuple: (name, class, number|None, brand|None, team|None)
# price is a placeholder — WSX is tippa-only (no season-team).
_WSX_2026_ROSTER = [
    # --- SX1 (Calgary line-up + season riders who may return later) ---
    ("Jason Anderson", "wsx_sx1", 21, "Suzuki", "Pipes Motorsport Group"),
    ("Colt Nichols", "wsx_sx1", 45, "Suzuki", "Pipes Motorsport Group"),
    ("Jordi Tixier", "wsx_sx1", 911, "Yamaha", "Team GSM"),
    ("Maxime Desprey", "wsx_sx1", 141, "Yamaha", "Team GSM"),
    ("Mitchell Harrison", "wsx_sx1", 41, "Kawasaki", "Venum Bud Racing Kawasaki"),
    ("Luke Clout", "wsx_sx1", 4, "Kawasaki", "Venum Bud Racing Kawasaki"),
    ("Cooper Webb", "wsx_sx1", 2, "Yamaha", "Rick Ware Racing"),
    ("Justin Hill", "wsx_sx1", 46, "Yamaha", "Rick Ware Racing"),
    ("Austin Politelli", "wsx_sx1", 98, "Honda", "MotoConcepts Racing"),
    ("Michael Alessi", "wsx_sx1", 800, "Honda", "MotoConcepts Racing"),  # Canadian GP
    ("Dean Wilson", "wsx_sx1", 15, "Honda", "Fire Power Honda / KMG"),
    ("Christian Craig", "wsx_sx1", 28, "Honda", "Fire Power Honda / KMG"),
    ("Vince Friese", "wsx_sx1", 719, "Stark", "Stark Racing"),
    ("Jorge Zaragoza", "wsx_sx1", 99, "Stark", "Stark Racing"),
    ("Greg Aranda", "wsx_sx1", 20, "KTM", "595 Racing"),
    ("Kevin Moranz", "wsx_sx1", 78, "KTM", "595 Racing"),
    # Season / later rounds (OUT for Calgary if not on gate)
    ("Joey Savatgy", "wsx_sx1", 17, "Honda", "Quad Lock Honda"),
    ("Enzo Lopes", "wsx_sx1", 16, "Honda", "MotoConcepts Racing"),
    ("Tom Vialle", "wsx_sx1", None, "KTM", "Red Bull KTM"),  # British GP SX1 wildcard
    # --- SX2 Calgary line-up ---
    ("Max Anstie", "wsx_sx2", 1, "Honda", "Fire Power Honda"),
    ("Devin Simonson", "wsx_sx2", 70, "Honda", "Fire Power Honda"),
    ("Crockett Myers", "wsx_sx2", 411, "Suzuki", "Pipes Motorsport Group"),
    ("Kyle Peters", "wsx_sx2", 110, "Suzuki", "Pipes Motorsport Group"),
    ("Cole Thompson", "wsx_sx2", 16, "Yamaha", "Team GSM"),
    ("Calvin Fonvieille", "wsx_sx2", 11, "Yamaha", "Team GSM"),
    ("Henry Miller", "wsx_sx2", 29, "Kawasaki", "Venum Bud Racing Kawasaki"),
    ("Jack Chambers", "wsx_sx2", 69, "Kawasaki", "Venum Bud Racing Kawasaki"),
    ("Ryan Breece", "wsx_sx2", 200, "Honda", "MotoConcepts Racing"),
    ("Robbie Wageman", "wsx_sx2", 237, "Honda", "MotoConcepts Racing"),
    ("Cameron McAdoo", "wsx_sx2", 142, "Honda", "KMG"),
    ("Brodie Connolly", "wsx_sx2", 88, "Honda", "KMG"),
    ("Michael Hicks", "wsx_sx2", 460, "Stark", "Stark Racing"),
    ("Brian Hsu", "wsx_sx2", 84, "Stark", "Stark Racing"),
    ("Nico Koch", "wsx_sx2", 262, "KTM", "595 Racing"),
    ("Luke Fauser", "wsx_sx2", 462, "KTM", "595 Racing"),
    # Season / later rounds (OUT for Calgary if not on gate)
    ("Shane McElrath", "wsx_sx2", 12, "Honda", "Quad Lock Honda"),
    ("Jake Cannon", "wsx_sx2", 3, "Kawasaki", "Venum Bud Racing Kawasaki"),
    ("Hector Assunção", "wsx_sx2", 4, "KTM", "595 Racing"),
]

# Calgary Canadian GP gate lists (official SX1/SX2 Calgary line-up cards).
_WSX_CANADIAN_GP_SX1 = {
    "Jason Anderson",
    "Colt Nichols",
    "Jordi Tixier",
    "Maxime Desprey",
    "Mitchell Harrison",
    "Luke Clout",
    "Cooper Webb",
    "Justin Hill",
    "Austin Politelli",
    "Michael Alessi",
    "Dean Wilson",
    "Christian Craig",
    "Vince Friese",
    "Jorge Zaragoza",
    "Greg Aranda",
    "Kevin Moranz",
}
_WSX_CANADIAN_GP_SX2 = {
    "Max Anstie",
    "Devin Simonson",
    "Crockett Myers",
    "Kyle Peters",
    "Cole Thompson",
    "Calvin Fonvieille",
    "Henry Miller",
    "Jack Chambers",
    "Ryan Breece",
    "Robbie Wageman",
    "Cameron McAdoo",
    "Brodie Connolly",
    "Michael Hicks",
    "Brian Hsu",
    "Nico Koch",
    "Luke Fauser",
}

# Round fill-ins / wildcards (not full-season championship seats for that GP).
# Shown with a small WC badge next to the tippa portrait.
_WSX_ROUND_WILDCARDS = {
    "Canadian GP": {
        "Michael Alessi",  # fill-in for Enzo Lopes
        "Dean Wilson",  # fill-in for Joey Savatgy
        "Jack Chambers",  # fill-in for Jake Cannon
        "Luke Fauser",  # fill-in for Hector Assunção
    },
    "British GP": {
        "Tom Vialle",  # SX1 wildcard debut (Birmingham)
    },
}


# Wildcards who only tippa on listed GPs (OUT on all other WSX 2026 rounds).
_WSX_ROUND_ONLY_WILDCARDS = {
    "Tom Vialle": frozenset({"British GP"}),
}


def _wsx_wildcard_names_for_competition(comp: Competition | None) -> set[str]:
    if not comp or (getattr(comp, "series", None) or "").upper() != "WSX":
        return set()
    return set(_WSX_ROUND_WILDCARDS.get((comp.name or "").strip(), set()))


_WSX_VENUE_BY_NAME = {
    "Canadian GP": "Calgary — McMahon Stadium",
    "British GP": "Birmingham — Alexander Stadium",
    "Buenos Aires City GP": "Buenos Aires — Oscar & Juan Gálvez",
    "Australian GP": "Gold Coast — Cbus Super Stadium",
    "South African GP": "TBA",
    "New Zealand GP": "Christchurch — One NZ Stadium",
}

# Names that moved class or left the championship grid — drop from tippa lists.
_WSX_2026_RETIRED_FROM_GRID = {
    "Coty Schock",  # RWR SX2 seat taken by Max Anstie
    # 2025 leftovers still stored as wsx_sx* in DB — never tippa for 2026
    "Ken Roczen",
    "Eli Tomac",
    "Haiden Deegan",
    "Justin Cooper",
    "Matt Moss",
    "Anthony Bourdon",
    "Kyle Chisholm",
    "Cullin Park",
    "Noah Viney",
    "Lance Kobusch",
}

_WSX_2026_ROSTER_NAMES_BY_CLASS = {
    "wsx_sx1": {name for name, class_name, *_ in _WSX_2026_ROSTER if class_name == "wsx_sx1"},
    "wsx_sx2": {name for name, class_name, *_ in _WSX_2026_ROSTER if class_name == "wsx_sx2"},
}


def wsx_roster_query(class_name: str):
    """Query only the currently official WSX 2026 roster for the given class."""
    names = _WSX_2026_ROSTER_NAMES_BY_CLASS.get(class_name, set())
    return rider_query_for_list_ui().filter_by(class_name=class_name).filter(Rider.name.in_(names))


def _wsx_official_roster_ids() -> set[int]:
    ids: set[int] = set()
    for cls in ("wsx_sx1", "wsx_sx2"):
        for (rid,) in (
            db.session.query(Rider.id)
            .filter(
                Rider.class_name == cls,
                Rider.name.in_(_WSX_2026_ROSTER_NAMES_BY_CLASS.get(cls, set())),
            )
            .all()
        ):
            ids.add(int(rid))
    return ids


def prune_off_roster_wsx_picks(competition_id: int) -> dict[str, int]:
    """
    Ta bort tippa/holeshot-val på WSX-tävlingar som pekar på förare utanför 2026-rostern
    (t.ex. Ken Roczen kvar från 2025).
    """
    comp = Competition.query.get(int(competition_id))
    if not comp or (getattr(comp, "series", None) or "").upper() != "WSX":
        return {"deleted_race": 0, "deleted_hs": 0, "skipped": 1}

    # Bevara historik för tidigare säsonger (t.ex. WSX 2025)
    year = None
    try:
        if getattr(comp, "series_id", None):
            series = Series.query.get(comp.series_id)
            if series and series.year:
                year = int(series.year)
    except Exception:
        year = None
    if year is None and getattr(comp, "event_date", None):
        year = int(comp.event_date.year)
    if year is not None and year < 2026:
        return {"deleted_race": 0, "deleted_hs": 0, "skipped": 1}

    allowed = _wsx_official_roster_ids()
    if not allowed:
        return {"deleted_race": 0, "deleted_hs": 0, "skipped": 1}

    deleted_race = (
        RacePick.query.filter(
            RacePick.competition_id == int(competition_id),
            ~RacePick.rider_id.in_(allowed),
        ).delete(synchronize_session=False)
        or 0
    )
    deleted_hs = (
        HoleshotPick.query.filter(
            HoleshotPick.competition_id == int(competition_id),
            ~HoleshotPick.rider_id.in_(allowed),
        ).delete(synchronize_session=False)
        or 0
    )
    # Wildcard finns inte på WSX — städa om gamla rader hängt kvar
    deleted_wc = (
        WildcardPick.query.filter_by(competition_id=int(competition_id)).delete(
            synchronize_session=False
        )
        or 0
    )
    if deleted_race or deleted_hs or deleted_wc:
        db.session.commit()
    return {
        "deleted_race": int(deleted_race),
        "deleted_hs": int(deleted_hs),
        "deleted_wc": int(deleted_wc),
        "skipped": 0,
    }


def _remap_wsx_rider_refs(old_id: int, new_id: int) -> int:
    """Flytta FK-referenser från orphan WSX-rad till kanonisk roster-rad."""
    if old_id == new_id:
        return 0
    moved = 0

    # OUT-status: undvik unik-krock per (competition_id, rider_id)
    for row in CompetitionRiderStatus.query.filter_by(rider_id=old_id).all():
        existing = CompetitionRiderStatus.query.filter_by(
            competition_id=row.competition_id, rider_id=new_id
        ).first()
        if existing:
            db.session.delete(row)
        else:
            row.rider_id = new_id
            moved += 1

    for model in (RacePick, HoleshotPick, WildcardPick, CompetitionResult, HoleshotResult):
        for row in model.query.filter_by(rider_id=old_id).all():
            # CompetitionResult / picks kan ha unikhet per rider — uppdatera om möjligt
            try:
                row.rider_id = new_id
                moved += 1
            except Exception:
                db.session.delete(row)

    try:
        for row in SeasonTeamRider.query.filter_by(rider_id=old_id).all():
            existing = SeasonTeamRider.query.filter_by(
                season_team_id=row.season_team_id, rider_id=new_id
            ).first()
            if existing:
                db.session.delete(row)
            else:
                row.rider_id = new_id
                moved += 1
    except Exception:
        pass

    return moved


def _merge_wsx_name_aliases() -> dict:
    """
    Slå ihop typo-rader (Jason Andersson → Jason Anderson) innan delete,
    så CompetitionResult inte blir rider_id=NULL.
    """
    merged = 0
    deleted = 0
    remapped = 0
    for typo, canon in _WSX_NAME_ALIASES.items():
        typo_rows = (
            Rider.query.filter(
                Rider.name == typo,
                Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
            ).all()
        )
        # Also catch case-only variants (Cameron Mcadoo vs Cameron McAdoo)
        if not typo_rows:
            typo_rows = (
                Rider.query.filter(
                    Rider.name.ilike(typo),
                    Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                )
                .all()
            )
            typo_rows = [r for r in typo_rows if (r.name or "") != canon]
        for row in typo_rows:
            keeper = Rider.query.filter_by(
                name=canon, class_name=row.class_name
            ).first()
            if keeper is None:
                keeper = (
                    Rider.query.filter(
                        Rider.name.ilike(canon),
                        Rider.class_name == row.class_name,
                    ).first()
                )
            if keeper is None:
                row.name = canon
                merged += 1
                continue
            if int(keeper.id) == int(row.id):
                if (row.name or "") != canon:
                    row.name = canon
                    merged += 1
                continue
            remapped += _remap_wsx_rider_refs(int(row.id), int(keeper.id))
            db.session.delete(row)
            deleted += 1
            merged += 1
    if merged or deleted or remapped:
        db.session.commit()
    return {"merged": merged, "deleted": deleted, "remapped": remapped}


def _repair_orphaned_wsx_p1_results() -> dict:
    """
    Återkoppla WSX P1-resultat där föraren raderats (rider_id NULL).
    Vanlig orsak: typo-rad Jason Andersson raderades utan remap.
    """
    fixed = 0
    removed = 0
    orphans = (
        CompetitionResult.query.filter(CompetitionResult.rider_id.is_(None))
        .filter(CompetitionResult.position == 1)
        .filter(CompetitionResult.class_name.in_(("wsx_sx1", "wsx_sx2")))
        .all()
    )
    for row in orphans:
        cls = (row.class_name or "").strip()
        # Finns redan en giltig P1 i klassen? Ta bort orphan-dubblett.
        existing = (
            db.session.query(CompetitionResult)
            .join(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == row.competition_id)
            .filter(CompetitionResult.position == 1)
            .filter(
                db.func.coalesce(CompetitionResult.class_name, Rider.class_name) == cls
            )
            .first()
        )
        if existing:
            db.session.delete(row)
            removed += 1
            continue

        keeper = None
        if cls == "wsx_sx1":
            keeper = Rider.query.filter_by(
                name="Jason Anderson", class_name="wsx_sx1"
            ).first()
        if keeper is None:
            continue
        row.rider_id = int(keeper.id)
        fixed += 1

    if fixed or removed:
        db.session.commit()
    return {"fixed": fixed, "removed": removed}


def _dedupe_wsx_roster_riders() -> dict:
    """
    Ta bort felklassade/duplicerade WSX-rader (t.ex. Crockett Myers som wsx_sx1 orphan
    medan tippa använder wsx_sx2 #411). Remappar OUT/picks till kanonisk rad.
    """
    merged = 0
    deleted = 0
    remapped = 0
    official_names = _WSX_2026_ROSTER_NAMES_BY_CLASS["wsx_sx1"] | _WSX_2026_ROSTER_NAMES_BY_CLASS["wsx_sx2"]
    target_class_by_name = {
        name: class_name for name, class_name, *_ in _WSX_2026_ROSTER
    }
    target_number_by_name = {
        name: number for name, _cls, number, *_ in _WSX_2026_ROSTER
    }

    for name in sorted(official_names):
        target_cls = target_class_by_name.get(name)
        if not target_cls:
            continue
        rows = (
            Rider.query.filter(
                Rider.name == name,
                Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
            )
            .order_by(Rider.id.asc())
            .all()
        )
        if len(rows) <= 1:
            # En rad men fel klass → reclassa
            if len(rows) == 1 and rows[0].class_name != target_cls:
                rows[0].class_name = target_cls
                merged += 1
            continue

        # Prefer correct class + matching number
        want_num = target_number_by_name.get(name)
        keeper = None
        for r in rows:
            if r.class_name == target_cls and (
                want_num is None or r.rider_number == want_num
            ):
                keeper = r
                break
        if keeper is None:
            for r in rows:
                if r.class_name == target_cls:
                    keeper = r
                    break
        if keeper is None:
            keeper = rows[0]
            keeper.class_name = target_cls

        for extra in rows:
            if extra.id == keeper.id:
                continue
            remapped += _remap_wsx_rider_refs(int(extra.id), int(keeper.id))
            db.session.delete(extra)
            deleted += 1
            merged += 1

    if merged or deleted or remapped:
        db.session.commit()
    return {"merged": merged, "deleted": deleted, "remapped": remapped}


def ensure_wsx_2026_roster() -> dict:
    """Create/update WSX SX1/SX2 riders; reclassify if a rider changed class."""
    created = 0
    updated = 0
    reclassed = 0
    for name, class_name, number, brand, team in _WSX_2026_ROSTER:
        rider = Rider.query.filter_by(name=name, class_name=class_name).first()
        if rider is None:
            # Case / spelling variants already in DB (e.g. Cameron Mcadoo)
            canon = _canonical_wsx_rider_name(name) or name
            rider = (
                Rider.query.filter(
                    Rider.name.ilike(name),
                    Rider.class_name == class_name,
                ).first()
            )
            if rider is None and canon != name:
                rider = (
                    Rider.query.filter(
                        Rider.name.ilike(canon),
                        Rider.class_name == class_name,
                    ).first()
                )
            if rider is not None:
                if (rider.name or "") != name:
                    rider.name = name
                    reclassed += 1
            else:
                # Same person may already exist in the other WSX class
                other = (
                    Rider.query.filter(
                        Rider.name == name,
                        Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                    ).first()
                )
                if other is None:
                    other = (
                        Rider.query.filter(
                            Rider.name.ilike(name),
                            Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                        ).first()
                    )
                if other:
                    other.class_name = class_name
                    other.name = name
                    rider = other
                    reclassed += 1
                else:
                    wsx_rel = _wsx_portrait_rel_for_seed(name)
                    rider = Rider(
                        name=name,
                        class_name=class_name,
                        rider_number=number,
                        bike_brand=brand or None,
                        manufacturer=brand or None,
                        team=team or None,
                        price=100000,
                        series_participation="wsx",
                        image_url=wsx_rel,
                    )
                    db.session.add(rider)
                    created += 1
                    continue

        changed = False
        if (rider.name or "") != name:
            rider.name = name
            changed = True
        if number is not None and rider.rider_number != number:
            rider.rider_number = number
            changed = True
        if brand and rider.bike_brand != brand:
            rider.bike_brand = brand
            changed = True
        if brand and getattr(rider, "manufacturer", None) != brand:
            rider.manufacturer = brand
            changed = True
        if team and rider.team != team:
            rider.team = team
            changed = True
        if getattr(rider, "series_participation", None) != "wsx":
            rider.series_participation = "wsx"
            changed = True
        # Bind local WSX card path when file exists (keeps tippa/spotlight off brand logos)
        wsx_rel = _wsx_portrait_rel_for_seed(name)
        if wsx_rel and (getattr(rider, "image_url", None) or "").strip() != wsx_rel:
            rider.image_url = wsx_rel
            changed = True
        if changed:
            updated += 1

    db.session.commit()
    # Alias merge + orphan P1 repair before class dedupe
    alias_info = {"merged": 0, "deleted": 0, "remapped": 0}
    orphan_info = {"fixed": 0, "removed": 0}
    try:
        alias_info = _merge_wsx_name_aliases()
    except Exception as alias_err:
        db.session.rollback()
        print(f"[WSX-SEED] alias merge skipped: {alias_err}")
    try:
        orphan_info = _repair_orphaned_wsx_p1_results()
    except Exception as orphan_err:
        db.session.rollback()
        print(f"[WSX-SEED] orphan P1 repair skipped: {orphan_err}")
    # Dedupe is best-effort: never fail the whole roster upsert if remap hits a constraint.
    dedupe = {"merged": 0, "deleted": 0, "remapped": 0, "skipped": False}
    try:
        dedupe = _dedupe_wsx_roster_riders()
    except Exception as dedupe_err:
        db.session.rollback()
        dedupe = {
            "merged": 0,
            "deleted": 0,
            "remapped": 0,
            "skipped": True,
            "error": str(dedupe_err),
        }
        print(f"[WSX-SEED] roster dedupe skipped: {dedupe_err}")
    sx1 = Rider.query.filter_by(class_name="wsx_sx1").count()
    sx2 = Rider.query.filter_by(class_name="wsx_sx2").count()
    info = {
        "created": created,
        "updated": updated,
        "reclassed": reclassed,
        "aliases": alias_info,
        "orphan_p1": orphan_info,
        "deduped": dedupe,
        "wsx_sx1": sx1,
        "wsx_sx2": sx2,
        "roster_size": len(_WSX_2026_ROSTER),
    }
    print(
        f"[WSX-SEED] roster created={created} updated={updated} "
        f"reclassed={reclassed} aliases={alias_info} orphan_p1={orphan_info} "
        f"dedupe={dedupe} sx1={sx1} sx2={sx2}"
    )
    return info


def sync_wsx_canadian_gp_entry_list() -> dict:
    """
    Markera roster-förare som inte står på Calgary-grinden som OUT för Canadian GP 2026.
    Rör bara den tävlingen (säsongsförare kan tippas i senare GP).
    Gate-förare som råkat vara OUT rensas.
    """
    wsx = Series.query.filter_by(name="WSX", year=2026).first()
    if not wsx:
        return {"skipped": True, "reason": "no_wsx_2026"}

    comp = Competition.query.filter_by(name="Canadian GP", series_id=wsx.id).first()
    if not comp:
        return {"skipped": True, "reason": "no_canadian_gp"}

    gate = _WSX_CANADIAN_GP_SX1 | _WSX_CANADIAN_GP_SX2
    gate_lower = {n.lower() for n in gate}
    marked_out = 0
    cleared = 0
    cleared_stray = 0

    roster_riders = (
        Rider.query.filter(
            Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
            Rider.name.in_(_WSX_2026_ROSTER_NAMES_BY_CLASS["wsx_sx1"]
                           | _WSX_2026_ROSTER_NAMES_BY_CLASS["wsx_sx2"]),
        ).all()
    )

    for rider in roster_riders:
        on_gate = (rider.name or "") in gate
        row = CompetitionRiderStatus.query.filter_by(
            competition_id=comp.id, rider_id=rider.id
        ).first()
        if on_gate:
            if row:
                db.session.delete(row)
                cleared += 1
            continue
        if not row:
            db.session.add(
                CompetitionRiderStatus(
                    competition_id=comp.id, rider_id=rider.id, status="OUT"
                )
            )
            marked_out += 1
        elif row.status != "OUT":
            row.status = "OUT"
            marked_out += 1

    # AMA/SX-rader med samma namn får inte ligga som OUT på WSX-GP
    # (tippa mappade tidigare OUT via namn och gömde t.ex. Cameron McAdoo).
    for row in list(
        CompetitionRiderStatus.query.filter_by(
            competition_id=comp.id, status="OUT"
        ).all()
    ):
        rider = Rider.query.get(row.rider_id)
        if not rider:
            db.session.delete(row)
            cleared_stray += 1
            continue
        cls = (rider.class_name or "")
        if cls in ("wsx_sx1", "wsx_sx2"):
            continue
        if (rider.name or "").strip().lower() in gate_lower:
            db.session.delete(row)
            cleared_stray += 1

    if marked_out or cleared or cleared_stray:
        db.session.commit()

    try:
        prune_off_roster_wsx_picks(int(comp.id))
    except Exception as prune_err:
        print(f"[WSX-SEED] Canadian GP pick prune skipped: {prune_err}")

    info = {
        "competition_id": int(comp.id),
        "gate_size": len(gate),
        "marked_out": marked_out,
        "cleared": cleared,
        "cleared_stray_ama_out": cleared_stray,
        "skipped": False,
    }
    print(
        f"[WSX-SEED] Canadian GP entry list: out={marked_out} cleared={cleared} "
        f"stray={cleared_stray} gate={len(gate)} comp_id={comp.id}"
    )
    return info


def sync_wsx_round_only_wildcards() -> dict:
    """
    Round-only wildcards (t.ex. Tom Vialle @ British GP): tippa bara på listade GP.
    Markeras OUT på övriga WSX 2026-omgångar; OUT rensas på deras GP.
    """
    wsx = Series.query.filter_by(name="WSX", year=2026).first()
    if not wsx:
        return {"skipped": True, "reason": "no_wsx_2026"}
    if not _WSX_ROUND_ONLY_WILDCARDS:
        return {"skipped": True, "reason": "none"}

    comps = Competition.query.filter_by(series_id=wsx.id).all()
    if not comps:
        return {"skipped": True, "reason": "no_comps"}

    marked_out = 0
    cleared = 0
    missing = []

    for name, allowed in _WSX_ROUND_ONLY_WILDCARDS.items():
        rider = (
            Rider.query.filter(
                Rider.name == name,
                Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
            ).first()
        )
        if not rider:
            missing.append(name)
            continue
        allowed_names = {str(x).strip() for x in allowed}
        for comp in comps:
            on_round = (comp.name or "").strip() in allowed_names
            row = CompetitionRiderStatus.query.filter_by(
                competition_id=comp.id, rider_id=rider.id
            ).first()
            if on_round:
                if row:
                    db.session.delete(row)
                    cleared += 1
                continue
            if not row:
                db.session.add(
                    CompetitionRiderStatus(
                        competition_id=comp.id, rider_id=rider.id, status="OUT"
                    )
                )
                marked_out += 1
            elif row.status != "OUT":
                row.status = "OUT"
                marked_out += 1

    if marked_out or cleared:
        db.session.commit()

    info = {
        "marked_out": marked_out,
        "cleared": cleared,
        "missing_riders": missing,
        "skipped": False,
    }
    print(
        f"[WSX-SEED] round-only wildcards: out={marked_out} cleared={cleared} "
        f"missing={missing}"
    )
    return info

