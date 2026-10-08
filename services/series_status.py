"""Homepage series-status cards + cache (skiva 20)."""
from __future__ import annotations

import time
from collections import defaultdict

from ama_season_totals import AMA_TOTAL_SERIES_NAME
from models import Competition, CompetitionResult, GlobalSimulation, Series, db
from services.picks_lock import (
    is_picks_locked,
    is_picks_preseason_locked,
    picks_preseason_opens_on,
)


_SERIES_STATUS_CACHE: tuple[float, list] | None = None
_SERIES_STATUS_CACHE_TTL = 120.0


def _main():
    import main as _m

    return _m


def invalidate_series_status_cache() -> None:
    global _SERIES_STATUS_CACHE
    _SERIES_STATUS_CACHE = None


def _upcoming_competitions_without_results() -> dict[str, list[Competition]]:
    """Framtida tävlingar utan resultat, grupperade per series-kod (en DB-pass)."""
    today = _main().get_today()
    result_comp_ids = {
        int(row[0])
        for row in db.session.query(CompetitionResult.competition_id).distinct().all()
        if row[0] is not None
    }
    comps = (
        Competition.query.filter(Competition.event_date.isnot(None))
        .filter(Competition.event_date >= today)
        .order_by(Competition.event_date.asc(), Competition.id.asc())
        .all()
    )
    grouped: dict[str, list[Competition]] = defaultdict(list)
    for comp in comps:
        if getattr(comp, "is_cancelled", False):
            continue
        if comp.id in result_comp_ids:
            continue
        code = (comp.series or "").strip()
        if code:
            grouped[code].append(comp)
    return grouped

def _pick_next_competition(
    candidates: list[Competition],
    *,
    require_open: bool,
) -> Competition | None:
    for comp in candidates:
        if require_open and is_picks_locked(comp):
            continue
        return comp
    return None

def build_series_status_list() -> list[dict]:
    """Seriekort för startsidan — cachad, undviker upprepade fullskanningar."""
    global _SERIES_STATUS_CACHE
    now = time.time()
    if _SERIES_STATUS_CACHE and _SERIES_STATUS_CACHE[0] > now:
        return _SERIES_STATUS_CACHE[1]

    from sqlalchemy import or_, and_

    current_date = _main().get_today()
    all_series = Series.query.filter(
        or_(
            Series.year.in_((2026, 2027)),
            and_(Series.year == 2025, Series.end_date != None, Series.end_date >= current_date),
        )
    ).all()

    # Tie-break only — real card order is next-race / finished-last in _series_sort_key
    series_order = {
        "Supercross": 1,
        "Motocross": 2,
        "SMX Finals": 3,
        "WSX": 4,
        "MXGP": 5,
        "MXON": 6,
        "MXoN": 6,
    }
    all_series.sort(key=lambda s: series_order.get(s.name, 999))

    simulation_active = False
    try:
        simulation_active = (
            GlobalSimulation.query.filter_by(id=1, active=True).first() is not None
        )
    except Exception:
        simulation_active = False

    upcoming_by_series = _upcoming_competitions_without_results()
    series_data: list[dict] = []

    for s in all_series:
        # Synthetic AMA Total belongs on Finished series / totals — not homepage "Välj Serie".
        if (s.name or "").strip() == AMA_TOTAL_SERIES_NAME:
            continue
        # One MXGP homepage card only (2027 UC). Keep 2026 series in DB for calendar/admin.
        if s.name == "MXGP" and int(getattr(s, "year", 0) or 0) != 2027:
            continue
        # AMA tippa: once next year's Series exists, drop prior year from Välj Serie
        # (finished seasons live in Fantasy-arkiv — not as Avslutad/Startar-om twins).
        if s.name in ("Supercross", "Motocross", "SMX Finals"):
            sy = int(getattr(s, "year", 0) or 0)
            if sy and any(
                (o.name == s.name)
                and int(getattr(o, "year", 0) or 0) > sy
                for o in all_series
            ):
                continue

        series_code = None
        if s.name == "Supercross":
            series_code = "SX"
        elif s.name == "Motocross":
            series_code = "MX"
        elif s.name == "SMX Finals":
            series_code = "SMX"
        elif s.name == "WSX":
            series_code = "WSX"
        elif s.name in ("MXON", "MXoN"):
            series_code = "MXON"
        elif s.name == "MXGP":
            series_code = "MXGP"

        series_year = int(getattr(s, "year", 0) or 0)

        def _candidates_for_this_series(code: str) -> list:
            raw = upcoming_by_series.get(code, [])
            # Prefer series_id match so 2026 cards never steal 2027 races
            by_id = [c for c in raw if getattr(c, "series_id", None) == s.id]
            if by_id:
                return by_id
            if series_year:
                return [
                    c
                    for c in raw
                    if getattr(c, "event_date", None) is not None
                    and c.event_date.year == series_year
                ]
            return []

        next_race = None
        if series_code:
            candidates = _candidates_for_this_series(series_code)
            next_race = _pick_next_competition(candidates, require_open=True)
            if not next_race:
                next_race = _pick_next_competition(candidates, require_open=False)
        if not next_race:
            next_race = next(
                (
                    c
                    for c in (
                        Competition.query.filter_by(series_id=s.id)
                        .filter(Competition.event_date >= current_date)
                        .order_by(Competition.event_date)
                        .all()
                    )
                    if not getattr(c, "is_cancelled", False)
                ),
                None,
            )

        under_construction = False
        if series_code == "MXGP":
            try:
                from mxgp_fantasy import (
                    ADMIN_TEST_GP_NAME,
                    mxgp_public_play_enabled,
                )

                under_construction = not mxgp_public_play_enabled()
                # Public card: never advertise Admin Test GP as "next race"
                # (it sorted MXGP above live WSX while UC).
                if next_race and getattr(next_race, "name", None) == ADMIN_TEST_GP_NAME:
                    next_race = None
                if under_construction:
                    real_upcoming = [
                        c
                        for c in _candidates_for_this_series("MXGP")
                        if getattr(c, "name", None) != ADMIN_TEST_GP_NAME
                        and not getattr(c, "is_cancelled", False)
                    ]
                    next_race = _pick_next_competition(real_upcoming, require_open=False)
                    if not next_race:
                        next_race = next(
                            (
                                c
                                for c in (
                                    Competition.query.filter_by(series="MXGP")
                                    .filter(Competition.event_date >= current_date)
                                    .order_by(Competition.event_date)
                                    .all()
                                )
                                if not getattr(c, "is_cancelled", False)
                                and getattr(c, "name", None) != ADMIN_TEST_GP_NAME
                                and (
                                    getattr(c, "series_id", None) == s.id
                                    or (
                                        getattr(c, "event_date", None) is not None
                                        and c.event_date.year == series_year
                                    )
                                )
                            ),
                            None,
                        )
            except Exception:
                under_construction = True

        # Playable/active for UI: not past end_date, and either inside the window
        # or already has an upcoming race (so preseason tippa works — e.g. WSX before R01).
        if under_construction:
            is_currently_active = True
        elif not simulation_active:
            if s.end_date and current_date > s.end_date and next_race is None:
                is_currently_active = False
            elif s.end_date and current_date > s.end_date:
                # Season window over — only stay "active" if this series_id still has races
                is_currently_active = False
            elif next_race is not None:
                is_currently_active = True
            elif s.start_date and s.end_date:
                is_currently_active = s.start_date <= current_date <= s.end_date
            elif s.start_date:
                is_currently_active = current_date >= s.start_date
            else:
                is_currently_active = bool(s.is_active)
        else:
            is_currently_active = bool(s.is_active)

        days_until_next_race = None
        if next_race and next_race.event_date:
            days_until_next_race = (next_race.event_date - current_date).days

        days_until_start = None
        if s.start_date:
            days_until_start = (s.start_date - current_date).days

        picks_opens_on = None
        picks_preseason = False
        days_until_picks_open = None
        if next_race is not None:
            try:
                picks_preseason = is_picks_preseason_locked(next_race)
                opens = picks_preseason_opens_on(next_race)
                if opens:
                    picks_opens_on = opens.isoformat()
                    days_until_picks_open = (opens - current_date).days
            except Exception:
                picks_preseason = False

        # Finished seasons without upcoming races belong in Fantasy-arkiv, not Välj Serie.
        # Exception: MXoN stays selectable so the home topplista remains after archive.
        if (
            not under_construction
            and not is_currently_active
            and next_race is None
            and s.end_date
            and current_date > s.end_date
            and series_code != "MXON"
        ):
            continue

        series_data.append(
            {
                "id": s.id,
                "name": s.name,
                "year": series_year or None,
                "series_code": series_code,
                "is_active": is_currently_active,
                "under_construction": under_construction,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "days_until_start": days_until_start,
                "days_until_next_race": days_until_next_race,
                "picks_preseason_locked": picks_preseason,
                "picks_opens_on": picks_opens_on,
                "days_until_picks_open": days_until_picks_open,
                "next_race": (
                    {
                        "id": next_race.id,
                        "name": next_race.name,
                        "date": next_race.event_date.isoformat(),
                    }
                    if next_race
                    else None
                ),
            }
        )

    def _series_family_key(item: dict) -> str:
        name = (item.get("name") or "").strip()
        if name in ("MXON", "MXoN"):
            return "MXON"
        return name

    def _prefer_series_card(a: dict, b: dict) -> dict:
        """One card per family: current season over finished, sooner next race over later."""
        if bool(a.get("under_construction")) != bool(b.get("under_construction")):
            return b if a.get("under_construction") else a
        if bool(a.get("is_active")) != bool(b.get("is_active")):
            return a if a.get("is_active") else b
        da = a.get("days_until_next_race")
        db_ = b.get("days_until_next_race")
        a_has = isinstance(da, int) and da >= 0
        b_has = isinstance(db_, int) and db_ >= 0
        if a_has and b_has and da != db_:
            return a if da < db_ else b
        if a_has != b_has:
            return a if a_has else b
        ya = int(a.get("year") or 0)
        yb = int(b.get("year") or 0)
        if ya != yb:
            # Prefer the season that hasn't started yet over a finished twin,
            # else the higher (upcoming) year.
            return a if ya > yb else b
        return a

    # Deduplicate SX/MX/SMX (and peers) when both 2026 and 2027 rows exist
    best_by_family: dict[str, dict] = {}
    for item in series_data:
        key = _series_family_key(item)
        prev = best_by_family.get(key)
        best_by_family[key] = item if prev is None else _prefer_series_card(prev, item)
    series_data = list(best_by_family.values())

    # Sort: soonest next race first; under-construction teasers next; finished last.
    def _series_sort_key(item: dict):
        d = item.get("days_until_next_race")
        name = item.get("name") or ""
        tie = series_order.get(name, 999)
        if isinstance(d, int) and d >= 0:
            return (0, d, tie)
        if item.get("is_active"):
            return (1, 0, tie)
        until_start = item.get("days_until_start")
        if isinstance(until_start, int) and until_start > 0:
            return (2, until_start, tie)
        if item.get("under_construction"):
            return (3, 0, tie)
        return (4, 9999, tie)

    series_data.sort(key=_series_sort_key)

    _SERIES_STATUS_CACHE = (now + _SERIES_STATUS_CACHE_TTL, series_data)
    return series_data
