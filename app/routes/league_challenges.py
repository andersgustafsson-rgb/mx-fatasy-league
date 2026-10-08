"""League challenge API + admin routes (skiva 14).

Same URL paths (no prefix). Domain logic in services.league_challenges.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request, session

from auth_helpers import is_admin_user
from models import (
    Competition,
    League,
    LeagueChallenge,
    LeagueMembership,
    db,
)
from services import league_challenges as lc
from services.picks_lock import is_picks_locked

bp = Blueprint("league_challenges", __name__)


def _main():
    import main as _m
    return _m

@bp.get("/api/leagues/<int:league_id>/challenges")
def api_league_challenges(league_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    if not LeagueMembership.query.filter_by(league_id=league_id, user_id=session["user_id"]).first():
        return jsonify({"error": "not_member"}), 403
    return jsonify({"success": True, "data": lc._league_challenges_context(league_id, session["user_id"])})


@bp.post("/api/leagues/<int:league_id>/challenges")
def api_create_league_challenge(league_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    if not LeagueMembership.query.filter_by(league_id=league_id, user_id=uid).first():
        return jsonify({"error": "not_member"}), 403
    data = request.get_json(silent=True) or {}
    challenged_id = data.get("challenged_id")
    if not challenged_id:
        return jsonify({"error": "challenged_id required"}), 400
    next_comp = _main()._next_open_picks_competition()
    competition_id = data.get("competition_id") or (next_comp.id if next_comp else None)
    if not competition_id:
        return jsonify({"error": "no_open_race"}), 400
    err = lc._validate_challenge_create(league_id, uid, int(challenged_id), int(competition_id))
    if err:
        return jsonify({"error": err}), 400
    ch = LeagueChallenge(
        league_id=league_id,
        competition_id=int(competition_id),
        challenger_id=uid,
        challenged_id=int(challenged_id),
        status="pending_type",
    )
    db.session.add(ch)
    db.session.commit()
    comp_label = _main()._short_competition_label(next_comp) if next_comp else "nästa race"
    lc._notify_challenge(
        ch.challenged_id,
        f"⚔️ {lc._challenge_user_label(uid)} utmanar dig!",
        f"{comp_label} — välj din motfråga innan picks stänger",
        league_id,
    )
    return jsonify({"success": True, "challenge": lc._serialize_challenge(ch, uid)}), 201


@bp.post("/api/leagues/<int:league_id>/challenges/<int:challenge_id>/respond")
def api_respond_league_challenge(league_id: int, challenge_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    ch = LeagueChallenge.query.filter_by(id=challenge_id, league_id=league_id).first_or_404()
    if ch.challenged_id != uid:
        return jsonify({"error": "not_challenged"}), 403
    if ch.status != "pending_type":
        return jsonify({"error": "invalid_status"}), 400
    comp = Competition.query.get(ch.competition_id)
    if not comp or is_picks_locked(comp):
        return jsonify({"error": "picks_locked"}), 400
    if lc._user_committed_challenge_count_for_race(uid, league_id, ch.competition_id) >= lc._MAX_CHALLENGES_PER_USER_RACE:
        return jsonify({"error": f"Du har redan {lc._MAX_CHALLENGES_PER_USER_RACE} aktiva dueller detta race"}), 400
    data = request.get_json(silent=True) or {}
    ctype = (data.get("challenge_type") or "").strip()
    if ctype not in lc.CHALLENGE_TYPE_META:
        return jsonify({"error": "invalid_type"}), 400
    class_name = (data.get("class_name") or "").strip()
    riders_by_class = lc._challenge_riders_for_competition(comp)
    if class_name not in riders_by_class:
        return jsonify({"error": "invalid_class"}), 400

    ch.challenge_type = ctype
    ch.class_name = class_name
    if ctype == "head_to_head":
        rider_a = data.get("rider_a_id")
        rider_b = data.get("rider_b_id")
        if not rider_a or not rider_b or rider_a == rider_b:
            return jsonify({"error": "invalid_riders"}), 400
        ch.rider_a_id = int(rider_a)
        ch.rider_b_id = int(rider_b)
        ch.status = "pending_answers"
    elif ctype == "brand_battle":
        brand_a = (data.get("brand_a") or "").strip()
        brand_b = (data.get("brand_b") or "").strip()
        brands = {b.lower() for b in lc._challenge_brands_for_competition(comp)}
        if not brand_a or not brand_b or brand_a.lower() == brand_b.lower():
            return jsonify({"error": "invalid_brands"}), 400
        if brand_a.lower() not in brands or brand_b.lower() not in brands:
            return jsonify({"error": "brand_not_in_race"}), 400
        ch.brand_a = brand_a
        ch.brand_b = brand_b
        ch.status = "pending_answers"
    else:
        ch.status = "pending_answers"
    db.session.commit()
    type_label = lc.CHALLENGE_TYPE_META.get(ctype, {}).get("label", "motfråga")
    lc._notify_challenge(
        ch.challenger_id,
        f"🎯 {lc._challenge_user_label(uid)} svarade på din utmaning",
        f"{type_label} vald — lås ditt svar innan picks stänger",
        league_id,
    )
    return jsonify({"success": True, "challenge": lc._serialize_challenge(ch, uid)})


@bp.post("/api/leagues/<int:league_id>/challenges/<int:challenge_id>/answer")
def api_answer_league_challenge(league_id: int, challenge_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    ch = LeagueChallenge.query.filter_by(id=challenge_id, league_id=league_id).first_or_404()
    if ch.status != "pending_answers":
        return jsonify({"error": "invalid_status"}), 400
    comp = Competition.query.get(ch.competition_id)
    if not comp or is_picks_locked(comp):
        return jsonify({"error": "picks_locked"}), 400
    data = request.get_json(silent=True) or {}

    if ch.challenge_type == "h2h":
        rider_id = data.get("rider_id")
        position = data.get("position")
        if not rider_id or not position:
            return jsonify({"error": "rider_and_position_required"}), 400
        try:
            position = int(position)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_position"}), 400
        if position < 1 or position > 20:
            return jsonify({"error": "invalid_position"}), 400
        if uid == ch.challenger_id:
            if ch.challenger_answered_at:
                return jsonify({"error": "already_answered"}), 400
            if ch.challenged_rider_id and int(rider_id) == ch.challenged_rider_id:
                return jsonify({"error": "same_rider"}), 400
            ch.challenger_rider_id = int(rider_id)
            ch.challenger_position = position
            ch.challenger_answered_at = datetime.utcnow()
        elif uid == ch.challenged_id:
            if ch.challenged_answered_at:
                return jsonify({"error": "already_answered"}), 400
            if ch.challenger_rider_id and int(rider_id) == ch.challenger_rider_id:
                return jsonify({"error": "same_rider"}), 400
            ch.challenged_rider_id = int(rider_id)
            ch.challenged_position = position
            ch.challenged_answered_at = datetime.utcnow()
        else:
            return jsonify({"error": "not_participant"}), 403

    elif ch.challenge_type == "head_to_head":
        if uid != ch.challenger_id:
            return jsonify({"error": "challenger_only"}), 403
        if ch.challenger_answered_at:
            return jsonify({"error": "already_answered"}), 400
        guess = data.get("guess_rider_id")
        if guess not in (ch.rider_a_id, ch.rider_b_id):
            return jsonify({"error": "invalid_guess"}), 400
        ch.challenger_guess_rider_id = int(guess)
        ch.challenger_answered_at = datetime.utcnow()

    elif ch.challenge_type == "brand_battle":
        pick = (data.get("brand_pick") or "").strip()
        if not pick:
            return jsonify({"error": "brand_required"}), 400
        allowed = {ch.brand_a.lower(), ch.brand_b.lower()}
        if pick.lower() not in allowed:
            return jsonify({"error": "invalid_brand"}), 400
        if uid == ch.challenger_id:
            if ch.challenger_answered_at:
                return jsonify({"error": "already_answered"}), 400
            if ch.challenged_brand_pick and pick.lower() == ch.challenged_brand_pick.lower():
                return jsonify({"error": "brand_taken"}), 400
            ch.challenger_brand_pick = pick
            ch.challenger_answered_at = datetime.utcnow()
        elif uid == ch.challenged_id:
            if ch.challenged_answered_at:
                return jsonify({"error": "already_answered"}), 400
            if ch.challenger_brand_pick and pick.lower() == ch.challenger_brand_pick.lower():
                return jsonify({"error": "brand_taken"}), 400
            ch.challenged_brand_pick = pick
            ch.challenged_answered_at = datetime.utcnow()
        else:
            return jsonify({"error": "not_participant"}), 403
    else:
        return jsonify({"error": "unknown_type"}), 400

    lc._lock_challenge_if_ready(ch)
    db.session.commit()
    other_id = ch.challenged_id if uid == ch.challenger_id else ch.challenger_id
    if ch.status == "locked":
        lc._notify_challenge(
            other_id,
            f"🔒 Duellen mot {lc._challenge_user_label(uid)} är låst",
            "Båda svaren inne — avgörs efter racet",
            league_id,
        )
    else:
        lc._notify_challenge(
            other_id,
            f"✍️ {lc._challenge_user_label(uid)} låste sitt svar",
            "Din tur — lås ditt svar innan picks stänger",
            league_id,
        )
    return jsonify({"success": True, "challenge": lc._serialize_challenge(ch, uid)})


@bp.post("/api/leagues/<int:league_id>/challenges/<int:challenge_id>/decline")
def api_decline_league_challenge(league_id: int, challenge_id: int):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    ch = LeagueChallenge.query.filter_by(id=challenge_id, league_id=league_id).first_or_404()
    if ch.challenged_id != uid:
        return jsonify({"error": "not_challenged"}), 403
    if ch.status not in ("pending_type", "pending_answers"):
        return jsonify({"error": "invalid_status"}), 400
    ch.status = "declined"
    db.session.commit()
    lc._notify_challenge(
        ch.challenger_id,
        f"🚫 {lc._challenge_user_label(uid)} avböjde din utmaning",
        "Utmaningen är avslutad",
        league_id,
    )
    return jsonify({"success": True})


@bp.post("/api/leagues/<int:league_id>/challenges/<int:challenge_id>/cancel")
def api_cancel_league_challenge(league_id: int, challenge_id: int):
    """Challenger withdraws a pending invitation / unfinished duel."""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    ch = LeagueChallenge.query.filter_by(id=challenge_id, league_id=league_id).first_or_404()
    if ch.challenger_id != uid:
        return jsonify({"error": "not_challenger"}), 403
    if ch.status not in ("pending_type", "pending_answers"):
        return jsonify({"error": "invalid_status"}), 400
    ch.status = "cancelled"
    db.session.commit()
    lc._notify_challenge(
        ch.challenged_id,
        f"↩️ {lc._challenge_user_label(uid)} avbröt utmaningen",
        "Inbjudan är indragen",
        league_id,
    )
    return jsonify({"success": True})


@bp.post("/admin/leagues/challenges/reset")
def admin_reset_all_league_challenges():
    """Reset all league duels — temporary admin test helper."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        deleted = lc._admin_reset_league_challenges()
        msg = (
            f"Raderade {deleted['challenges']} utmaningar, "
            f"{deleted['badges']} märken och {deleted['notifications']} notiser"
        )
        print(f"⚔️ Admin reset all challenges: {deleted}")
        return jsonify({"success": True, "message": msg, "deleted": deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.post("/admin/leagues/<int:league_id>/challenges/reset")
def admin_reset_league_challenges(league_id: int):
    """Reset league duels for one league — temporary admin test helper."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        league = League.query.get_or_404(league_id)
        deleted = lc._admin_reset_league_challenges(league_id)
        msg = (
            f"Raderade {deleted['challenges']} utmaningar i '{league.name}', "
            f"{deleted['badges']} märken och {deleted['notifications']} notiser"
        )
        print(f"⚔️ Admin reset challenges for league {league_id}: {deleted}")
        return jsonify({"success": True, "message": msg, "deleted": deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/leagues/challenges/re-resolve", methods=["POST"])
def admin_re_resolve_league_challenges_post():
    """Re-resolve duels for a race (fixes stale ties, DNF, shame badges)."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    data = request.get_json(silent=True) or {}
    competition_id = data.get("competition_id")
    name = (data.get("name") or "southwick").strip()
    try:
        if competition_id:
            comp = Competition.query.get(int(competition_id))
        else:
            comp = (
                Competition.query.filter(Competition.name.ilike(f"%{name}%"))
                .order_by(Competition.event_date.desc().nullslast())
                .first()
            )
        if not comp:
            return jsonify({"error": f"Ingen tävling matchar '{name}'"}), 404
        report = lc._build_re_resolve_challenges_report(comp.id)
        return jsonify(
            {
                "success": True,
                "message": f"Dueller omräknade för {report['competition_name']}",
                **report,
            }
        )
    except Exception as e:
        db.session.rollback()
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/re-resolve-challenges", methods=["GET"])
def admin_re_resolve_challenges_by_name():
    """Re-resolve locked/stale-tied league duels for a race (admin). ?name=southwick"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    name = (request.args.get("name") or "southwick").strip()
    comp = (
        Competition.query.filter(Competition.name.ilike(f"%{name}%"))
        .order_by(Competition.event_date.desc().nullslast())
        .first()
    )
    if not comp:
        return jsonify({"error": f"Ingen tävling matchar '{name}'"}), 404
    try:
        report = lc._build_re_resolve_challenges_report(comp.id)
        return jsonify(
            {
                "success": True,
                "message": f"Dueller omräknade för {report['competition_name']}",
                **report,
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/re-resolve-challenges/<int:competition_id>", methods=["GET"])
def admin_re_resolve_league_challenges(competition_id: int):
    """Re-resolve league duels after results (fixes stale ties, DNF logic, badges/shame)."""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    try:
        report = lc._build_re_resolve_challenges_report(competition_id)
        return jsonify(
            {
                "success": True,
                "message": f"Dueller omräknade för {report['competition_name']}",
                **report,
            }
        )
    except ValueError:
        return jsonify({"error": "competition not found"}), 404
    except Exception as e:
        db.session.rollback()
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
