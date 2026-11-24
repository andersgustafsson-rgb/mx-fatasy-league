"""League digests + fair league points (skiva 24 + 26).

Heavy tippa/AMA helpers still live in main and are reached via lazy `_main()`.
"""
from __future__ import annotations

from flask import url_for

from models import (
    Competition,
    CompetitionResult,
    CompetitionScore,
    HoleshotPick,
    League,
    LeagueMembership,
    MxonClassPick,
    MxonNationPick,
    QualifyingPick,
    RacePick,
    Rider,
    User,
    WildcardPick,
    db,
)
from services.picks_lock import _competition_race_schedule, get_current_time
from services.scoring import TIPPA_ONLY_SERIES


def _main():
    import main as _m

    return _m


def _user_avatar_fields(user: User | None) -> dict[str, str | int | bool | None]:
    """Profile picture + fallback initial for avatar UI."""
    if not user:
        return {
            "user_id": None,
            "profile_picture_url": None,
            "avatar_letter": "?",
            "has_profile_image": False,
        }
    dn = getattr(user, "display_name", None) or user.username or "?"
    pic = getattr(user, "profile_picture_url", None)
    has_pic = bool(pic and not str(pic).startswith("uploaded_"))
    return {
        "user_id": int(user.id),
        "profile_picture_url": pic,
        "avatar_letter": (dn.strip()[:1] or "?").upper(),
        "has_profile_image": has_pic,
    }


def _league_member_standings(league_id: int) -> list[dict]:
    """Individual race-pick standings for league members (excludes WSX)."""
    member_user_ids = [
        m.user_id
        for m in LeagueMembership.query.filter_by(league_id=league_id).all()
    ]
    if not member_user_ids:
        return []

    members = User.query.filter(User.id.in_(member_user_ids)).all()
    pick_total = _main()._user_pick_total_points
    scored = [
        {
            "user_id": u.id,
            "username": u.username,
            "display_name": getattr(u, "display_name", None) or u.username,
            "total_points": pick_total(u.id),
            **_user_avatar_fields(u),
        }
        for u in members
    ]
    scored.sort(key=lambda x: x["total_points"], reverse=True)

    standings: list[dict] = []
    for rank, row in enumerate(scored, start=1):
        standings.append({"rank": rank, **row})
    return standings


def _league_summary_for_user(league_id: int, user_id: int) -> dict:
    """Standings + current user's rank/gap for a league."""
    member_count = LeagueMembership.query.filter_by(league_id=league_id).count()
    standings = _league_member_standings(league_id)
    for s in standings:
        s["is_me"] = s["user_id"] == user_id

    my_entry = next((s for s in standings if s["user_id"] == user_id), None)
    my_rank = my_entry["rank"] if my_entry else None
    my_points = my_entry["total_points"] if my_entry else 0
    gap_above = gap_below = None
    rival_name = leader_name = None
    rival_user_id = chaser_name = chaser_user_id = None

    if my_entry and my_rank:
        if my_rank > 1:
            above = standings[my_rank - 2]
            gap_above = int(above["total_points"] - my_points)
            rival_name = above["display_name"]
            rival_user_id = above["user_id"]
        if my_rank < len(standings):
            below = standings[my_rank]
            gap_below = int(my_points - below["total_points"])
            chaser_name = below["display_name"]
            chaser_user_id = below["user_id"]
    if standings:
        leader_name = standings[0]["display_name"]

    return {
        "standings": standings,
        "member_count": member_count,
        "my_rank": my_rank,
        "my_points": my_points,
        "gap_above": gap_above,
        "gap_below": gap_below,
        "rival_name": rival_name,
        "rival_user_id": rival_user_id,
        "chaser_name": chaser_name,
        "chaser_user_id": chaser_user_id,
        "leader_name": leader_name,
    }


def _short_competition_label(comp: Competition, max_len: int = 14) -> str:
    """Compact label for race matrix column headers."""
    name = (comp.name or "").strip()
    if not name:
        return f"#{comp.id}"
    parts = name.replace("—", " ").replace("-", " ").split()
    if len(parts) >= 2:
        short = " ".join(parts[-2:])
    else:
        short = name
    if len(short) > max_len:
        return short[: max_len - 1] + "…"
    return short


def _completed_competitions_for_league(limit: int | None = None) -> list[Competition]:
    """Non-WSX competitions with results, newest first."""
    ids_with_results = [
        row[0] for row in db.session.query(CompetitionResult.competition_id).distinct().all()
    ]
    if not ids_with_results:
        return []
    q = (
        Competition.query.filter(Competition.id.in_(ids_with_results))
        .filter(_main().ama_competition_clause())
        .order_by(Competition.event_date.desc().nullslast(), Competition.id.desc())
    )
    if limit:
        q = q.limit(limit)
    return q.all()


def _league_race_matrix(league_id: int, race_limit: int = 8) -> dict:
    """Members × recent races grid with per-cell points."""
    standings = _league_member_standings(league_id)
    races = _completed_competitions_for_league(limit=race_limit)
    member_ids = [s["user_id"] for s in standings]
    comp_ids = [c.id for c in races]

    score_map: dict[tuple[int, int], int] = {}
    if comp_ids and member_ids:
        for sc in (
            CompetitionScore.query.filter(
                CompetitionScore.user_id.in_(member_ids),
                CompetitionScore.competition_id.in_(comp_ids),
            )
            .order_by(CompetitionScore.score_id.desc())
            .all()
        ):
            key = (sc.user_id, sc.competition_id)
            if key not in score_map:
                score_map[key] = int(sc.total_points or 0)

    col_best: dict[int, int | None] = {}
    for comp in races:
        pts = [score_map.get((uid, comp.id)) for uid in member_ids]
        valid = [p for p in pts if p is not None]
        col_best[comp.id] = max(valid) if valid else None

    race_cols = []
    for comp in races:
        race_cols.append({
            "id": comp.id,
            "name": comp.name,
            "short_label": _short_competition_label(comp),
            "series": comp.series or "",
            "date": comp.event_date.strftime("%d/%m") if comp.event_date else "",
            "date_full": comp.event_date.strftime("%Y-%m-%d") if comp.event_date else "",
        })

    rows = []
    for s in standings:
        cells = []
        for comp in races:
            pts = score_map.get((s["user_id"], comp.id))
            best = col_best.get(comp.id)
            cells.append({
                "competition_id": comp.id,
                "points": pts,
                "is_best": pts is not None and best is not None and pts == best,
            })
        rows.append({**s, "cells": cells})

    return {"races": race_cols, "rows": rows}


def _upcoming_competitions(limit: int = 4) -> list[dict]:
    """Next races without results (non-WSX), as compact card data."""
    ids_with_results = {
        row[0] for row in db.session.query(CompetitionResult.competition_id).distinct().all()
    }
    upcoming = (
        Competition.query.filter(_main().ama_competition_clause())
        .order_by(Competition.event_date.asc().nullslast(), Competition.id.asc())
        .all()
    )
    cards = []
    for comp in upcoming:
        if getattr(comp, "is_cancelled", False):
            continue
        if comp.id in ids_with_results:
            continue
        cards.append({
            "id": comp.id,
            "name": comp.name,
            "series": comp.series or "",
            "event_date": comp.event_date.strftime("%Y-%m-%d") if comp.event_date else "",
            "date_short": comp.event_date.strftime("%d %b") if comp.event_date else "TBA",
            "coast_250": getattr(comp, "coast_250", None),
            "is_triple_crown": bool(getattr(comp, "is_triple_crown", False)),
        })
        if len(cards) >= limit:
            break
    return cards


def _user_competition_points(user_id: int, competition_id: int) -> int | None:
    """Points for one competition (latest score row if duplicates)."""
    score = (
        CompetitionScore.query.filter_by(
            user_id=user_id, competition_id=competition_id
        )
        .order_by(CompetitionScore.score_id.desc())
        .first()
    )
    if not score or score.total_points is None:
        return None
    return int(score.total_points)


def _assess_users_picks_on_comp(user_ids: list[int], comp: Competition) -> dict[int, str]:
    """Map user_id -> 'complete' | 'partial' | 'none'."""
    if not user_ids:
        return {}
    series_u = (comp.series or "").strip().upper()
    comp_id = int(comp.id)

    if series_u == "MXON":
        nation_counts = dict(
            db.session.query(MxonNationPick.user_id, db.func.count(MxonNationPick.id))
            .filter(
                MxonNationPick.competition_id == comp_id,
                MxonNationPick.user_id.in_(user_ids),
            )
            .group_by(MxonNationPick.user_id)
            .all()
        )
        class_counts = dict(
            db.session.query(MxonClassPick.user_id, db.func.count(MxonClassPick.id))
            .filter(
                MxonClassPick.competition_id == comp_id,
                MxonClassPick.user_id.in_(user_ids),
            )
            .group_by(MxonClassPick.user_id)
            .all()
        )
        result: dict[int, str] = {}
        for uid in user_ids:
            n = int(nation_counts.get(uid, 0) or 0)
            c = int(class_counts.get(uid, 0) or 0)
            if n >= 5 and c >= 3:
                result[uid] = "complete"
            elif n > 0 or c > 0:
                result[uid] = "partial"
            else:
                result[uid] = "none"
        return result

    is_wsx = series_u == "WSX"
    is_mxgp = series_u == "MXGP"
    class_450 = "wsx_sx1" if is_wsx else ("mxgp" if is_mxgp else "450cc")
    class_250 = "wsx_sx2" if is_wsx else ("mx2" if is_mxgp else "250cc")

    race_picks = RacePick.query.filter(
        RacePick.competition_id == comp_id,
        RacePick.user_id.in_(user_ids),
    ).all()
    holeshots = HoleshotPick.query.filter(
        HoleshotPick.competition_id == comp_id,
        HoleshotPick.user_id.in_(user_ids),
    ).all()
    wildcards = {
        wc.user_id: wc
        for wc in WildcardPick.query.filter(
            WildcardPick.competition_id == comp_id,
            WildcardPick.user_id.in_(user_ids),
        ).all()
    }
    qual_by_user: dict[int, set[str]] = {}
    if is_mxgp:
        for qp in QualifyingPick.query.filter(
            QualifyingPick.competition_id == comp_id,
            QualifyingPick.user_id.in_(user_ids),
        ).all():
            if qp.rider_id:
                qual_by_user.setdefault(int(qp.user_id), set()).add(
                    (qp.class_name or "").strip().lower()
                )

    rider_ids = {p.rider_id for p in race_picks}
    rider_ids.update(h.rider_id for h in holeshots)
    riders_by_id = (
        {r.id: r for r in Rider.query.filter(Rider.id.in_(rider_ids)).all()}
        if rider_ids
        else {}
    )

    race_by_user: dict[int, dict[int, RacePick]] = {}
    for pick in race_picks:
        uid = int(pick.user_id)
        rid = int(pick.rider_id)
        bucket = race_by_user.setdefault(uid, {})
        if rid not in bucket or pick.pick_id > bucket[rid].pick_id:
            bucket[rid] = pick

    holeshot_by_user: dict[int, dict[str, bool]] = {}
    for hs in holeshots:
        uid = int(hs.user_id)
        rider = riders_by_id.get(hs.rider_id)
        if not rider:
            continue
        cls = (rider.class_name or "").strip().lower()
        flags = holeshot_by_user.setdefault(uid, {class_450: False, class_250: False})
        if cls in (class_450, "450cc", "wsx_sx1", "mxgp"):
            flags[class_450] = True
        elif cls in (class_250, "250cc", "wsx_sx2", "mx2"):
            flags[class_250] = True

    result = {}
    for uid in user_ids:
        picks_map = race_by_user.get(uid, {})
        n450 = n250 = 0
        for pick in picks_map.values():
            rider = riders_by_id.get(pick.rider_id)
            if not rider:
                continue
            cls = (rider.class_name or "").strip().lower()
            if cls in (class_450, "450cc", "wsx_sx1", "mxgp"):
                n450 += 1
            elif cls in (class_250, "250cc", "wsx_sx2", "mx2"):
                n250 += 1
        hs_flags = holeshot_by_user.get(uid, {class_450: False, class_250: False})
        wc = wildcards.get(uid)
        wildcard_complete = True if (is_wsx or is_mxgp) else bool(
            wc and wc.rider_id and wc.position is not None
        )
        qual_ok = True
        if is_mxgp:
            qset = qual_by_user.get(uid, set())
            qual_ok = "mxgp" in qset and "mx2" in qset
        race_complete = n450 == 6 and n250 == 6
        holeshot_complete = hs_flags[class_450] and hs_flags[class_250]
        started = bool(
            n450
            or n250
            or hs_flags[class_450]
            or hs_flags[class_250]
            or (wc and (wc.rider_id or wc.position))
            or (is_mxgp and qual_by_user.get(uid))
        )
        if race_complete and holeshot_complete and wildcard_complete and qual_ok:
            result[uid] = "complete"
        elif started:
            result[uid] = "partial"
        else:
            result[uid] = "none"
    return result


def _league_picks_pulse(league_id: int, viewer_id: int) -> dict | None:
    """Who in the league has submitted picks for the next open race."""
    comp = _main()._next_open_picks_competition()
    if not comp or (comp.series or "") == "WSX":
        return None

    member_rows = (
        db.session.query(User)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id)
        .all()
    )
    if not member_rows:
        return None

    member_ids = [int(r.id) for r in member_rows]
    status_map = _assess_users_picks_on_comp(member_ids, comp)

    def _member_row(u: User) -> dict:
        uid = int(u.id)
        return {
            "user_id": uid,
            "display_name": u.display_name or u.username,
            "is_me": uid == viewer_id,
            "status": status_map.get(uid, "none"),
            **_user_avatar_fields(u),
        }

    members = [_member_row(u) for u in member_rows]
    complete = [m for m in members if m["status"] == "complete"]
    partial = [m for m in members if m["status"] == "partial"]
    waiting = [m for m in members if m["status"] == "none"]

    hours_left = None
    deadline_display = None
    try:
        sched = _competition_race_schedule(comp)
        deadline_display = sched.get("pick_deadline_display")
        deadline_utc = sched.get("deadline_utc")
        if deadline_utc:
            now = get_current_time()
            if getattr(now, "tzinfo", None):
                now = now.replace(tzinfo=None)
            delta = deadline_utc - now
            hours_left = max(0, int(delta.total_seconds() // 3600))
    except Exception:
        pass

    viewer_status = status_map.get(viewer_id, "none")
    return {
        "competition_id": comp.id,
        "name": comp.name,
        "short_label": _short_competition_label(comp, max_len=22),
        "picks_url": (
            url_for("mxon_picks_page", competition_id=comp.id)
            if (comp.series or "").upper() == "MXON"
            else url_for("race_picks_page", competition_id=comp.id)
        ),
        "complete_count": len(complete),
        "partial_count": len(partial),
        "waiting_count": len(waiting),
        "member_count": len(members),
        "complete": complete,
        "partial": partial,
        "waiting": waiting,
        "deadline_display": deadline_display,
        "hours_left": hours_left,
        "viewer_status": viewer_status,
        "viewer_needs_picks": viewer_status != "complete",
    }


def _pick_points_map_from_detail(detail: dict) -> dict[str, dict]:
    """Rider name -> pick row from race results detail."""
    out: dict[str, dict] = {}
    sections = (detail or {}).get("sections") or {}
    for key in ("picks_450", "picks_250", "picks_u17"):
        for row in sections.get(key) or []:
            if row.get("kind") == "pick" and row.get("rider_name"):
                out[str(row["rider_name"])] = row
    return out


def _rival_pick_highlights(
    user_id: int,
    rival_id: int,
    rival_name: str,
    competition_id: int,
    *,
    limit: int = 3,
) -> list[str]:
    """Biggest pick swings where rival outscored you on the same race."""
    try:
        me_detail = _main()._build_race_results_detail(
            user_id, competition_id, dedupe_picks=True
        )
        rival_detail = _main()._build_race_results_detail(
            rival_id, competition_id, dedupe_picks=True
        )
    except Exception:
        return []

    me_map = _pick_points_map_from_detail(me_detail)
    rival_map = _pick_points_map_from_detail(rival_detail)
    swings: list[tuple[int, str, int, int]] = []

    for rider in set(me_map) | set(rival_map):
        mp = int(me_map.get(rider, {}).get("points") or 0)
        rp = int(rival_map.get(rider, {}).get("points") or 0)
        diff = rp - mp
        if diff > 0:
            swings.append((diff, rider, mp, rp))

    swings.sort(key=lambda x: (-x[0], x[1]))
    lines = []
    for diff, rider, mp, rp in swings[:limit]:
        if mp == 0 and rp >= 20:
            lines.append(f"{rival_name} hade perfekt på {rider} (+{rp}p)")
        else:
            lines.append(f"{rival_name} +{diff}p på {rider} ({rp} vs {mp}p)")
    return lines


def _league_h2h(user_id: int, other_id: int, race_limit: int = 20) -> dict:
    """Race-by-race wins between two league members (by competition score)."""
    races = _completed_competitions_for_league(limit=race_limit)
    me_wins = rival_wins = ties = 0
    for comp in races:
        my_pts = _user_competition_points(user_id, comp.id)
        other_pts = _user_competition_points(other_id, comp.id)
        if my_pts is None and other_pts is None:
            continue
        my_pts = my_pts or 0
        other_pts = other_pts or 0
        if my_pts > other_pts:
            me_wins += 1
        elif other_pts > my_pts:
            rival_wins += 1
        else:
            ties += 1
    return {
        "me": me_wins,
        "rival": rival_wins,
        "ties": ties,
        "races": me_wins + rival_wins + ties,
    }


def _league_rival_card(league_id: int, user_id: int, summary: dict) -> dict | None:
    """Rival / chaser comparison for the league detail page."""
    my_rank = summary.get("my_rank")
    if not my_rank:
        return None

    if my_rank > 1 and summary.get("rival_user_id"):
        opp_id = summary["rival_user_id"]
        opp_name = summary["rival_name"]
        opp_rank = my_rank - 1
        gap = summary.get("gap_above") or 0
        role = "rival"
    elif summary.get("chaser_user_id"):
        opp_id = summary["chaser_user_id"]
        opp_name = summary["chaser_name"]
        opp_rank = my_rank + 1
        gap = summary.get("gap_below") or 0
        role = "chaser"
    else:
        return None

    last_races = _completed_competitions_for_league(limit=1)
    last_race_block = None
    pick_highlights: list[str] = []

    if last_races:
        comp = last_races[0]
        my_pts = _user_competition_points(user_id, comp.id) or 0
        opp_pts = _user_competition_points(opp_id, comp.id) or 0
        last_race_block = {
            "competition_id": comp.id,
            "name": comp.name,
            "short_label": _short_competition_label(comp),
            "my_points": my_pts,
            "opp_points": opp_pts,
            "point_diff": my_pts - opp_pts,
        }
        if role == "rival" and opp_pts > my_pts:
            pick_highlights = _rival_pick_highlights(
                user_id, opp_id, opp_name, comp.id, limit=3
            )
        elif role == "chaser" and my_pts > opp_pts:
            pick_highlights = _rival_pick_highlights(
                opp_id, user_id, opp_name, comp.id, limit=2
            )

    h2h = _league_h2h(user_id, opp_id)
    opp_user = User.query.get(opp_id)
    viewer_user = User.query.get(user_id)
    return {
        "role": role,
        "opp_user_id": opp_id,
        "opp_name": opp_name,
        "opp_rank": opp_rank,
        "gap_points": gap,
        "h2h": h2h,
        "last_race": last_race_block,
        "pick_highlights": pick_highlights,
        "opp_avatar": _user_avatar_fields(opp_user),
        "viewer_avatar": _user_avatar_fields(viewer_user),
    }


def _league_last_race_digest(league_id: int, user_id: int, summary: dict) -> dict | None:
    """Post-race story: how the latest race shook up the league."""
    races = _completed_competitions_for_league(limit=1)
    if not races:
        return None

    comp = races[0]
    member_rows = (
        db.session.query(User)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id)
        .all()
    )
    uid_map = {int(u.id): u for u in member_rows}
    race_scores = []
    for u in member_rows:
        pts = _user_competition_points(int(u.id), comp.id)
        if pts is not None:
            race_scores.append({
                "user_id": int(u.id),
                "display_name": (u.display_name or u.username),
                "points": pts,
                **_user_avatar_fields(u),
            })
    if not race_scores:
        return None

    race_scores.sort(key=lambda x: (-x["points"], x["display_name"].lower()))
    for i, row in enumerate(race_scores, start=1):
        row["race_rank"] = i

    my_row = next((r for r in race_scores if r["user_id"] == user_id), None)
    winner = race_scores[0]
    winner_user = uid_map.get(winner["user_id"])
    highlights: list[str] = []

    if my_row:
        if my_row["race_rank"] == 1:
            highlights.append("Du vann racet i ligan 🏆")
        elif winner["user_id"] != user_id:
            gap = winner["points"] - my_row["points"]
            highlights.append(
                f"{winner['display_name']} vann liga-racet (+{gap}p mer än dig)"
            )

        rival_id = summary.get("rival_user_id")
        if rival_id and summary.get("my_rank", 0) > 1:
            rival_row = next((r for r in race_scores if r["user_id"] == rival_id), None)
            if rival_row:
                diff = my_row["points"] - rival_row["points"]
                rname = summary.get("rival_name") or rival_row["display_name"]
                if diff > 0:
                    highlights.append(f"+{diff}p före {rname} detta race")
                elif diff < 0:
                    highlights.append(f"{rname} slog dig med +{-diff}p detta race")

        try:
            detail = _main()._build_race_results_detail(
                user_id, comp.id, dedupe_picks=True
            )
            secs = (detail or {}).get("sections") or {}
            perfects = [
                r["rider_name"]
                for r in (secs.get("picks_450") or [])
                + (secs.get("picks_250") or [])
                + (secs.get("picks_u17") or [])
                if r.get("status") == "perfect"
            ]
            if perfects:
                highlights.append(
                    f"Perfekt pick: {perfects[0]}"
                    + (f" (+{len(perfects)-1} till)" if len(perfects) > 1 else "")
                )
            hs_pts = int((detail.get("summary") or {}).get("holeshot_points") or 0)
            if hs_pts >= 20:
                highlights.append(f"Full holeshot-träff (+{hs_pts}p)")
        except Exception:
            pass

    return {
        "competition_id": comp.id,
        "name": comp.name,
        "short_label": _short_competition_label(comp, max_len=22),
        "trackmap_url": url_for(
            "trackmaps_competition_page", competition_id=comp.id, league_id=league_id
        ),
        "my_points": my_row["points"] if my_row else None,
        "my_race_rank": my_row["race_rank"] if my_row else None,
        "member_count": len(member_rows),
        "scored_count": len(race_scores),
        "winner_name": winner["display_name"],
        "winner_points": winner["points"],
        "winner_user_id": winner["user_id"],
        **_user_avatar_fields(winner_user),
        "highlights": highlights[:4],
    }

def calculate_league_points(league_id, competition_id):
    """Calculate fair league points based on member race pick performance.

    Fair system that works regardless of league size:
    - 1 member: Use their score directly
    - 2 members: Use average of both
    - 3-4 members: Use average of top 2
    - 5-6 members: Use average of top 3
    - 7+ members: Use average of top 50% (rounded up)

    This ensures smaller leagues can compete fairly with larger ones,
    while still rewarding leagues with multiple strong performers.
    """
    try:
        members = (
            db.session.query(User)
            .join(LeagueMembership)
            .filter(LeagueMembership.league_id == league_id)
            .all()
        )

        if not members:
            return 0

        # Exclude WSX competitions - league points should only count SX, MX, SMX
        competition = Competition.query.get(competition_id)
        if competition and competition.series == "WSX":
            return 0

        member_scores = []
        for member in members:
            score = CompetitionScore.query.filter_by(
                user_id=member.id,
                competition_id=competition_id,
            ).first()
            if score and score.total_points:
                member_scores.append(score.total_points)

        if not member_scores:
            return 0

        member_scores.sort(reverse=True)
        num_members = len(member_scores)

        if num_members == 1:
            final_score = member_scores[0]
            top_n = 1
        elif num_members == 2:
            final_score = sum(member_scores) / 2
            top_n = 2
        elif num_members <= 4:
            final_score = sum(member_scores[:2]) / 2
            top_n = 2
        elif num_members <= 6:
            final_score = sum(member_scores[:3]) / 3
            top_n = 3
        else:
            top_n = (num_members + 1) // 2
            final_score = sum(member_scores[:top_n]) / top_n

        print(
            f"🏆 League {league_id}: {num_members} members, "
            f"using top {top_n}, league score: {final_score:.1f}"
        )

        return round(final_score, 1)

    except Exception as e:
        print(f"Error calculating league points: {e}")
        return 0


def update_league_points_for_competition(competition_id):
    """Recalculate league totals after a competition is scored (avoids double-count on re-import)."""
    try:
        comp = Competition.query.get(competition_id)
        if comp and (getattr(comp, "series", None) or "").strip().upper() in TIPPA_ONLY_SERIES:
            print(
                f"ℹ️ Skipping league recalc for tippa-only competition "
                f"{competition_id} ({comp.series})"
            )
            return
        _recalculate_all_league_totals()
        print(f"✅ Recalculated league points after competition {competition_id}")
    except Exception as e:
        print(f"❌ Error updating league points: {e}")
        db.session.rollback()
        raise e


def _recalculate_all_league_totals() -> None:
    """Sum fair per-race league scores into League.total_points (AMA only — tippa-only excluded)."""
    competitions_with_results = (
        db.session.query(Competition.id)
        .join(CompetitionScore, Competition.id == CompetitionScore.competition_id)
        .filter(_main().ama_competition_clause())
        .distinct()
        .order_by(Competition.id.asc())
        .all()
    )
    comp_ids = [row[0] for row in competitions_with_results]

    for league in League.query.all():
        league_total = sum(
            calculate_league_points(league.id, comp_id) for comp_id in comp_ids
        )
        league.total_points = round(league_total, 1)

    db.session.commit()
