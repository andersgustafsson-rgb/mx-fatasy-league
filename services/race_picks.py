"""Race picks payload / status helpers (skiva 17a).

Moved out of main.py. Portrait helpers still live in main (lazy via _main).
Routes (get_my_picks / save_picks / …) stay in main until skiva 17b.
"""
from __future__ import annotations

import json

from models import (
    Competition,
    MxonClassPick,
    MxonNationPick,
    Rider,
    rider_query_for_list_ui,
)
from services.picks_lock import is_picks_locked
from services.picks_snapshots import (
    _build_picks_snapshot_payload,
    _ensure_user_picks_snapshot_if_locked,
)


def _main():
    """Lazy import for portrait helpers that still live in main."""
    import main as _m

    return _m


_TOP450_CLASSES = frozenset({"450cc", "wsx_sx1", "mxgp"})
_TOP250_CLASSES = frozenset({"250cc", "wsx_sx2", "mx2"})


def my_picks_api_dict(user_id: int, comp: Competition) -> dict:
    """Normalized picks payload for /get_my_picks and race_picks page embed."""
    competition_id = int(comp.id)
    series_u = (getattr(comp, "series", None) or "").strip().upper()
    is_wsx = series_u == "WSX"
    is_mxgp = series_u == "MXGP"
    picks_locked = is_picks_locked(comp)

    snap = None
    if picks_locked:
        snap = _ensure_user_picks_snapshot_if_locked(user_id, comp)

    if snap:
        payload = json.loads(snap.payload_json or "{}")
        picks = payload.get("race_picks", []) or []
        holos_map = payload.get("holeshot_picks", {}) or {}
        wc_rider = payload.get("wildcard_pick")
        wc_pos = payload.get("wildcard_pos")
        qual_map = payload.get("qualifying_picks", {}) or {}
    else:
        payload = _build_picks_snapshot_payload(user_id, competition_id)
        picks = payload["race_picks"]
        holos_map = payload["holeshot_picks"]
        wc_rider = payload["wildcard_pick"]
        wc_pos = payload["wildcard_pos"]
        qual_map = payload.get("qualifying_picks") or {}

    rider_ids = [int(p["rider_id"]) for p in picks if p.get("rider_id") is not None]
    hs450_id = next(
        (
            rid
            for cls, rid in holos_map.items()
            if cls in ("450cc", "wsx_sx1", "mxgp")
        ),
        None,
    )
    hs250_id = next(
        (
            rid
            for cls, rid in holos_map.items()
            if cls in ("250cc", "wsx_sx2", "mx2")
        ),
        None,
    )
    qual_mxgp_id = qual_map.get("mxgp")
    qual_mx2_id = qual_map.get("mx2")
    for extra_id in (hs450_id, hs250_id, wc_rider, qual_mxgp_id, qual_mx2_id):
        if extra_id is not None:
            try:
                rider_ids.append(int(extra_id))
            except (TypeError, ValueError):
                pass
    rider_ids = list({int(rid) for rid in rider_ids if rid})

    riders_by_id: dict[int, Rider] = {}
    if rider_ids:
        riders_by_id = {
            int(r.id): r
            for r in rider_query_for_list_ui().filter(Rider.id.in_(rider_ids)).all()
        }
    m = _main()
    riders_by_name = m._riders_by_name_for(list(riders_by_id.values())) if riders_by_id else {}

    def _pick_rider_payload(rid: int | None) -> dict | None:
        if rid is None:
            return None
        rider = riders_by_id.get(int(rid))
        if not rider:
            return {"rider_id": int(rid), "rider_name": "?", "rider_number": "?", "class": ""}
        portraits = m._rider_portrait_payload(rider, riders_by_name=riders_by_name)
        return {
            "rider_id": int(rider.id),
            "rider_name": rider.name,
            "rider_number": rider.rider_number,
            "class": rider.class_name or "",
            **portraits,
        }

    top6_picks = []
    for p in picks:
        rid = p.get("rider_id")
        if rid is None:
            continue
        rider = riders_by_id.get(int(rid))
        portraits = (
            m._rider_portrait_payload(rider, riders_by_name=riders_by_name)
            if rider
            else {}
        )
        top6_picks.append(
            {
                "rider_id": int(rid),
                "predicted_position": p.get("predicted_position"),
                "class": (rider.class_name if rider else "") or "",
                "rider_name": rider.name if rider else "?",
                "rider_number": rider.rider_number if rider else "?",
                **portraits,
            }
        )

    hs450 = _pick_rider_payload(hs450_id)
    hs250 = _pick_rider_payload(hs250_id)
    wc_payload = _pick_rider_payload(wc_rider)
    if wc_payload is not None and wc_pos is not None:
        wc_payload = {**wc_payload, "position": wc_pos}

    hs_extra = {}
    if is_wsx:
        hs_extra = {
            "wsx_sx1": holos_map.get("wsx_sx1") or hs450_id,
            "wsx_sx2": holos_map.get("wsx_sx2") or hs250_id,
        }
    elif is_mxgp:
        hs_extra = {
            "mxgp": holos_map.get("mxgp") or hs450_id,
            "mx2": holos_map.get("mx2") or hs250_id,
        }

    return {
        "top6_picks": top6_picks,
        "holeshot_picks": {
            "450cc": hs450_id,
            "250cc": hs250_id,
            **hs_extra,
        },
        "holeshot_450": hs450,
        "holeshot_250": hs250,
        "wildcard_pick": wc_rider,
        "wildcard_pos": wc_pos,
        "wildcard": wc_payload,
        "qualifying_picks": {
            "mxgp": int(qual_mxgp_id) if qual_mxgp_id is not None else None,
            "mx2": int(qual_mx2_id) if qual_mx2_id is not None else None,
        },
        "qualifying_mxgp": _pick_rider_payload(qual_mxgp_id),
        "qualifying_mx2": _pick_rider_payload(qual_mx2_id),
        "is_wsx": is_wsx,
        "is_mxgp": is_mxgp,
        "competition_id": competition_id,
        "series": getattr(comp, "series", None),
        "snapshot_used": bool(snap),
    }


# Back-compat alias
_my_picks_api_dict = my_picks_api_dict


def initial_wizard_step(my_picks: dict, *, is_wsx: bool, is_mxgp: bool = False) -> int:
    """Which wizard step to open on first paint.

    Incomplete picks always start at step 1 (forward flow).
    Complete picks open step 3 (overview). Holeshot-first is edit-only in JS.
    """
    top6 = my_picks.get("top6_picks") or []
    n450 = sum(1 for p in top6 if (p.get("class") or "") in _TOP450_CLASSES)
    n250 = sum(1 for p in top6 if (p.get("class") or "") in _TOP250_CLASSES)
    hs = my_picks.get("holeshot_picks") or {}
    hs450 = bool(hs.get("450cc") or hs.get("wsx_sx1") or hs.get("mxgp"))
    hs250 = bool(hs.get("250cc") or hs.get("wsx_sx2") or hs.get("mx2"))
    wc_ok = True
    if not is_wsx and not is_mxgp:
        wc_ok = bool(my_picks.get("wildcard_pick")) and my_picks.get("wildcard_pos") is not None
    qual_ok = True
    if is_mxgp:
        qm = my_picks.get("qualifying_picks") or {}
        qual_ok = bool(qm.get("mxgp")) and bool(qm.get("mx2"))
    if n450 >= 6 and n250 >= 6 and hs450 and hs250 and wc_ok and qual_ok:
        return 3
    return 1


_initial_wizard_step = initial_wizard_step


def user_picks_status_code(user_id: int | None, comp: Competition | None) -> str:
    """Homepage / countdown: no_picks | partial_picks | has_picks."""
    if not user_id or not comp:
        return "no_picks"
    try:
        if (getattr(comp, "series", None) or "").upper() == "MXON":
            n = MxonNationPick.query.filter_by(
                user_id=int(user_id), competition_id=int(comp.id)
            ).count()
            c = MxonClassPick.query.filter_by(
                user_id=int(user_id), competition_id=int(comp.id)
            ).count()
            if n >= 5 and c >= 3:
                return "has_picks"
            if n > 0 or c > 0:
                return "partial_picks"
            return "no_picks"
        series_u = (getattr(comp, "series", None) or "").strip().upper()
        is_wsx = series_u == "WSX"
        is_mxgp = series_u == "MXGP"
        my = my_picks_api_dict(int(user_id), comp)
        top6 = my.get("top6_picks") or []
        n450 = sum(1 for p in top6 if (p.get("class") or "") in _TOP450_CLASSES)
        n250 = sum(1 for p in top6 if (p.get("class") or "") in _TOP250_CLASSES)
        hs = my.get("holeshot_picks") or {}
        hs450 = bool(hs.get("450cc") or hs.get("wsx_sx1") or hs.get("mxgp"))
        hs250 = bool(hs.get("250cc") or hs.get("wsx_sx2") or hs.get("mx2"))
        wc_ok = True
        if not is_wsx and not is_mxgp:
            wc_ok = bool(my.get("wildcard_pick")) and my.get("wildcard_pos") is not None
        qual_ok = True
        qm = my.get("qualifying_picks") or {}
        if is_mxgp:
            qual_ok = bool(qm.get("mxgp")) and bool(qm.get("mx2"))
        if n450 == 6 and n250 == 6 and hs450 and hs250 and wc_ok and qual_ok:
            return "has_picks"
        if (
            n450
            or n250
            or hs450
            or hs250
            or (not is_wsx and not is_mxgp and my.get("wildcard_pick"))
            or (is_mxgp and (qm.get("mxgp") or qm.get("mx2")))
        ):
            return "partial_picks"
        return "no_picks"
    except Exception as e:
        print(f"_user_picks_status_code: {e}")
        return "no_picks"


_user_picks_status_code = user_picks_status_code


def picks_status_summary(
    my_picks: dict, *, is_wsx: bool, picks_locked: bool, is_mxgp: bool = False
) -> dict:
    """UI strings for picks status banner (mirrors updatePicksStatus in race_picks.html)."""
    top6 = my_picks.get("top6_picks") or []
    hs = my_picks.get("holeshot_picks") or {}
    holeshot450 = hs.get("450cc") or hs.get("wsx_sx1") or hs.get("mxgp")
    holeshot250 = hs.get("250cc") or hs.get("wsx_sx2") or hs.get("mx2")
    has_wc = bool(my_picks.get("wildcard_pick")) and not is_wsx and not is_mxgp
    qm = my_picks.get("qualifying_picks") or {}
    qual_count = (1 if qm.get("mxgp") else 0) + (1 if qm.get("mx2") else 0) if is_mxgp else 0
    holeshot_count = (1 if holeshot450 else 0) + (1 if holeshot250 else 0)
    total = len(top6) + holeshot_count + (1 if has_wc else 0) + qual_count
    if is_mxgp:
        required = 16
        empty_msg = "Gör dina val för topp 6, holeshot och kvalvinnare"
    elif is_wsx:
        required = 14
        empty_msg = "Gör dina val för topp 6 och holeshot"
    else:
        required = 15
        empty_msg = "Gör dina val för topp 6, holeshot och wildcard"

    if total == 0:
        return {
            "icon": "📝",
            "title": "Inga val gjorda än",
            "message": empty_msg,
            "container_class": (
                "mb-4 p-4 rounded-lg border-2 border-dashed border-yellow-400 bg-yellow-900/30"
            ),
            "show_actions": False,
        }
    if picks_locked:
        if total >= required:
            return {
                "icon": "✅",
                "title": "Alla val gjorda!",
                "message": "Du har gjort alla dina val för detta race. Lycka till!",
                "container_class": (
                    "mb-4 p-4 rounded-lg border-2 border-dashed border-green-400 bg-green-900/30"
                ),
                "show_actions": False,
            }
        return {
            "icon": "⚠️",
            "title": f"Delvis klart ({total}/{required} val)",
            "message": "Du har gjort några val, men inte alla. Komplettera dina picks!",
            "container_class": (
                "mb-4 p-4 rounded-lg border-2 border-dashed border-orange-400 bg-orange-900/30"
            ),
            "show_actions": False,
        }
    if total < required:
        return {
            "icon": "⚠️",
            "title": f"Delvis klart ({total}/{required} val)",
            "message": "Du har gjort några val, men inte alla. Komplettera dina picks!",
            "container_class": (
                "mb-4 p-4 rounded-lg border-2 border-dashed border-orange-400 bg-orange-900/30"
            ),
            "show_actions": True,
        }
    return {
        "icon": "✅",
        "title": "Alla val gjorda!",
        "message": "Du har gjort alla dina val för detta race. Lycka till!",
        "container_class": (
            "mb-4 p-4 rounded-lg border-2 border-dashed border-green-400 bg-green-900/30"
        ),
        "show_actions": True,
    }


_picks_status_summary = picks_status_summary
