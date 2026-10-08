"""Series status JSON API (skiva 20). Same URL paths, no prefix."""
from __future__ import annotations

from flask import Blueprint, jsonify, session

from models import Competition
from services.race_picks import user_picks_status_code
from services.series_status import build_series_status_list

bp = Blueprint("series_status", __name__)


@bp.route("/api/series_status")
def series_status():
    """Get status of all series for user interface"""
    try:
        return jsonify(build_series_status_list())
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.get("/api/my_series_picks_status")
def my_series_picks_status():
    """Per-series pick completeness for the logged-in user's next race in each series."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({})
    try:
        out: dict[str, dict] = {}
        for row in build_series_status_list():
            code = (row.get("series_code") or "").strip().upper()
            if not code or row.get("under_construction"):
                continue
            next_race = row.get("next_race") or {}
            comp_id = next_race.get("id")
            if not comp_id:
                continue
            comp = Competition.query.get(int(comp_id))
            if not comp or getattr(comp, "is_cancelled", False):
                continue
            status = user_picks_status_code(int(uid), comp)
            out[code] = {
                "status": status,
                "competition_id": int(comp.id),
                "competition_name": getattr(comp, "name", None) or next_race.get("name"),
            }
        return jsonify(out)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
