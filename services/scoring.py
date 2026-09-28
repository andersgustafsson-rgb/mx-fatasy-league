"""Fantasy tippa + säsongsteam scoring helpers (pure / low-coupling).

Skiva 1 av kodstädning: flyttade från main.py utan beteendeförändring.
Se docs/REFACTOR.md.
"""
from __future__ import annotations

from typing import Any


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
