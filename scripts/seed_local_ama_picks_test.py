"""Local-only: finish AMA Local Test with fake results so my_scores season-team UI works.

Run from repo root: python scripts/seed_local_ama_picks_test.py --finish
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app, calculate_scores, recalculate_season_team_total_points
from models import (
    Competition,
    CompetitionResult,
    HoleshotPick,
    HoleshotResult,
    RacePick,
    Rider,
    SeasonTeam,
    SeasonTeamRider,
    User,
    WildcardPick,
    db,
)

TEST_NAME = "AMA Local Test"
TEST_DATE = date(2026, 10, 12)
USERNAME = "spliffan"


def _ensure_competition() -> Competition:
    comp = Competition.query.filter_by(name=TEST_NAME).first()
    if not comp:
        comp = Competition(
            name=TEST_NAME,
            series="SMX",
            series_id=12,
            event_date=TEST_DATE,
            start_time=time(19, 0),
            timezone="America/Chicago",
        )
        db.session.add(comp)
        db.session.flush()
        print(f"Created competition id={comp.id}")
    else:
        comp.series = "SMX"
        comp.series_id = 12
        if not comp.event_date:
            comp.event_date = TEST_DATE
        print(f"Using competition id={comp.id}")
    return comp


def _ensure_season_team(user: User) -> SeasonTeam:
    team = SeasonTeam.query.filter_by(user_id=user.id).first()
    if not team:
        team = SeasonTeam(
            user_id=user.id,
            team_name=f"{USERNAME} Local Test",
            total_points=0,
        )
        db.session.add(team)
        db.session.flush()
        print(f"Created season team id={team.id}")
    existing = {
        tr.rider_id
        for tr in SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
    }
    if len(existing) < 4:
        SeasonTeamRider.query.filter_by(season_team_id=team.id).delete()
        for class_name, limit in (("450cc", 2), ("250cc", 2)):
            rows = (
                Rider.query.filter_by(class_name=class_name)
                .order_by(Rider.price.desc())
                .limit(limit)
                .all()
            )
            for r in rows:
                db.session.add(SeasonTeamRider(season_team_id=team.id, rider_id=r.id))
                print(f"  team + {r.class_name} #{r.rider_number} {r.name}")
    return team


def _rider(rid: int) -> Rider:
    r = db.session.get(Rider, rid)
    if not r:
        raise SystemExit(f"Missing rider id={rid}")
    return r


def _ensure_picks(user: User, comp: Competition) -> None:
    """Recreate picks matching the earlier local UI test (if missing)."""
    if RacePick.query.filter_by(user_id=user.id, competition_id=comp.id).count() >= 12:
        print("Picks already present")
        return

    RacePick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
    HoleshotPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
    WildcardPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()

    # From the picks screenshot
    picks_450 = [489, 483, 463, 462, 469, 340]  # Hunter, Prado, Webb, Jett, Ferrandis, Marchbanks
    picks_250 = [356, 412, 338, 405, 337, 589]  # Davies, Kitchen, Difrancesco, Hymas, Beaumer, Minear
    for pos, rid in enumerate(picks_450, 1):
        db.session.add(
            RacePick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=rid,
                predicted_position=pos,
            )
        )
    for pos, rid in enumerate(picks_250, 1):
        db.session.add(
            RacePick(
                user_id=user.id,
                competition_id=comp.id,
                rider_id=rid,
                predicted_position=pos,
            )
        )
    db.session.add(
        HoleshotPick(user_id=user.id, competition_id=comp.id, rider_id=489, class_name="450cc")
    )
    db.session.add(
        HoleshotPick(user_id=user.id, competition_id=comp.id, rider_id=412, class_name="250cc")
    )
    db.session.add(
        WildcardPick(
            user_id=user.id,
            competition_id=comp.id,
            rider_id=560,  # Christian Craig 450cc
            position=17,
        )
    )
    print("Seeded tippa picks for spliffan")


def _finish_with_results(comp: Competition, team: SeasonTeam) -> None:
    """Fake overall: team riders score, tippa gets some hits."""
    CompetitionResult.query.filter_by(competition_id=comp.id).delete()
    HoleshotResult.query.filter_by(competition_id=comp.id).delete()

    # Move race to yesterday so it feels finished
    comp.event_date = date.today() - timedelta(days=1)
    if hasattr(comp, "start_time"):
        comp.start_time = time(19, 0)

    # Team must predate the race or season points stay 0
    from datetime import datetime

    if not team.created_at or team.created_at.date() > comp.event_date:
        team.created_at = datetime.combine(comp.event_date - timedelta(days=14), time(12, 0))
        print(f"Backdated team created_at -> {team.created_at}")

    # 450 results — include season-team Jett(462)=2, Webb(463)=4
    results_450 = [
        (489, 1),  # Hunter
        (462, 2),  # Jett (team)
        (483, 3),  # Prado
        (463, 4),  # Webb (team)
        (464, 5),  # Tomac
        (469, 6),  # Ferrandis
        (466, 7),  # Plessinger
        (473, 8),  # Justin Cooper
        (340, 9),  # Marchbanks
        (560, 17),  # Craig — matches wildcard spot
    ]
    # 250 results — Davies(356)=1, Difrancesco(338)=5
    results_250 = [
        (356, 1),  # Davies (team)
        (412, 2),  # Kitchen
        (339, 3),  # Shimoda
        (405, 4),  # Hymas
        (338, 5),  # Difrancesco (team)
        (337, 6),  # Beaumer
        (589, 7),  # Minear
    ]

    for rid, pos in results_450:
        r = _rider(rid)
        db.session.add(
            CompetitionResult(
                competition_id=comp.id,
                rider_id=rid,
                position=pos,
                class_name="450cc",
            )
        )
        print(f"  450 P{pos}: #{r.rider_number} {r.name}")
    for rid, pos in results_250:
        r = _rider(rid)
        db.session.add(
            CompetitionResult(
                competition_id=comp.id,
                rider_id=rid,
                position=pos,
                class_name="250cc",
            )
        )
        print(f"  250 P{pos}: #{r.rider_number} {r.name}")

    db.session.add(
        HoleshotResult(competition_id=comp.id, rider_id=489, class_name="450cc")
    )
    db.session.add(
        HoleshotResult(competition_id=comp.id, rider_id=412, class_name="250cc")
    )
    print("Holeshots: Hunter 450 / Kitchen 250")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--finish",
        action="store_true",
        help="Seed results, move date to yesterday, recalculate tippa + season team points",
    )
    args = parser.parse_args()

    with app.app_context():
        user = User.query.filter_by(username=USERNAME).first()
        if not user:
            raise SystemExit(f"User {USERNAME!r} not found")

        comp = _ensure_competition()
        team = _ensure_season_team(user)
        _ensure_picks(user, comp)

        if args.finish:
            _finish_with_results(comp, team)
            db.session.commit()
            calculate_scores(comp.id)
            pts = recalculate_season_team_total_points(team)
            db.session.commit()
            print()
            print(f"Season team total_points now: {pts}")
            print(f"Open my scores: http://127.0.0.1:5000/my_scores?focus={comp.id}")
            print(f"Or details API: /get_season_team_competition_details/{comp.id}")
        else:
            db.session.commit()
            print()
            print(f"Open race picks:  http://127.0.0.1:5000/race_picks/{comp.id}")
            print("Re-run with --finish to load fake results for my_scores.")


if __name__ == "__main__":
    main()
