"""Web Push subscribe/status/admin diagnostics (skiva 16).

Same URL paths (no prefix). Uses push_service.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from auth_helpers import is_admin_user
from models import db

bp = Blueprint("push_api", __name__)


def _push_diagnostics_payload() -> dict:
    import push_service as ps

    uid = session.get("user_id")
    pem_ok = bool(ps._vapid_private_key())
    pub = ps.get_vapid_public_key_b64()
    return {
        "configured": ps.push_configured(),
        "private_key_present": pem_ok,
        "public_key_derived": bool(pub),
        "public_key_preview": (pub[:12] + "…" + pub[-8:]) if pub and len(pub) > 24 else pub,
        "subject": ps._vapid_subject(),
        "user_id": uid,
        "subscriptions": ps.list_subscriptions_for_user(uid) if uid else [],
    }


@bp.get("/api/push/vapid-public-key")
def api_push_vapid_public_key():
    import push_service as ps

    key = ps.get_vapid_public_key_b64()
    return jsonify({"enabled": bool(key), "publicKey": key})


@bp.get("/api/push/status")
@bp.get("/api/push/challenges/status")
def api_push_status():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    import push_service as ps

    return jsonify(
        {
            "configured": ps.push_configured(),
            "subscribed": ps.user_has_push(session["user_id"]),
        }
    )


@bp.post("/api/push/subscribe")
@bp.post("/api/push/challenges/subscribe")
def api_push_subscribe():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    import push_service as ps

    if not ps.push_configured():
        return jsonify({"error": "push_not_configured"}), 503
    data = request.get_json(silent=True) or {}
    sub = data.get("subscription")
    if not sub:
        return jsonify({"error": "subscription_required"}), 400
    try:
        ps.save_subscription(
            session["user_id"],
            sub,
            topic=ps.PUSH_TOPIC,
            user_agent=(request.headers.get("User-Agent") or "")[:300],
        )
        return jsonify({"success": True, "subscribed": True})
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": str(ex)}), 500


@bp.post("/api/push/unsubscribe")
@bp.post("/api/push/challenges/unsubscribe")
def api_push_unsubscribe():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    import push_service as ps

    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    deleted = ps.remove_subscription(session["user_id"], endpoint=endpoint)
    return jsonify({"success": True, "deleted": deleted})


@bp.post("/api/push/test")
def api_push_test():
    """Send a harmless test notification to the current user's own devices."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    import push_service as ps

    user_id = int(session["user_id"])
    if not ps.push_configured():
        return jsonify({"error": "push_not_configured"}), 503
    if not ps.user_has_push(user_id):
        return jsonify(
            {
                "error": "subscribe_first",
                "hint": "Slå på notiser på den här enheten först.",
            }
        ), 400

    result = ps.send_push_sync(
        user_id,
        "🔔 Test från MX Fantasy",
        "Notiser fungerar på den här enheten.",
        "/pit-lane",
        tag="player-push-test",
    )
    if result.get("ok"):
        return jsonify({"success": True, "message": "Testnotis skickad"})
    return jsonify({"error": result.get("error", "send_failed")}), 500


@bp.get("/admin/push/diagnostics")
def admin_push_diagnostics():
    """Push-status för felsökning (admin)."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    return jsonify(_push_diagnostics_payload())


@bp.route("/admin/leagues/push-diagnostics", methods=["GET"])
def admin_leagues_push_diagnostics():
    """Push-status (admin) — via liga-admin som redan fungerar på prod."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    return jsonify(_push_diagnostics_payload())


@bp.route("/admin/leagues/push-test", methods=["POST"])
def admin_leagues_push_test():
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
                "hint": "På mobilen: Pit Lane → Slå på notiser",
                "diagnostics": _push_diagnostics_payload(),
            }
        ), 400
    result = ps.send_push_sync(
        uid,
        "🔔 Test — Pit Lane-notis",
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
            "diagnostics": _push_diagnostics_payload(),
        }
    ), 500
