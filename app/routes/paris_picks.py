"""Paris Supercross weekend tippa (lördag + söndag, egna deadlines)."""
from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, request, session, url_for

from models import Competition, User, db
from paris_fantasy import (
    clear_user_paris_picks,
    get_active_paris_year,
    get_paris_series,
    get_paris_weekend,
    get_user_paris_picks_ui,
    get_user_paris_weekend_picks_ui,
    paris_is_saturday,
    paris_is_weekend_comp,
    paris_roster_payload,
    paris_user_can_play,
    save_user_paris_picks,
)
from services.picks_lock import is_picks_locked

bp = Blueprint("paris_picks", __name__)


def _is_admin_user() -> bool:
    username = session.get("username")
    if not username:
        return False
    user = User.query.filter_by(username=username).first()
    return bool(user and user.is_admin)


def _paris_race_picks_url(competition_id: int) -> str:
    """Prefer named endpoint (main.py); fall back to path for create_app factory."""
    try:
        return url_for("race_picks_page", competition_id=competition_id)
    except Exception:
        return f"/race_picks/{int(competition_id)}"


def _paris_coming_soon_redirect():
    flash(
        "Paris Supercross — picks öppnar snart. Tippa släpps när startlista och banlayout är ute.",
        "info",
    )
    return redirect(url_for("index"))


@bp.get("/paris-sx")
def paris_hub_page():
    """Bakåtkompatibilitet — nästa kväll, eller startsida om tippa är spärrad."""
    if not paris_user_can_play(is_admin=_is_admin_user()):
        ser = get_paris_series(get_active_paris_year())
        if ser:
            try:
                return redirect(url_for("series_page", series_id=ser.id))
            except Exception:
                pass
        return _paris_coming_soon_redirect()
    wk = get_paris_weekend(get_active_paris_year())
    for comp in (wk.get("saturday"), wk.get("sunday")):
        if comp and not is_picks_locked(comp):
            return redirect(_paris_race_picks_url(comp.id))
    for comp in (wk.get("saturday"), wk.get("sunday")):
        if comp:
            return redirect(_paris_race_picks_url(comp.id))
    return redirect(url_for("index"))


@bp.get("/paris_picks/<int:competition_id>")
def paris_picks_page(competition_id: int):
    if not paris_user_can_play(is_admin=_is_admin_user()):
        return _paris_coming_soon_redirect()
    return redirect(_paris_race_picks_url(competition_id))


@bp.get("/paris_picks/<int:competition_id>/roster")
def paris_roster_api(competition_id: int):
    if not paris_user_can_play(is_admin=_is_admin_user()):
        return jsonify({"error": "Paris Supercross — picks öppnar snart."}), 403
    comp = Competition.query.get_or_404(competition_id)
    if not paris_is_weekend_comp(comp):
        return jsonify({"error": "not_paris"}), 400
    return jsonify({"ok": True, "roster": paris_roster_payload(competition_id)})


@bp.get("/paris_picks/weekend/mine")
def paris_weekend_mine_api():
    """Homepage: combined Saturday + Sunday picks (Sunday omitted if empty)."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    # Read-only: own picks always OK (tippa/save still gated by paris_user_can_play).
    year = request.args.get("year", type=int) or get_active_paris_year()
    payload = get_user_paris_weekend_picks_ui(int(session["user_id"]), year)
    return jsonify({"ok": True, **payload})


@bp.get("/paris_picks/<int:competition_id>/mine")
def paris_mine_api(competition_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    # Read-only own picks (homepage) — no PUBLIC_PLAY gate.
    comp = Competition.query.get_or_404(competition_id)
    if not paris_is_weekend_comp(comp):
        return jsonify({"error": "not_paris"}), 400
    ui = get_user_paris_picks_ui(int(session["user_id"]), comp)
    return jsonify(
        {
            "ok": True,
            "picks_locked": is_picks_locked(comp),
            "complete": bool(ui.get("complete")),
            "saturday": bool(ui.get("saturday")),
            "picks": ui.get("ids") or {},
            "picks_ui": ui,
        }
    )


@bp.post("/paris_picks/<int:competition_id>/save")
def paris_save_api(competition_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    if not paris_user_can_play(is_admin=_is_admin_user()):
        return jsonify({
            "error": "Paris Supercross — picks öppnar snart. Tippa släpps när startlista är ute."
        }), 403
    comp = Competition.query.get_or_404(competition_id)
    if not paris_is_weekend_comp(comp):
        return jsonify({"error": "not_paris"}), 400
    data = request.get_json(force=True) or {}
    try:
        save_user_paris_picks(int(session["user_id"]), comp, data)
        ui = get_user_paris_picks_ui(int(session["user_id"]), comp)
        return jsonify({
            "ok": True,
            "complete": bool(ui.get("complete")),
            "saturday": bool(ui.get("saturday")),
            "picks": ui.get("ids") or {},
            "picks_ui": ui,
        })
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Paris save error: {e}")
        return jsonify({"error": "Kunde inte spara"}), 500


@bp.post("/paris_picks/<int:competition_id>/clear")
def paris_clear_api(competition_id: int):
    """Clear own Paris picks for this evening (back to empty tippa)."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    if not paris_user_can_play(is_admin=_is_admin_user()):
        return jsonify({
            "error": "Paris Supercross — picks öppnar snart."
        }), 403
    comp = Competition.query.get_or_404(competition_id)
    if not paris_is_weekend_comp(comp):
        return jsonify({"error": "not_paris"}), 400
    try:
        deleted = clear_user_paris_picks(int(session["user_id"]), comp)
        return jsonify({
            "ok": True,
            "cleared": True,
            "deleted": deleted,
            "saturday": paris_is_saturday(comp),
            "picks": {},
            "complete": False,
        })
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Paris clear error: {e}")
        return jsonify({"error": "Kunde inte rensa"}), 500
