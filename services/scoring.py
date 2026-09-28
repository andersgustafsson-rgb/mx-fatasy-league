"""Fantasy tippa + säsongsteam scoring.

Skiva 1: pure helpers. Skiva 2: calculate_scores.
Se docs/REFACTOR.md. Beteende oförändrat vs tidigare main.py.
"""
from __future__ import annotations

from typing import Any

from models import (
    Competition,
    CompetitionResult,
    CompetitionScore,
    HoleshotPick,
    HoleshotResult,
    QualifyingPick,
    QualifyingResult,
    RacePick,
    Rider,
    SeasonTeam,
    User,
    WildcardPick,
    db,
)

# Keep in sync with main.TIPPA_ONLY_SERIES (skiva 2: duplicate on purpose).
TIPPA_ONLY_SERIES = frozenset({"WSX", "MXON", "MXGP"})


def calculate_rider_points_for_position(position) -> int:
    """Calculate points for a rider based on their finishing position (season team system)"""
    if position is None or position == 0:
        return 0

    # Season team points system - higher rewards for top positions
    if position == 1:
        return 25
    if position == 2:
        return 20
    if position == 3:
        return 15
    if position == 4:
        return 12
    if position == 5:
        return 10
    if position == 6:
        return 8
    if position <= 10:
        return 5
    if position <= 15:
        return 3
    if position <= 20:
        return 1
    return 0


def calculate_race_pick_points(predicted_position, actual_position) -> int:
    """
    Calculate points for a race pick based on how close the prediction was.
    Uses the new scoring system (Förslag 3):
    - Rätt plats: 25 poäng
    - 1 plats fel: 18 poäng
    - 2 platser fel: 13 poäng
    - 3 platser fel: 9 poäng
    - 4 platser fel: 6 poäng
    - 5+ platser fel: 3 poäng
    """
    if actual_position is None:
        return 0

    if predicted_position == actual_position:
        return 25

    diff = abs(predicted_position - actual_position)

    if diff == 1:
        return 18
    if diff == 2:
        return 13
    if diff == 3:
        return 9
    if diff == 4:
        return 6
    return 3


def holeshot_result_class_bucket(raw_class: str | None) -> str:
    """
    Normalisera holeshot_results.kolumnen "class" till 450cc / 250cc.
    Olika importvägar eller manuella rader kan ge "450", "SX1", mellanslag m.m.
    Okända värden ger tom sträng (raden ignoreras vid uppslag).
    """
    c = (raw_class or "").strip().lower().replace(" ", "")
    if c in ("450cc", "450", "sx450", "sx1", "wsx_sx1", "mxgp"):
        return "450cc"
    if c in ("250cc", "250", "sx250", "sx2", "wsx_sx2", "250east", "250west", "mx2"):
        return "250cc"
    return ""


def holeshot_results_by_bucket(holeshots: list) -> dict[str, Any]:
    """Bygg {450cc: HoleshotResult, 250cc: ...} med normaliserade nycklar och dedupe."""
    out: dict[str, Any] = {}
    for hs in holeshots:
        bucket = holeshot_result_class_bucket(getattr(hs, "class_name", None))
        if bucket not in ("450cc", "250cc"):
            print(
                f"WARNING: HoleshotResult id={getattr(hs, 'id', '?')} "
                f"competition_id={getattr(hs, 'competition_id', '?')} "
                f"has unrecognized class={getattr(hs, 'class_name', None)!r} (skipped for scoring)"
            )
            continue
        existing = out.get(bucket)
        if existing is not None:
            ex_id = getattr(existing, "id", 0) or 0
            hs_id = getattr(hs, "id", 0) or 0
            if hs_id > ex_id:
                print(
                    f"WARNING: Duplicate HoleshotResult for {bucket}; "
                    f"keeping id={hs_id} over id={ex_id}"
                )
                out[bucket] = hs
            else:
                print(
                    f"WARNING: Duplicate HoleshotResult for {bucket}; "
                    f"keeping id={ex_id} over id={hs_id}"
                )
        else:
            out[bucket] = hs
    return out


def holeshot_pick_class_for_result(pick_class: str) -> str:
    """
    HoleshotResult använder alltid class_name 450cc / 250cc (bucket).
    Picks kan sparas som wsx_sx1/mxgp m.m. — mappa till samma bucket som resultatraden.
    """
    c = (pick_class or "").strip().lower().replace(" ", "")
    if c in ("wsx_sx1", "450cc", "450", "sx450", "sx1", "mxgp"):
        return "450cc"
    if c in ("wsx_sx2", "250cc", "250", "sx250", "sx2", "250east", "250west", "mx2"):
        return "250cc"
    return pick_class or ""


def calculate_scores(comp_id: int):
    # Determine series for this competition (to disable features for WSX)
    comp = Competition.query.get(comp_id)
    series_name = getattr(comp, "series", None)
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()

    users = User.query.all()
    actual_results = CompetitionResult.query.filter_by(competition_id=comp_id).all()
    actual_holeshots = HoleshotResult.query.filter_by(competition_id=comp_id).all()

    print(
        f"DEBUG: Found {len(users)} users, {len(actual_results)} results, "
        f"{len(actual_holeshots)} holeshots"
    )

    # Check for duplicates and handle them (keep the one with highest result_id = most recent)
    seen_riders = {}
    duplicate_count = 0
    for res in actual_results:
        if res.rider_id in seen_riders:
            duplicate_count += 1
            # Keep the one with higher result_id (more recent)
            if res.result_id > seen_riders[res.rider_id].result_id:
                seen_riders[res.rider_id] = res
        else:
            seen_riders[res.rider_id] = res

    if duplicate_count > 0:
        print(
            f"⚠️ WARNING: Found {duplicate_count} duplicate results for competition "
            f"{comp_id}. Using most recent entry for each rider."
        )

    actual_results_dict = seen_riders
    actual_holeshots_dict = holeshot_results_by_bucket(actual_holeshots)

    for user in users:
        race_points = 0
        holeshot_points = 0
        wildcard_points = 0
        picks = RacePick.query.filter_by(user_id=user.id, competition_id=comp_id).all()

        # Check for duplicate RacePick entries (same user, competition, rider)
        # Keep only the most recent one (highest pick_id). Endast *förlorande* rad raderas —
        # annars kan båda hamna i delete-listan om DB returnerar äldre rad före nyare.
        seen_picks = {}
        duplicate_picks = []
        for pick in picks:
            key = (pick.user_id, pick.competition_id, pick.rider_id)
            if key not in seen_picks:
                seen_picks[key] = pick
                continue
            existing = seen_picks[key]
            if pick.pick_id > existing.pick_id:
                duplicate_picks.append(existing)
                seen_picks[key] = pick
            else:
                duplicate_picks.append(pick)

        if duplicate_picks:
            print(
                f"⚠️ WARNING: Found {len(duplicate_picks)} duplicate RacePick entries for "
                f"{user.username} in competition {comp_id}. Removing duplicates..."
            )
            for dup in duplicate_picks:
                print(
                    f"  - Deleting duplicate pick_id={dup.pick_id} for "
                    f"rider_id={dup.rider_id}, position={dup.predicted_position}"
                )
                db.session.delete(dup)
            # Commit deletions immediately to avoid issues
            db.session.commit()
            print(f"DEBUG: Kept {len(seen_picks)} unique picks for {user.username}")

        # Use only unique picks for scoring
        unique_picks = list(seen_picks.values())

        if user.username == "Robban B":
            print("DEBUG: ===== Robban B Score Calculation =====")
            print(f"DEBUG: Found {len(picks)} total picks in database")
            print(f"DEBUG: Found {len(duplicate_picks)} duplicate picks")
            print(f"DEBUG: Kept {len(unique_picks)} unique picks after deduplication")
            for pick in unique_picks:
                rider = Rider.query.get(pick.rider_id)
                rider_name = rider.name if rider else f"rider {pick.rider_id}"
                print(
                    f"  - Pick: {rider_name} at position {pick.predicted_position} "
                    f"(pick_id={pick.pick_id})"
                )

        for pick in unique_picks:
            actual_pos_for_pick = (
                actual_results_dict.get(pick.rider_id).position
                if pick.rider_id in actual_results_dict
                else None
            )
            # Use new scoring system based on position difference
            race_points += calculate_race_pick_points(
                pick.predicted_position, actual_pos_for_pick
            )

        holeshot_picks = HoleshotPick.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).all()

        # Check for duplicate HoleshotPick entries (same user, competition, class)
        # Keep only the most recent one (highest id); radera bara den äldre dubbletten.
        seen_holeshots = {}
        duplicate_holeshots = []
        for hp in holeshot_picks:
            key = (hp.user_id, hp.competition_id, hp.class_name)
            if key not in seen_holeshots:
                seen_holeshots[key] = hp
                continue
            existing = seen_holeshots[key]
            if hp.id > existing.id:
                duplicate_holeshots.append(existing)
                seen_holeshots[key] = hp
            else:
                duplicate_holeshots.append(hp)

        if duplicate_holeshots:
            print(
                f"⚠️ WARNING: Found {len(duplicate_holeshots)} duplicate HoleshotPick "
                f"entries for {user.username} in competition {comp_id}. Removing duplicates..."
            )
            for dup in duplicate_holeshots:
                print(
                    f"  - Deleting duplicate holeshot id={dup.id} for "
                    f"class={dup.class_name}, rider_id={dup.rider_id}"
                )
                db.session.delete(dup)
            # Commit deletions immediately to avoid issues
            db.session.commit()
            print(
                f"DEBUG: Kept {len(seen_holeshots)} unique holeshot picks for {user.username}"
            )

        # Use only unique holeshot picks for scoring
        unique_holeshot_picks = list(seen_holeshots.values())

        holeshot_450_correct = False
        holeshot_250_correct = False
        for hp in unique_holeshot_picks:
            bucket = holeshot_pick_class_for_result(hp.class_name)
            actual_hs = actual_holeshots_dict.get(bucket)
            if actual_hs and actual_hs.rider_id == hp.rider_id:
                if bucket == "450cc":
                    holeshot_450_correct = True
                    holeshot_points += 10
                elif bucket == "250cc":
                    holeshot_250_correct = True
                    holeshot_points += 10

        # Bonus: Om båda holeshots är rätt, ge 25 poäng totalt istället för 20
        if holeshot_450_correct and holeshot_250_correct:
            holeshot_points = 25

        series_u = (series_name or "").strip().upper()
        # Wildcard: AMA/SMX only. WSX/MXGP tippa-only har ingen wildcard.
        if series_u not in TIPPA_ONLY_SERIES:
            wc_pick = WildcardPick.query.filter_by(
                user_id=user.id, competition_id=comp_id
            ).first()
            if wc_pick:
                # Wildcard is always 450cc, so filter results to only 450cc
                actual_results_450cc = []
                for res in actual_results:
                    rider = Rider.query.get(res.rider_id)
                    if rider and rider.class_name == "450cc":
                        actual_results_450cc.append(res)
                actual_wc = next(
                    (
                        res
                        for res in actual_results_450cc
                        if res.position == wc_pick.position
                    ),
                    None,
                )
                if actual_wc and actual_wc.rider_id == wc_pick.rider_id:
                    wildcard_points += 15

        # MXGP: qualifying winners scored into wildcard_points column (no WC on MXGP)
        if series_u == "MXGP":
            qual_results = {
                (q.class_name or "").strip().lower(): q
                for q in QualifyingResult.query.filter_by(competition_id=comp_id).all()
            }
            for qp in QualifyingPick.query.filter_by(
                user_id=user.id, competition_id=comp_id
            ).all():
                cls = (qp.class_name or "").strip().lower()
                actual_q = qual_results.get(cls)
                if actual_q and actual_q.rider_id == qp.rider_id:
                    wildcard_points += 10

        total_points = race_points + holeshot_points + wildcard_points

        # Check for duplicates first (in case calculate_scores was called multiple times)
        all_score_entries = CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).all()

        if len(all_score_entries) > 1:
            # Found duplicates - keep the first one, delete the rest
            print(
                f"⚠️ WARNING: Found {len(all_score_entries)} duplicate score entries for "
                f"{user.username} in competition {comp_id}. Fixing..."
            )
            score_entry = all_score_entries[0]
            for dup in all_score_entries[1:]:
                db.session.delete(dup)
        elif len(all_score_entries) == 1:
            score_entry = all_score_entries[0]
        else:
            score_entry = CompetitionScore(user_id=user.id, competition_id=comp_id)
            db.session.add(score_entry)
            print(f"DEBUG: Created new score entry for {user.username}")

        score_entry.total_points = total_points
        score_entry.race_points = race_points
        score_entry.holeshot_points = holeshot_points
        score_entry.wildcard_points = wildcard_points

        if user.username == "Robban B":
            print("DEBUG: Robban B FINAL SCORES:")
            print(f"  - Race points: {race_points}")
            print(f"  - Holeshot points: {holeshot_points}")
            print(f"  - Wildcard points: {wildcard_points}")
            print(f"  - TOTAL: {total_points}")
            print("DEBUG: ===== End Robban B Calculation =====")

        print(
            f"DEBUG: {user.username} - Race: {race_points}, Holeshot: {holeshot_points}, "
            f"Wildcard: {wildcard_points}, Total: {total_points}"
        )

        # Debug: Check if user has any picks at all
        all_user_picks = RacePick.query.filter_by(user_id=user.id).all()
        print(
            f"DEBUG: {user.username} has {len(all_user_picks)} total picks "
            f"across all competitions"
        )

    db.session.commit()

    # Update season team points based on rider results (separate from race picks)
    # NOTE: This recalculates points based on ALL race results in the database
    # If you want to reset points to 0 for a new season, use /reset_season_team_points first
    # and make sure to clear old CompetitionResult entries for previous season
    # Update season team points after race scores (no retroactive races for late teams)
    # Lazy import: post-hooks still live in main.py (avoids circular import at load time).
    from main import (  # noqa: WPS433
        invalidate_homepage_result_caches,
        recalculate_season_team_total_points,
        resolve_league_challenges_for_competition,
        update_league_points_for_competition,
    )

    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        recalculate_season_team_total_points(team)
        print(
            f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) "
            f"to {team.total_points} points"
        )

    db.session.commit()
    print(f"✅ Poängberäkning klar för tävling ID: {comp_id}")

    # Automatically calculate league points after race scores are calculated
    try:
        print(f"🏆 Automatically calculating league points for competition {comp_id}...")
        update_league_points_for_competition(comp_id)
        print(f"✅ League points updated for competition {comp_id}")
    except Exception as e:
        print(f"❌ Error calculating league points: {e}")
        # Don't fail the entire score calculation if league points fail

    try:
        resolved = resolve_league_challenges_for_competition(comp_id)
        if resolved:
            print(f"⚔️ Resolved {resolved} league challenge(s) for competition {comp_id}")
    except Exception as e:
        print(f"❌ Error resolving league challenges: {e}")

    try:
        invalidate_homepage_result_caches()
    except Exception as cache_exc:
        print(f"WARNING invalidate_homepage_result_caches: {cache_exc}")
