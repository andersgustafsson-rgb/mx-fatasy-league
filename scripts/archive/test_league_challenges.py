#!/usr/bin/env python3
"""Simulate league duel flow (all 3 types) + resolution + shame avatars.

Safe to run locally — rolls back DB changes at the end unless --keep is passed.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from main import (
    app,
    _challenge_picks_summary,
    _challenge_riders_for_competition,
    _challenge_brands_for_competition,
    _league_shame_map,
    _lock_challenge_if_ready,
    _next_open_picks_competition,
    _resolve_single_challenge,
    _recompute_user_challenge_badge,
    _rider_position,
    is_picks_locked,
)
from models import (
    Competition,
    CompetitionResult,
    LeagueChallenge,
    LeagueMembership,
    Rider,
    User,
    UserLeagueChallengeBadge,
    db,
)


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL {msg}")
    raise SystemExit(1)


def _api(client, method: str, path: str, user_id: int, payload: dict | None = None):
    with client.session_transaction() as s:
        s["user_id"] = user_id
    fn = getattr(client, method.lower())
    kwargs = {"json": payload} if payload is not None else {}
    return fn(path, **kwargs)


def _make_challenge(league_id: int, a_id: int, b_id: int, comp_id: int) -> LeagueChallenge:
    ch = LeagueChallenge(
        league_id=league_id,
        competition_id=comp_id,
        challenger_id=a_id,
        challenged_id=b_id,
        status="pending_type",
    )
    db.session.add(ch)
    db.session.flush()
    return ch


def _find_league_pair():
    rows = (
        db.session.query(LeagueMembership.league_id)
        .group_by(LeagueMembership.league_id)
        .having(db.func.count(LeagueMembership.user_id) >= 2)
        .all()
    )
    for (league_id,) in rows:
        members = (
            LeagueMembership.query.filter_by(league_id=league_id)
            .order_by(LeagueMembership.user_id)
            .limit(2)
            .all()
        )
        if len(members) >= 2:
            return league_id, members[0].user_id, members[1].user_id
    return None, None, None


def _scored_competition() -> Competition | None:
    for comp in (
        Competition.query.filter(Competition.event_date.isnot(None))
        .order_by(Competition.event_date.desc())
        .all()
    ):
        if CompetitionResult.query.filter_by(competition_id=comp.id).first():
            return comp
    return None


def _riders_for(comp: Competition, class_name: str = "450cc", n: int = 4) -> list[Rider]:
    groups = _challenge_riders_for_competition(comp)
    rows = [r for r in groups.get(class_name, []) if not r.get("is_out")]
    ids = [r["id"] for r in rows[:n]]
    return Rider.query.filter(Rider.id.in_(ids)).all() if ids else []


def _cleanup_test_challenges(league_id: int, user_ids: list[int], comp_id: int) -> None:
    rows = LeagueChallenge.query.filter(
        LeagueChallenge.league_id == league_id,
        LeagueChallenge.competition_id == comp_id,
        db.or_(
            LeagueChallenge.challenger_id.in_(user_ids),
            LeagueChallenge.challenged_id.in_(user_ids),
        ),
    ).all()
    for ch in rows:
        db.session.delete(ch)
    if rows:
        db.session.flush()
        print(f"  (cleared {len(rows)} existing duel(s) for test pair)")


def simulate_api_flow(league_id: int, a_id: int, b_id: int, comp: Competition) -> None:
    print("\n== API flow (open picks) ==")
    _cleanup_test_challenges(league_id, [a_id, b_id], comp.id)
    riders = _riders_for(comp, "450cc", 4)
    brands = _challenge_brands_for_competition(comp)
    if len(riders) < 3:
        _fail("Need at least 3 riders for simulation")
    if len(brands) < 2:
        _fail("Need at least 2 brands for simulation")

    # --- head_to_head ---
    ch = _make_challenge(league_id, a_id, b_id, comp.id)
    ch.challenge_type = "head_to_head"
    ch.class_name = "450cc"
    ch.rider_a_id = riders[0].id
    ch.rider_b_id = riders[1].id
    ch.status = "pending_answers"
    ch.challenger_guess_rider_id = riders[0].id
    ch.challenger_answered_at = datetime.utcnow()
    _lock_challenge_if_ready(ch)
    if ch.status != "locked":
        _fail(f"head_to_head expected locked, got {ch.status}")
    picks = _challenge_picks_summary(ch)
    if not picks.get("show") or len(picks["rows"]) < 2:
        _fail(f"picks summary incomplete: {picks}")
    _ok(f"head_to_head locked + {len(picks['rows'])} pick rows")
    db.session.delete(ch)
    db.session.flush()

    # --- h2h ---
    ch = _make_challenge(league_id, a_id, b_id, comp.id)
    ch.challenge_type = "h2h"
    ch.class_name = "450cc"
    ch.status = "pending_answers"
    ch.challenger_rider_id = riders[0].id
    ch.challenger_position = 3
    ch.challenger_answered_at = datetime.utcnow()
    ch.challenged_rider_id = riders[2].id
    ch.challenged_position = 7
    ch.challenged_answered_at = datetime.utcnow()
    _lock_challenge_if_ready(ch)
    if ch.status != "locked":
        _fail(f"h2h expected locked, got {ch.status}")
    _ok("h2h locked after both answers")
    db.session.delete(ch)
    db.session.flush()

    # --- brand_battle ---
    ch = _make_challenge(league_id, a_id, b_id, comp.id)
    ch.challenge_type = "brand_battle"
    ch.class_name = "450cc"
    ch.brand_a = brands[0]
    ch.brand_b = brands[1]
    ch.status = "pending_answers"
    ch.challenger_brand_pick = brands[0]
    ch.challenger_answered_at = datetime.utcnow()
    ch.challenged_brand_pick = brands[1]
    ch.challenged_answered_at = datetime.utcnow()
    _lock_challenge_if_ready(ch)
    if ch.status != "locked":
        _fail(f"brand_battle expected locked, got {ch.status}")
    _ok("brand_battle locked after both picks")
    db.session.delete(ch)
    db.session.flush()


def simulate_resolution(league_id: int, a_id: int, b_id: int, comp: Competition) -> None:
    print("\n== Resolution (scored race) ==")
    riders = _riders_for(comp, "450cc", 4)
    brands = _challenge_brands_for_competition(comp)
    if len(riders) < 2 or len(brands) < 2:
        _fail("Not enough riders/brands on scored comp")

    pos_a = _rider_position(comp.id, riders[0].id)
    pos_b = _rider_position(comp.id, riders[1].id)
    if not pos_a or not pos_b:
        _fail("Scored comp missing rider positions for test pair")
    winner_rider = riders[0].id if pos_a < pos_b else riders[1].id
    loser_guess = riders[1].id if winner_rider == riders[0].id else riders[0].id

    ch = LeagueChallenge(
        league_id=league_id,
        competition_id=comp.id,
        challenger_id=a_id,
        challenged_id=b_id,
        status="locked",
        challenge_type="head_to_head",
        class_name="450cc",
        rider_a_id=riders[0].id,
        rider_b_id=riders[1].id,
        challenger_guess_rider_id=winner_rider,
        challenger_answered_at=datetime.utcnow(),
    )
    db.session.add(ch)
    db.session.flush()
    _resolve_single_challenge(ch)
    _recompute_user_challenge_badge(a_id, league_id, comp.id)
    _recompute_user_challenge_badge(b_id, league_id, comp.id)
    db.session.flush()

    if ch.status != "resolved":
        _fail(f"resolution status {ch.status}: {ch.result_summary}")
    if ch.winner_id != a_id:
        _fail(f"expected challenger to win, winner={ch.winner_id}")
    _ok(f"head_to_head resolved: {ch.result_summary}")

    badge_a = UserLeagueChallengeBadge.query.filter_by(
        user_id=a_id, league_id=league_id, competition_id=comp.id
    ).first()
    badge_b = UserLeagueChallengeBadge.query.filter_by(
        user_id=b_id, league_id=league_id, competition_id=comp.id
    ).first()
    if not badge_a or badge_a.kind != "glory":
        _fail("challenger should have glory badge")
    if not badge_b or badge_b.kind != "shame":
        _fail("challenged should have shame badge (implicit loser on head_to_head)")
    _ok(f"badges: winner={badge_a.badge_key}, loser={badge_b.badge_key}")

    shame = _league_shame_map(league_id)
    if b_id not in shame:
        _fail(f"shame map missing loser: {shame}")
    _ok(f"shame avatar for loser: {shame[b_id]['emoji']} {shame[b_id]['label']}")

    # page render check
    with app.test_client() as client:
        with client.session_transaction() as s:
            s["user_id"] = a_id
        r = client.get(f"/leagues/{league_id}")
        html = r.data.decode("utf-8", "replace")
        if r.status_code != 200:
            _fail(f"league page {r.status_code}")
        if "user-avatar--shamed" not in html:
            _fail("shame overlay not in league page HTML")
        _ok("league page renders shame overlay")

    db.session.delete(ch)
    if badge_a:
        db.session.delete(badge_a)
    if badge_b:
        db.session.delete(badge_b)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate league duels")
    parser.add_argument("--keep", action="store_true", help="Keep DB changes (default: rollback)")
    args = parser.parse_args()

    with app.app_context():
        league_id, a_id, b_id = _find_league_pair()
        if not league_id:
            print("No league with 2+ members found.")
            return 1

        open_comp = _next_open_picks_competition()
        scored_comp = _scored_competition()
        print(f"League #{league_id}, users {a_id} vs {b_id}")
        print(f"Open picks race: {open_comp.name if open_comp else 'none'}")
        print(f"Scored race: {scored_comp.name if scored_comp else 'none'}")

        try:
            if open_comp and not is_picks_locked(open_comp):
                simulate_api_flow(league_id, a_id, b_id, open_comp)
            else:
                print("\n== API flow skipped (no open picks race) ==")

            if scored_comp:
                simulate_resolution(league_id, a_id, b_id, scored_comp)
            else:
                print("\n== Resolution skipped (no scored race) ==")

            print("\nAll simulations passed.")
            if args.keep:
                db.session.commit()
                print("(changes kept)")
            else:
                db.session.rollback()
                print("(rolled back — no data changed)")
            return 0
        except SystemExit as e:
            db.session.rollback()
            return int(e.code or 1)
        except Exception as e:
            db.session.rollback()
            print(f"\nERROR: {e}")
            raise


if __name__ == "__main__":
    sys.exit(main())
