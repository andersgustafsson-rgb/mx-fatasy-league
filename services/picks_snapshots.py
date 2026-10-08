"""PicksSnapshot helpers — persist locked picks as JSON (skiva 15).

Moved out of main.py. Call sites re-export from main for compatibility.
"""
from __future__ import annotations

import json
import time

from models import (
    Competition,
    HoleshotPick,
    PicksSnapshot,
    QualifyingPick,
    RacePick,
    WildcardPick,
    db,
)
from services.picks_lock import is_picks_deadline_passed, is_picks_locked


def build_picks_snapshot_payload(user_id: int, competition_id: int) -> dict:
    """
    Normalize current picks into a stable JSON payload.
    Keeps only latest rows if duplicates exist (by PK), and sorts race picks by position.
    """
    # Race picks: dedupe by (rider_id, predicted_position) preferring latest pick_id
    picks = (
        RacePick.query.filter_by(user_id=user_id, competition_id=competition_id)
        .order_by(RacePick.predicted_position.asc())
        .all()
    )
    by_key = {}
    for p in picks:
        k = (int(p.rider_id or 0), int(p.predicted_position or 0))
        prev = by_key.get(k)
        if prev is None or int(p.pick_id or 0) > int(prev.pick_id or 0):
            by_key[k] = p
    unique_picks = sorted(by_key.values(), key=lambda p: int(p.predicted_position or 0))

    holos = HoleshotPick.query.filter_by(user_id=user_id, competition_id=competition_id).all()
    # Dedupe holeshot by class_name, prefer latest id
    holo_by_class = {}
    for h in holos:
        cls = (h.class_name or "").strip()
        prev = holo_by_class.get(cls)
        if prev is None or int(h.id or 0) > int(prev.id or 0):
            holo_by_class[cls] = h

    wc = WildcardPick.query.filter_by(user_id=user_id, competition_id=competition_id).first()

    quals = QualifyingPick.query.filter_by(
        user_id=user_id, competition_id=competition_id
    ).all()
    qual_by_class = {}
    for q in quals:
        cls = (q.class_name or "").strip()
        prev = qual_by_class.get(cls)
        if prev is None or int(q.id or 0) > int(prev.id or 0):
            qual_by_class[cls] = q

    payload = {
        "user_id": int(user_id),
        "competition_id": int(competition_id),
        "race_picks": [
            {"rider_id": int(p.rider_id), "predicted_position": int(p.predicted_position)}
            for p in unique_picks
            if p.rider_id is not None and p.predicted_position is not None
        ],
        "holeshot_picks": {
            cls: int(h.rider_id) for cls, h in holo_by_class.items() if h.rider_id is not None
        },
        "wildcard_pick": (int(wc.rider_id) if wc and wc.rider_id is not None else None),
        "wildcard_pos": (int(wc.position) if wc and wc.position is not None else None),
        "qualifying_picks": {
            cls: int(q.rider_id)
            for cls, q in qual_by_class.items()
            if q.rider_id is not None
        },
    }
    return payload


# Back-compat alias used throughout main / social_recap
_build_picks_snapshot_payload = build_picks_snapshot_payload


def ensure_picks_snapshots_for_competition(
    competition_id: int, source: str = "auto_lock"
) -> int:
    """
    Create missing PicksSnapshot rows for users who have any picks for this competition.
    Safe to call multiple times (unique constraint prevents duplicates).
    Returns number of snapshots created.
    """
    user_ids = set()
    user_ids.update(
        uid
        for (uid,) in db.session.query(RacePick.user_id)
        .filter(RacePick.competition_id == competition_id)
        .distinct()
        .all()
        if uid is not None
    )
    user_ids.update(
        uid
        for (uid,) in db.session.query(HoleshotPick.user_id)
        .filter(HoleshotPick.competition_id == competition_id)
        .distinct()
        .all()
        if uid is not None
    )
    user_ids.update(
        uid
        for (uid,) in db.session.query(WildcardPick.user_id)
        .filter(WildcardPick.competition_id == competition_id)
        .distinct()
        .all()
        if uid is not None
    )
    user_ids.update(
        uid
        for (uid,) in db.session.query(QualifyingPick.user_id)
        .filter(QualifyingPick.competition_id == competition_id)
        .distinct()
        .all()
        if uid is not None
    )
    if not user_ids:
        return 0

    existing = {
        int(uid)
        for (uid,) in db.session.query(PicksSnapshot.user_id)
        .filter(PicksSnapshot.competition_id == competition_id)
        .filter(PicksSnapshot.user_id.in_(list(user_ids)))
        .all()
    }

    created = 0
    for uid in user_ids:
        uid_i = int(uid)
        if uid_i in existing:
            continue
        payload = build_picks_snapshot_payload(uid_i, int(competition_id))
        snap = PicksSnapshot(
            user_id=uid_i,
            competition_id=int(competition_id),
            payload_json=json.dumps(payload, ensure_ascii=False),
            source=source,
        )
        db.session.add(snap)
        created += 1

    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            created = 0
    return created


_PICKS_SNAPSHOT_AUTO_DONE: set[int] = set()
_PICKS_SNAPSHOT_AUTO_LAST_RUN: dict[int, float] = {}
_PICKS_SNAPSHOT_AUTO_INTERVAL_SEC = 90


def _user_ids_with_any_live_picks(competition_id: int) -> set[int]:
    user_ids: set[int] = set()
    for model in (RacePick, HoleshotPick, WildcardPick):
        user_ids.update(
            int(uid)
            for (uid,) in db.session.query(model.user_id)
            .filter(model.competition_id == competition_id)
            .distinct()
            .all()
            if uid is not None
        )
    return user_ids


def _missing_pick_snapshot_user_count(competition_id: int) -> int:
    user_ids = _user_ids_with_any_live_picks(competition_id)
    if not user_ids:
        return 0
    existing = {
        int(uid)
        for (uid,) in db.session.query(PicksSnapshot.user_id)
        .filter(PicksSnapshot.competition_id == competition_id)
        .filter(PicksSnapshot.user_id.in_(list(user_ids)))
        .all()
    }
    return len(user_ids - existing)


def auto_ensure_picks_snapshots_if_locked(comp: Competition | None) -> None:
    """
    Best-effort: when picks are locked, persist snapshots without admin action.
    Throttled per competition; retries until every user with live picks has a row.
    """
    if comp is None:
        return
    comp_id = int(comp.id)
    if comp_id in _PICKS_SNAPSHOT_AUTO_DONE:
        return
    try:
        if not is_picks_deadline_passed(comp):
            return
    except Exception:
        return

    now = time.time()
    if now - _PICKS_SNAPSHOT_AUTO_LAST_RUN.get(comp_id, 0.0) < _PICKS_SNAPSHOT_AUTO_INTERVAL_SEC:
        return
    _PICKS_SNAPSHOT_AUTO_LAST_RUN[comp_id] = now

    try:
        created = ensure_picks_snapshots_for_competition(comp_id, source="auto_lock")
        if created:
            print(f"INFO: auto picks snapshots created={created} competition_id={comp_id}")
        if _missing_pick_snapshot_user_count(comp_id) == 0:
            _PICKS_SNAPSHOT_AUTO_DONE.add(comp_id)
    except Exception as e:
        db.session.rollback()
        print(f"WARNING: auto picks snapshots failed competition_id={comp_id}: {e}")


# Back-compat alias
_auto_ensure_picks_snapshots_if_locked = auto_ensure_picks_snapshots_if_locked


def ensure_user_picks_snapshot_if_locked(
    user_id: int, comp: Competition
) -> PicksSnapshot | None:
    """Create a snapshot for one user when picks are locked (not the whole competition)."""
    if not is_picks_locked(comp):
        return None

    competition_id = int(comp.id)
    snap = PicksSnapshot.query.filter_by(user_id=user_id, competition_id=competition_id).first()
    if snap:
        return snap

    payload = build_picks_snapshot_payload(user_id, competition_id)
    has_any = bool(payload.get("race_picks")) or bool(payload.get("holeshot_picks")) or (
        payload.get("wildcard_pick") is not None
    )
    if not has_any:
        return None

    try:
        snap = PicksSnapshot(
            user_id=user_id,
            competition_id=competition_id,
            payload_json=json.dumps(payload, separators=(",", ":")),
            source="auto_lock",
        )
        db.session.add(snap)
        db.session.commit()
        return snap
    except Exception:
        db.session.rollback()
        return PicksSnapshot.query.filter_by(
            user_id=user_id, competition_id=competition_id
        ).first()


# Back-compat alias
_ensure_user_picks_snapshot_if_locked = ensure_user_picks_snapshot_if_locked
