"""Public league cards for discover / empty-state UI."""
from __future__ import annotations

from models import League, LeagueMembership, LeagueRequest, db
from services.official_leagues import (
    OFFICIAL_LEAGUE_OWNER_LABEL,
    is_official_public_league,
)


def _league_member_standings(league_id: int) -> list[dict]:
    from main import _league_member_standings as fn

    return fn(league_id)


def build_public_league_discover(viewer_user_id: int | None) -> list[dict]:
    """Publika ligor med medlemsantal, topp 3 och viewer-status."""
    rows = (
        db.session.query(
            League,
            db.func.count(db.func.distinct(LeagueMembership.user_id)).label("member_count"),
        )
        .outerjoin(LeagueMembership, League.id == LeagueMembership.league_id)
        .filter(League.is_public.is_(True))
        .group_by(League.id)
        .order_by(
            db.func.count(db.func.distinct(LeagueMembership.user_id)).desc(),
            League.total_points.desc(),
            League.created_at.desc(),
        )
        .all()
    )

    member_ids: set[int] = set()
    pending_ids: set[int] = set()
    if viewer_user_id:
        member_ids = {
            int(r[0])
            for r in db.session.query(LeagueMembership.league_id)
            .filter(LeagueMembership.user_id == viewer_user_id)
            .all()
        }
        pending_ids = {
            int(r[0])
            for r in db.session.query(LeagueRequest.league_id)
            .filter(
                LeagueRequest.user_id == viewer_user_id,
                LeagueRequest.status == "pending",
            )
            .all()
        }

    cards: list[dict] = []
    for league, member_count in rows:
        standings = _league_member_standings(league.id)[:3]
        if viewer_user_id:
            for row in standings:
                row["is_me"] = row.get("user_id") == viewer_user_id

        if league.id in member_ids:
            status = "member"
        elif league.id in pending_ids:
            status = "pending"
        else:
            status = "open"

        official = is_official_public_league(league)
        cards.append(
            {
                "id": league.id,
                "name": league.name,
                "description": (league.description or "").strip(),
                "is_official": official,
                "join_mode": "instant" if official else "request",
                "created_by": OFFICIAL_LEAGUE_OWNER_LABEL if official else None,
                "member_count": int(member_count or 0),
                "total_points": int(league.total_points or 0),
                "invite_code": league.invite_code,
                "top_standings": [
                    {
                        "rank": s.get("rank"),
                        "display_name": s.get("display_name") or s.get("username"),
                        "total_points": s.get("total_points", 0),
                        "is_me": s.get("is_me", False),
                    }
                    for s in standings
                ],
                "membership_status": status,
            }
        )
    cards.sort(
        key=lambda c: (
            0 if c.get("is_official") else 1,
            -int(c.get("member_count") or 0),
            -int(c.get("total_points") or 0),
        )
    )
    return cards
