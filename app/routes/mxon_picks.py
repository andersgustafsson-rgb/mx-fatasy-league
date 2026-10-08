"""MXoN tippa page + save/mine API (skiva 21).

Same URL paths (no prefix). Bare endpoint alias `mxon_picks_page` registered
in main so url_for / invite / race_picks redirects keep working.
"""
from __future__ import annotations

import json

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth_helpers import check_session_timeout
from models import Competition, db
from services.picks_lock import _competition_race_schedule, is_picks_locked

bp = Blueprint("mxon_picks", __name__)


def _main():
    import main as _m

    return _m


@bp.route("/mxon_picks/<int:competition_id>")
def mxon_picks_page(competition_id):
    """MXoN tippa — topp 5 nationer (egen UI, ingen AMA/WSX-wizard)."""
    from mxon_fantasy import (
        apply_mxon_outs_to_nations,
        get_user_class_picks,
        get_user_nation_picks,
        list_active_nations,
        nation_dict,
    )

    is_logged_in = "user_id" in session and bool(session.get("user_id"))
    if is_logged_in and not check_session_timeout():
        flash("Din session har gått ut. Logga in igen.", "error")
        return redirect(url_for("login", next=request.path))
    is_logged_in = "user_id" in session and bool(session.get("user_id"))

    comp = Competition.query.get_or_404(competition_id)
    if (getattr(comp, "series", None) or "").upper() != "MXON":
        return redirect(url_for("race_picks_page", competition_id=competition_id))

    picks_locked = is_picks_locked(comp)
    nations_raw = list_active_nations()
    nations = [nation_dict(n, include_lineup=True) for n in nations_raw]
    nations = apply_mxon_outs_to_nations(nations, int(comp.id), hide_nation_out=True)
    for d in nations:
        lineup = d.get("lineup") or {}
        parts = []
        for cls_key, label in (("mxgp", "MXGP"), ("mx2", "MX2"), ("open", "OPEN")):
            seat = lineup.get(cls_key) or {}
            nm = "TBA" if seat.get("is_tba") else (seat.get("rider_name") or "TBA")
            num = seat.get("rider_number")
            prefix = f"#{num} " if num is not None else ""
            suffix = " (OUT)" if seat.get("is_out") else ""
            parts.append(f"{label}: {prefix}{nm}{suffix}")
        d["lineup_label"] = " · ".join(parts)

    initial = []
    initial_class = {}
    if is_logged_in:
        uid = int(session["user_id"])
        initial = get_user_nation_picks(uid, int(comp.id))
        initial_class = get_user_class_picks(uid, int(comp.id))

    schedule = _competition_race_schedule(comp)
    hero_image = "/static/images/mxon/ernee_trackmap.jpg"
    try:
        from pathlib import Path

        if not (Path("static") / "images/mxon/ernee_trackmap.jpg").is_file():
            hero_image = "/static/images/mxon/ernee_aerial.jpg"
    except Exception:
        pass

    trackmap_images = []
    trackmap_urls: list[str] = []
    picks_good_to_know: list[str] = []
    picks_weather = None
    try:
        from trackmap_utils import get_picks_good_to_know, get_trackmaps_for_competition

        trackmap_images = get_trackmaps_for_competition(comp)
        trackmap_urls = [
            ci.image_url for ci in trackmap_images if getattr(ci, "image_url", None)
        ]
        picks_good_to_know = get_picks_good_to_know(comp)
    except Exception:
        current_app.logger.exception(
            "mxon_picks trackmap/tips failed for competition_id=%s", competition_id
        )
        picks_good_to_know = [
            "MXoN: tippa topp 5 nationer + klassfavoriter (förare i MXGP/MX2/OPEN).",
            "Picks låses 2 timmar före lördagens MXGP-kval.",
        ]

    try:
        from track_weather import build_picks_weather_tips, get_weather_for_competition

        picks_weather = get_weather_for_competition(comp)
        weather_tips = build_picks_weather_tips(
            picks_weather, series=getattr(comp, "series", None)
        )
        if weather_tips:
            generic = [t for t in picks_good_to_know if t not in weather_tips]
            picks_good_to_know = weather_tips + generic[:3]
    except Exception:
        current_app.logger.exception(
            "mxon_picks weather tips failed for competition_id=%s", competition_id
        )
        picks_weather = None

    nation_count = len(nations)
    rider_count = nation_count * 3
    m = _main()

    return render_template(
        "mxon_picks.html",
        competition=comp,
        nations=nations,
        picks_locked=picks_locked,
        is_logged_in=is_logged_in,
        initial_picks_json=json.dumps(initial),
        initial_class_json=json.dumps(initial_class),
        deadline_display=schedule.get("pick_deadline_display"),
        hero_image=hero_image,
        trackmap_images=trackmap_images,
        trackmap_urls=trackmap_urls,
        picks_good_to_know=picks_good_to_know,
        picks_weather=picks_weather,
        is_mx_race=False,
        race_prep_venue=m._race_prep_venue_label(comp),
        race_prep_start_label=m._race_prep_start_label(comp),
        race_prep_wildcard_names=[],
        race_prep_nation_count=nation_count,
        race_prep_active_count=rider_count,
        out_ids=[],
        riders_450_json=[],
        riders_250_json=[],
    )


@bp.post("/mxon_picks/<int:competition_id>/save")
def mxon_picks_save(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "login_required"}), 401
    if not check_session_timeout():
        return jsonify({"error": "session_expired"}), 401

    from mxon_fantasy import save_user_class_picks, save_user_nation_picks

    comp = Competition.query.get_or_404(competition_id)
    if (getattr(comp, "series", None) or "").upper() != "MXON":
        return jsonify({"error": "not_mxon"}), 400
    if is_picks_locked(comp):
        return jsonify({"error": "picks_locked"}), 403

    data = request.get_json(silent=True) or {}
    nation_ids = data.get("nation_ids") or []
    class_picks = data.get("class_picks") or {}
    try:
        nation_ids = [int(x) for x in nation_ids]
        uid = int(session["user_id"])
        picks = save_user_nation_picks(uid, int(comp.id), nation_ids)
        class_out = save_user_class_picks(uid, int(comp.id), class_picks)
        return jsonify({"ok": True, "picks": picks, "class_picks": class_out})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.get("/mxon_picks/<int:competition_id>/mine")
def mxon_picks_mine(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "login_required"}), 401
    from mxon_fantasy import get_user_class_picks, get_user_nation_picks

    comp = Competition.query.get_or_404(competition_id)
    uid = int(session["user_id"])
    picks = get_user_nation_picks(uid, int(comp.id))
    class_picks = get_user_class_picks(uid, int(comp.id))
    complete = len(picks) == 5 and len(class_picks) == 3
    return jsonify(
        {
            "picks": picks,
            "class_picks": class_picks,
            "complete": complete,
            "picks_locked": is_picks_locked(comp),
        }
    )
