"""Registration spam heuristics (free, no third-party).

Scores are soft signals — high score can block signup; medium shows in admin.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

from models import (
    CompetitionScore,
    LeagueMembership,
    RacePick,
    SeasonTeam,
    User,
    db,
)

# Block at/above this (admin can lower via env).
BLOCK_SCORE = int(os.environ.get("SPAM_BLOCK_SCORE", "8") or "8")

_RANDOM_USER = re.compile(r"^[a-z0-9]{12,}$", re.I)
_UGSSER = re.compile(r"^ugsser", re.I)
_DIGIT_HEAVY_LOCAL = re.compile(r"^[a-z]*\d{3,}[a-z0-9]*$", re.I)
_DISPOSABLE_HINTS = (
    "mailinator",
    "guerrillamail",
    "tempmail",
    "10minutemail",
    "yopmail",
    "trashmail",
    "sharklasers",
)


def score_registration(
    *,
    username: str,
    email: str,
    honeypot: str | None = None,
) -> dict[str, Any]:
    """Return {score, reasons, block} for a signup attempt."""
    reasons: list[str] = []
    score = 0
    uname = (username or "").strip()
    em = (email or "").strip().lower()
    hp = (honeypot or "").strip()

    if hp:
        score += 20
        reasons.append("honeypot_filled")

    if _UGSSER.search(uname):
        score += 6
        reasons.append("ugsser_prefix")
    elif _RANDOM_USER.match(uname) and not re.search(r"[_\-. ]", uname):
        # Long alphanumeric with no separators — common bot pattern
        score += 4
        reasons.append("random_username")

    if len(uname) >= 14 and re.fullmatch(r"[a-z0-9]+", uname, re.I):
        score += 2
        reasons.append("long_alphanum_username")

    local, _, domain = em.partition("@")
    if domain:
        if any(h in domain for h in _DISPOSABLE_HINTS):
            score += 8
            reasons.append("disposable_domain")
        if domain in ("aol.com",) and _DIGIT_HEAVY_LOCAL.match(local or ""):
            score += 2
            reasons.append("digit_heavy_aol")
        if _DIGIT_HEAVY_LOCAL.match(local or "") and len(local) >= 12:
            score += 2
            reasons.append("digit_heavy_local")

    # DB burst signals (skip cleanly outside app context / on DB blip)
    try:
        if domain and domain not in (
            "gmail.com",
            "hotmail.com",
            "outlook.com",
            "icloud.com",
            "live.se",
            "hotmail.se",
        ):
            recent = (
                User.query.filter(
                    User.created_at >= datetime.utcnow() - timedelta(hours=24),
                    db.func.lower(User.email).like(f"%@{domain}"),
                ).count()
            )
            if recent >= 3:
                score += 3
                reasons.append("domain_burst_24h")

        hour_count = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        if hour_count >= 5:
            score += 3
            reasons.append("signup_burst_1h")
    except Exception:
        pass

    block = score >= BLOCK_SCORE
    return {
        "score": score,
        "reasons": reasons,
        "block": block,
        "block_threshold": BLOCK_SCORE,
    }


def assess_existing_user(user: User) -> dict[str, Any]:
    """Score an existing account for admin review (includes activity)."""
    base = score_registration(
        username=user.username or "",
        email=(user.email or ""),
        honeypot="",
    )
    reasons = list(base["reasons"])
    score = int(base["score"])

    has_google = bool(getattr(user, "google_sub", None))
    if has_google:
        score = max(0, score - 4)
        reasons.append("google_oauth_credit")

    picks_n = RacePick.query.filter_by(user_id=user.id).count()
    league_n = LeagueMembership.query.filter_by(user_id=user.id).count()
    team = SeasonTeam.query.filter_by(user_id=user.id).first()
    scores_n = CompetitionScore.query.filter_by(user_id=user.id).count()

    if picks_n == 0 and league_n == 0 and team is None:
        score += 2
        reasons.append("no_play_activity")
    if picks_n > 0 or league_n > 0 or team is not None:
        score = max(0, score - 5)
        reasons.append("has_play_activity")
    if scores_n and picks_n == 0:
        # Touch without picks — mild curiosity, not strong spam proof
        reasons.append("score_row_without_picks")

    empty_profile = not (
        (getattr(user, "display_name", None) or "").strip()
        or (getattr(user, "bio", None) or "").strip()
        or (getattr(user, "profile_picture_url", None) or "").strip()
    )
    if empty_profile and not has_google:
        score += 1
        reasons.append("empty_profile")

    created = getattr(user, "created_at", None)
    night = False
    if created:
        hour = created.hour  # stored UTC-ish
        # ~02–05 UTC ≈ Swedish night / common bot window
        if 2 <= hour <= 5:
            night = True
            score += 1
            reasons.append("created_late_night_utc")

    level = "ok"
    if score >= BLOCK_SCORE:
        level = "high"
    elif score >= 4:
        level = "medium"

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": created.isoformat() if created else None,
        "google": has_google,
        "score": score,
        "level": level,
        "reasons": reasons,
        "activity": {
            "picks": picks_n,
            "leagues": league_n,
            "season_team": bool(team),
            "competition_scores": scores_n,
        },
        "night_utc": night,
    }


def list_recent_signups(*, days: int = 21, limit: int = 40) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=max(1, min(days, 90)))
    users = (
        User.query.filter(User.created_at >= since)
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )
    rows = [assess_existing_user(u) for u in users]
    rows.sort(
        key=lambda r: (
            {"high": 0, "medium": 1, "ok": 2}.get(r["level"], 9),
            -int(r["score"] or 0),
        )
    )
    return rows
