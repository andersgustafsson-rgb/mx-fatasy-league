"""AMA / SMX series seed helpers (refactor skiva 9).

Idempotent boot/admin utilities for 2026 series dates + SMX competition meta,
plus a single orchestrator for the AMA/SMX boot chain. 2027 calendar stays in
`ama_2027_calendar.py`; official standings overlays stay in `official_smx_2026.py`.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from datetime import time as dt_time
from typing import Any, Callable


def ensure_ama_2026_series_dates() -> dict:
    """Keep Motocross/SMX 2026 end dates aligned with finales (Ironman / Ridgedale).

    Prevents Motocross from showing under Fantasy-arkiv before Ironman is done
    when series.end_date was wrongly set to Budds Creek (23 aug).
    """
    from models import Competition, Series, db

    changed: list[str] = []

    def _max_event_date(series_row: Series | None, series_code: str, year: int):
        """Max event_date for this series year only (never bleed into next season)."""
        q = Competition.query.filter(
            db.func.upper(db.func.coalesce(Competition.series, "")) == series_code,
            Competition.event_date >= _date(year, 1, 1),
            Competition.event_date <= _date(year, 12, 31),
        )
        if series_row is not None:
            q = q.filter(Competition.series_id == series_row.id)
        return q.with_entities(db.func.max(Competition.event_date)).scalar()

    mx = Series.query.filter_by(name="Motocross", year=2026).first()
    if mx:
        ironman_end = _date(2026, 8, 29)
        target_end = _max_event_date(mx, "MX", 2026) or ironman_end
        if target_end < ironman_end:
            target_end = ironman_end
        # Cap hard at 2026 — never pull 2027 nationals into 2026 series meta
        if target_end.year != 2026:
            target_end = ironman_end
        if mx.end_date != target_end or not mx.is_active:
            mx.end_date = target_end
            mx.is_active = True
            changed.append(f"Motocross.end_date={target_end.isoformat()}")

    smx = Series.query.filter_by(name="SMX Finals", year=2026).first()
    if smx:
        final_end = _date(2026, 9, 26)
        target_end = _max_event_date(smx, "SMX", 2026) or final_end
        if target_end < final_end:
            target_end = final_end
        if target_end.year != 2026:
            target_end = final_end
        if smx.end_date != target_end or not smx.is_active:
            smx.end_date = target_end
            smx.is_active = True
            changed.append(f"SMX Finals.end_date={target_end.isoformat()}")

    if changed:
        db.session.commit()
        print(f"[SERIES] AMA 2026 dates fixed: {', '.join(changed)}")
    return {"changed": changed}


def ensure_smx_2026_competition_meta() -> dict:
    """Patch SMX Finals 2026 with official playoff dates, venues, timezones and gate times."""
    from models import Competition, Series, db
    from trackmap_utils import SMX_RACE_META, SMX_RACES_2026

    changed: list[str] = []
    smx_series = Series.query.filter_by(name="SMX Finals", year=2026).first()
    series_id = smx_series.id if smx_series else None

    for race in SMX_RACES_2026:
        name = race["name"]
        meta = SMX_RACE_META.get(name) or {}
        target_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
        st = meta.get("start_time")
        start_time_val = dt_time(st[0], st[1]) if st else None

        existing = None
        if series_id:
            existing = Competition.query.filter_by(name=name, series_id=series_id).first()
        if not existing:
            # Prefer 2026-dated rows; never steal a 2027 playoff with the same display name
            existing = (
                Competition.query.filter(
                    Competition.name == name,
                    Competition.series == "SMX",
                    Competition.event_date >= datetime(2026, 1, 1).date(),
                    Competition.event_date <= datetime(2026, 12, 31).date(),
                ).first()
            )
        if existing:
            if existing.event_date != target_date:
                existing.event_date = target_date
                changed.append(f"{name}.date")
            if meta.get("timezone") and existing.timezone != meta["timezone"]:
                existing.timezone = meta["timezone"]
                changed.append(f"{name}.timezone")
            if start_time_val and existing.start_time != start_time_val:
                existing.start_time = start_time_val
                changed.append(f"{name}.start_time")
            if series_id and existing.series_id != series_id:
                existing.series_id = series_id
                changed.append(f"{name}.series_id")
            if existing.series != "SMX":
                existing.series = "SMX"
                changed.append(f"{name}.series")
            if existing.phase != race.get("phase"):
                existing.phase = race.get("phase")
            target_mult = race.get("multiplier")
            if target_mult is not None and existing.point_multiplier != target_mult:
                existing.point_multiplier = target_mult
        elif series_id:
            competition = Competition(
                name=name,
                event_date=target_date,
                series="SMX",
                point_multiplier=race.get("multiplier", 1.0),
                is_triple_crown=0,
                coast_250=None,
                timezone=meta.get("timezone") or "America/New_York",
                start_time=start_time_val,
                series_id=series_id,
                phase=race.get("phase"),
                is_qualifying=False,
            )
            db.session.add(competition)
            changed.append(f"{name}.created")

    if changed:
        db.session.commit()
        print(f"[SMX] 2026 competition meta fixed: {', '.join(changed)}")
    return {"changed": changed}


def ensure_ama_2027_calendar_with_trackmaps(
    *,
    get_timezone_for_track: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Upsert AMA 2027 calendar and bind SX 2027 trackmap images when available."""
    from ama_2027_calendar import ensure_ama_2027_calendar

    info = ensure_ama_2027_calendar(get_timezone_for_track=get_timezone_for_track)
    try:
        from trackmap_utils import ensure_sx_2027_trackmap_images

        maps_info = ensure_sx_2027_trackmap_images()
        info = {**info, "trackmaps": maps_info}
    except Exception as map_err:
        info = {**info, "trackmaps_error": str(map_err)}
    return info


def run_ama_smx_boot_seeds(
    *,
    get_timezone_for_track: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Boot-time AMA/SMX seed chain (each step isolated with its own try/except)."""
    from models import Competition, CompetitionResult, db

    results: dict[str, Any] = {}

    try:
        results["ama_2026_dates"] = ensure_ama_2026_series_dates()
    except Exception as seed_err:
        print(f"Warning: AMA 2026 series date fix failed: {seed_err}")
        results["ama_2026_dates_error"] = str(seed_err)

    try:
        results["ama_2027"] = ensure_ama_2027_calendar_with_trackmaps(
            get_timezone_for_track=get_timezone_for_track
        )
    except Exception as seed_err:
        print(f"Warning: AMA 2027 calendar seed failed: {seed_err}")
        results["ama_2027_error"] = str(seed_err)

    try:
        results["smx_2026_meta"] = ensure_smx_2026_competition_meta()
    except Exception as seed_err:
        print(f"Warning: SMX 2026 competition meta fix failed: {seed_err}")
        results["smx_2026_meta_error"] = str(seed_err)

    try:
        from official_smx_2026 import reconcile_championship_results_2026

        recon = reconcile_championship_results_2026(db, CompetitionResult, Competition)
        results["reconcile"] = recon
        if recon.get("deleted"):
            print(
                f"[SMX] Reconciled duplicate AMA results: "
                f"deleted={recon['deleted']} season={recon.get('season_year')}"
            )
    except Exception as seed_err:
        print(f"Warning: AMA standings reconcile failed: {seed_err}")
        results["reconcile_error"] = str(seed_err)

    return results
