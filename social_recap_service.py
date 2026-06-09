"""Race Recap Studio — aggregat och bild/text för sociala delningar."""
from __future__ import annotations

import base64
import io
import json
import os
import re
from urllib.parse import urlparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from models import (
    db,
    User,
    Competition,
    CompetitionResult,
    CompetitionScore,
    Rider,
    RacePick,
    PicksSnapshot,
    HoleshotPick,
    WildcardPick,
)

# Brand palette
BG_TOP = (8, 15, 35)
BG_BOTTOM = (22, 36, 68)
PANEL = (30, 41, 59)
PANEL_EDGE = (51, 65, 85)
CYAN = (34, 211, 238)
CYAN_DIM = (14, 116, 144)
GOLD = (251, 191, 36)
SILVER = (203, 213, 225)
BRONZE = (217, 119, 6)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)
GREEN = (52, 211, 153)
RED = (248, 113, 113)
ACCENT_ORANGE = (251, 146, 60)

W_PORTRAIT = 1080
W_SQUARE = 1200
H_SQUARE = 1200
W_FB = 1620  # liggande — fyller FB-bildvisaren (som nyhetsbilder)
H_FB_MIN = 900
H_FB_MAX = 1180
H_FB_WORK = 1220
H_FEED_MIN = 1350  # minhöjd porträtt-flöde
H_STORY = 1920
H_WORK = 2400  # ritbuffer porträtt
W = W_PORTRAIT  # bakåtkompatibilitet
# Större typsnitt/ikoner så texten är läsbar när FB krymper bilden
FONT_SCALE = 1.48
LAYOUT_SCALE = 1.26
_ROOT = Path(__file__).resolve().parent


def _fs(size: int) -> int:
    return max(11, int(round(size * FONT_SCALE)))


def _sz(size: int) -> int:
    return max(1, int(round(size * LAYOUT_SCALE)))


def _compact(data: dict[str, Any]) -> bool:
    return (data.get("layout") or "square") in ("feed", "portrait")


def _canvas_w(img) -> int:
    return img.size[0]


def _section_gap(data: dict[str, Any]) -> int:
    return _sz(8) if _compact(data) else _sz(14)

AVATAR_BG = [
    (14, 116, 144),
    (37, 99, 235),
    (124, 58, 237),
    (219, 39, 119),
    (234, 88, 12),
    (22, 163, 74),
    (6, 182, 212),
]


def _display_name(user: User | None, fallback: str = "?") -> str:
    if not user:
        return fallback
    return (getattr(user, "display_name", None) or user.username or fallback).strip()


def _short_rider_name(name: str, max_len: int = 16) -> str:
    name = (name or "?").strip()
    parts = name.split()
    if len(parts) >= 2:
        s = f"{parts[0][0]}. {parts[-1]}"
    else:
        s = name
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _short_user_name(name: str, max_len: int = 14) -> str:
    s = (name or "?").strip()
    return (s[: max_len - 1] + "…") if len(s) > max_len else s


def _short_recap_display_name(name: str) -> str:
    """Förnamn + efternamnsinitial — ryms i smala recap-rutor."""
    s = (name or "?").strip()
    parts = s.split()
    if len(parts) >= 2 and parts[-1]:
        return f"{parts[0]} {parts[-1][0].upper()}."
    return s


def _leaderboard_rank(row: dict[str, Any], default: int = 99) -> int:
    """Säker int(rank) — None/värden från API ska inte ge TypeError."""
    v = row.get("rank", default)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _pct_num(x: Any) -> float:
    """Crowd-summary kan ge pct som str — undvik ValueError i f-strängar med :.0f."""
    try:
        return float(x if x is not None else 0)
    except (TypeError, ValueError):
        return 0.0


def _plain_draw_text(text: str) -> str:
    """Ta bort emoji — DejaVu kan inte rita dem (visas som □)."""
    s = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]",
        "",
        text or "",
    )
    return re.sub(r"\s+", " ", s).strip()


def _user_initials(display_name: str) -> str:
    parts = (display_name or "?").strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    s = (display_name or "?").strip()
    return (s[:2] or "?").upper()


def _attach_user_meta(row: dict[str, Any]) -> dict[str, Any]:
    uid = row.get("user_id")
    if not uid:
        return row
    user = User.query.get(int(uid))
    if user:
        row["display_name"] = _display_name(user)
        row["username"] = user.username
    return row


def _class_config(comp: Competition) -> dict[str, Any]:
    is_wsx = getattr(comp, "series", None) == "WSX"
    if is_wsx:
        return {
            "primary": ("wsx_sx1", "SX1"),
            "secondary": ("wsx_sx2", "SX2"),
        }
    return {
        "primary": ("450cc", "450"),
        "secondary": ("250cc", "250"),
    }


def _dedupe_scores_by_user(scores: list[CompetitionScore]) -> dict[int, CompetitionScore]:
    out: dict[int, CompetitionScore] = {}
    for s in scores:
        uid = int(s.user_id)
        if uid not in out or s.score_id > out[uid].score_id:
            out[uid] = s
    return out


def _race_leaderboard(competition_id: int, limit: int) -> list[dict[str, Any]]:
    scores = CompetitionScore.query.filter_by(competition_id=competition_id).all()
    by_user = _dedupe_scores_by_user(scores)
    rows = []
    for uid, sc in by_user.items():
        user = User.query.get(uid)
        rows.append(
            {
                "user_id": uid,
                "username": user.username if user else "?",
                "display_name": _display_name(user),
                "points": int(sc.total_points or 0),
            }
        )
    rows.sort(key=lambda r: (-r["points"], r["display_name"].lower()))
    for i, r in enumerate(rows[: max(1, limit)], 1):
        r["rank"] = i
        _attach_user_meta(r)
    return rows[: max(1, limit)]


def _season_top_snippet(limit: int = 5) -> list[dict[str, Any]]:
    from main import calculate_leaderboard_deltas

    out = []
    for i, row in enumerate(calculate_leaderboard_deltas()[: max(1, limit)]):
        item = {
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": row.get("display_name") or row["username"],
            "points": int(row.get("total_points") or 0),
            "rank": _leaderboard_rank(row, i + 1),
        }
        _attach_user_meta(item)
        out.append(item)
    return out


def _comp_ids_for_recap_week(comp: Competition | None) -> list[int]:
    """Tävlingar i samma vecka som den valda tävlingen (för recap — inte bara 'senaste 7 dagar från idag')."""
    from datetime import timedelta

    if not comp:
        return []
    if comp.event_date:
        end = comp.event_date
        start = end - timedelta(days=6)
        recent = Competition.query.filter(
            Competition.event_date.isnot(None),
            Competition.event_date >= start,
            Competition.event_date <= end,
            db.or_(Competition.series.is_(None), Competition.series != "WSX"),
        ).all()
        ids = [int(c.id) for c in recent]
        if int(comp.id) not in ids:
            ids.append(int(comp.id))
        return ids
    return [int(comp.id)]


def _fallback_race_highlights(
    competition_id: int, race_leaderboard: list[dict] | None
) -> list[dict[str, Any]]:
    """Minst en prestation från själva tävlingen om veckofönstret saknar data."""
    cards: list[dict[str, Any]] = []
    if race_leaderboard:
        top = race_leaderboard[0]
        cards.append(
            {
                "icon": "🏆",
                "title": "Tävlingsvinnare",
                "user_id": top.get("user_id"),
                "display_name": top.get("display_name") or "?",
                "detail": f"{int(top.get('points', 0))} p denna tävling",
            }
        )
    picks_raw = RacePick.query.filter_by(competition_id=competition_id).all()
    by_pick: dict[tuple, RacePick] = {}
    for p in picks_raw:
        pk = (p.user_id, p.rider_id)
        if pk not in by_pick or p.pick_id > by_pick[pk].pick_id:
            by_pick[pk] = p
    actual = _actual_positions(competition_id)
    perfect_stats: dict[int, dict] = {}
    for p in by_pick.values():
        act = actual.get(p.rider_id)
        if act is not None and act == p.predicted_position:
            uid = int(p.user_id)
            if uid not in perfect_stats:
                u = User.query.get(uid)
                perfect_stats[uid] = {
                    "user_id": uid,
                    "display_name": _display_name(u),
                    "count": 0,
                }
            perfect_stats[uid]["count"] += 1
    if perfect_stats:
        best = max(perfect_stats.values(), key=lambda x: x["count"])
        cards.append(
            {
                "icon": "🎯",
                "title": "Perfekt gissning",
                "user_id": best["user_id"],
                "display_name": best["display_name"],
                "detail": f"{best['count']} fullträffar i tävlingen",
            }
        )
    try:
        from main import aggregate_weekly_holeshot_points_from_picks

        hs = aggregate_weekly_holeshot_points_from_picks([competition_id])
        if hs:
            uid, pts = max(hs.items(), key=lambda x: x[1])
            u = User.query.get(int(uid))
            if u and pts:
                cards.append(
                    {
                        "icon": "🏁",
                        "title": "Holeshot-kung",
                        "user_id": int(uid),
                        "display_name": _display_name(u),
                        "detail": f"{int(pts)} holeshot-poäng",
                    }
                )
    except Exception:
        pass
    return cards[:4]


def _get_weekly_highlights(
    competition_id: int,
    race_leaderboard: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Veckans raket, ankare, perfekt gissning, holeshot — vecka kring vald tävling."""
    from datetime import timedelta
    from main import calculate_leaderboard_deltas, aggregate_weekly_holeshot_points_from_picks

    comp = Competition.query.get(competition_id)
    comp_ids = _comp_ids_for_recap_week(comp)
    if not comp_ids:
        return _fallback_race_highlights(competition_id, race_leaderboard)

    leaderboard_data = calculate_leaderboard_deltas()
    weekly_pts: dict[int, int] = defaultdict(int)
    scores = CompetitionScore.query.filter(CompetitionScore.competition_id.in_(comp_ids)).all()
    by_uc: dict[tuple[int, int], CompetitionScore] = {}
    for s in scores:
        k = (s.user_id, s.competition_id)
        if k not in by_uc or s.score_id > by_uc[k].score_id:
            by_uc[k] = s
    for s in by_uc.values():
        weekly_pts[int(s.user_id)] += int(s.total_points or 0)

    def pick_winner(*, want_climb: bool) -> dict | None:
        positive = {uid: pts for uid, pts in weekly_pts.items() if pts > 0}
        if not positive:
            return None
        ranked = []
        for u in leaderboard_data:
            uid = int(u.get("user_id") or 0)
            if uid not in positive:
                continue
            d = int(u.get("delta") or 0)
            if d == 0:
                continue
            if want_climb and d >= 0:
                continue
            if (not want_climb) and d <= 0:
                continue
            ranked.append(
                {
                    "user_id": uid,
                    "delta": d,
                    "weekly_points": positive[uid],
                    "current_rank": u.get("rank"),
                }
            )
        if ranked:
            ranked.sort(
                key=lambda r: (int(r["delta"]), -int(r["weekly_points"]))
                if want_climb
                else (-int(r["delta"]), int(r["weekly_points"]))
            )
            row = ranked[0]
        else:
            uid, pts = (
                max(positive.items(), key=lambda x: x[1])
                if want_climb
                else min(positive.items(), key=lambda x: x[1])
            )
            urow = next(
                (x for x in leaderboard_data if int(x.get("user_id") or 0) == uid),
                None,
            )
            row = {
                "user_id": uid,
                "delta": int(urow.get("delta") or 0) if urow else 0,
                "weekly_points": pts,
                "current_rank": urow.get("rank") if urow else None,
            }
        user = User.query.get(int(row["user_id"]))
        if not user:
            return None
        d = int(row["delta"])
        climb_txt = f"↑{abs(d)} platser" if d < 0 else (f"↓{d}" if d > 0 else "stabil vecka")
        return {
            "user_id": int(row["user_id"]),
            "display_name": _display_name(user),
            "detail": f"{climb_txt} · {row['weekly_points']} p i veckan",
        }

    cards: list[dict[str, Any]] = []
    rocket = pick_winner(want_climb=True)
    if rocket:
        cards.append(
            {
                "icon": "🚀",
                "title": "Veckans raket",
                **rocket,
            }
        )
    anchor = pick_winner(want_climb=False)
    if anchor:
        cards.append(
            {
                "icon": "⚓",
                "title": "Veckans ankare",
                **anchor,
            }
        )

    picks_raw = RacePick.query.filter(RacePick.competition_id.in_(comp_ids)).all()
    by_pick: dict[tuple, RacePick] = {}
    for p in picks_raw:
        pk = (p.user_id, p.competition_id, p.rider_id)
        if pk not in by_pick or p.pick_id > by_pick[pk].pick_id:
            by_pick[pk] = p
    actual_rows = CompetitionResult.query.filter(
        CompetitionResult.competition_id.in_(comp_ids)
    ).all()
    results_lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for res in actual_rows:
        k = (res.competition_id, res.rider_id)
        if k not in results_lookup or res.result_id > results_lookup[k][0]:
            results_lookup[k] = (res.result_id, res.position)
    perfect_stats: dict[int, dict] = {}
    for p in by_pick.values():
        res_row = results_lookup.get((p.competition_id, p.rider_id))
        act = res_row[1] if res_row else None
        if act is not None and act == p.predicted_position:
            uid = int(p.user_id)
            if uid not in perfect_stats:
                u = User.query.get(uid)
                perfect_stats[uid] = {"user_id": uid, "display_name": _display_name(u), "count": 0}
            perfect_stats[uid]["count"] += 1
    if perfect_stats:
        best = max(perfect_stats.values(), key=lambda x: x["count"])
        cards.append(
            {
                "icon": "🎯",
                "title": "Perfekt gissning",
                "user_id": best["user_id"],
                "display_name": best["display_name"],
                "detail": f"{best['count']} fullträffar denna vecka",
            }
        )

    hs_totals = aggregate_weekly_holeshot_points_from_picks(comp_ids)
    if hs_totals:
        uid, pts = max(hs_totals.items(), key=lambda x: x[1])
        u = User.query.get(int(uid))
        if u and pts:
            cards.append(
                {
                    "icon": "🏁",
                    "title": "Holeshot-kung",
                    "user_id": int(uid),
                    "display_name": _display_name(u),
                    "detail": f"{int(pts)} holeshot-poäng i veckan",
                }
            )

    if len(cards) < 2:
        for fb in _fallback_race_highlights(competition_id, race_leaderboard):
            if not any(c.get("title") == fb.get("title") for c in cards):
                cards.append(fb)
            if len(cards) >= 4:
                break

    return cards[:4]


def _actual_positions(competition_id: int) -> dict[int, int]:
    rows = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for res in rows:
        k = (res.competition_id, res.rider_id)
        if k not in lookup or res.result_id > lookup[k][0]:
            lookup[k] = (res.result_id, res.position)
    return {k[1]: v[1] for k, v in lookup.items()}


def _latest_results_by_rider(competition_id: int) -> dict[int, CompetitionResult]:
    rows = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    out: dict[int, CompetitionResult] = {}
    for res in rows:
        rid = int(res.rider_id)
        if rid not in out or res.result_id > out[rid].result_id:
            out[rid] = res
    return out


def _result_class_at_competition(
    comp: Competition,
    res: CompetitionResult,
    rider: Rider | None,
    *,
    promoted_250_coasts: dict[str, str] | None = None,
) -> str | None:
    """Klass vid tävlingen — snapshot + promoted-250-logik, inte nuvarande rider.class."""
    from main import _promoted_250_coast_by_name, _standing_class_and_coast

    if rider is None and res.rider_id:
        rider = Rider.query.get(res.rider_id)
    if rider is None:
        return None
    coasts = promoted_250_coasts if promoted_250_coasts is not None else _promoted_250_coast_by_name()
    class_name, _coast = _standing_class_and_coast(res, comp, rider, coasts)
    return class_name


def _result_class_matches_config(
    comp: Competition, effective_class: str | None, class_names: tuple[str, ...]
) -> bool:
    if not effective_class:
        return False
    norm = {
        "wsx_sx1": "450cc",
        "wsx_sx2": "250cc",
        "450cc": "450cc",
        "250cc": "250cc",
    }
    eff = norm.get(effective_class, effective_class)
    for cn in class_names:
        if norm.get(cn, cn) == eff:
            return True
    return False


def _rider_podium(
    comp: Competition,
    competition_id: int,
    class_names: tuple[str, ...],
    limit: int = 3,
) -> list[dict[str, Any]]:
    from main import _promoted_250_coast_by_name

    promoted = _promoted_250_coast_by_name()
    riders = {r.id: r for r in Rider.query.all()}
    found: list[tuple[int, Rider]] = []
    for res in _latest_results_by_rider(competition_id).values():
        pos = res.position
        if pos is None or pos < 1 or pos > limit:
            continue
        rider = riders.get(int(res.rider_id))
        if not rider:
            continue
        eff = _result_class_at_competition(comp, res, rider, promoted_250_coasts=promoted)
        if _result_class_matches_config(comp, eff, class_names):
            found.append((int(pos), rider))
    found.sort(key=lambda x: x[0])
    out = []
    for pos, r in found[:limit]:
        num = getattr(r, "rider_number", None)
        out.append(
            {
                "position": pos,
                "rider_id": r.id,
                "name": r.name,
                "short_name": _short_rider_name(r.name),
                "number": num,
                "label": f"#{num} {r.name}" if num else r.name,
            }
        )
    return out


def _iter_pick_payloads(competition_id: int) -> list[tuple[int, dict]]:
    from main import _build_picks_snapshot_payload, ensure_picks_snapshots_for_competition

    try:
        ensure_picks_snapshots_for_competition(int(competition_id), source="social_recap")
    except Exception:
        pass

    snap_by_uid = {
        int(s.user_id): s
        for s in PicksSnapshot.query.filter_by(competition_id=competition_id).all()
    }
    uid_sources: set[int] = set()
    for model in (RacePick, HoleshotPick, WildcardPick):
        uid_sources.update(
            int(uid)
            for (uid,) in db.session.query(model.user_id)
            .filter(model.competition_id == competition_id)
            .distinct()
            .all()
            if uid is not None
        )
    out: list[tuple[int, dict]] = []
    for uid in sorted(set(snap_by_uid.keys()) | uid_sources):
        snap = snap_by_uid.get(uid)
        if snap:
            try:
                payload = json.loads(snap.payload_json or "{}")
            except Exception:
                payload = {}
        else:
            payload = _build_picks_snapshot_payload(uid, competition_id)
        out.append((uid, payload))
    return out


def _winner_pick_stats(
    competition_id: int,
    winner_id: int,
    class_names: tuple[str, ...],
    picker_n: int,
) -> tuple[int, int]:
    """Andel som hade vinnaren som P1 respektive topp 3 (450/250)."""
    p1_count = top3_count = 0
    for _uid, payload in _iter_pick_payloads(competition_id):
        for p in payload.get("race_picks") or []:
            try:
                rid = int(p.get("rider_id"))
                pos = int(p.get("predicted_position"))
            except (TypeError, ValueError):
                continue
            if rid != winner_id:
                continue
            if pos == 1:
                p1_count += 1
            if 1 <= pos <= 3:
                top3_count += 1
    if picker_n <= 0:
        return 0, 0
    p1_pct = round(100.0 * p1_count / picker_n, 0)
    top3_pct = round(100.0 * top3_count / picker_n, 0)
    return int(p1_pct), int(top3_pct)


def _select_fun_facts_for_display(
    candidates: list[dict[str, str]], competition_id: int, limit: int = 3
) -> list[dict[str, str]]:
    """Välj fakta per tävling (stabilt men olika mellan race — inte samma mall varje gång)."""
    import random

    pinned = [f for f in candidates if f.get("id") == "picker_count"]
    pool = [f for f in candidates if f.get("id") not in ("picker_count", "no_picks")]
    rng = random.Random(int(competition_id) * 1009 + 17)
    rng.shuffle(pool)

    out: list[dict[str, str]] = []
    used_groups: set[str] = set()
    for f in pinned:
        out.append(f)
    for f in pool:
        if len(out) >= limit:
            break
        grp = str(f.get("group") or f.get("id") or "")
        if grp in used_groups:
            continue
        used_groups.add(grp)
        out.append(f)
    return out[:limit]


def _compute_fun_facts(comp: Competition, competition_id: int) -> list[dict[str, str]]:
    from main import _build_crowd_picks_summary

    crowd = _build_crowd_picks_summary(competition_id, comp, ensure_snapshots=True)
    n_lineups = int(crowd.get("n_lineups") or 0)
    n_users = int(crowd.get("n_users_with_snapshots_or_picks") or 0)
    picker_n = n_lineups or n_users
    if picker_n <= 0:
        return [{"id": "no_picks", "text": "Inga tips inlämnade för detta race ännu."}]

    candidates: list[dict[str, str]] = [
        {"id": "picker_count", "group": "meta", "text": f"{picker_n} spelare lämnade tips"}
    ]

    riders = {r.id: r for r in Rider.query.all()}
    cfg = _class_config(comp)
    cls450 = (cfg["primary"][0],)
    cls250 = (cfg["secondary"][0],)
    from main import _promoted_250_coast_by_name

    promoted = _promoted_250_coast_by_name()

    def winner_for_class(class_names: tuple[str, ...]) -> tuple[int | None, str]:
        for res in _latest_results_by_rider(competition_id).values():
            if int(res.position or 0) != 1:
                continue
            r = riders.get(int(res.rider_id))
            if not r:
                continue
            eff = _result_class_at_competition(comp, res, r, promoted_250_coasts=promoted)
            if not _result_class_matches_config(comp, eff, class_names):
                continue
            num = getattr(r, "rider_number", None)
            return int(r.id), f"#{num} {r.name}" if num else r.name
        return None, ""

    win450_id, win450_label = winner_for_class(cls450)
    slots450 = crowd.get("slots_450") or {}

    def slot_top(class_slots: dict, pos: int) -> dict | None:
        raw = class_slots.get(str(pos)) or class_slots.get(pos)
        return raw[0] if raw else None

    if win450_id and slot_top(slots450, 1):
        fav = slot_top(slots450, 1)
        fav_pct = float(fav.get("pct", 0) or 0)
        fav_name = fav.get("name") or fav.get("short", "?")
        p1_pct, top3_pct = _winner_pick_stats(competition_id, win450_id, cls450, picker_n)
        if int(fav.get("rider_id", 0)) == win450_id:
            candidates.append(
                {
                    "id": "p1_crowd_correct",
                    "group": "p1_450",
                    "text": f"{fav_pct:.0f}% hade {win450_label} som P1 — fältet hade rätt!",
                }
            )
        else:
            candidates.append(
                {
                    "id": "p1_upset",
                    "group": "p1_450",
                    "text": (
                        f"Fältets P1-favorit var {fav_name} ({fav_pct:.0f}%) "
                        f"men {win450_label} vann — {p1_pct:.0f}% hade honom P1"
                    ),
                }
            )
            if top3_pct >= 40:
                candidates.append(
                    {
                        "id": "winner_top3_share",
                        "group": "winner_top3",
                        "text": f"{top3_pct:.0f}% hade vinnaren {win450_label} i topp 3",
                    }
                )

    for pos, plabel in ((2, "P2"), (3, "P3")):
        top = slot_top(slots450, pos)
        if top:
            candidates.append(
                {
                    "id": f"slot_{pos}_450",
                    "group": f"slot_{pos}",
                    "text": f"Fältets {plabel}-val 450: {top.get('name', '?')} ({_pct_num(top.get('pct')):.0f}%)",
                }
            )

    win250_id, win250_label = winner_for_class(cls250)
    slots250 = crowd.get("slots_250") or {}
    if win250_id:
        p1_250, top3_250 = _winner_pick_stats(competition_id, win250_id, cls250, picker_n)
        fav250 = slot_top(slots250, 1)
        if fav250 and int(fav250.get("rider_id", 0)) == win250_id:
            candidates.append(
                {
                    "id": "250_crowd_correct",
                    "group": "p1_250",
                    "text": f"{cfg['secondary'][1]}: {win250_label} vann — fältet hade rätt P1",
                }
            )
        elif fav250:
            candidates.append(
                {
                    "id": "250_upset",
                    "group": "p1_250",
                    "text": (
                        f"{cfg['secondary'][1]}: {win250_label} vann, "
                        f"fältet gissade {fav250.get('name', '?')} P1"
                    ),
                }
            )
        else:
            candidates.append(
                {
                    "id": "250_winner",
                    "group": "p1_250",
                    "text": f"{cfg['secondary'][1]}: {win250_label} tog segern",
                }
            )
        if top3_250 > 0:
            candidates.append(
                {
                    "id": "250_top3",
                    "group": "winner_top3_250",
                    "text": f"{top3_250:.0f}% hade {win250_label} topp 3 i {cfg['secondary'][1]}",
                }
            )

    holo450 = crowd.get("holeshot_450") or []
    if holo450:
        top_h = holo450[0]
        candidates.append(
            {
                "id": "holeshot_crowd",
                "group": "holeshot",
                "text": f"Holeshot {cfg['primary'][1]}: {top_h.get('name', '?')} ({_pct_num(top_h.get('pct')):.0f}%)",
            }
        )

    holo250 = crowd.get("holeshot_250") or []
    if holo250:
        top_h = holo250[0]
        candidates.append(
            {
                "id": "holeshot_250",
                "group": "holeshot_250",
                "text": f"Holeshot {cfg['secondary'][1]}: {top_h.get('name', '?')} ({_pct_num(top_h.get('pct')):.0f}%)",
            }
        )

    if actual:
        perfect_total = 0
        pickers_with_perfect = 0
        for _uid, payload in _iter_pick_payloads(competition_id):
            user_perfect = 0
            for p in payload.get("race_picks") or []:
                try:
                    rid = int(p.get("rider_id"))
                    pred = int(p.get("predicted_position"))
                except (TypeError, ValueError):
                    continue
                act = actual.get(rid)
                if act is not None and act == pred:
                    user_perfect += 1
                    perfect_total += 1
            if user_perfect > 0:
                pickers_with_perfect += 1
        if perfect_total > 0:
            candidates.append(
                {
                    "id": "perfect_aggregate",
                    "group": "perfect",
                    "text": f"{perfect_total} perfekta gissningar · {pickers_with_perfect} spelare med fullträff",
                }
            )

    if getattr(comp, "series", None) != "WSX":
        # Inte "fältets vanligaste wildcard" (alla väljer olika platser) — visa träff mot resultat.
        promoted = _promoted_250_coast_by_name()
        by_pos_450: dict[int, int] = {}
        for res in _latest_results_by_rider(competition_id).values():
            rider = riders.get(int(res.rider_id))
            if not rider:
                continue
            eff = _result_class_at_competition(comp, res, rider, promoted_250_coasts=promoted)
            if _result_class_matches_config(comp, eff, (cfg["primary"][0],)):
                by_pos_450[int(res.position)] = int(res.rider_id)
        if by_pos_450:
            wcs = (
                WildcardPick.query.filter_by(competition_id=competition_id)
                .filter(
                    WildcardPick.rider_id.isnot(None),
                    WildcardPick.position.isnot(None),
                )
                .all()
            )
            if wcs:
                hits = sum(
                    1
                    for wc in wcs
                    if by_pos_450.get(int(wc.position)) == int(wc.rider_id)
                )
                n_wc = len(wcs)
                if hits <= 0:
                    txt = (
                        f"Ingen prickade wildcard — {n_wc} spelade "
                        f"(rätt {cfg['primary'][1]}-förare på vald plats = +15 p)."
                    )
                elif hits == 1:
                    txt = "1 spelare prickade wildcard — rätt förare på rätt plats (+15 p)!"
                else:
                    txt = f"{hits} spelare prickade wildcard — rätt förare på rätt plats (+15 p)!"
                candidates.append({"id": "wildcard_hits", "group": "wildcard", "text": txt})

    return _select_fun_facts_for_display(candidates, competition_id, limit=3)


def build_social_recap_data(
    competition_id: int,
    *,
    race_top: int = 3,
    season_top: int = 5,
    include_race: bool = True,
    include_weekly: bool = True,
    include_season_snippet: bool = True,
    include_facts: bool = True,
    include_rider_podium: bool = True,
) -> dict[str, Any]:
    comp = Competition.query.get(competition_id)
    if not comp:
        raise ValueError("competition_not_found")

    has_results = (
        CompetitionResult.query.filter_by(competition_id=competition_id).first() is not None
    )
    cfg = _class_config(comp)

    event_label = comp.name or "Race"
    if comp.event_date:
        event_label = f"{comp.name} · {comp.event_date.strftime('%d %b %Y')}"

    data: dict[str, Any] = {
        "competition_id": competition_id,
        "competition_name": comp.name,
        "event_date": comp.event_date.isoformat() if comp.event_date else None,
        "series": getattr(comp, "series", None),
        "event_label": event_label,
        "has_results": has_results,
        "class_labels": {"primary": cfg["primary"][1], "secondary": cfg["secondary"][1]},
        "race_top": max(1, min(int(race_top), 15)),
        "season_top": max(1, min(int(season_top), 15)),
        "modules": {
            "race": include_race,
            "weekly": include_weekly,
            "season_snippet": include_season_snippet,
            "facts": include_facts,
            "rider_podium": include_rider_podium,
        },
    }

    if include_rider_podium and has_results:
        data["rider_podium_primary"] = _rider_podium(
            comp, competition_id, (cfg["primary"][0],), limit=3
        )
        data["rider_podium_secondary"] = _rider_podium(
            comp, competition_id, (cfg["secondary"][0],), limit=3
        )
    else:
        data["rider_podium_primary"] = []
        data["rider_podium_secondary"] = []

    if include_race:
        data["race_leaderboard"] = _race_leaderboard(competition_id, data["race_top"])
    else:
        data["race_leaderboard"] = []

    if include_weekly:
        data["weekly_highlights"] = _get_weekly_highlights(
            competition_id, data.get("race_leaderboard")
        )
    else:
        data["weekly_highlights"] = []

    if include_season_snippet:
        data["season_top_snippet"] = _season_top_snippet(data["season_top"])
    else:
        data["season_top_snippet"] = []

    if include_facts:
        data["fun_facts"] = _compute_fun_facts(comp, competition_id)
    else:
        data["fun_facts"] = []

    data["caption"] = build_facebook_caption(data)
    return data


def build_facebook_caption(data: dict[str, Any]) -> str:
    labels = data.get("class_labels") or {}
    lines = [f"🏁 {data.get('event_label', 'Race')} — MX Fantasy League", ""]

    rp = data.get("rider_podium_primary") or []
    rs = data.get("rider_podium_secondary") or []
    if data.get("modules", {}).get("rider_podium") and (rp or rs):
        if rp:
            lines.append(f"🏍️ {labels.get('primary', '450')} — resultat:")
            for row in rp:
                lines.append(f"  P{row['position']}: {row['label']}")
        if rs:
            lines.append(f"🏍️ {labels.get('secondary', '250')} — resultat:")
            for row in rs:
                lines.append(f"  P{row['position']}: {row['label']}")
        lines.append("")

    if data.get("modules", {}).get("race") and data.get("race_leaderboard"):
        lines.append("🏆 Fantasy — denna tävling:")
        for row in data["race_leaderboard"][:5]:
            lines.append(f"{row['rank']}. {row['display_name']} — {row['points']} p")
        lines.append("")

    highlights = data.get("weekly_highlights") or []
    if data.get("modules", {}).get("weekly") and highlights:
        lines.append("⭐ Veckans prestationer:")
        for h in highlights:
            lines.append(f"{h.get('icon', '')} {h.get('title', '')}: {h.get('display_name', '?')} — {h.get('detail', '')}")
        lines.append("")

    snippet = data.get("season_top_snippet") or []
    if data.get("modules", {}).get("season_snippet") and snippet:
        lines.append("📊 Säsongstoppen:")
        for row in snippet:
            rk = row.get("rank", "?")
            nm = row.get("display_name") or "?"
            pts = row.get("points", 0)
            lines.append(f"{rk}. {nm} — {pts} p")
        lines.append("")

    for fact in (data.get("fun_facts") or [])[:4]:
        t = fact.get("text")
        if t:
            lines.append(f"💡 {t}")

    lines.extend(
        [
            "",
            "Spela med oss — lämna dina tips inför nästa race! 🔥",
            "#MXFantasy #Supercross #FantasyMX",
        ]
    )
    return "\n".join(lines).strip()


# --- Rendering ---


def _load_font_px(size: int, bold: bool = False):
    """Fast pixelstorlek (Facebook-enkel layout) — ingen FONT_SCALE."""
    from PIL import ImageFont

    size = max(12, int(size))
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    # load_default() ignorerar size — ger alltid ~10px text (vanlig orsak på Render utan fonts)
    return ImageFont.load_default()


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont

    size = _fs(size)
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load_display_font(size: int, bold: bool = True):
    """Större display-rubriker (Impact/Arial Black när det finns)."""
    from PIL import ImageFont

    size = _fs(size)
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/impact.ttf",
                "C:/Windows/Fonts/ariblk.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return _load_font(size, bold=bold)


def _draw_styled_text(
    draw,
    pos: tuple[int, int],
    text: str,
    font,
    fill: tuple[int, int, int],
    *,
    anchor: str = "mt",
    stroke: tuple[int, int, int] | None = None,
    stroke_width: int = 3,
    glow: tuple[int, int, int] | None = None,
) -> None:
    x, y = pos
    if glow:
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
            draw.text((x + dx, y + dy), text, font=font, fill=glow, anchor=anchor)
    kw: dict = {"fill": fill, "anchor": anchor}
    if stroke:
        kw["stroke_width"] = stroke_width
        kw["stroke_fill"] = stroke
    draw.text(pos, text, font=font, **kw)


def _font_height(font, text: str = "Ay") -> int:
    bbox = font.getbbox(text or "A")
    return max(8, int(bbox[3] - bbox[1]))


def _text_width(font, text: str) -> int:
    bbox = font.getbbox(text or "")
    return max(0, int(bbox[2] - bbox[0]))


def _wrap_text_width(text: str, font, max_width: int) -> list[str]:
    """Radbrytning efter faktisk pixelbredd — inte antal tecken."""
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        if _text_width(font, test) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _fit_font_px(text: str, max_width: int, *, bold: bool = True, min_px: int = 36, max_px: int = 58) -> Any:
    """Välj största typsnitt som får plats på en rad (fältfakta-rader)."""
    for px in range(max_px, min_px - 1, -2):
        font = _load_font_px(px, bold=bold)
        if _text_width(font, text) <= max_width:
            return font
    return _load_font_px(min_px, bold=bold)


def _large_podium_layout(usable_width: int) -> tuple[int, int]:
    """Blockbredd och avstånd mellan P1/P2/P3 så namn inte krockar."""
    block_w = min(140, max(118, usable_width // 6))
    side_pad = 28
    spacing = (usable_width - block_w - 2 * side_pad) // 2
    spacing = max(block_w // 2 + 18, spacing)
    return block_w, spacing


def _fit_podium_name(
    name: str, max_width: int, *, min_px: int = 17, max_px: int = 30
) -> tuple[str, Any]:
    """Korta vid behov och välj font som ryms inom given bredd."""
    text = (name or "?").strip()
    for _ in range(5):
        font = _fit_font_px(text, max_width, bold=True, min_px=min_px, max_px=max_px)
        if _text_width(font, text) <= max_width:
            return text, font
        if len(text) <= 5:
            return text, font
        text = text[: max(4, len(text) - 2)].rstrip(".") + "…"
    return text, _load_font_px(min_px, bold=True)


def _draw_text_shadow_mt(
    draw, cx: int, y: int, text: str, font, *, fill: tuple[int, int, int] = WHITE
) -> None:
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        draw.text((cx + dx, y + dy), text, font=font, fill=(0, 0, 0), anchor="mt")
    draw.text((cx, y), text, font=font, fill=fill, anchor="mt")


def _header_event_lines(data: dict[str, Any]) -> tuple[str, str]:
    """Tävlingsnamn och datum på separata rader."""
    name = (data.get("competition_name") or "").strip()
    date_line = ""
    raw_date = data.get("event_date")
    if raw_date:
        try:
            from datetime import datetime

            d = datetime.fromisoformat(str(raw_date).replace("Z", "")).date()
            date_line = d.strftime("%d %b %Y")
        except Exception:
            date_line = str(raw_date)[:16]
    label = (data.get("event_label") or "").strip()
    if not name and label:
        if "·" in label:
            parts = [p.strip() for p in label.split("·", 1)]
            name = parts[0]
            if len(parts) > 1 and not date_line:
                date_line = parts[1]
        else:
            name = label
    if not name:
        name = "Race"
    return name[:40], date_line[:32]


def _draw_recap_pill(
    draw,
    x: int,
    y_mid: int,
    text: str,
    font,
    *,
    pad_x: int = 14,
    pad_y: int = 6,
) -> int:
    """RACE RECAP-badge — returnerar x efter pill."""
    tw = _text_width(font, text)
    th = _font_height(font)
    w = tw + pad_x * 2
    h = th + pad_y * 2
    top = y_mid - h // 2
    draw.rounded_rectangle(
        [x, top, x + w, top + h],
        radius=h // 2,
        fill=(12, 74, 110),
        outline=CYAN,
        width=2,
    )
    _draw_styled_text(draw, (x + w // 2, y_mid), text, font, WHITE, anchor="mm")
    return x + w


def _draw_recap_header(img, draw, data: dict[str, Any]) -> int:
    """Horisontell header: logga vänster, text på en rad."""
    cw = _canvas_w(img)
    compact_header = data.get("layout") in ("square", "facebook", "facebook_graphic")
    header_h = _sz(118) if compact_header else _sz(148)
    pad_x = _sz(32)
    race_name, race_date = _header_event_lines(data)

    draw.rectangle([0, 0, cw, 8], fill=CYAN)
    for row in range(8, header_h):
        t = (row - 8) / max(header_h - 9, 1)
        r = int(10 + 6 * (1 - t))
        g = int(18 + 8 * (1 - t))
        b = int(38 + 10 * (1 - t))
        draw.line([(0, row), (cw, row)], fill=(r, g, b))
    draw.line([(0, header_h - 1), (cw, header_h - 1)], fill=CYAN_DIM, width=2)

    logo = _load_brand_logo(_sz(108))
    logo_w = 0
    mid_y = header_h // 2 + 2
    if logo:
        logo_w = logo.width
        ly = mid_y - logo.height // 2
        img.paste(logo, (pad_x, ly), logo)

    text_x = pad_x + logo_w + (28 if logo_w else 0)
    max_x = cw - pad_x

    def _row_width(brand_f, recap_f, race_f, date_f) -> int:
        w = text_x
        w += _text_width(brand_f, "MX FANTASY") + 18
        w += _text_width(recap_f, "RACE RECAP") + 14 * 2 + 18
        w += 2 + 14
        w += _text_width(race_f, race_name)
        if race_date:
            w += 10 + _text_width(date_f, "·") + 10 + _text_width(date_f, race_date)
        return w

    brand_f = recap_f = race_f = date_f = None
    for bs, rp, rs, ds in ((38, 24, 34, 28), (34, 22, 30, 26), (30, 20, 28, 24), (28, 18, 26, 22)):
        brand_f = _load_display_font(bs, bold=True)
        recap_f = _load_display_font(rp, bold=True)
        race_f = _load_display_font(rs, bold=True)
        date_f = _load_display_font(ds, bold=True)
        if _row_width(brand_f, recap_f, race_f, date_f) <= max_x:
            break

    x = text_x
    _draw_styled_text(
        draw, (x, mid_y), "MX FANTASY", brand_f, CYAN, anchor="lm",
        stroke=(4, 30, 50), stroke_width=2,
    )
    x += _text_width(brand_f, "MX FANTASY") + 18

    x = _draw_recap_pill(draw, x, mid_y, "RACE RECAP", recap_f) + 18

    draw.line([(x, mid_y - 26), (x, mid_y + 26)], fill=PANEL_EDGE, width=2)
    x += 14

    _draw_styled_text(
        draw, (x, mid_y), race_name, race_f, WHITE, anchor="lm",
        stroke=(20, 28, 45), stroke_width=2,
    )
    x += _text_width(race_f, race_name)

    if race_date:
        x += 10
        _draw_styled_text(draw, (x, mid_y), "·", date_f, MUTED, anchor="lm")
        x += _text_width(date_f, "·") + 10
        _draw_styled_text(
            draw, (x, mid_y), race_date, date_f, CYAN, anchor="lm",
            stroke=(0, 0, 0), stroke_width=1,
        )

    return header_h + 14


def _load_brand_logo(size: int = 96):
    from PIL import Image

    for rel in (
        "static/icons/mx_fantasy_app_icon_512.png",
        "static/images/mx_fantasy_favicon.png",
    ):
        p = _ROOT / rel
        if p.exists():
            img = Image.open(p).convert("RGBA")
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            return img
    return None


def _paste_recap_brand_logo_in_circle(
    base,
    circle: dict[str, int],
    ref_w: int,
    ref_h: int,
    out_w: int,
    out_h: int,
) -> None:
    """Placera MX Fantasy-loggan i header-cirkeln på recap-mallen."""
    from PIL import Image, ImageDraw

    cx, cy, r = _scale_recap_circle(circle, ref_w, ref_h, out_w, out_h)
    d = max(24, r * 2)
    fill = int(d * 1.02)  # fyll nästan hela header-cirkeln
    logo = _load_brand_logo(fill * 2)
    if logo is None:
        return
    logo = logo.resize((fill, fill), Image.Resampling.LANCZOS)
    inner = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ox = (d - logo.width) // 2
    oy = (d - logo.height) // 2
    inner.paste(logo, (ox, oy), logo)
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d - 1, d - 1], fill=255)
    inner.putalpha(mask)
    base.paste(inner, (cx - d // 2, cy - d // 2), inner)


def _load_image_bytes(raw: str, size: int = 0):
    """Ladda bild från data-URL, http(s) eller relativ sökväg — utan resize."""
    from PIL import Image

    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.startswith("data:"):
            b64 = s.split(",", 1)[-1]
            data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
        elif s.startswith("http"):
            import urllib.request

            req = urllib.request.Request(
                s, headers={"User-Agent": "MXFantasyRecap/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGBA")
        else:
            if not s.startswith(("riders/", "uploads/", "trackmaps/")):
                s = "riders/" + s.lstrip("/")
            p = _ROOT / "static" / s.lstrip("/")
            if not p.exists():
                p = _ROOT / s.lstrip("/")
            if not p.exists():
                return None
            img = Image.open(p).convert("RGBA")
        return img
    except Exception:
        return None


def _normalize_portrait_url(url: str) -> str:
    try:
        from app.portrait_urls import normalize_racerx_portrait_url

        return normalize_racerx_portrait_url(url) or url
    except Exception:
        return url


def _load_rider_thumb(rider_id: int, size: int = 72):
    rider = Rider.query.get(rider_id)
    if not rider:
        return None
    raw = getattr(rider, "rider_image_data", None) or getattr(rider, "image_url", None)
    if not raw:
        return None
    s = str(raw).strip()
    if s.startswith("http"):
        s = _normalize_portrait_url(s)
    return _load_image_bytes(s, size)


def _load_user_profile_image(user_id: int, size: int = 72):
    user = User.query.get(user_id)
    if not user:
        return None
    raw = getattr(user, "profile_picture_url", None)
    if not raw:
        return None
    return _load_image_bytes(str(raw), size)


def _make_initials_avatar(display_name: str, user_id: int, size: int):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg = AVATAR_BG[int(user_id or 0) % len(AVATAR_BG)]
    draw.ellipse([0, 0, size - 1, size - 1], fill=bg)
    ini = _user_initials(display_name)
    f = _load_font(max(14, size // 3), bold=True)
    draw.text((size // 2, size // 2), ini, font=f, fill=WHITE, anchor="mm")
    return img


def _paste_user_avatar(
    base,
    cx: int,
    cy: int,
    radius: int,
    user_id: int | None,
    display_name: str,
):
    from PIL import Image, ImageDraw

    ring = Image.new("RGBA", (radius * 2 + 8, radius * 2 + 8), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([0, 0, radius * 2 + 7, radius * 2 + 7], fill=(*CYAN, 200))

    inner = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    thumb = None
    if user_id:
        thumb = _load_user_profile_image(int(user_id), radius * 2)
    if thumb is None:
        thumb = _make_initials_avatar(display_name, int(user_id or 0), radius * 2)

    mask = Image.new("L", (radius * 2, radius * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, radius * 2 - 1, radius * 2 - 1], fill=255)
    inner.paste(
        thumb,
        ((radius * 2 - thumb.width) // 2, (radius * 2 - thumb.height) // 2),
        thumb if thumb.mode == "RGBA" else None,
    )
    inner.putalpha(mask)

    base.paste(ring, (cx - radius - 4, cy - radius - 4), ring)
    base.paste(inner, (cx - radius, cy - radius), inner)


def _paste_circle_avatar(base, cx: int, cy: int, radius: int, rider_id: int | None, initials: str):
    from PIL import Image, ImageDraw

    ring = Image.new("RGBA", (radius * 2 + 8, radius * 2 + 8), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([0, 0, radius * 2 + 7, radius * 2 + 7], fill=(*CYAN, 180))

    inner = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(inner)
    thumb = _load_rider_thumb(rider_id, radius * 2) if rider_id else None
    if thumb:
        mask = Image.new("L", (radius * 2, radius * 2), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, radius * 2 - 1, radius * 2 - 1], fill=255)
        inner.paste(thumb, ((radius * 2 - thumb.width) // 2, (radius * 2 - thumb.height) // 2), thumb)
        inner.putalpha(mask)
    else:
        fallback = _make_initials_avatar(str(initials), int(rider_id or 0), radius * 2)
        inner.paste(
            fallback,
            ((radius * 2 - fallback.width) // 2, (radius * 2 - fallback.height) // 2),
            fallback,
        )

    base.paste(ring, (cx - radius - 4, cy - radius - 4), ring)
    base.paste(inner, (cx - radius, cy - radius), inner)


def _draw_vertical_gradient(img) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    _, img_h = img.size
    for y in range(img_h):
        t = y / max(img_h - 1, 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (img.size[0], y)], fill=(r, g, b))


def _draw_panel(
    draw, xy: tuple[int, int, int, int], title: str | None = None, *, large: bool = False
) -> None:
    x0, y0, x1, y1 = xy
    rad = 16 if large else _sz(16)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=PANEL, outline=PANEL_EDGE, width=2)
    if title:
        tf = _load_font_px(44, bold=True) if large else _load_font(28, bold=True)
        draw.text((x0 + (20 if large else _sz(16)), y0 + (14 if large else _sz(12))), title.upper(), font=tf, fill=CYAN)


def _draw_panel_title_on_top(
    draw, x0: int, y0: int, x1: int, title: str, *, large: bool = False
) -> None:
    """Paneltitel ovanpå avatarer/innehåll."""
    bar_h = 58 if large else _sz(50)
    draw.rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + bar_h], fill=PANEL)
    draw.line([(x0 + 2, y0 + bar_h), (x1 - 2, y0 + bar_h)], fill=PANEL_EDGE, width=1)
    tf = _load_font_px(38, bold=True) if large else _load_font(28, bold=True)
    draw.text((x0 + 20, y0 + 14), title.upper(), font=tf, fill=CYAN)


def _draw_podium_block(
    draw,
    base_img,
    cx: int,
    floor_y: int,
    entry: dict | None,
    block_w: int,
    block_h: int,
    medal_color: tuple[int, int, int],
    rank_label: str,
    is_rider: bool,
    *,
    large: bool = False,
    label_max_width: int | None = None,
) -> None:
    if not entry:
        return
    x0 = cx - block_w // 2
    y0 = floor_y - block_h
    draw.rounded_rectangle(
        [x0, y0, x0 + block_w, floor_y],
        radius=10,
        fill=PANEL,
        outline=medal_color,
        width=3,
    )
    for i in range(block_h):
        t = i / max(block_h, 1)
        col = tuple(
            int(medal_color[j] * (0.2 + 0.65 * t) + PANEL[j] * (0.8 - 0.5 * t)) for j in range(3)
        )
        draw.line([(x0 + 5, y0 + i), (x0 + block_w - 5, y0 + i)], fill=col)

    text_max = block_w - 14

    if large:
        if is_rider:
            av_r, av_above = 48, 40
        else:
            av_r, av_above = 32, 26
        rank_f = _fit_font_px(rank_label, text_max, bold=True, min_px=18, max_px=24)
    else:
        av_r = _sz(44)
        av_above = _sz(40)
        rank_f = _load_font(24, bold=True)
        nf = _load_font(28, bold=True)
        sub_f = _load_font(22)
        pts_f = _load_font(26, bold=True)

    draw.text((cx, y0 + (14 if large else _sz(10))), rank_label, font=rank_f, fill=medal_color, anchor="mt")

    if is_rider:
        num = entry.get("number")
        initials = str(num) if num else (entry.get("short_name") or "?")[:1]
        _paste_circle_avatar(base_img, cx, y0 - av_above, av_r, entry.get("rider_id"), initials)
        name = entry.get("short_name") or "?"
        num_s = f"#{num}" if num else ""
    else:
        uid = entry.get("user_id")
        name_full = entry.get("display_name") or "?"
        _paste_user_avatar(base_img, cx, y0 - av_above, av_r, uid, name_full)
        # Stora fantasy-pallen: låt _fit_podium_name skala font / … — inte hårdbromsa till 11 tecken.
        name = (name_full or "?").strip() if large else _short_user_name(name_full, 14)
        num_s = ""

    if large:
        label_w = label_max_width or text_max
        if is_rider:
            name, nf = _fit_podium_name(name, text_max, min_px=18, max_px=30)
            name_y = floor_y - (58 if num_s else 48)
            _draw_text_shadow_mt(draw, cx, name_y, name, nf)
            if num_s:
                sub_f = _fit_font_px(num_s, text_max, bold=True, min_px=16, max_px=22)
                draw.text((cx, floor_y - 26), num_s, font=sub_f, fill=(230, 230, 230), anchor="mt")
        else:
            # Fantasy: hela namnet om det ryms; mindre min-font = färre onödiga …
            cap_w = min(label_w, text_max + 18)
            name, nf = _fit_podium_name(name, cap_w, min_px=15, max_px=28)
            name_y = floor_y + 20
            _draw_text_shadow_mt(draw, cx, name_y, name, nf)
            pts = entry.get("points", 0)
            pts_line = f"{pts} p"
            pts_f = _fit_font_px(pts_line, cap_w, bold=True, min_px=18, max_px=26)
            draw.text(
                (cx, name_y + int(_font_height(nf) * 1.2) + 4),
                pts_line,
                font=pts_f,
                fill=CYAN,
                anchor="mt",
            )
    else:
        draw.text((cx, floor_y + _sz(12)), name, font=nf, fill=WHITE, anchor="mt")
        if num_s and is_rider:
            draw.text((cx, floor_y + _sz(42)), num_s, font=sub_f, fill=MUTED, anchor="mt")
        elif not is_rider:
            pts = entry.get("points", 0)
            draw.text(
                (cx, floor_y + _sz(40)), f"{pts} p", font=pts_f, fill=CYAN, anchor="mt"
            )


def _draw_rider_podium_row(
    draw,
    base_img,
    x0: int,
    y0: int,
    width: int,
    title: str,
    podium: list[dict],
    *,
    panel_h: int | None = None,
    large: bool = False,
) -> int:
    """Draw class podium inside panel; return bottom y."""
    panel_h = panel_h or _sz(290)
    _draw_panel(draw, (x0, y0, x0 + width, y0 + panel_h), title, large=large)
    if not podium:
        draw.text(
            (x0 + width // 2, y0 + panel_h // 2),
            "Inga resultat",
            font=_load_font(24),
            fill=MUTED,
            anchor="mm",
        )
        return y0 + panel_h

    by_pos = {int(p["position"]): p for p in podium}
    if large:
        order = [(2, SILVER, 115), (1, GOLD, 150), (3, BRONZE, 100)]
        block_w, spacing = _large_podium_layout(width)
        floor_off = 52
    else:
        order = [(2, SILVER, 78), (1, GOLD, 108), (3, BRONZE, 66)]
        order = [(a, b, _sz(c)) for a, b, c in order]
        block_w = _sz(118)
        floor_off = _sz(28)
        spacing = min(_sz(140), (width - _sz(40)) // 3)
    floor_y = y0 + panel_h - floor_off
    cx_mid = x0 + width // 2
    for pos, color, bh in order:
        entry = by_pos.get(pos)
        off = {1: 0, 2: -spacing, 3: spacing}[pos]
        bh_use = bh if large else bh
        _draw_podium_block(
            draw,
            base_img,
            cx_mid + off,
            floor_y,
            entry,
            block_w=block_w,
            block_h=bh_use,
            medal_color=color,
            rank_label=f"P{pos}",
            is_rider=True,
            large=large,
        )
    return y0 + panel_h


def _draw_user_podium_section(
    draw,
    base_img,
    y0: int,
    title: str,
    leaderboard: list[dict],
    data: dict[str, Any],
    *,
    x0: int | None = None,
    x1: int | None = None,
    base_panel: int | None = None,
    max_extras: int | None = None,
    large: bool = False,
) -> int:
    """Podium for top 3 + optional rows 4+."""
    cw = _canvas_w(base_img)
    top3 = [r for r in leaderboard if _leaderboard_rank(r) <= 3]
    extras = [r for r in leaderboard if _leaderboard_rank(r) > 3]
    if max_extras is not None:
        extras = extras[:max_extras]
    row_extra_h = 68 if large else _sz(48)
    title_pad = 92 if large else _sz(52)
    margin = x0 if x0 is not None else _sz(36)
    right = x1 if x1 is not None else cw - _sz(36)
    if large:
        inner_w = right - margin
        bw, spacing = _large_podium_layout(inner_w)
        label_w = bw + 12
        under_title = 36
        max_bh = 125
        pod_blocks_h = under_title + max_bh
        caption_h = 88
        list_gap = 22 if extras else 0
        list_h = len(extras) * row_extra_h
        panel_h = title_pad + pod_blocks_h + caption_h + list_gap + list_h + 20
    else:
        base_panel = base_panel or _sz(300)
        panel_h = base_panel if not extras else base_panel + len(extras) * row_extra_h + _sz(8)
        label_w = None
    _draw_panel(draw, (margin, y0, right, y0 + panel_h), None if large else title, large=large)

    by_pos = {_leaderboard_rank(r): r for r in top3}
    if large:
        floor_y = y0 + title_pad + under_title + max_bh
        blocks = [(2, SILVER, 100), (1, GOLD, 125), (3, BRONZE, 90)]
    else:
        floor_y = y0 + (_sz(248) if not extras else _sz(218))
        spacing = _sz(162)
        blocks = [(2, SILVER, 78), (1, GOLD, 108), (3, BRONZE, 66)]
        bw = _sz(128)
    cx_mid = (margin + right) // 2
    for pos, color, bh in blocks:
        entry = by_pos.get(pos)
        bh_use = bh if large else _sz(bh)
        _draw_podium_block(
            draw,
            base_img,
            cx_mid + {1: 0, 2: -spacing, 3: spacing}[pos],
            floor_y,
            entry,
            block_w=bw,
            block_h=bh_use,
            medal_color=color,
            rank_label=str(pos),
            is_rider=False,
            large=large,
            label_max_width=label_w if large else None,
        )
    if large:
        _draw_panel_title_on_top(draw, margin, y0, right, title, large=True)

    if extras:
        if large:
            extras_top = y0 + title_pad + pod_blocks_h + caption_h + list_gap
            draw.line(
                [(margin + 24, extras_top - 11), (right - 24, extras_top - 11)],
                fill=PANEL_EDGE,
                width=1,
            )
        bf = _load_font_px(40, bold=True) if large else _load_font(26)
        for i, row in enumerate(extras):
            if large:
                row_y = extras_top + i * row_extra_h
                draw.rounded_rectangle(
                    [margin + 12, row_y + 2, right - 12, row_y + row_extra_h - 2],
                    radius=10,
                    fill=(18, 28, 48),
                    outline=PANEL_EDGE,
                    width=1,
                )
                row_cy = row_y + row_extra_h // 2
                row_mid = row_cy
                av = 30
                # Ring vänsterkant = av_cx - av - 4; håll innanför marginal + luft
                av_cx = margin + 28 + av + 4
                ring_right = av_cx + av + 4
                rank_x = ring_right + 14
            else:
                row_y = y0 + panel_h - _sz(20) - len(extras) * row_extra_h + i * row_extra_h
                row_cy = row_y + row_extra_h // 2
                row_mid = row_cy
                av = _sz(22)
                av_cx = margin + _sz(40) + av + 4
                ring_right = av_cx + av + 4
                rank_x = ring_right + _sz(10)
            name = row.get("display_name") or "?"
            if large:
                name, nf = _fit_podium_name(
                    name, right - rank_x - 130, min_px=26, max_px=36
                )
            else:
                nf = bf
                name = _short_user_name(name)
            pts = int(row.get("points", 0))
            rank = _leaderboard_rank(row, 0)
            _paste_user_avatar(
                base_img, av_cx, row_cy,
                av, row.get("user_id"), row.get("display_name") or "?",
            )
            rank_f = bf if not large else _fit_font_px(f"{rank}.", 44, bold=True, min_px=24, max_px=30)
            rank_txt = f"{rank}."
            draw.text((rank_x, row_mid), rank_txt, font=rank_f, fill=MUTED, anchor="lm")
            name_x = rank_x + _text_width(rank_f, rank_txt) + 12
            draw.text((name_x, row_mid), name, font=nf, fill=WHITE, anchor="lm")
            pts_f = bf if not large else _fit_font_px(f"{pts} p", 120, bold=True, min_px=24, max_px=32)
            draw.text((right - 12, row_mid), f"{pts} p", font=pts_f, fill=CYAN, anchor="rm")

    return y0 + panel_h


def _draw_weekly_highlights_section(
    draw,
    base_img,
    y0: int,
    cards: list[dict],
    data: dict[str, Any],
    *,
    x0: int | None = None,
    x1: int | None = None,
    card_h: int | None = None,
    large: bool = False,
) -> int:
    if not cards:
        return y0
    cw = _canvas_w(base_img)
    cols = 2
    rows_n = (len(cards) + cols - 1) // cols
    card_h = card_h or (184 if large else _sz(96))
    gap = 20 if large else _sz(12)
    margin = x0 if x0 is not None else _sz(36)
    right = x1 if x1 is not None else cw - _sz(36)
    inner = right - margin
    title_h = 64 if large else _sz(52)
    panel_h = title_h + rows_n * (card_h + gap)
    _draw_panel(draw, (margin, y0, right, y0 + panel_h), "Veckans prestationer", large=large)
    col_w = (inner - gap) // 2
    av = 44 if large else _sz(32)
    pad = 22 if large else _sz(16)
    av_inset = 24 if large else _sz(18)
    av_cx = av_inset + av + 4  # offset from card_x; ring left = card_x + av_inset
    tx_off = (av_inset + (av + 4) * 2 + 20) if large else _sz(80)
    text_w = col_w - tx_off - 12
    for i, card in enumerate(cards[:4]):
        col = i % cols
        row_i = i // cols
        card_x = margin + pad + col * (col_w + gap)
        y = y0 + title_h + row_i * (card_h + gap)
        draw.rounded_rectangle(
            [card_x, y, card_x + col_w, y + card_h],
            radius=12 if large else _sz(12),
            fill=(15, 25, 45),
            outline=PANEL_EDGE,
            width=1,
        )
        _paste_user_avatar(
            base_img,
            card_x + av_cx,
            y + card_h // 2,
            av,
            card.get("user_id"),
            card.get("display_name") or "?",
        )
        tx = card_x + tx_off
        title = _plain_draw_text(card.get("title") or "")
        if large:
            tf = _fit_font_px(title, text_w, bold=True, min_px=32, max_px=40)
            disp = _short_recap_display_name(card.get("display_name") or "?")
            disp, nf = _fit_podium_name(disp, text_w, min_px=30, max_px=40)
            d1, d2 = _weekly_detail_recap_lines(card.get("detail") or "")
            df = _fit_font_px(d1, text_w, bold=True, min_px=26, max_px=32)
            d2f = _fit_font_px(d2, text_w, bold=False, min_px=24, max_px=28) if d2 else None
            draw.text((tx, y + 18), title, font=tf, fill=CYAN)
            draw.text((tx, y + 56), disp, font=nf, fill=WHITE)
            draw.text((tx, y + 108), d1, font=df, fill=_weekly_detail_line1_fill(d1))
            if d2 and d2f:
                draw.text((tx, y + 148), d2, font=d2f, fill=MUTED)
        else:
            tf = _load_font(24, bold=True)
            nf = _load_font(24, bold=True)
            d1, d2 = _weekly_detail_recap_lines(card.get("detail") or "")
            df = _load_font(22, bold=True)
            d2f = _load_font(20)
            draw.text((tx, y + _sz(16)), title[:28], font=tf, fill=CYAN)
            draw.text(
                (tx, y + _sz(44)),
                _short_recap_display_name(card.get("display_name") or "?"),
                font=nf,
                fill=WHITE,
            )
            draw.text((tx, y + _sz(68)), d1[:48], font=df, fill=_weekly_detail_line1_fill(d1))
            if d2:
                draw.text((tx, y + _sz(92)), d2[:48], font=d2f, fill=MUTED)
    return y0 + panel_h


def _draw_season_top_snippet(
    draw,
    base_img,
    y0: int,
    rows: list[dict],
    data: dict[str, Any],
    *,
    x0: int | None = None,
    x1: int | None = None,
    row_h: int | None = None,
    large: bool = False,
) -> int:
    if not rows:
        return y0
    cw = _canvas_w(base_img)
    list_top_pad = 14 if large else 0
    row_h = row_h or (82 if large else _sz(56))
    margin = x0 if x0 is not None else _sz(36)
    right = x1 if x1 is not None else cw - _sz(36)
    title_h = 64 if large else _sz(52)
    panel_h = title_h + list_top_pad + len(rows) * row_h + (12 if large else _sz(8))
    _draw_panel(draw, (margin, y0, right, y0 + panel_h), "Säsongstoppen", large=large)
    av = 30 if large else _sz(26)
    av_x = margin + (58 if large else _sz(56))
    rank_x = av_x + av + 4 + 16
    name_x = rank_x + 44
    pts_reserve = 140 if large else _sz(120)
    name_avail = right - name_x - pts_reserve
    for i, row in enumerate(rows):
        y_base = y0 + title_h + list_top_pad + i * row_h
        rank = _leaderboard_rank(row, i + 1)
        medal = GOLD if rank == 1 else SILVER if rank == 2 else BRONZE if rank == 3 else MUTED
        row_mid = y_base + row_h // 2
        _paste_user_avatar(
            base_img, av_x, row_mid, av,
            row.get("user_id"), row.get("display_name") or "?",
        )
        if large:
            rank_f = _fit_font_px(f"{rank}.", 40, bold=True, min_px=24, max_px=30)
            disp = (row.get("display_name") or "?").strip()
            disp, name_f = _fit_podium_name(disp, name_avail, min_px=26, max_px=34)
            pts_line = f"{int(row.get('points', 0)):,} p".replace(",", " ")
            pts_f = _fit_font_px(pts_line, pts_reserve, bold=True, min_px=24, max_px=32)
            line_h = max(_font_height(name_f), _font_height(rank_f))
            ty = row_mid - line_h // 2
            draw.text((rank_x, ty), f"{rank}.", font=rank_f, fill=medal)
            draw.text((name_x, ty), disp, font=name_f, fill=WHITE)
            draw.text((right - 8, ty), pts_line, font=pts_f, fill=CYAN, anchor="rt")
        else:
            bf = _load_font(26)
            bf_b = _load_font(26, bold=True)
            ty = y_base + _sz(14)
            draw.text((rank_x, ty), f"{rank}.", font=bf_b, fill=medal)
            draw.text(
                (name_x, ty),
                _short_user_name(row.get("display_name") or "?"),
                font=bf,
                fill=WHITE,
            )
            draw.text(
                (right, ty),
                f"{int(row.get('points', 0)):,} p".replace(",", " "),
                font=bf_b,
                fill=CYAN,
                anchor="rt",
            )
        if i < len(rows) - 1:
            draw.line(
                [(margin + _sz(24), y_base + row_h - 2), (right - _sz(24), y_base + row_h - 2)],
                fill=PANEL_EDGE,
                width=1,
            )
    return y0 + panel_h


def _draw_fact_cards(
    draw,
    y0: int,
    facts: list[dict],
    data: dict[str, Any],
    *,
    img_width: int | None = None,
    compact: bool = False,
    large: bool = False,
) -> int:
    shown = [f for f in facts if f.get("text")][:3]
    if not shown:
        return y0
    cw = img_width or W_PORTRAIT
    gap = 12 if large else (_sz(8) if compact else _sz(10))
    margin = 36 if large else _sz(36)
    title_h = 64 if large else _sz(52)
    box_x0 = margin + (24 if large else _sz(16))
    box_x1 = cw - margin - (24 if large else _sz(16))
    box_w = box_x1 - box_x0

    # Förberäkna radhöjd per faktum (storlek anpassas till rutebredd)
    rows: list[tuple[list[str], Any, int]] = []
    total_body = 0
    for fact in shown:
        text = fact.get("text", "")
        if large:
            inner_x = 22
            wrap_w = box_w - 2 * inner_x
            font = _fit_font_px(text, wrap_w, bold=True, min_px=38, max_px=54)
            lines = _wrap_text_width(text, font, wrap_w)
            if not lines:
                lines = [text]
            line_h = max(44, int(_font_height(font) * 1.25))
            v_pad = 32
        else:
            font = _load_font(26)
            inner_x = 16
            wrap_w = box_w - 2 * inner_x
            lines = _wrap_text_width(text, font, wrap_w)[:2]
            line_h = _sz(30)
            v_pad = 24
        card_h = max(88 if large else _sz(56), len(lines) * line_h + v_pad)
        rows.append((lines, font, card_h))
        total_body += card_h + gap

    total_h = title_h + total_body + (6 if large else 0)
    _draw_panel(draw, (margin, y0, cw - margin, y0 + total_h), "Fältet säger", large=large)
    y = y0 + title_h

    for lines, font, card_h in rows:
        inner_x = 22 if large else 16
        draw.rounded_rectangle(
            [box_x0, y, box_x1, y + card_h],
            radius=12 if large else _sz(12),
            fill=(15, 25, 45),
            outline=CYAN_DIM,
            width=1,
        )
        line_h = max(36, int(_font_height(font) * 1.2))
        block_h = len(lines) * line_h
        v_pad_draw = 18 if large else 12
        ty = y + v_pad_draw + max(0, (card_h - block_h - 2 * v_pad_draw) // 2)
        for ln in lines:
            tw = _text_width(font, ln)
            tx = box_x0 + inner_x + max(0, (box_w - 2 * inner_x - tw) // 2)
            if large:
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    draw.text((tx + dx, ty + dy), ln, font=font, fill=(0, 0, 0))
            draw.text((tx, ty), ln, font=font, fill=WHITE)
            ty += line_h
        y += card_h + gap
    return y0 + total_h


def _draw_fb_header(img, draw, data: dict[str, Any]) -> int:
    """Enkel header — stor text, inga pills."""
    cw = _canvas_w(img)
    h = 108
    race_name, race_date = _header_event_lines(data)
    draw.rectangle([0, 0, cw, 5], fill=CYAN)
    for row in range(5, h):
        t = (row - 5) / max(h - 6, 1)
        col = (
            int(12 + 8 * (1 - t)),
            int(20 + 10 * (1 - t)),
            int(40 + 12 * (1 - t)),
        )
        draw.line([(0, row), (cw, row)], fill=col)

    logo = _load_brand_logo(80)
    tx = 36
    if logo:
        img.paste(logo, (32, 18), logo)
        tx = 32 + logo.width + 20

    f_brand = _load_font_px(46, bold=True)
    f_event = _load_font_px(40, bold=True)
    draw.text((tx, 22), "MX FANTASY  ·  RACE RECAP", font=f_brand, fill=CYAN)
    sub = race_name
    if race_date:
        sub = f"{race_name}  ·  {race_date}"
    draw.text((tx, 64), sub, font=f_event, fill=WHITE)
    draw.line([(0, h - 1), (cw, h - 1)], fill=CYAN_DIM, width=2)
    return h


def _draw_fb_rider_class(
    draw,
    base_img,
    x0: int,
    y0: int,
    width: int,
    height: int,
    title: str,
    podium: list[dict],
) -> None:
    """Topp 3 som stor lista — inga podieblock."""
    x1 = x0 + width
    y1 = y0 + height
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=PANEL, outline=PANEL_EDGE, width=2)
    draw.text((x0 + 18, y0 + 14), title.upper(), font=_load_font_px(30, bold=True), fill=CYAN)

    by_pos = {int(p["position"]): p for p in podium}
    medals = {1: GOLD, 2: SILVER, 3: BRONZE}
    row_top = y0 + 52
    row_h = (height - 58) // 3
    f_rank = _load_font_px(32, bold=True)
    f_name = _load_font_px(34, bold=True)
    f_num = _load_font_px(28)

    for i, pos in enumerate((1, 2, 3)):
        ry = row_top + i * row_h + row_h // 2
        entry = by_pos.get(pos)
        col = medals[pos]
        draw.text((x0 + 22, ry), f"P{pos}", font=f_rank, fill=col, anchor="lm")
        if not entry:
            continue
        _paste_circle_avatar(
            base_img,
            x0 + 100,
            ry,
            38,
            entry.get("rider_id"),
            str(entry.get("number") or (entry.get("short_name") or "?")[:1]),
        )
        name = entry.get("short_name") or "?"
        draw.text((x0 + 155, ry), name, font=f_name, fill=WHITE, anchor="lm")
        num = entry.get("number")
        if num:
            draw.text((x1 - 22, ry), f"#{num}", font=f_num, fill=MUTED, anchor="rm")


def _draw_fb_fantasy_top3(
    draw,
    base_img,
    x0: int,
    y0: int,
    width: int,
    height: int,
    leaderboard: list[dict],
) -> None:
    x1 = x0 + width
    y1 = y0 + height
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=PANEL, outline=PANEL_EDGE, width=2)
    draw.text(
        (x0 + 18, y0 + 14),
        "FANTASY — DENNA TÄVLING",
        font=_load_font_px(30, bold=True),
        fill=CYAN,
    )

    top3 = sorted(
        [r for r in leaderboard if _leaderboard_rank(r) <= 3],
        key=_leaderboard_rank,
    )
    col_w = width // 3
    medals = {1: GOLD, 2: SILVER, 3: BRONZE}
    f_rank = _load_font_px(36, bold=True)
    f_name = _load_font_px(32, bold=True)
    f_pts = _load_font_px(30, bold=True)

    for ci, row in enumerate(top3):
        rank = _leaderboard_rank(row, ci + 1)
        cx = x0 + col_w * ci + col_w // 2
        cy = y0 + height // 2 + 8
        _paste_user_avatar(
            base_img, cx, cy - 50, 44, row.get("user_id"), row.get("display_name") or "?"
        )
        draw.text((cx, cy + 8), str(rank), font=f_rank, fill=medals.get(rank, MUTED), anchor="mt")
        draw.text(
            (cx, cy + 44),
            _short_user_name(row.get("display_name") or "?"),
            font=f_name,
            fill=WHITE,
            anchor="mt",
        )
        draw.text(
            (cx, cy + 78),
            f"{int(row.get('points', 0))} p",
            font=f_pts,
            fill=CYAN,
            anchor="mt",
        )


def _draw_fb_season_strip(
    draw,
    base_img,
    x0: int,
    y0: int,
    width: int,
    height: int,
    rows: list[dict],
) -> None:
    x1 = x0 + width
    y1 = y0 + height
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=PANEL, outline=PANEL_EDGE, width=2)
    draw.text((x0 + 18, y0 + 12), "SÄSONGSTOPPEN", font=_load_font_px(28, bold=True), fill=CYAN)
    shown = rows[:5]
    if not shown:
        return
    col_w = width // len(shown)
    f_name = _load_font_px(26, bold=True)
    f_pts = _load_font_px(24, bold=True)
    cy = y0 + height // 2 + 10
    for i, row in enumerate(shown):
        rank = _leaderboard_rank(row, i + 1)
        cx = x0 + col_w * i + col_w // 2
        medal = GOLD if rank == 1 else SILVER if rank == 2 else BRONZE if rank == 3 else MUTED
        _paste_user_avatar(
            base_img, cx, cy - 42, 32, row.get("user_id"), row.get("display_name") or "?"
        )
        draw.text((cx, cy + 2), f"{rank}.", font=f_name, fill=medal, anchor="mt")
        draw.text(
            (cx, cy + 30),
            _short_user_name(row.get("display_name") or "?")[:14],
            font=f_name,
            fill=WHITE,
            anchor="mt",
        )
        draw.text(
            (cx, cy + 58),
            f"{int(row.get('points', 0)):,}".replace(",", " "),
            font=f_pts,
            fill=CYAN,
            anchor="mt",
        )


RECAP_TEMPLATE_GRAPHIC = _ROOT / "static" / "recap_templates" / "recap_fb_graphic.png"
RECAP_TEMPLATE_STATS = _ROOT / "static" / "recap_templates" / "recap_fb_stats.png"
RECAP_SLOTS_JSON = _ROOT / "static" / "recap_templates" / "slots.json"
def _recap_templates_ready() -> bool:
    return (
        RECAP_TEMPLATE_GRAPHIC.is_file()
        and RECAP_TEMPLATE_STATS.is_file()
        and RECAP_SLOTS_JSON.is_file()
    )


def _load_recap_slots() -> dict[str, Any]:
    with open(RECAP_SLOTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _recap_is_grey_pixel(r: int, g: int, b: int) -> bool:
    return 88 < r < 178 and abs(r - g) < 24 and abs(g - b) < 24


def _recap_grey_circle_in_region(
    px, x0: int, x1: int, y0: int, y1: int,
) -> dict[str, int] | None:
    """Hitta grå avatar-cirkel i en avgränsad panelkolumn."""
    import math

    pts = [
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if _recap_is_grey_pixel(*px[x, y])
    ]
    if len(pts) < 400:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # Medelpunkt av grå pixlar — bbox-centrum dras ned av pallblock som klipper cirkeln.
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    dists = sorted(math.hypot(x - cx, y - cy) for x, y in pts)
    r = dists[int(len(dists) * 0.92)]
    return {"cx": int(round(cx)), "cy": int(round(cy)), "r": int(round(r))}


def _recap_name_box_at_column(px, col_cx: int, *, y0: int, y1: int, margin: int = 125) -> dict[str, int] | None:
    """Hitta mörk namnplatta centrerad under en pallkolumn."""
    best: dict[str, int] | None = None
    for y in range(y0, y1):
        spans: list[tuple[int, int]] = []
        start: int | None = None
        for x in range(col_cx - margin, col_cx + margin):
            if px[x, y][0] < 70:
                if start is None:
                    start = x
            elif start is not None:
                if x - start >= 50:
                    spans.append((start, x - 1))
                start = None
        if start is not None and col_cx + margin - start >= 50:
            spans.append((start, col_cx + margin - 1))
        for a, b in spans:
            cx = (a + b) // 2
            if abs(cx - col_cx) > 55:
                continue
            width = b - a
            if width < 60:
                continue
            cand = {"x0": a, "x1": b, "y0": y - 3, "y1": y + 22}
            if best is None or width > (best["x1"] - best["x0"]):
                best = cand
    return best


# ~8 px ≈ 1 mm i 2190-mallen (används i finjusteringar nedan).
_RECAP_MM = 8

# Veckans prestationer — per kort (IB, AN, GR, holeshot).
# 1 mm på mallen ≈ _RECAP_MM (8) px; 1,5 mm ≈ 12 px.
_RECAP_STATS_WEEKLY_RING_UP = int(1.5 * _RECAP_MM)
_RECAP_STATS_WEEKLY_AVATAR_NUDGE: dict[int, tuple[int, int, int]] = {
    0: (0, -_RECAP_STATS_WEEKLY_RING_UP, 12),   # IB — upp ~1,5 mm
    1: (0, -_RECAP_STATS_WEEKLY_RING_UP, 12),   # AN
    2: (0, -_RECAP_STATS_WEEKLY_RING_UP, 12),   # GR
    3: (0, -1 * _RECAP_MM, 12),                 # holeshot — upp ~1 mm
}
_RECAP_STATS_WEEKLY_TEXT_DX = 4 * _RECAP_MM       # namn/detalj ~4 mm höger
_RECAP_STATS_WEEKLY_DETAIL_DY = 5 * _RECAP_MM     # förklaringstext ner ~5 mm
_RECAP_STATS_WEEKLY_DETAIL_NUDGE: dict[int, tuple[int, int]] = {
    0: (-1 * _RECAP_MM, 0),       # IB — förklaring ~1 mm vänster
}
# Säsongstoppen — poängruta + avatar.
_RECAP_STATS_SEASON_POINTS_SHIFT = -20 * _RECAP_MM  # 2 cm vänster
_RECAP_STATS_SEASON_AVATAR_DY = -1 * _RECAP_MM       # initialer upp ~1 mm

# Finjustering per pall / fantasy-plats: (dx, dy, dr) i px på 2190-mallen.
_RECAP_AVATAR_NUDGE: dict[tuple[str, int], tuple[int, int, int]] = {
    ("rider_450", 1): (0, -2, 0),    # Hunter — upp ~1 mm
    ("rider_450", 2): (0, 22, 0),    # JP — ner ~1 mm
    ("rider_450", 3): (4, 19, 1),    # Jett — perfekt
    ("rider_250", 1): (0, 0, 0),     # SH — upp ~1 mm
    ("rider_250", 2): (0, 20, 0),    # C. Dudney — ner ~1 mm
    ("rider_250", 3): (0, 28, 0),    # C. Davies — ner ~2 mm
    ("fantasy", 1): (0, 42, -18),    # KA — ner ~1 mm
    ("fantasy", 2): (_RECAP_MM, 40, -18),   # GR — ner + höger ~1 mm
    ("fantasy", 3): (_RECAP_MM, 44, -18),   # IB — ner + höger ~1 mm
}

# Plats 4/5 — separata rader i höger ruta (2190-mall).
_RECAP_FANTASY_EXTRAS = [
    {
        "rank": 4,
        "avatar": {"cx": 1215, "cy": 1195, "r": 26},
        "name_pts": {"x0": 1255, "y0": 1178, "x1": 2095, "y1": 1198},
    },
    {
        "rank": 5,
        "avatar": {"cx": 1215, "cy": 1345, "r": 26},
        "name_pts": {"x0": 1255, "y0": 1327, "x1": 2095, "y1": 1359},
    },
]

# Klassrubrik — vit text ca y 250–278; sudda endast textbandet.
_RECAP_CLASS_TITLE_BOXES = {
    "primary": {"x0": 458, "y0": 248, "x1": 732, "y1": 280},
    "secondary": {"x0": 1528, "y0": 248, "x1": 1802, "y1": 280},
}
_RECAP_CLASS_HEADER_RESTORE = {
    "primary": {"x0": 458, "x1": 732, "ref_x": 380},
    "secondary": {"x0": 1528, "x1": 1802, "ref_x": 1450},
}
# Gemini-artefakter i fantasy-panelen (hörn).
_RECAP_ARTIFACT_INPAINT = [
    {"x0": 2032, "y0": 1000, "x1": 2125, "y1": 1072},
    {"x0": 2040, "y0": 1290, "x1": 2155, "y1": 1375},
]
RECAP_RENDERER_REV = "30"

# Pallnamn (#96 H. Lawrence …) — ned i namnplattan (~0,5 cm).
_RECAP_RIDER_NAME_Y_SHIFT = 40


def _recap_detect_dark_row(px, x0: int, x1: int, y0: int, y1: int) -> tuple[int, int] | None:
    """Vertikal mittpunkt för en mörk listrad (fantasy plats 4/5)."""
    best_y = -1
    best_count = 0
    for y in range(y0, y1):
        count = sum(1 for x in range(x0, x1) if px[x, y][0] < 50)
        if count > best_count:
            best_count = count
            best_y = y
    if best_y < 0 or best_count < 400:
        return None
    top = y0
    bottom = y1 - 1
    for y in range(best_y, y0 - 1, -1):
        if sum(1 for x in range(x0, x1) if px[x, y][0] < 50) < best_count // 3:
            top = y + 1
            break
    for y in range(best_y, y1):
        if sum(1 for x in range(x0, x1) if px[x, y][0] < 50) < best_count // 3:
            bottom = y - 1
            break
    return top, bottom


def _detect_recap_graphic_slots_from_image(img) -> dict[str, Any]:
    """Mät avatar- och textrutor direkt från recap-mallen (2190-bild)."""
    from PIL import Image

    if img.mode != "RGB":
        img = img.convert("RGB")
    px = img.load()
    w, h = img.size

    def ring(col_cx: int, x0: int, x1: int, y0: int, y1: int) -> dict[str, int] | None:
        return _recap_grey_circle_in_region(px, x0, x1, y0, y1)

    rider_cols = [
        ("rider_450", 2, 266, 150, 380, 350, 530),
        ("rider_450", 1, 560, 450, 690, 320, 520),
        ("rider_450", 3, 851, 730, 970, 370, 530),
        ("rider_250", 2, 1336, 1220, 1450, 350, 530),
        ("rider_250", 1, 1629, 1520, 1760, 320, 520),
        ("rider_250", 3, 1924, 1800, 2040, 370, 530),
    ]
    fantasy_cols = [
        (2, 252, 150, 360, 1050, 1220),
        (1, 563, 450, 670, 1050, 1220),
        (3, 846, 730, 960, 1050, 1220),
    ]

    graphic: dict[str, Any] = {"ref_w": w, "ref_h": h, "rider_450": {"avatars": [], "names": []}, "rider_250": {"avatars": [], "names": []}, "fantasy": {"avatars": [], "names": [], "extras": []}}

    for panel, pos, col_cx, x0, x1, y0, y1 in rider_cols:
        av = ring(col_cx, x0, x1, y0, y1)
        if av:
            graphic[panel]["avatars"].append({"pos": pos, **av})
        nm = _recap_name_box_at_column(px, col_cx, y0=818, y1=852)
        if nm:
            graphic[panel]["names"].append({"pos": pos, **nm})

    for panel in ("rider_450", "rider_250"):
        avatars = graphic[panel]["avatars"]
        if avatars:
            uniform_r = max(int(a["r"]) for a in avatars)
            for a in avatars:
                a["r"] = uniform_r

    for pos, col_cx, x0, x1, y0, y1 in fantasy_cols:
        av = ring(col_cx, x0, x1, y0, y1)
        if av:
            graphic["fantasy"]["avatars"].append({"pos": pos, **av})
        nm = _recap_name_box_at_column(px, col_cx, y0=1290, y1=1338, margin=145)
        if nm:
            nm = dict(nm)
            nm["y0"] = nm.get("y0", 1300) + 10
            nm["y1"] = nm.get("y1", 1325) + 10
            graphic["fantasy"]["names"].append({"pos": pos, **nm})

    fantasy_avatars = graphic["fantasy"]["avatars"]
    if fantasy_avatars:
        uniform_r = max(int(a["r"]) for a in fantasy_avatars)
        for a in fantasy_avatars:
            a["r"] = uniform_r

    graphic["fantasy"]["extras"] = [dict(row) for row in _RECAP_FANTASY_EXTRAS]

    title_rows = [
        y
        for y in range(48, 128)
        if sum(1 for x in range(1405, 2148) if px[x, y][0] < 80) > 400
    ]
    if title_rows:
        graphic["race_title"] = {
            "x0": 1410,
            "y0": min(title_rows) + 2,
            "x1": 2145,
            "y1": max(title_rows) - 2,
        }
    brand = _recap_grey_circle_in_region(px, 30, 260, 20, 175)
    if brand and 35 <= brand["r"] <= 75:
        graphic["brand_logo"] = brand
    return graphic


def _recap_dark_subbox_in_region(
    px, x0: int, x1: int, y0: int, y1: int, *, pad: int = 8,
) -> dict[str, int] | None:
    min_x, max_x, min_y, max_y = x1, x0, y1, y0
    found = False
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y][0] < 55:
                found = True
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
    if not found or max_x - min_x < 60:
        return None
    return {
        "x0": min_x + pad,
        "y0": min_y + pad,
        "x1": max_x - pad,
        "y1": max_y - pad,
    }


def _split_recap_weekly_text_boxes(px, box: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """Dela veckokort i namn (över) och detalj (under) inom mörk textruta."""
    x0, x1, y0, y1 = box["x0"], box["x1"], box["y0"], box["y1"]
    panel_bottom = y0
    for y in range(y1, y0 - 1, -1):
        dark = sum(1 for x in range(x0, x1) if px[x, y][0] < 55)
        if dark > (x1 - x0) * 0.55:
            panel_bottom = y
            break
    y1 = max(y0 + 48, panel_bottom - 12)
    split_y = y0 + int((y1 - y0) * 0.28)
    pad_x = 8
    name = {"x0": x0 + pad_x, "y0": y0 + 4, "x1": x1 - pad_x, "y1": split_y - 2}
    detail = {"x0": x0 + pad_x, "y0": split_y + 2, "x1": x1 - pad_x, "y1": y1 - 4}
    return name, detail


def _tune_recap_stats_weekly_slot(slot: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Finjustera avatar + textrutor per veckokort."""
    dx, dy, dr = _RECAP_STATS_WEEKLY_AVATAR_NUDGE.get(index, (0, 0, 12))
    av = dict(slot["avatar"])
    av["cx"] = int(av["cx"]) + dx
    av["cy"] = int(av["cy"]) + dy
    av["r"] = min(72, int(av["r"]) + dr)
    name = dict(slot["name"])
    detail = dict(slot["detail"])
    text_dx = _RECAP_STATS_WEEKLY_TEXT_DX
    name["x0"] = int(name["x0"]) + text_dx
    name["x1"] = int(name["x1"]) + text_dx
    detail["x0"] = int(detail["x0"]) + text_dx
    detail["x1"] = int(detail["x1"]) + text_dx
    detail_dy = _RECAP_STATS_WEEKLY_DETAIL_DY
    detail_dx, detail_dy_extra = _RECAP_STATS_WEEKLY_DETAIL_NUDGE.get(index, (0, 0))
    detail["x0"] = int(detail["x0"]) + detail_dx
    detail["x1"] = int(detail["x1"]) + detail_dx
    detail["y0"] = int(detail["y0"]) + detail_dy + detail_dy_extra
    detail["y1"] = int(detail["y1"]) + detail_dy + detail_dy_extra
    return {**slot, "avatar": av, "name": name, "detail": detail}


def _tune_recap_stats_season_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Flytta poängruta + avatar innanför säsongsraden."""
    shift = _RECAP_STATS_SEASON_POINTS_SHIFT
    pts = dict(slot["points"])
    pts["x0"] = int(pts["x0"]) + shift
    pts["x1"] = int(pts["x1"]) + shift
    name_x1 = int(slot["name"]["x1"])
    pts["x0"] = max(name_x1 + 10, int(pts["x0"]))
    av = dict(slot["avatar"])
    av["cy"] = int(av["cy"]) + _RECAP_STATS_SEASON_AVATAR_DY
    return {**slot, "avatar": av, "points": pts}


def _detect_recap_stats_slots_from_image(img) -> dict[str, Any]:
    """Mät avatar- och textrutor direkt från recap-statistikmallen."""
    from PIL import Image

    if img.mode != "RGB":
        img = img.convert("RGB")
    px = img.load()
    w, h = img.size
    stats: dict[str, Any] = {"ref_w": w, "ref_h": h, "weekly": [], "season": [], "facts": []}

    weekly_regions = [
        (80, 350, 350, 550, 260, 600, 378, 518),
        (550, 1050, 350, 550, 720, 1100, 378, 518),
        (80, 350, 600, 800, 260, 600, 668, 808),
        (550, 1050, 600, 800, 720, 1100, 668, 808),
    ]
    for av_x0, av_x1, av_y0, av_y1, tx_x0, tx_x1, ty0, ty1 in weekly_regions:
        av = _recap_grey_circle_in_region(px, av_x0, av_x1, av_y0, av_y1)
        text_box = _recap_dark_subbox_in_region(px, tx_x0, tx_x1, ty0, ty1)
        if not av or not text_box:
            continue
        av = dict(av)
        av["r"] = min(int(av["r"]), 66)
        name, detail = _split_recap_weekly_text_boxes(px, text_box)
        stats["weekly"].append({"avatar": av, "name": name, "detail": detail})

    season_bands = [(330, 450), (450, 570), (570, 690), (690, 810), (810, 930)]
    for rank, (y0, y1) in enumerate(season_bands, start=1):
        av = _recap_grey_circle_in_region(px, 1080, 1285, y0, y1)
        name = _recap_dark_subbox_in_region(px, 1395, 1850, y0, y1)
        points = _recap_dark_subbox_in_region(px, 1855, 2140, y0, y1)
        if not av or not name or not points:
            continue
        av = dict(av)
        av["r"] = min(int(av["r"]), 42)
        stats["season"].append({"rank": rank, "avatar": av, "name": name, "points": points})

    fact_boxes: list[dict[str, int]] = []
    in_box = False
    start_y = 0
    for y in range(1140, 1420):
        dark = sum(1 for x in range(1270, 2080) if px[x, y][0] < 55)
        if dark > 500:
            if not in_box:
                start_y = y
                in_box = True
        elif in_box:
            if y - start_y >= 40:
                fact_boxes.append({"x0": 1280, "y0": start_y + 8, "x1": 2070, "y1": y - 8})
            in_box = False
    stats["facts"] = fact_boxes[:3]

    title_rows = [
        y
        for y in range(48, 128)
        if sum(1 for x in range(1405, 2148) if px[x, y][0] < 80) > 400
    ]
    if title_rows:
        stats["race_title"] = {
            "x0": 1410,
            "y0": min(title_rows) + 2,
            "x1": 2145,
            "y1": max(title_rows) - 2,
        }
    brand = _recap_grey_circle_in_region(px, 30, 260, 20, 175)
    if brand and 35 <= brand["r"] <= 75:
        stats["brand_logo"] = brand
    return stats


def _merge_detected_stats_slots(static: dict[str, Any], detected: dict[str, Any]) -> dict[str, Any]:
    merged = {**static, **detected}
    for key in ("weekly", "season", "facts"):
        if detected.get(key):
            merged[key] = detected[key]
    if "race_title" in detected:
        merged["race_title"] = detected["race_title"]
    if detected.get("brand_logo"):
        merged["brand_logo"] = detected["brand_logo"]
    return merged


def _recap_avatar_visual_nudge(panel: str, pos: int, slot: dict[str, int]) -> dict[str, int]:
    """Applicera manuell finjustering ovanpå mätta mallkoordinater."""
    cx, cy, r = int(slot["cx"]), int(slot["cy"]), int(slot["r"])
    dx, dy, dr = _RECAP_AVATAR_NUDGE.get((panel, pos), (0, 0, 0))
    return {"cx": cx + dx, "cy": cy + dy, "r": max(52, r + dr)}


def _shift_recap_box_y(
    box: tuple[int, int, int, int], dy: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return x0, y0 + dy, x1, y1 + dy


def _recap_class_header_label(data: dict[str, Any], key: str) -> str:
    labels = data.get("class_labels") or {}
    series = str(data.get("series") or "").upper()
    primary = str(labels.get("primary") or "450")
    secondary = str(labels.get("secondary") or "250")
    if series == "WSX":
        return str(labels.get("primary") or "SX1") if key == "primary" else str(labels.get("secondary") or "SX2")
    if series == "SX":
        base_lbl = primary if key == "primary" else secondary
        return f"{base_lbl} SX"
    return primary if key == "primary" else secondary


def _inpaint_recap_region(base, x0: int, y0: int, x1: int, y1: int, passes: int = 2) -> None:
    """Sudda små artefakter/vattenmärken med medelvärde av grannpixlar."""
    px = base.load()
    w, h = base.size
    for _ in range(passes):
        updates: list[tuple[int, int, tuple]] = []
        for y in range(max(0, y0), min(h - 1, y1) + 1):
            for x in range(max(0, x0), min(w - 1, x1) + 1):
                acc = [0, 0, 0, 0]
                n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if x0 <= nx <= x1 and y0 <= ny <= y1:
                            continue
                        if 0 <= nx < w and 0 <= ny < h:
                            p = px[nx, ny]
                            for i in range(3):
                                acc[i] += p[i]
                            acc[3] += p[3] if len(p) > 3 else 255
                            n += 1
                if n:
                    updates.append(
                        (x, y, tuple(int(acc[i] / n) for i in range(3)) + (int(acc[3] / n),))
                    )
        for x, y, color in updates:
            px[x, y] = color


def _clean_recap_template_artifacts(base) -> None:
    for spec in _RECAP_ARTIFACT_INPAINT:
        _inpaint_recap_region(base, spec["x0"], spec["y0"], spec["x1"], spec["y1"])


def recap_renderer_engine() -> str:
    return "template" if _recap_templates_ready() else "fallback"


def _recap_panel_fill_color(base, x0: int, y0: int, x1: int, y1: int) -> tuple:
    """Bakgrundsfärg precis under rubriktexten."""
    w, h = base.size
    sx = (x0 + x1) // 2
    sy = min(h - 1, y1 + 6)
    p = base.getpixel((sx, sy))
    if isinstance(p, tuple) and len(p) >= 3:
        return p[:3]
    return (21, 35, 61)


def _wipe_recap_header_text_band(base, x0: int, y0: int, x1: int, y1: int) -> None:
    """Sudda rubriktext rad för rad så panelgradienten bevaras ovanför texten."""
    px = base.load()
    w, h = base.size
    ref_l = max(0, x0 - 24)
    ref_r = min(w - 1, x1 + 24)
    for y in range(max(0, y0), min(h, y1 + 1)):
        left = px[ref_l, y][:3]
        right = px[ref_r, y][:3]
        for x in range(max(0, x0), min(w, x1 + 1)):
            t = (x - x0) / max(1, x1 - x0)
            px[x, y] = (
                int(left[0] * (1 - t) + right[0] * t),
                int(left[1] * (1 - t) + right[1] * t),
                int(left[2] * (1 - t) + right[2] * t),
                px[x, y][3] if len(px[x, y]) > 3 else 255,
            )


def _draw_recap_class_headers(
    draw,
    base,
    data: dict[str, Any],
    ref_w: int,
    ref_h: int,
    out_w: int,
    out_h: int,
) -> None:
    """Sudda inbakad malltext och rita rätt klassnamn (MX/SX/WSX)."""
    for key in ("primary", "secondary"):
        box = _scale_recap_box(_RECAP_CLASS_TITLE_BOXES[key], ref_w, ref_h, out_w, out_h)
        x0, y0, x1, y1 = box
        _wipe_recap_header_text_band(base, x0, y0, x1, y1)
        text = _recap_class_header_label(data, key)
        _draw_text_in_box(draw, box, text, bold=True, max_px=46, min_px=24, fill=WHITE)


def _merge_detected_graphic_slots(static: dict[str, Any], detected: dict[str, Any]) -> dict[str, Any]:
    """Statisk slots.json + mätta koordinater från aktuell PNG-mall."""
    merged = {**static, **detected}
    for key in ("rider_450", "rider_250", "fantasy"):
        if key in detected:
            merged[key] = detected[key]
    if "race_title" in detected:
        merged["race_title"] = detected["race_title"]
    if detected.get("brand_logo"):
        merged["brand_logo"] = detected["brand_logo"]
    return merged


def _scale_recap_coord(
    value: float, ref: int, out: int,
) -> int:
    return int(round(value * out / ref))


def _scale_recap_box(
    box: dict[str, int], ref_w: int, ref_h: int, out_w: int, out_h: int,
) -> tuple[int, int, int, int]:
    return (
        _scale_recap_coord(box["x0"], ref_w, out_w),
        _scale_recap_coord(box["y0"], ref_h, out_h),
        _scale_recap_coord(box["x1"], ref_w, out_w),
        _scale_recap_coord(box["y1"], ref_h, out_h),
    )


def _scale_recap_circle(
    slot: dict[str, int], ref_w: int, ref_h: int, out_w: int, out_h: int,
) -> tuple[int, int, int]:
    return (
        _scale_recap_coord(slot["cx"], ref_w, out_w),
        _scale_recap_coord(slot["cy"], ref_h, out_h),
        max(8, _scale_recap_coord(slot["r"], ref_w, out_w)),
    )


def _cover_crop_square(img, size: int, *, face_bias: float = 0.1):
    """Fyll en kvadrat (cover) — porträtt zoomas in istället för letterbox."""
    from PIL import Image

    w, h = img.size
    if w < 1 or h < 1:
        return img
    scale = max(size / w, size / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - size) // 2)
    top = max(0, (nh - size) // 2 - int(size * face_bias))
    left = min(left, max(0, nw - size))
    top = min(top, max(0, nh - size))
    return img.crop((left, top, left + size, top + size))


def _paste_plain_circle_avatar(
    base,
    cx: int,
    cy: int,
    radius: int,
    *,
    rider_id: int | None = None,
    user_id: int | None = None,
    display_name: str = "?",
    initials: str = "?",
    face_bias: float = 0.1,
) -> None:
    """Cirkulär avatar utan ring — mallen har redan ram."""
    from PIL import Image, ImageDraw

    d = radius * 2
    inner = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    thumb = None
    if rider_id:
        thumb = _load_rider_thumb(int(rider_id), d * 2)
    elif user_id:
        thumb = _load_user_profile_image(int(user_id), d * 2)
    if thumb is None:
        thumb = _make_initials_avatar(display_name or initials, int(user_id or rider_id or 0), d)
    else:
        thumb = _cover_crop_square(thumb.convert("RGBA"), d, face_bias=face_bias)

    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d - 1, d - 1], fill=255)
    ox = (d - thumb.width) // 2
    oy = (d - thumb.height) // 2
    inner.paste(thumb, (ox, oy), thumb if thumb.mode == "RGBA" else None)
    inner.putalpha(mask)
    base.paste(inner, (cx - radius, cy - radius), inner)


def _draw_recap_name_in_box(
    draw,
    box: tuple[int, int, int, int],
    name: str,
    *,
    max_px: int = 24,
    min_px: int = 14,
    pad_x: int = 4,
    pad_y: int = 2,
) -> None:
    """Kort namn (Förnamn E.) som ryms i recap-ruta."""
    x0, y0, x1, y1 = box
    w = max(10, x1 - x0)
    text, font = _fit_podium_name(
        _short_recap_display_name(name), w - pad_x * 2, min_px=min_px, max_px=max_px,
    )
    draw.text((x0 + pad_x, y0 + pad_y), text, font=font, fill=WHITE, anchor="lt")


def _draw_text_in_box(
    draw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    bold: bool = True,
    fill=WHITE,
    align: str = "center",
    max_px: int = 34,
    min_px: int = 18,
    pad_x: int = 8,
    pad_y: int = 0,
    valign: str = "center",
) -> None:
    x0, y0, x1, y1 = box
    w = max(10, x1 - x0)
    h = max(10, y1 - y0)
    text = (text or "").strip() or "—"
    font = _fit_font_px(text, w - pad_x * 2, bold=bold, min_px=min_px, max_px=max_px)
    if valign == "top":
        if align == "right":
            x, anchor = x1 - pad_x, "rt"
        elif align == "center":
            x, anchor = x0 + w // 2, "mt"
        else:
            x, anchor = x0 + pad_x, "lt"
        draw.text((x, y0 + pad_y), text, font=font, fill=fill, anchor=anchor)
        return
    try:
        ascent, descent = font.getmetrics()
        cy = y0 + (h + ascent - descent) // 2 + pad_y
    except Exception:
        cy = y0 + h // 2 + pad_y
    if align == "left":
        x = x0 + pad_x
        anchor = "lm"
    elif align == "right":
        x = x1 - pad_x
        anchor = "rm"
    else:
        x = x0 + w // 2
        anchor = "mm"
    draw.text((x, cy), text, font=font, fill=fill, anchor=anchor)


def _wrap_text_lines(text: str, font, max_width: int, *, max_lines: int = 2) -> list[str]:
    words = (text or "").strip().split()
    if not words:
        return ["—"]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(font, trial) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        last = lines[-1]
        while last and _text_width(font, last + "…") > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + "…") if last else "…"
    return lines


def _draw_text_wrapped_in_box(
    draw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    bold: bool = False,
    fill=WHITE,
    align: str = "left",
    max_px: int = 26,
    min_px: int = 14,
    max_lines: int = 2,
    pad_x: int = 12,
    pad_y: int | None = None,
) -> None:
    x0, y0, x1, y1 = box
    w = max(10, x1 - x0)
    h = max(10, y1 - y0)
    text = (text or "").strip() or "—"
    max_w = w - pad_x * 2
    font = None
    lines: list[str] = []
    for px in range(max_px, min_px - 1, -1):
        trial = _load_font_px(px, bold=bold)
        trial_lines = _wrap_text_lines(text, trial, max_w, max_lines=max_lines)
        if all(_text_width(trial, line) <= max_w for line in trial_lines):
            font = trial
            lines = trial_lines
            break
    if font is None:
        font = _load_font_px(min_px, bold=bold)
        lines = _wrap_text_lines(text, font, max_w, max_lines=max_lines)
    line_h = _font_height(font)
    gap = 4
    total_h = len(lines) * line_h + max(0, len(lines) - 1) * gap
    y = y0 + (pad_y if pad_y is not None else max(0, (h - total_h) // 2))
    for line in lines:
        if align == "right":
            x, anchor = x1 - pad_x, "ra"
        elif align == "center":
            x, anchor = x0 + w // 2, "ma"
        else:
            x, anchor = x0 + pad_x, "la"
        draw.text((x, y), line, font=font, fill=fill, anchor=anchor)
        y += line_h + gap


def _short_weekly_detail(detail: str, max_len: int = 44) -> str:
    s = (detail or "").strip()
    s = s.replace(" i veckan", " i vk.").replace(" denna vecka", " denna vk.")
    s = s.replace(" platser", " pl.")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _weekly_detail_recap_lines(detail: str) -> tuple[str, str]:
    """Dela veckodetalj på två rader (klättring / poäng eller fullträffar / vecka)."""
    s = (detail or "").strip()
    if not s:
        return "—", ""
    if " · " in s:
        line1, line2 = s.split(" · ", 1)
        line1 = line1.replace("platser", "pl.").strip()
        line2 = (
            line2.replace(" i veckan", " denna vecka")
            .replace(" i vk.", " denna vecka")
            .strip()
        )
        return line1, line2
    if " denna vecka" in s:
        head, tail = s.split(" denna vecka", 1)
        return head.strip(), "denna vecka"
    if " holeshot-poäng" in s:
        head, tail = s.split(" holeshot-poäng", 1)
        return head.strip(), f"holeshot-poäng{tail.replace(' i veckan', ' denna vecka')}".strip()
    return _short_weekly_detail(s, max_len=36), ""


def _weekly_detail_line1_fill(line1: str):
    """Grön pil upp, röd pil ner — annars dämpad text."""
    s = (line1 or "").strip()
    if s.startswith("↑"):
        return GREEN
    if s.startswith("↓"):
        return RED
    return MUTED


def _draw_weekly_detail_in_box(
    draw,
    box: tuple[int, int, int, int],
    line1: str,
    line2: str,
    *,
    line1_max_px: int = 20,
    line2_max_px: int = 18,
    valign: str = "top",
    pad_y: int = 0,
) -> None:
    """Veckodetalj: rad 1 med färgad pil, rad 2 dämpad."""
    x0, y0, x1, y1 = box
    w = max(10, x1 - x0)
    h = max(10, y1 - y0)
    gap = 4
    line1 = (line1 or "—").strip()
    line2 = (line2 or "").strip()
    f1 = _fit_font_px(line1, w - 12, bold=True, min_px=13, max_px=line1_max_px)
    f2 = _fit_font_px(line2, w - 12, bold=False, min_px=11, max_px=line2_max_px) if line2 else None
    h1 = _font_height(f1)
    h2 = _font_height(f2) if f2 else 0
    total = h1 + (gap + h2 if line2 else 0)
    y = y0 + pad_y if valign == "top" else y0 + (h - total) // 2
    x = x0 + 8
    draw.text((x, y), line1, font=f1, fill=_weekly_detail_line1_fill(line1), anchor="lt")
    if line2 and f2:
        draw.text((x, y + h1 + gap), line2, font=f2, fill=MUTED, anchor="lt")


def _draw_text_lines_in_box(
    draw,
    box: tuple[int, int, int, int],
    line1: str,
    line2: str,
    *,
    line1_fill=WHITE,
    line2_fill=MUTED,
    line1_bold: bool = True,
    line1_max_px: int = 28,
    line2_max_px: int = 22,
    valign: str = "center",
    pad_y: int = 0,
) -> None:
    x0, y0, x1, y1 = box
    w = max(10, x1 - x0)
    h = max(10, y1 - y0)
    gap = 4
    line1 = (line1 or "—").strip()
    line2 = (line2 or "").strip()
    f1 = _fit_font_px(line1, w - 12, bold=line1_bold, min_px=13, max_px=line1_max_px)
    f2 = _fit_font_px(line2, w - 12, bold=False, min_px=11, max_px=line2_max_px) if line2 else None
    h1 = _font_height(f1)
    h2 = _font_height(f2) if f2 else 0
    total = h1 + (gap + h2 if line2 else 0)
    y = y0 + pad_y if valign == "top" else y0 + (h - total) // 2
    x = x0 + 8
    draw.text((x, y), line1, font=f1, fill=line1_fill, anchor="lt")
    if line2 and f2:
        draw.text((x, y + h1 + gap), line2, font=f2, fill=line2_fill, anchor="lt")


def _recap_race_title_text(data: dict[str, Any]) -> str:
    name = (data.get("competition_name") or "Race").strip()
    raw_date = data.get("event_date")
    if raw_date:
        try:
            from datetime import datetime

            if isinstance(raw_date, str):
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            else:
                dt = raw_date
            date_s = dt.strftime("%d %b %Y")
            return f"{name} · {date_s}"
        except Exception:
            pass
    return name


def _podium_entry_by_pos(podium: list[dict], pos: int) -> dict | None:
    for p in podium or []:
        if int(p.get("position", 0)) == pos:
            return p
    return None


def _leaderboard_by_rank(rows: list[dict], rank: int) -> dict | None:
    for r in rows or []:
        if _leaderboard_rank(r) == rank:
            return r
    return None


def _resize_recap_template(img, out_w: int) -> Any:
    from PIL import Image

    tw, th = img.size
    out_h = max(1, int(round(th * out_w / tw)))
    return img.resize((out_w, out_h), Image.Resampling.LANCZOS)


def _render_recap_graphic_from_template(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    static_slots = _load_recap_slots()["graphic"]
    base = Image.open(RECAP_TEMPLATE_GRAPHIC).convert("RGBA")
    out_w, out_h = base.size
    _clean_recap_template_artifacts(base)
    try:
        detected = _detect_recap_graphic_slots_from_image(base)
        slots = _merge_detected_graphic_slots(static_slots, detected)
    except Exception as exc:
        print(f"recap slot detect fallback: {exc}")
        slots = static_slots
    ref_w, ref_h = int(slots.get("ref_w", out_w)), int(slots.get("ref_h", out_h))
    draw = ImageDraw.Draw(base)
    mods = data.get("modules") or {}

    brand_logo = slots.get("brand_logo")
    if brand_logo:
        _paste_recap_brand_logo_in_circle(base, brand_logo, ref_w, ref_h, out_w, out_h)

    title_box = _scale_recap_box(slots["race_title"], ref_w, ref_h, out_w, out_h)
    _draw_text_in_box(draw, title_box, _recap_race_title_text(data), max_px=32, min_px=20, pad_y=1)
    _draw_recap_class_headers(draw, base, data, ref_w, ref_h, out_w, out_h)

    if mods.get("rider_podium") and data.get("has_results"):
        for key, podium_key in (("rider_450", "rider_podium_primary"), ("rider_250", "rider_podium_secondary")):
            panel = slots[key]
            podium = data.get(podium_key) or []
            for av in panel["avatars"]:
                pos = int(av["pos"])
                entry = _podium_entry_by_pos(podium, pos)
                tuned = _recap_avatar_visual_nudge(key, pos, av)
                cx, cy, r = _scale_recap_circle(tuned, ref_w, ref_h, out_w, out_h)
                if entry:
                    _paste_plain_circle_avatar(
                        base, cx, cy, r,
                        rider_id=entry.get("rider_id"),
                        display_name=entry.get("name") or "?",
                        initials=(entry.get("short_name") or "?")[:2],
                        face_bias=0.05,
                    )
            name_slots = {int(n["pos"]): n for n in panel.get("names") or []}
            for av in panel["avatars"]:
                pos = int(av["pos"])
                entry = _podium_entry_by_pos(podium, pos)
                if not entry:
                    continue
                label = entry.get("short_name") or entry.get("name") or "—"
                if entry.get("number"):
                    label = f"#{entry['number']} {label}"
                nm = name_slots.get(pos)
                if nm:
                    box = _scale_recap_box(nm, ref_w, ref_h, out_w, out_h)
                    dy = _scale_recap_coord(_RECAP_RIDER_NAME_Y_SHIFT, ref_h, out_h)
                    box = _shift_recap_box_y(box, dy)
                else:
                    cx, cy, r = _scale_recap_circle(av, ref_w, ref_h, out_w, out_h)
                    below = int(panel.get("name_below_avatar", 228))
                    half_w = int(panel.get("name_half_w", 96))
                    h = int(panel.get("name_box_h", 72))
                    y0 = cy + r + _scale_recap_coord(below, ref_h, out_h)
                    hw = _scale_recap_coord(half_w, ref_w, out_w)
                    hh = _scale_recap_coord(h, ref_h, out_h)
                    box = (cx - hw, y0, cx + hw, y0 + hh)
                _draw_text_in_box(
                    draw, box, label,
                    max_px=22, min_px=12, pad_x=4, fill=WHITE,
                )

    if mods.get("race") and data.get("race_leaderboard"):
        lb = data["race_leaderboard"]
        fantasy = slots["fantasy"]
        f_name_slots = {int(n["pos"]): n for n in fantasy.get("names") or []}
        for av in fantasy["avatars"]:
            pos = int(av["pos"])
            row = _leaderboard_by_rank(lb, pos)
            tuned = _recap_avatar_visual_nudge("fantasy", pos, av)
            cx, cy, r = _scale_recap_circle(tuned, ref_w, ref_h, out_w, out_h)
            if row:
                _paste_plain_circle_avatar(
                    base, cx, cy, r,
                    user_id=row.get("user_id"),
                    display_name=row.get("display_name") or "?",
                )
                nm = f_name_slots.get(pos)
                if nm:
                    box = _scale_recap_box(nm, ref_w, ref_h, out_w, out_h)
                    _draw_text_in_box(
                        draw, box,
                        _short_user_name(row.get("display_name") or "?"),
                        max_px=24, min_px=13, fill=WHITE,
                    )
        for extra in fantasy["extras"]:
            rank = int(extra["rank"])
            row = _leaderboard_by_rank(lb, rank)
            if not row:
                continue
            cx, cy, r = _scale_recap_circle(extra["avatar"], ref_w, ref_h, out_w, out_h)
            _paste_plain_circle_avatar(
                base, cx, cy, r,
                user_id=row.get("user_id"),
                display_name=row.get("display_name") or "?",
            )
            box = _scale_recap_box(extra["name_pts"], ref_w, ref_h, out_w, out_h)
            pts = int(row.get("points", 0))
            line = f"{rank}. {_short_user_name(row.get('display_name') or '?')}"
            _draw_text_in_box(
                draw, box, f"{line}  ·  {pts} p",
                align="left", max_px=28, min_px=16, fill=WHITE, pad_y=1,
            )

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_recap_stats_from_template(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    static_slots = _load_recap_slots()["stats"]
    base_src = Image.open(RECAP_TEMPLATE_STATS).convert("RGBA")
    try:
        detected = _detect_recap_stats_slots_from_image(base_src)
        slots = _merge_detected_stats_slots(static_slots, detected)
    except Exception as exc:
        print(f"recap stats slot detect fallback: {exc}")
        slots = static_slots
    ref_w, ref_h = int(slots.get("ref_w", base_src.size[0])), int(slots.get("ref_h", base_src.size[1]))
    base = _resize_recap_template(base_src, W_FB)
    out_w, out_h = base.size
    draw = ImageDraw.Draw(base)
    mods = data.get("modules") or {}

    brand_logo = slots.get("brand_logo")
    if brand_logo:
        _paste_recap_brand_logo_in_circle(base, brand_logo, ref_w, ref_h, out_w, out_h)

    title_box = _scale_recap_box(slots["race_title"], ref_w, ref_h, out_w, out_h)
    _draw_text_in_box(draw, title_box, _recap_race_title_text(data), max_px=32, min_px=20)

    if mods.get("weekly"):
        cards = (data.get("weekly_highlights") or [])[:4]
        for i, slot in enumerate(slots["weekly"]):
            if i >= len(cards):
                break
            card = cards[i]
            slot = _tune_recap_stats_weekly_slot(slot, i)
            cx, cy, r = _scale_recap_circle(slot["avatar"], ref_w, ref_h, out_w, out_h)
            _paste_plain_circle_avatar(
                base, cx, cy, r,
                user_id=card.get("user_id"),
                display_name=card.get("display_name") or "?",
            )
            name_box = _scale_recap_box(slot["name"], ref_w, ref_h, out_w, out_h)
            detail_box = _scale_recap_box(slot["detail"], ref_w, ref_h, out_w, out_h)
            _draw_recap_name_in_box(
                draw, name_box, card.get("display_name") or "?",
                max_px=24, min_px=14, pad_x=4, pad_y=2,
            )
            d1, d2 = _weekly_detail_recap_lines(card.get("detail") or "")
            _draw_weekly_detail_in_box(
                draw, detail_box, d1, d2,
                line1_max_px=20, line2_max_px=18,
                valign="top", pad_y=6,
            )

    if mods.get("season_snippet"):
        rows = (data.get("season_top_snippet") or [])[:5]
        for i, slot in enumerate(slots["season"]):
            if i >= len(rows):
                break
            row = rows[i]
            slot = _tune_recap_stats_season_slot(slot)
            cx, cy, r = _scale_recap_circle(slot["avatar"], ref_w, ref_h, out_w, out_h)
            _paste_plain_circle_avatar(
                base, cx, cy, r,
                user_id=row.get("user_id"),
                display_name=row.get("display_name") or "?",
            )
            name_box = _scale_recap_box(slot["name"], ref_w, ref_h, out_w, out_h)
            _draw_recap_name_in_box(
                draw, name_box, row.get("display_name") or "?",
                max_px=26, min_px=13, pad_x=8, pad_y=0,
            )
            pts_box = _scale_recap_box(slot["points"], ref_w, ref_h, out_w, out_h)
            pts_txt = f"{int(row.get('points', 0)):,}".replace(",", " ")
            _draw_text_in_box(
                draw, pts_box, pts_txt,
                align="right", max_px=24, min_px=14, fill=CYAN, pad_x=16,
            )

    if mods.get("facts"):
        facts = [f for f in (data.get("fun_facts") or []) if f.get("text")][:3]
        for i, slot in enumerate(slots["facts"]):
            if i >= len(facts):
                break
            box = _scale_recap_box(slot, ref_w, ref_h, out_w, out_h)
            _draw_text_wrapped_in_box(
                draw, box, facts[i]["text"],
                align="left", max_px=24, min_px=17, max_lines=3, pad_x=14,
            )

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


RECAP_FOOTER_HOST = "mx-fatasy-league.eu.onrender.com"


def _normalize_recap_host(host: str) -> str:
    """Rätta vanliga Render-felskrivningar (bindestreck istället för punkt före eu)."""
    h = (host or "").strip()
    if not h:
        return RECAP_FOOTER_HOST
    # t.ex. mx-fatasy-league-eu.onrender.com → mx-fatasy-league.eu.onrender.com
    if re.search(r"-eu\.onrender\.com$", h, re.I):
        h = re.sub(r"-eu\.onrender\.com$", ".eu.onrender.com", h, flags=re.I)
    return h


def _recap_footer_label() -> str:
    """Webbadress i recap-footer — EU Render (eu.onrender.com)."""
    host = ""
    for key in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        v = (os.getenv(key) or "").strip().rstrip("/")
        if v:
            host = urlparse(v).netloc or v.split("://", 1)[-1].split("/")[0]
            break
    host = _normalize_recap_host(host)
    if not host or host.lower() == "mx-fatasy-league.onrender.com":
        host = RECAP_FOOTER_HOST
    return f"{host} · Spela med oss"


def _footer(img, draw, final_h: int, *, bar_h: int = 6) -> None:
    """Sidfot för alla recap-bilder: sajt + Powered by MotoAction + cyan kant."""
    cw = _canvas_w(img)
    f_site = _load_font_px(26)
    f_pb = _load_font_px(20)
    strip_top = final_h - bar_h
    gap_above_strip = 16
    h_pb = _font_height(f_pb)
    h_site = _font_height(f_site)
    y_pb = strip_top - gap_above_strip - h_pb
    y_site = y_pb - 12 - h_site
    draw.text((cw // 2, y_site), _recap_footer_label(), font=f_site, fill=MUTED, anchor="mt")
    draw.text((cw // 2, y_pb), "Powered by MotoAction.se", font=f_pb, fill=CYAN_DIM, anchor="mt")
    draw.rectangle([0, strip_top, cw, final_h], fill=CYAN)


def _render_recap_graphic_png(data: dict[str, Any]) -> bytes:
    """Bild 1 — grafik: header, förarpall, fantasy-podium."""
    if _recap_templates_ready():
        return _render_recap_graphic_from_template(data)

    from PIL import Image, ImageDraw

    data = {**data, "layout": "facebook_graphic"}
    work_h = 1500
    img = Image.new("RGB", (W_FB, work_h), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    y = _draw_recap_header(img, draw, data) + 14
    margin = 36
    gap = 14
    half = (W_FB - margin * 2 - gap) // 2
    mods = data.get("modules") or {}
    labels = data.get("class_labels") or {}

    if mods.get("rider_podium") and data.get("has_results"):
        rp = data.get("rider_podium_primary") or []
        rs = data.get("rider_podium_secondary") or []
        ph = 400
        y1 = y2 = y
        if rp:
            y1 = _draw_rider_podium_row(
                draw, img, margin, y, half,
                _recap_class_header_label(data, "primary"), rp, panel_h=ph, large=True,
            )
        if rs:
            y2 = _draw_rider_podium_row(
                draw, img, margin + half + gap, y, half,
                _recap_class_header_label(data, "secondary"), rs, panel_h=ph, large=True,
            )
        y = max(y1, y2) + gap

    if mods.get("race") and data.get("race_leaderboard"):
        lb = data["race_leaderboard"]
        extras_n = max(0, min(2, len([r for r in lb if _leaderboard_rank(r) > 3])))
        y = _draw_user_podium_section(
            draw, img, y, "Fantasy — denna tävling", lb, data,
            max_extras=extras_n, large=True,
        ) + gap

    final_h = min(work_h, max(1180, y + 88))
    if final_h < work_h:
        img = img.crop((0, 0, W_FB, final_h))
        draw = ImageDraw.Draw(img)
    _footer(img, draw, final_h)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_recap_stats_png(data: dict[str, Any]) -> bytes:
    """Bild 2 — statistik: veckan, säsong, fältfakta."""
    if _recap_templates_ready():
        return _render_recap_stats_from_template(data)

    from PIL import Image, ImageDraw

    data = {**data, "layout": "facebook"}
    work_h = 1800
    img = Image.new("RGB", (W_FB, work_h), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    y = _draw_fb_header(img, draw, data) + 16
    margin = 36
    gap = 16
    mods = data.get("modules") or {}

    if mods.get("weekly"):
        highlights = data.get("weekly_highlights") or []
        if highlights:
            y = _draw_weekly_highlights_section(
                draw, img, y, highlights, data, large=True,
            ) + gap

    if mods.get("season_snippet") and data.get("season_top_snippet"):
        y = _draw_season_top_snippet(
            draw, img, y, data["season_top_snippet"], data, large=True,
        ) + gap

    if mods.get("facts") and data.get("fun_facts"):
        y = _draw_fact_cards(
            draw, y, data["fun_facts"], data, img_width=W_FB, large=True,
        ) + gap

    final_h = min(work_h, max(1000, y + 88))
    if final_h < work_h:
        img = img.crop((0, 0, W_FB, final_h))
        draw = ImageDraw.Draw(img)
    _footer(img, draw, final_h)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_facebook_landscape_png(data: dict[str, Any], *, part: str = "graphic") -> bytes:
    if part == "stats":
        return _render_recap_stats_png(data)
    return _render_recap_graphic_png(data)


def _render_square_recap_png(data: dict[str, Any]) -> bytes:
    """Kvadrat 1200×1200 — fyller Facebooks bildvisare (bredare = större)."""
    from PIL import Image, ImageDraw

    data = {**data, "layout": "square"}
    img = Image.new("RGB", (W_SQUARE, H_SQUARE), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    y = _draw_recap_header(img, draw, data)
    gap = _sz(8)
    margin = _sz(24)
    col_gap = _sz(10)
    half = (W_SQUARE - margin * 2 - col_gap) // 2
    mods = data.get("modules") or {}
    labels = data.get("class_labels") or {}

    if mods.get("rider_podium") and data.get("has_results"):
        rp = data.get("rider_podium_primary") or []
        rs = data.get("rider_podium_secondary") or []
        if rp or rs:
            ph = _sz(200)
            y1 = _draw_rider_podium_row(
                draw, img, margin, y, half,
                f"{labels.get('primary', '450')} SX", rp, panel_h=ph,
            )
            y2 = _draw_rider_podium_row(
                draw, img, margin + half + col_gap, y, half,
                f"{labels.get('secondary', '250')} SX", rs, panel_h=ph,
            )
            y = max(y1, y2) + gap

    if mods.get("race") and data.get("race_leaderboard"):
        y = _draw_user_podium_section(
            draw, img, y, "Fantasy — denna tävling", data["race_leaderboard"], data,
            base_panel=_sz(220), max_extras=0,
        ) + gap

    row_y = y
    row_bottom = row_y
    if mods.get("weekly"):
        highlights = data.get("weekly_highlights") or []
        if highlights:
            row_bottom = max(
                row_bottom,
                _draw_weekly_highlights_section(
                    draw, img, row_y, highlights, data,
                    x0=margin, x1=margin + half, card_h=_sz(70),
                ),
            )
    if mods.get("season_snippet") and data.get("season_top_snippet"):
        row_bottom = max(
            row_bottom,
            _draw_season_top_snippet(
                draw, img, row_y, data["season_top_snippet"], data,
                x0=margin + half + col_gap, x1=W_SQUARE - margin, row_h=_sz(46),
            ),
        )
    if row_bottom > row_y:
        y = row_bottom + gap

    if mods.get("facts") and data.get("fun_facts"):
        facts = [f for f in data["fun_facts"] if f.get("text")][:2]
        if facts:
            y = _draw_fact_cards(
                draw, y, facts, data, img_width=W_SQUARE, compact=True
            ) + gap

    _footer(img, draw, H_SQUARE, bar_h=max(5, _sz(6)))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_social_recap_png(
    data: dict[str, Any],
    *,
    layout: str | None = None,
    part: str | None = None,
) -> bytes:
    from PIL import Image, ImageDraw

    layout = (layout or data.get("layout") or "facebook").lower()
    if layout == "feed":
        layout = "facebook"
    if layout == "facebook":
        p = (part or "graphic").lower()
        if p not in ("graphic", "stats"):
            p = "graphic"
        return _render_facebook_landscape_png(data, part=p)
    if layout == "square":
        return _render_square_recap_png(data)
    if layout not in ("portrait", "story"):
        return _render_facebook_landscape_png(data)

    data = {**data, "layout": layout}
    work_h = H_WORK if layout == "portrait" else H_STORY

    img = Image.new("RGB", (W_PORTRAIT, work_h), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    y = _draw_recap_header(img, draw, data)
    gap = _section_gap(data)
    margin = _sz(36)

    mods = data.get("modules") or {}
    labels = data.get("class_labels") or {}

    if mods.get("rider_podium") and data.get("has_results"):
        rp = data.get("rider_podium_primary") or []
        rs = data.get("rider_podium_secondary") or []
        if rp or rs:
            col_gap = _sz(14)
            half = (W_PORTRAIT - margin * 2 - col_gap) // 2
            bottom_left = _draw_rider_podium_row(
                draw,
                img,
                margin,
                y,
                half,
                f"{labels.get('primary', '450')} SX",
                rp,
            )
            bottom_right = _draw_rider_podium_row(
                draw,
                img,
                margin + half + col_gap,
                y,
                half,
                f"{labels.get('secondary', '250')} SX",
                rs,
            )
            y = max(bottom_left, bottom_right) + gap

    if mods.get("race") and data.get("race_leaderboard"):
        y = _draw_user_podium_section(
            draw,
            img,
            y,
            "Fantasy — denna tävling",
            data["race_leaderboard"],
            data,
        ) + gap

    if mods.get("weekly"):
        highlights = data.get("weekly_highlights") or []
        if highlights:
            y = _draw_weekly_highlights_section(draw, img, y, highlights, data) + gap

    if mods.get("season_snippet") and data.get("season_top_snippet"):
        y = _draw_season_top_snippet(draw, img, y, data["season_top_snippet"], data) + gap

    if mods.get("facts") and data.get("fun_facts"):
        y = _draw_fact_cards(draw, y, data["fun_facts"], data) + gap

    footer_pad = _sz(74)
    content_h = y + footer_pad
    if layout == "portrait":
        final_h = min(H_WORK, max(H_FEED_MIN, content_h))
    else:
        final_h = H_STORY

    if final_h < work_h:
        img = img.crop((0, 0, W_PORTRAIT, final_h))
        draw = ImageDraw.Draw(img)

    _footer(img, draw, final_h, bar_h=max(5, _sz(6)))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
