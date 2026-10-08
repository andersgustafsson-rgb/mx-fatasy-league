"""Invite landing + share card API (skiva 19).

Same URL paths (no prefix). Bare endpoint aliases registered in main
so url_for('start_invite') / url_for('api_invite_card_png') keep working.
"""
from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

from models import User, db
from services.invite_share import (
    _absolute_url,
    _build_invite_share_payload,
    _invite_picks_target,
)

bp = Blueprint("invite", __name__)


@bp.get("/start")
def start_invite():
    """Invite landing: /start or /start?ref=username — register + picks, no league required."""
    ref_raw = (request.args.get("ref") or "").strip()
    inviter = None
    if ref_raw:
        inviter = User.query.filter(db.func.lower(User.username) == ref_raw.lower()).first()
        if inviter:
            session["invite_ref"] = inviter.username
        else:
            session.pop("invite_ref", None)
    else:
        session.pop("invite_ref", None)

    race_name, next_url = _invite_picks_target()
    is_logged_in = "user_id" in session and bool(session.get("user_id"))
    if is_logged_in:
        return redirect(next_url)

    display_race = race_name if race_name != "MX Fantasy League" else "Nästa race"
    og_title = (
        f"{display_race} i helgen — slår du {inviter.username}?"
        if inviter
        else (
            f"{display_race} i helgen — MX Fantasy"
            if race_name != "MX Fantasy League"
            else "MX Fantasy League — gratis fantasy motocross"
        )
    )
    og_desc = (
        f"{inviter.username} har satt picks inför {race_name}. Skapa konto på 20 sek och häng med."
        if inviter and race_name != "MX Fantasy League"
        else (
            f"Utmanad av {inviter.username}. Skapa konto på 20 sek och sätt picks."
            if inviter
            else (
                f"Tippa {race_name} — topp 6, holeshot & wildcard. Gratis, klart på några minuter."
                if race_name != "MX Fantasy League"
                else "Tippa topp 6, holeshot & wildcard. Gratis — klart på ett par minuter."
            )
        )
    )
    og_image = _absolute_url(
        "api_invite_card_png",
        ref=inviter.username if inviter else None,
        layout="og",
    )

    return render_template(
        "start.html",
        inviter=inviter,
        inviter_name=(inviter.display_name or inviter.username) if inviter else None,
        inviter_username=inviter.username if inviter else None,
        pit_pass_race_name=display_race,
        pit_pass_next_url=next_url,
        pit_pass_peek_key="mx_pit_pass_peek_start",
        pit_pass_auto_show=True,
        pit_pass_start_hidden=False,
        pit_pass_guard_selectors=[],
        is_logged_in=False,
        race_name=race_name,
        next_url=next_url,
        og_title=og_title,
        og_description=og_desc,
        og_image=og_image,
        og_url=_absolute_url("start_invite", ref=inviter.username)
        if inviter
        else _absolute_url("start_invite"),
    )


@bp.get("/api/invite-card.png")
def api_invite_card_png():
    """Race-hype invite card PNG for Stories and og:image previews."""
    ref = (request.args.get("ref") or "").strip() or None
    layout = (request.args.get("layout") or "story").lower()
    if layout not in ("story", "og"):
        layout = "story"
    series = (request.args.get("series") or "").strip().upper() or None
    competition_id = request.args.get("competition_id", type=int)
    try:
        from invite_card_service import build_invite_card_data, render_invite_card_png

        data = build_invite_card_data(
            ref, prefer_series=series, competition_id=competition_id
        )
        png_bytes = render_invite_card_png(data, layout=layout)
        resp = Response(png_bytes, mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp
    except Exception as e:
        print(f"invite_card_png failed: {e}")
        return Response(status=500)


@bp.get("/api/invite_share")
def api_invite_share():
    """JSON share payload for logged-in users (Web Share / copy)."""
    if "user_id" not in session or not session.get("user_id"):
        return jsonify({"error": "Login required"}), 401
    username = session.get("username") or ""
    payload = _build_invite_share_payload(username)
    # Optional trash-talk from query (rank/points from homepage leaderboard)
    rank = request.args.get("rank", type=int)
    points = request.args.get("points", type=float)
    if rank or points is not None:
        body = [
            "🏁 Slår du mig i MX Fantasy?",
            f"Jag kör som {username}.",
        ]
        if rank:
            body.append(
                f"Just nu #{rank}"
                + (f" med {int(points)}p." if points is not None else ".")
            )
        elif points is not None:
            body.append(f"Jag ligger på {int(points)}p.")
        if payload.get("race_name") and payload["race_name"] != "MX Fantasy League":
            body.append(f"Nästa race: {payload['race_name']} — sätt picks innan deadline.")
        payload["share_body"] = "\n".join(body)
        payload["share_text"] = payload["share_body"] + "\n" + payload["invite_url"]
    return jsonify({"ok": True, **payload})
