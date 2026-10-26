"""Public TV / ambient scoreboard display (no login)."""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("tv_display", __name__)


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _upcoming_ama_races(limit: int = 8, skip_first: bool = True) -> list[dict]:
    """Upcoming AMA races for bottom ticker (skip soonest = shown in countdown)."""
    try:
        from models import Competition, CompetitionResult
    except Exception as e:
        print(f"[tv] models import failed: {e}")
        return []

    today = date.today()
    try:
        # Broad fetch — filter series in Python (avoids dialect .in_ quirks).
        rows = (
            Competition.query.filter(Competition.event_date >= today)
            .order_by(Competition.event_date.asc(), Competition.id.asc())
            .limit(80)
            .all()
        )
    except Exception as e:
        print(f"[tv] upcoming query failed: {e}")
        try:
            from models import db

            db.session.rollback()
        except Exception:
            pass
        return []

    ama = {"SX", "MX", "SMX"}
    out: list[dict] = []
    skipped = 0
    for comp in rows:
        series = (getattr(comp, "series", None) or "").strip().upper()
        if series not in ama:
            continue
        if getattr(comp, "is_cancelled", False):
            continue
        name = (getattr(comp, "name", None) or "").strip()
        if not name or name.upper() == "ADMIN TEST GP":
            continue
        ed = _as_date(getattr(comp, "event_date", None))
        if ed is None or ed < today:
            continue
        try:
            has_results = (
                CompetitionResult.query.filter_by(competition_id=int(comp.id)).first()
                is not None
            )
        except Exception:
            has_results = False
        if has_results:
            continue
        if skip_first and skipped == 0:
            skipped = 1
            continue
        out.append(
            {
                "id": int(comp.id),
                "name": name,
                "series": series,
                "date": ed.isoformat(),
                "round": len(out) + 2 if skip_first else len(out) + 1,
            }
        )
        if len(out) >= limit:
            break

    # If skip left us empty (only one race), show that race instead.
    if not out and skip_first:
        return _upcoming_ama_races(limit=limit, skip_first=False)
    return out


@bp.get("/tv")
def tv_page():
    """Fullscreen leaderboard + next-race countdown for Smart TVs / cast."""
    kiosk = (request.args.get("kiosk") or "").strip().lower() in ("1", "true", "yes")
    upcoming = _upcoming_ama_races()
    return render_template(
        "tv_display.html",
        kiosk=kiosk,
        upcoming_races=upcoming,
    )


@bp.get("/tv/upcoming")
def tv_upcoming_json():
    """JSON fallback so the ticker can self-heal if SSR list is empty."""
    return jsonify({"ok": True, "races": _upcoming_ama_races()})
