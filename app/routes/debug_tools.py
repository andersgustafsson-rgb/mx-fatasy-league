"""Kept admin helpers that still have live UI callers.

Legacy one-shot /fix_/debug_ bootstrap routes were removed (2026 admin cleanup).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, session

from auth_helpers import is_admin_user
from models import Competition, CompetitionResult, Rider, db

bp = Blueprint("debug_tools", __name__)


def _main():
    """Lazy import for helpers that still live in main."""
    import main as _m

    return _m


@bp.post("/admin/push/challenges/test")
def admin_test_challenge_push():
    """Skicka test-push till inloggad admin."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    import push_service as ps

    if not ps.push_configured():
        return jsonify({"error": "push_not_configured"}), 503
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401
    subs = ps.list_subscriptions_for_user(uid)
    if not subs:
        return jsonify(
            {
                "error": "subscribe_first",
                "hint": "Öppna Pit Lane på samma mobil → Slå på notiser",
            }
        ), 400
    result = ps.send_push_sync(
        uid,
        "Test — Pit Lane-notis",
        "Push funkar! Du får DM, dueller och Race Control.",
        "/pit-lane",
        tag="push-test",
    )
    if result.get("ok"):
        return jsonify(
            {
                "success": True,
                "message": "Test-push skickad",
                "subscriptions": len(subs),
                "result": result,
            }
        )
    return jsonify(
        {
            "error": result.get("error", "send_failed"),
            "subscriptions": subs,
            "result": result,
        }
    ), 500


@bp.get("/admin/debug_results/<int:competition_id>")
def admin_debug_results(competition_id):
    """Readable dump of competition results (used by /admin results tools)."""
    if not is_admin_user():
        return jsonify({"error": "unauthorized"}), 403

    try:
        comp = Competition.query.get(competition_id)
        if not comp:
            return jsonify({"error": "Competition not found"}), 404

        results = (
            db.session.query(
                CompetitionResult.rider_id,
                CompetitionResult.position,
                CompetitionResult.rider_points,
                db.func.coalesce(CompetitionResult.class_name, Rider.class_name).label(
                    "class_name"
                ),
                Rider.name.label("rider_name"),
                Rider.rider_number.label("rider_number"),
            )
            .join(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == competition_id)
            .order_by(
                db.func.coalesce(CompetitionResult.class_name, Rider.class_name).asc(),
                CompetitionResult.position.asc(),
            )
            .all()
        )

        is_wsx = comp.series == "WSX"
        sx1_results = []
        sx2_results = []
        get_smx_qualification_points = _main().get_smx_qualification_points

        for r in results:
            if is_wsx:
                if r.rider_points is not None:
                    points = r.rider_points
                else:
                    points = get_smx_qualification_points(r.position)
            else:
                points = get_smx_qualification_points(r.position)

            result_data = {
                "position": r.position,
                "rider_id": r.rider_id,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_points": r.rider_points,
                "calculated_points": points,
                "class": r.class_name,
            }

            if r.class_name in ("450cc", "wsx_sx1"):
                sx1_results.append(result_data)
            elif r.class_name in ("250cc", "wsx_sx2"):
                sx2_results.append(result_data)

        return jsonify(
            {
                "competition": {
                    "id": comp.id,
                    "name": comp.name,
                    "series": comp.series,
                },
                "total_results": len(results),
                "sx1_results": sx1_results,
                "sx2_results": sx2_results,
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
