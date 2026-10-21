"""Paris Supercross weekend tippa (lördag + söndag, separata lås).

Public: homepage card shows Coming soon until PARIS_PUBLIC_PLAY.
Admin: can open tippa / roster for testing before official lists drop.
"""
from __future__ import annotations

from datetime import date, time
from typing import Any

from models import (
    Competition,
    CompetitionResult,
    CompetitionRiderStatus,
    HoleshotPick,
    HoleshotResult,
    QualifyingPick,
    QualifyingResult,
    RacePick,
    Rider,
    Series,
    db,
    rider_query_for_list_ui,
)

# Flip to True when official entry list / layout is out and tippa should open.
PARIS_PUBLIC_PLAY = False

SERIES_CODE = "PARIS"
SERIES_DISPLAY = "Paris SX"
PHASE_SAT = "paris_sat"
PHASE_SUN = "paris_sun"
OVERALL_CLASS_SX1 = "ps_ov1"
OVERALL_CLASS_SX2 = "ps_ov2"


def paris_public_play_enabled() -> bool:
    return bool(PARIS_PUBLIC_PLAY)


def paris_user_can_play(*, is_admin: bool) -> bool:
    """Public tippa locked until PARIS_PUBLIC_PLAY; admins can always test."""
    return bool(is_admin) or paris_public_play_enabled()

# Bekräftade / listade namn (uppdateras närmare event — idempotent seed).
PARIS_2026_SX1_NAMES = (
    "Ken Roczen",
    "Malcolm Stewart",
    "Cooper Webb",
    "Jett Lawrence",
    "Hunter Lawrence",
    "Tom Vialle",
    "Aaron Plessinger",
    "Jo Shimoda",
    "Lucas Coenen",
    "Mitchell Harrison",
    "Jess Pettis",
)

PARIS_2026_SX2_NAMES = (
    "Sacha Coenen",
    "Luke Clout",
    "Jake Cannon",
    "Anthony Bourdon",
    "Mathys Boisrame",
)


def _invalidate_series_status_cache() -> None:
    try:
        from services.series_status import invalidate_series_status_cache

        invalidate_series_status_cache()
    except Exception:
        pass


def paris_is_saturday(comp: Competition | None) -> bool:
    return bool(
        comp
        and (getattr(comp, "series", None) or "").upper() == SERIES_CODE
        and (getattr(comp, "phase", None) or "") == PHASE_SAT
    )


def paris_is_sunday(comp: Competition | None) -> bool:
    return bool(
        comp
        and (getattr(comp, "series", None) or "").upper() == SERIES_CODE
        and (getattr(comp, "phase", None) or "") == PHASE_SUN
    )


def paris_is_weekend_comp(comp: Competition | None) -> bool:
    """True only for tagged Paris SX competitions (series=PARIS + phase)."""
    return paris_is_saturday(comp) or paris_is_sunday(comp)


def get_paris_series(year: int = 2026) -> Series | None:
    return Series.query.filter_by(name=SERIES_DISPLAY, year=year).first()


def get_active_paris_year(default: int = 2026) -> int:
    """Prefer active Paris SX series year, else newest, else default."""
    ser = (
        Series.query.filter_by(name=SERIES_DISPLAY, is_active=True)
        .order_by(Series.year.desc())
        .first()
    )
    if ser and ser.year:
        return int(ser.year)
    ser = (
        Series.query.filter_by(name=SERIES_DISPLAY)
        .order_by(Series.year.desc())
        .first()
    )
    if ser and ser.year:
        return int(ser.year)
    return int(default)


def get_paris_weekend(year: int = 2026) -> dict[str, Competition | None]:
    ser = get_paris_series(year)
    if not ser:
        return {"series": None, "saturday": None, "sunday": None}
    sat = Competition.query.filter_by(series_id=ser.id, phase=PHASE_SAT).first()
    sun = Competition.query.filter_by(series_id=ser.id, phase=PHASE_SUN).first()
    return {"series": ser, "saturday": sat, "sunday": sun}


def _paris_competition_has_scores(comp: Competition | None) -> bool:
    if not comp:
        return False
    from models import CompetitionScore

    return (
        CompetitionScore.query.filter_by(competition_id=int(comp.id))
        .filter(CompetitionScore.total_points > 0)
        .first()
        is not None
    ) or (
        # Also treat "results entered" as scored evening even if everyone got 0
        CompetitionResult.query.filter_by(competition_id=int(comp.id)).first() is not None
        or HoleshotResult.query.filter_by(competition_id=int(comp.id)).first() is not None
        or QualifyingResult.query.filter_by(competition_id=int(comp.id)).first() is not None
    )


def fantasy_paris_leaderboard_payload(year: int = 2026) -> dict[str, Any]:
    """Paris weekend leaderboard with lör/sön split + phase label for UI."""
    from models import CompetitionScore, User

    wk = get_paris_weekend(int(year))
    sat = wk.get("saturday")
    sun = wk.get("sunday")
    sat_id = int(sat.id) if sat is not None else None
    sun_id = int(sun.id) if sun is not None else None
    ids = [i for i in (sat_id, sun_id) if i is not None]
    saturday_scored = _paris_competition_has_scores(sat)
    sunday_scored = _paris_competition_has_scores(sun)

    if saturday_scored and sunday_scored:
        label_sv = "Helg totalt"
        label_en = "Weekend total"
    elif saturday_scored:
        label_sv = "Efter lördag"
        label_en = "After Saturday"
    elif sunday_scored:
        label_sv = "Efter söndag"
        label_en = "After Sunday"
    else:
        label_sv = "Inga poäng ännu"
        label_en = "No points yet"

    if not ids:
        return {
            "year": int(year),
            "saturday_scored": False,
            "sunday_scored": False,
            "label_sv": label_sv,
            "label_en": label_en,
            "leaderboard": [],
        }

    # Per-user points keyed by competition
    score_rows = (
        db.session.query(
            CompetitionScore.user_id,
            CompetitionScore.competition_id,
            CompetitionScore.total_points,
        )
        .filter(CompetitionScore.competition_id.in_(ids))
        .all()
    )
    by_user: dict[int, dict[str, int]] = {}
    for uid, cid, pts in score_rows:
        bucket = by_user.setdefault(int(uid), {"saturday_points": 0, "sunday_points": 0})
        p = int(pts or 0)
        if sat_id is not None and int(cid) == sat_id:
            bucket["saturday_points"] = p
        elif sun_id is not None and int(cid) == sun_id:
            bucket["sunday_points"] = p

    if not by_user:
        return {
            "year": int(year),
            "saturday_scored": saturday_scored,
            "sunday_scored": sunday_scored,
            "label_sv": label_sv,
            "label_en": label_en,
            "leaderboard": [],
        }

    users = {
        int(u.id): u.username
        for u in User.query.filter(User.id.in_(list(by_user.keys()))).all()
    }
    ranked = sorted(
        by_user.items(),
        key=lambda kv: (
            -(kv[1]["saturday_points"] + kv[1]["sunday_points"]),
            (users.get(kv[0]) or "").lower(),
        ),
    )
    leaderboard: list[dict[str, Any]] = []
    for i, (uid, pts) in enumerate(ranked, start=1):
        sat_p = int(pts["saturday_points"])
        sun_p = int(pts["sunday_points"])
        total = sat_p + sun_p
        leaderboard.append(
            {
                "rank": i,
                "user_id": uid,
                "username": users.get(uid) or "?",
                "saturday_points": sat_p,
                "sunday_points": sun_p,
                "total_points": total,
                "paris_split": True,
            }
        )
    return {
        "year": int(year),
        "saturday_scored": saturday_scored,
        "sunday_scored": sunday_scored,
        "label_sv": label_sv,
        "label_en": label_en,
        "leaderboard": leaderboard,
    }


def fantasy_paris_leaderboard_for_year(year: int = 2026) -> list[dict[str, Any]]:
    """Back-compat: list rows only (total ranked). Prefer fantasy_paris_leaderboard_payload."""
    return fantasy_paris_leaderboard_payload(year).get("leaderboard") or []


def _find_riders_by_names(names: tuple[str, ...], class_name: str) -> list[Rider]:
    out: list[Rider] = []
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        r = Rider.query.filter(db.func.lower(Rider.name) == name.lower()).first()
        if r is None:
            r = Rider.query.filter(Rider.name.ilike(f"%{name}%")).first()
        if r is None:
            print(f"[PARIS-SEED] rider not found: {name!r}")
            continue
        if (r.class_name or "") != class_name:
            r.class_name = class_name
        out.append(r)
    return out


def _sync_competition_roster(comp: Competition, riders: list[Rider]) -> int:
    seen = set()
    n = 0
    for r in riders:
        if r.id in seen:
            continue
        seen.add(r.id)
        row = CompetitionRiderStatus.query.filter_by(
            competition_id=comp.id, rider_id=r.id
        ).first()
        if row is None:
            row = CompetitionRiderStatus(
                competition_id=comp.id, rider_id=r.id, status="IN"
            )
            db.session.add(row)
            n += 1
        elif (row.status or "").upper() != "IN":
            row.status = "IN"
            n += 1
    db.session.flush()
    return n


def paris_allowed_rider_ids(competition_id: int) -> set[int]:
    rows = (
        CompetitionRiderStatus.query.filter_by(competition_id=competition_id)
        .filter(CompetitionRiderStatus.status != "OUT")
        .all()
    )
    if rows:
        return {int(r.rider_id) for r in rows}
    return {
        int(r.id)
        for r in Rider.query.filter(
            Rider.class_name.in_(("wsx_sx1", "wsx_sx2"))
        ).all()
    }


def paris_roster_payload(competition_id: int) -> dict[str, list[dict]]:
    allowed = paris_allowed_rider_ids(competition_id)
    if not allowed:
        return {
            "sx1": [],
            "sx2": [],
            "empty": True,
            "message": "Officiell startlista för Paris Supercross är inte publicerad än.",
        }
    riders = rider_query_for_list_ui().filter(Rider.id.in_(allowed)).all()
    sx1: list[dict] = []
    sx2: list[dict] = []
    for r in riders:
        item = {
            "id": int(r.id),
            "name": r.name,
            "number": r.rider_number,
            "class_name": r.class_name or "",
        }
        cls = (r.class_name or "").lower()
        if cls == "wsx_sx2":
            sx2.append(item)
        else:
            sx1.append(item)
    sx1.sort(key=lambda x: (x.get("name") or "").lower())
    sx2.sort(key=lambda x: (x.get("name") or "").lower())
    return {"sx1": sx1, "sx2": sx2, "empty": not (sx1 or sx2)}


def paris_required_pick_keys(comp: Competition) -> tuple[str, ...]:
    if paris_is_saturday(comp):
        return ("superpole_sx1", "superpole_sx2", "final_sx1", "final_sx2")
    return ("final_sx1", "final_sx2", "overall_sx1", "overall_sx2")


def paris_picks_complete(user_id: int, comp: Competition) -> bool:
    p = get_user_paris_picks(user_id, comp)
    return all(p.get(k) for k in paris_required_pick_keys(comp))


def get_user_paris_picks(user_id: int, comp: Competition) -> dict[str, Any]:
    cid = int(comp.id)
    holes = {
        (h.class_name or "").lower(): int(h.rider_id)
        for h in HoleshotPick.query.filter_by(user_id=user_id, competition_id=cid).all()
    }
    finals: dict[str, int | None] = {"sx1": None, "sx2": None}
    for p in RacePick.query.filter_by(user_id=user_id, competition_id=cid).all():
        rider = Rider.query.get(p.rider_id)
        if not rider:
            continue
        cls = (rider.class_name or "").lower()
        if cls == "wsx_sx2":
            finals["sx2"] = int(p.rider_id)
        elif cls in ("wsx_sx1", "450cc"):
            finals["sx1"] = int(p.rider_id)
    overall: dict[str, int | None] = {"sx1": None, "sx2": None}
    for q in QualifyingPick.query.filter_by(user_id=user_id, competition_id=cid).all():
        cls = (q.class_name or "").lower()
        if cls == OVERALL_CLASS_SX2:
            overall["sx2"] = int(q.rider_id)
        elif cls == OVERALL_CLASS_SX1:
            overall["sx1"] = int(q.rider_id)
    return {
        "superpole_sx1": holes.get("wsx_sx1"),
        "superpole_sx2": holes.get("wsx_sx2"),
        "final_sx1": finals["sx1"],
        "final_sx2": finals["sx2"],
        "overall_sx1": overall["sx1"],
        "overall_sx2": overall["sx2"],
    }


def _paris_rider_ui(rider_id: int | None) -> dict[str, Any] | None:
    if not rider_id:
        return None
    rider = Rider.query.get(int(rider_id))
    if not rider:
        return None
    brand = (rider.bike_brand or "").strip()
    racerx_url = ""
    try:
        from app.portrait_urls import lookup_racerx_portrait_by_name

        racerx_url = lookup_racerx_portrait_by_name(rider.name) or ""
    except Exception:
        racerx_url = ""
    portrait = racerx_url or f"/rider_portrait/{int(rider.id)}"
    return {
        "rider_id": int(rider.id),
        "rider_name": rider.name,
        "rider_number": rider.rider_number,
        "bike_brand": brand,
        "class": rider.class_name,
        "portrait_url": portrait,
        "image_url": racerx_url or None,
        "racerx_portrait_url": racerx_url,
    }


def _paris_ui_has_any(ui: dict[str, Any] | None, keys: tuple[str, ...]) -> bool:
    if not ui:
        return False
    for k in keys:
        slot = ui.get(k)
        if slot and (slot.get("rider_id") or slot.get("id")):
            return True
    return False


def get_user_paris_picks_ui(user_id: int, comp: Competition) -> dict[str, Any]:
    """Enriched picks for overview / homepage (ids + rider cards)."""
    raw = get_user_paris_picks(user_id, comp)
    fields = {
        key: _paris_rider_ui(raw.get(key))
        for key in (
            "superpole_sx1",
            "superpole_sx2",
            "final_sx1",
            "final_sx2",
            "overall_sx1",
            "overall_sx2",
        )
    }
    return {
        **fields,
        "ids": raw,
        "complete": paris_picks_complete(user_id, comp),
        "saturday": paris_is_saturday(comp),
        "competition_id": int(comp.id),
    }


def get_user_paris_weekend_picks_ui(
    user_id: int, year: int | None = None
) -> dict[str, Any]:
    """Combined lördag + söndag picks for homepage (sunday omitted if empty)."""
    y = int(year or get_active_paris_year())
    wk = get_paris_weekend(y)
    sat = wk.get("saturday")
    sun = wk.get("sunday")
    sat_keys = ("superpole_sx1", "superpole_sx2", "final_sx1", "final_sx2")
    sun_keys = ("final_sx1", "final_sx2", "overall_sx1", "overall_sx2")

    sat_ui = get_user_paris_picks_ui(user_id, sat) if sat else None
    sun_ui = get_user_paris_picks_ui(user_id, sun) if sun else None

    sat_has = _paris_ui_has_any(sat_ui, sat_keys)
    sun_has = _paris_ui_has_any(sun_ui, sun_keys)
    sat_complete = bool(sat_ui and sat_ui.get("complete"))
    sun_complete = bool(sun_ui and sun_ui.get("complete"))

    # Prefer next unlocked evening for "edit" link
    open_id = None
    for comp in (sat, sun):
        if not comp:
            continue
        try:
            from services.picks_lock import is_picks_locked

            if not is_picks_locked(comp):
                open_id = int(comp.id)
                break
        except Exception:
            open_id = int(comp.id)
            break
    if open_id is None:
        if sat:
            open_id = int(sat.id)
        elif sun:
            open_id = int(sun.id)

    return {
        "year": y,
        "saturday": sat_ui if sat_has else None,
        "sunday": sun_ui if sun_has else None,
        "saturday_complete": sat_complete,
        "sunday_complete": sun_complete,
        "saturday_has_picks": sat_has,
        "sunday_has_picks": sun_has,
        "weekend_complete": sat_complete and sun_complete,
        "open_competition_id": open_id,
        "saturday_competition_id": int(sat.id) if sat else None,
        "sunday_competition_id": int(sun.id) if sun else None,
    }


def _validate_rider(
    rid: int,
    allowed: set[int],
    out_ids: set[int],
    *,
    expect_class: str | None = None,
) -> Rider:
    rider = Rider.query.get(rid)
    if not rider:
        raise ValueError("Förare hittades inte")
    if rid not in allowed:
        raise ValueError(f"{rider.name} finns inte i Paris-startlistan")
    if rid in out_ids:
        raise ValueError(f"{rider.name} är OUT för denna kväll")
    if expect_class and (rider.class_name or "").lower() != expect_class:
        raise ValueError(f"{rider.name} är inte i rätt klass")
    return rider


def save_user_paris_picks(user_id: int, comp: Competition, data: dict) -> None:
    from services.picks_lock import is_picks_locked

    if is_picks_locked(comp):
        raise PermissionError("Picks är låsta")

    cid = int(comp.id)
    allowed = paris_allowed_rider_ids(cid)
    out_ids = {
        int(row.rider_id)
        for row in CompetitionRiderStatus.query.filter_by(
            competition_id=cid, status="OUT"
        ).all()
    }

    def _int(key: str) -> int:
        try:
            return int(data.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"Ogiltigt val för {key}")

    RacePick.query.filter_by(user_id=user_id, competition_id=cid).delete()
    HoleshotPick.query.filter_by(user_id=user_id, competition_id=cid).delete()
    QualifyingPick.query.filter_by(user_id=user_id, competition_id=cid).delete()

    if paris_is_saturday(comp):
        sp1 = _validate_rider(_int("superpole_sx1"), allowed, out_ids, expect_class="wsx_sx1")
        sp2 = _validate_rider(_int("superpole_sx2"), allowed, out_ids, expect_class="wsx_sx2")
        f1 = _validate_rider(_int("final_sx1"), allowed, out_ids, expect_class="wsx_sx1")
        f2 = _validate_rider(_int("final_sx2"), allowed, out_ids, expect_class="wsx_sx2")
        db.session.add(
            HoleshotPick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(sp1.id),
                class_name="wsx_sx1",
            )
        )
        db.session.add(
            HoleshotPick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(sp2.id),
                class_name="wsx_sx2",
            )
        )
        db.session.add(
            RacePick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(f1.id),
                predicted_position=1,
            )
        )
        db.session.add(
            RacePick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(f2.id),
                predicted_position=1,
            )
        )
    elif paris_is_sunday(comp):
        f1 = _validate_rider(_int("final_sx1"), allowed, out_ids, expect_class="wsx_sx1")
        f2 = _validate_rider(_int("final_sx2"), allowed, out_ids, expect_class="wsx_sx2")
        o1 = _validate_rider(_int("overall_sx1"), allowed, out_ids, expect_class="wsx_sx1")
        o2 = _validate_rider(_int("overall_sx2"), allowed, out_ids, expect_class="wsx_sx2")
        db.session.add(
            RacePick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(f1.id),
                predicted_position=1,
            )
        )
        db.session.add(
            RacePick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(f2.id),
                predicted_position=1,
            )
        )
        db.session.add(
            QualifyingPick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(o1.id),
                class_name=OVERALL_CLASS_SX1,
            )
        )
        db.session.add(
            QualifyingPick(
                user_id=user_id,
                competition_id=cid,
                rider_id=int(o2.id),
                class_name=OVERALL_CLASS_SX2,
            )
        )
    else:
        raise ValueError("Ogiltig Paris-tävling")

    db.session.commit()


def get_paris_official_results(comp: Competition) -> dict[str, int | None]:
    """Current official rows for admin UI."""
    cid = int(comp.id)
    holes = {
        (h.class_name or "").lower(): int(h.rider_id)
        for h in HoleshotResult.query.filter_by(competition_id=cid).all()
    }
    finals: dict[str, int | None] = {"sx1": None, "sx2": None}
    for row in CompetitionResult.query.filter_by(competition_id=cid).all():
        rider = Rider.query.get(row.rider_id)
        if not rider or int(row.position) != 1:
            continue
        cls = (rider.class_name or "").lower()
        if cls == "wsx_sx2":
            finals["sx2"] = int(row.rider_id)
        elif cls in ("wsx_sx1", "450cc"):
            finals["sx1"] = int(row.rider_id)
    overall: dict[str, int | None] = {"sx1": None, "sx2": None}
    for q in QualifyingResult.query.filter_by(competition_id=cid).all():
        cls = (q.class_name or "").lower()
        if cls == OVERALL_CLASS_SX2:
            overall["sx2"] = int(q.rider_id)
        elif cls == OVERALL_CLASS_SX1:
            overall["sx1"] = int(q.rider_id)
    return {
        "superpole_sx1": holes.get("wsx_sx1"),
        "superpole_sx2": holes.get("wsx_sx2"),
        "final_sx1": finals["sx1"],
        "final_sx2": finals["sx2"],
        "overall_sx1": overall["sx1"],
        "overall_sx2": overall["sx2"],
    }


def _paris_opt_rider_id(data: dict, key: str) -> int | None:
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Ogiltigt förar-ID för {key}")


def _upsert_holeshot_result(
    competition_id: int, rider_id: int | None, class_name: str, aliases: list[str]
) -> None:
    if rider_id:
        existing = HoleshotResult.query.filter(
            HoleshotResult.competition_id == competition_id,
            HoleshotResult.class_name.in_(aliases),
        ).first()
        if existing:
            existing.rider_id = rider_id
            existing.class_name = class_name
        else:
            db.session.add(
                HoleshotResult(
                    competition_id=competition_id,
                    rider_id=rider_id,
                    class_name=class_name,
                )
            )
    else:
        HoleshotResult.query.filter(
            HoleshotResult.competition_id == competition_id,
            HoleshotResult.class_name.in_(aliases),
        ).delete(synchronize_session=False)


def _upsert_qualifying_result(
    competition_id: int, rider_id: int | None, class_name: str
) -> None:
    existing = QualifyingResult.query.filter_by(
        competition_id=competition_id, class_name=class_name
    ).first()
    if rider_id:
        if existing:
            existing.rider_id = rider_id
        else:
            db.session.add(
                QualifyingResult(
                    competition_id=competition_id,
                    rider_id=rider_id,
                    class_name=class_name,
                )
            )
    elif existing:
        db.session.delete(existing)


def _set_final_winner(competition_id: int, rider: Rider) -> None:
    cls = (rider.class_name or "").lower()
    if cls == "wsx_sx2":
        class_names = ("wsx_sx2", "250cc")
    else:
        class_names = ("wsx_sx1", "450cc", "mxgp")
    CompetitionResult.query.filter(
        CompetitionResult.competition_id == competition_id,
        CompetitionResult.position == 1,
        CompetitionResult.rider_id.in_(
            db.session.query(Rider.id).filter(Rider.class_name.in_(class_names))
        ),
    ).delete(synchronize_session=False)
    db.session.add(
        CompetitionResult(
            competition_id=competition_id,
            rider_id=int(rider.id),
            position=1,
            class_name=rider.class_name,
        )
    )


def save_paris_official_results(comp: Competition, data: dict[str, Any]) -> None:
    """Admin: spara officiella Paris-resultat för en kväll och räkna om poäng."""
    from services.scoring import calculate_scores

    if not paris_is_weekend_comp(comp):
        raise ValueError("Inte en Paris-kväll")

    cid = int(comp.id)
    allowed = paris_allowed_rider_ids(cid)
    out_ids = {
        int(row.rider_id)
        for row in CompetitionRiderStatus.query.filter_by(
            competition_id=cid, status="OUT"
        ).all()
    }

    if paris_is_saturday(comp):
        sp1 = _paris_opt_rider_id(data, "superpole_sx1")
        sp2 = _paris_opt_rider_id(data, "superpole_sx2")
        f1 = _paris_opt_rider_id(data, "final_sx1")
        f2 = _paris_opt_rider_id(data, "final_sx2")
        if sp1 is not None:
            _validate_rider(sp1, allowed, out_ids, expect_class="wsx_sx1")
        if sp2 is not None:
            _validate_rider(sp2, allowed, out_ids, expect_class="wsx_sx2")
        if f1 is not None:
            _validate_rider(f1, allowed, out_ids, expect_class="wsx_sx1")
        if f2 is not None:
            _validate_rider(f2, allowed, out_ids, expect_class="wsx_sx2")

        _upsert_holeshot_result(cid, sp1, "wsx_sx1", ["wsx_sx1", "450cc"])
        _upsert_holeshot_result(cid, sp2, "wsx_sx2", ["wsx_sx2", "250cc"])
        if f1 is not None:
            r1 = Rider.query.get(f1)
            if r1:
                _set_final_winner(cid, r1)
        if f2 is not None:
            r2 = Rider.query.get(f2)
            if r2:
                _set_final_winner(cid, r2)
    elif paris_is_sunday(comp):
        f1 = _paris_opt_rider_id(data, "final_sx1")
        f2 = _paris_opt_rider_id(data, "final_sx2")
        o1 = _paris_opt_rider_id(data, "overall_sx1")
        o2 = _paris_opt_rider_id(data, "overall_sx2")
        if f1 is not None:
            _validate_rider(f1, allowed, out_ids, expect_class="wsx_sx1")
        if f2 is not None:
            _validate_rider(f2, allowed, out_ids, expect_class="wsx_sx2")
        if o1 is not None:
            _validate_rider(o1, allowed, out_ids, expect_class="wsx_sx1")
        if o2 is not None:
            _validate_rider(o2, allowed, out_ids, expect_class="wsx_sx2")

        if f1 is not None:
            r1 = Rider.query.get(f1)
            if r1:
                _set_final_winner(cid, r1)
        if f2 is not None:
            r2 = Rider.query.get(f2)
            if r2:
                _set_final_winner(cid, r2)
        _upsert_qualifying_result(cid, o1, OVERALL_CLASS_SX1)
        _upsert_qualifying_result(cid, o2, OVERALL_CLASS_SX2)
    else:
        raise ValueError("Okänd Paris-fas")

    db.session.commit()
    calculate_scores(cid)


def heal_paris_competition_tags(series: Series) -> int:
    """Fix legacy rows named Paris Supercross but tagged SX/AMA."""
    fixed = 0
    rows = Competition.query.filter(
        db.func.lower(Competition.name).like("paris supercross%")
    ).all()
    for comp in rows:
        nm = (comp.name or "").lower()
        if "lördag" in nm or "lordag" in nm or "saturday" in nm:
            phase = PHASE_SAT
        elif "söndag" in nm or "sondag" in nm or "sunday" in nm:
            phase = PHASE_SUN
        else:
            phase = comp.phase
        changed = False
        if (comp.series or "").upper() != SERIES_CODE:
            comp.series = SERIES_CODE
            changed = True
        if comp.series_id != series.id:
            comp.series_id = series.id
            changed = True
        if phase and comp.phase != phase:
            comp.phase = phase
            changed = True
        if comp.timezone != "Europe/Paris":
            comp.timezone = "Europe/Paris"
            changed = True
        if changed:
            fixed += 1
    if fixed:
        db.session.flush()
    return fixed


def ensure_paris_2026() -> dict[str, Any]:
    """Upsert Paris SX 2026 — två competitions, samma serie."""
    try:
        from services.schema_patches import _ensure_competition_start_time_column

        _ensure_competition_start_time_column()
    except Exception as patch_err:
        print(f"[PARIS-SEED] start_time column patch skipped: {patch_err}")

    ser = get_paris_series(2026)
    created_series = False
    if not ser:
        ser = Series(
            name=SERIES_DISPLAY,
            year=2026,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 22),
            is_active=True,
            points_system="standard",
        )
        db.session.add(ser)
        db.session.flush()
        created_series = True

    specs = (
        (
            PHASE_SAT,
            "Paris Supercross — Lördag",
            date(2026, 11, 21),
            time(19, 0),
        ),
        (
            PHASE_SUN,
            "Paris Supercross — Söndag",
            date(2026, 11, 22),
            time(14, 0),
        ),
    )
    comp_ids: list[int] = []
    for phase, name, ev_date, start_t in specs:
        comp = Competition.query.filter_by(series_id=ser.id, phase=phase).first()
        if comp is None:
            comp = Competition(
                name=name,
                event_date=ev_date,
                series=SERIES_CODE,
                series_id=ser.id,
                phase=phase,
                timezone="Europe/Paris",
            )
            db.session.add(comp)
        comp.name = name
        comp.event_date = ev_date
        comp.series = SERIES_CODE
        comp.series_id = ser.id
        comp.phase = phase
        comp.timezone = "Europe/Paris"
        comp.is_cancelled = False
        # Official show start (supercrossparis.com/programme): sat 19:00 / sun 14:00 Paris.
        Competition._start_time_column_exists = None  # re-probe (may have cached False)
        db.session.flush()
        try:
            if Competition.has_start_time_column():
                comp.start_time = start_t
            else:
                db.session.execute(
                    db.text(
                        "UPDATE competitions SET start_time = :t WHERE id = :id"
                    ),
                    {"t": start_t.strftime("%H:%M:%S"), "id": int(comp.id)},
                )
        except Exception as st_err:
            print(f"[PARIS-SEED] start_time write failed: {st_err}")
        db.session.flush()
        comp_ids.append(int(comp.id))

    healed = heal_paris_competition_tags(ser)

    sx1 = _find_riders_by_names(PARIS_2026_SX1_NAMES, "wsx_sx1")
    sx2 = _find_riders_by_names(PARIS_2026_SX2_NAMES, "wsx_sx2")
    roster_n = 0
    for cid in comp_ids:
        roster_n += _sync_competition_roster(Competition.query.get(cid), sx1 + sx2)
    # Same startlist on any healed Paris rows (e.g. old SX-tagged duplicates).
    for comp in Competition.query.filter(
        db.func.lower(Competition.name).like("paris supercross%")
    ).all():
        roster_n += _sync_competition_roster(comp, sx1 + sx2)

    db.session.commit()
    _invalidate_series_status_cache()
    wk = get_paris_weekend(2026)
    return {
        "created_series": created_series,
        "saturday_id": wk["saturday"].id if wk["saturday"] else None,
        "sunday_id": wk["sunday"].id if wk["sunday"] else None,
        "roster_links": roster_n,
        "healed_competitions": healed,
        "sx1_riders": len(sx1),
        "sx2_riders": len(sx2),
    }
