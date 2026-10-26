"""Public TV / ambient scoreboard display (no login) + personal desktop widget."""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

bp = Blueprint("tv_display", __name__)

WIDGET_TOKEN_SALT = "tv-widget-v1"
WIDGET_CORNERS = ("tl", "tr", "bl", "br")
WIDGET_SIZES = {"s": 0.8, "m": 1.0, "l": 1.2}


def _widget_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.secret_key, salt=WIDGET_TOKEN_SALT)


def _password_fingerprint(user) -> str:
    """Changing password invalidates old widget links."""
    raw = (getattr(user, "password_hash", None) or "").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:10]


def make_widget_token(user) -> str:
    return _widget_serializer().dumps({"u": int(user.id), "p": _password_fingerprint(user)})


def _user_from_widget_token(token: str | None):
    if not token:
        return None
    try:
        data = _widget_serializer().loads(token)
    except BadSignature:
        return None
    try:
        from models import User

        user = User.query.get(int(data.get("u")))
    except Exception as e:
        print(f"[tv] widget token user lookup failed: {e}")
        return None
    if not user or data.get("p") != _password_fingerprint(user):
        return None
    return user


def _widget_user():
    """Token (Lively / wallpaper) wins over browser session."""
    token = (request.args.get("t") or "").strip()
    if token:
        return _user_from_widget_token(token), True
    uid = session.get("user_id")
    if not uid:
        return None, False
    try:
        from models import User

        return User.query.get(int(uid)), False
    except Exception:
        return None, False


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


@bp.get("/tv/widget")
def tv_widget_page():
    """Compact corner widget for desktop wallpapers (Lively) — personal via ?t= link."""
    user, via_token = _widget_user()
    corner = (request.args.get("pos") or "tr").strip().lower()
    if corner not in WIDGET_CORNERS:
        corner = "tr"
    size_key = (request.args.get("size") or "m").strip().lower()
    scale = WIDGET_SIZES.get(size_key, 1.0)
    embedded = (request.args.get("embedded") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    widget_url = None
    if user and not via_token and not embedded:
        widget_url = url_for(
            "tv_display.tv_widget_page", t=make_widget_token(user), _external=True
        )
        if request.headers.get("X-Forwarded-Proto") == "https":
            widget_url = widget_url.replace("http://", "https://", 1)

    return render_template(
        "tv_widget.html",
        widget_user=user,
        via_token=via_token,
        token=(request.args.get("t") or "").strip() if via_token else "",
        corner=corner,
        size_key=size_key if size_key in WIDGET_SIZES else "m",
        scale=scale,
        widget_url=widget_url,
        bad_token=via_token and user is None,
        embedded=embedded,
    )


@bp.get("/tv/me")
def tv_widget_me():
    """Who the widget belongs to + picks status for the countdown race."""
    user, _ = _widget_user()
    if not user:
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    status = None
    comp_id = request.args.get("competition_id", type=int)
    if comp_id:
        try:
            from models import Competition
            from services.race_picks import user_picks_status_code

            comp = Competition.query.get(int(comp_id))
            if comp:
                status = user_picks_status_code(int(user.id), comp)
        except Exception as e:
            print(f"[tv] picks status failed: {e}")

    return jsonify(
        {
            "ok": True,
            "user_id": int(user.id),
            "username": user.username,
            "display_name": getattr(user, "display_name", None) or None,
            "picks_status": status,
        }
    )
