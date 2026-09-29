"""League season archives — freeze standings at AMA tippa season closeout."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from models import (
    League,
    LeagueMembership,
    LeagueSeasonArchive,
    User,
    db,
)


def ensure_league_season_archives_table() -> None:
    try:
        LeagueSeasonArchive.__table__.create(bind=db.engine, checkfirst=True)
    except Exception as e:
        print(f"league_season_archives ensure: {e}")


def _avatar_fields(user: User | None) -> dict[str, Any]:
    if not user:
        return {
            "profile_picture_url": None,
            "avatar_letter": "?",
            "has_profile_image": False,
        }
    dn = (getattr(user, "display_name", None) or user.username or "?").strip() or "?"
    pic = getattr(user, "profile_picture_url", None)
    return {
        "profile_picture_url": pic,
        "avatar_letter": dn[:1].upper(),
        "has_profile_image": bool(pic),
    }


def _standings_from_points(
    members: list[User],
    points_by_user: dict[int, int],
) -> list[dict[str, Any]]:
    scored = [
        {
            "user_id": u.id,
            "username": u.username,
            "display_name": getattr(u, "display_name", None) or u.username,
            "total_points": int(points_by_user.get(u.id, 0) or 0),
            **_avatar_fields(u),
        }
        for u in members
    ]
    scored.sort(key=lambda x: (-x["total_points"], (x["username"] or "").lower()))
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(scored, start=1):
        out.append({"rank": rank, **row})
    return out


def build_league_archive_payload_live(
    *,
    pick_points_fn,
) -> list[dict[str, Any]]:
    """Snapshot all leagues using live tippa totals (call before CompetitionScore wipe)."""
    leagues = League.query.order_by(League.name.asc(), League.id.asc()).all()
    out: list[dict[str, Any]] = []
    for league in leagues:
        member_ids = [
            m.user_id
            for m in LeagueMembership.query.filter_by(league_id=league.id).all()
        ]
        members = User.query.filter(User.id.in_(member_ids)).all() if member_ids else []
        points = {u.id: int(pick_points_fn(u.id) or 0) for u in members}
        standings = _standings_from_points(members, points)
        winner = standings[0] if standings else None
        out.append(
            {
                "league_id": league.id,
                "name": league.name,
                "is_public": bool(getattr(league, "is_public", True)),
                "member_count": len(members),
                "league_total_points": int(league.total_points or 0),
                "winner_user_id": winner["user_id"] if winner else None,
                "winner_username": winner["username"] if winner else None,
                "winner_display_name": winner["display_name"] if winner else None,
                "winner_points": winner["total_points"] if winner else 0,
                "standings": standings,
            }
        )
    out.sort(key=lambda x: (-(x.get("league_total_points") or 0), (x.get("name") or "").lower()))
    return out


def build_league_archive_payload_from_finished(
    *,
    points_by_user: dict[int, int],
) -> list[dict[str, Any]]:
    """Rebuild member standings from FinishedSeriesStats-style tippa totals."""
    leagues = League.query.order_by(League.name.asc(), League.id.asc()).all()
    out: list[dict[str, Any]] = []
    for league in leagues:
        member_ids = [
            m.user_id
            for m in LeagueMembership.query.filter_by(league_id=league.id).all()
        ]
        members = User.query.filter(User.id.in_(member_ids)).all() if member_ids else []
        standings = _standings_from_points(members, points_by_user)
        winner = standings[0] if standings else None
        # league_total_points unknown after wipe — use sum of member tippa as display hint
        member_sum = sum(int(s["total_points"] or 0) for s in standings)
        out.append(
            {
                "league_id": league.id,
                "name": league.name,
                "is_public": bool(getattr(league, "is_public", True)),
                "member_count": len(members),
                "league_total_points": member_sum,
                "league_total_points_note": "sum_of_members",
                "winner_user_id": winner["user_id"] if winner else None,
                "winner_username": winner["username"] if winner else None,
                "winner_display_name": winner["display_name"] if winner else None,
                "winner_points": winner["total_points"] if winner else 0,
                "standings": standings,
            }
        )
    out.sort(key=lambda x: (-(x.get("winner_points") or 0), (x.get("name") or "").lower()))
    return out


def save_league_season_archive(
    *,
    season_year: int,
    label: str,
    leagues_payload: list[dict[str, Any]],
    source: str = "live",
    replace_existing: bool = True,
) -> LeagueSeasonArchive:
    ensure_league_season_archives_table()
    season_year = int(season_year)
    label = (label or f"AMA {season_year}").strip() or f"AMA {season_year}"
    existing = LeagueSeasonArchive.query.filter_by(
        season_year=season_year, label=label
    ).first()
    if existing and not replace_existing:
        return existing
    if existing:
        existing.archived_at = datetime.utcnow()
        existing.league_count = len(leagues_payload)
        existing.source = source
        existing.payload = json.dumps(leagues_payload, ensure_ascii=False)
        db.session.flush()
        return existing
    row = LeagueSeasonArchive(
        season_year=season_year,
        label=label,
        archived_at=datetime.utcnow(),
        league_count=len(leagues_payload),
        source=source,
        payload=json.dumps(leagues_payload, ensure_ascii=False),
    )
    db.session.add(row)
    db.session.flush()
    return row


def parse_archive_payload(row: LeagueSeasonArchive | None) -> list[dict[str, Any]]:
    if not row or not row.payload:
        return []
    try:
        data = json.loads(row.payload)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def get_archive_for_year(season_year: int) -> LeagueSeasonArchive | None:
    ensure_league_season_archives_table()
    return (
        LeagueSeasonArchive.query.filter_by(season_year=int(season_year))
        .order_by(LeagueSeasonArchive.archived_at.desc())
        .first()
    )


def get_league_from_archive(
    season_year: int, league_id: int
) -> dict[str, Any] | None:
    row = get_archive_for_year(season_year)
    for league in parse_archive_payload(row):
        if int(league.get("league_id") or 0) == int(league_id):
            return league
    return None


def list_archives_for_league(league_id: int) -> list[dict[str, Any]]:
    """Past seasons for one league (newest first)."""
    ensure_league_season_archives_table()
    rows = (
        LeagueSeasonArchive.query.order_by(
            LeagueSeasonArchive.season_year.desc(),
            LeagueSeasonArchive.archived_at.desc(),
        ).all()
    )
    out: list[dict[str, Any]] = []
    seen_years: set[int] = set()
    for row in rows:
        year = int(row.season_year)
        if year in seen_years:
            continue
        league = None
        for item in parse_archive_payload(row):
            if int(item.get("league_id") or 0) == int(league_id):
                league = item
                break
        if not league:
            continue
        seen_years.add(year)
        out.append(
            {
                "season_year": year,
                "label": row.label,
                "archived_at": row.archived_at.isoformat() + "Z" if row.archived_at else None,
                "source": row.source,
                "league": league,
            }
        )
    return out
