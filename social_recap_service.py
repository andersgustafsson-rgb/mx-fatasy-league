"""Race Recap Studio — aggregat och bild/text för sociala delningar."""
from __future__ import annotations

import io
import json
from collections import defaultdict
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

# Brand colors (MX Fantasy)
BG = (15, 23, 42)
PANEL = (30, 41, 59)
CYAN = (34, 211, 238)
GOLD = (251, 191, 36)
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)
GREEN = (52, 211, 153)
RED = (248, 113, 113)

W, H = 1080, 1350


def _display_name(user: User | None, fallback: str = "?") -> str:
    if not user:
        return fallback
    return (getattr(user, "display_name", None) or user.username or fallback).strip()


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
    return rows[: max(1, limit)]


def _season_leaderboard(limit: int, include_delta: bool) -> list[dict[str, Any]]:
    from main import calculate_leaderboard_deltas

    leaderboard = calculate_leaderboard_deltas()
    out = []
    for row in leaderboard[: max(1, limit)]:
        item = {
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": row.get("display_name") or row["username"],
            "team_name": row.get("team_name"),
            "points": int(row["total_points"]),
            "rank": row["rank"],
        }
        if include_delta:
            d = int(row.get("delta") or 0)
            item["delta"] = d
            if d < 0:
                item["delta_label"] = f"↑{abs(d)}"
            elif d > 0:
                item["delta_label"] = f"↓{d}"
            else:
                item["delta_label"] = "—"
        out.append(item)
    return out


def _actual_positions(competition_id: int) -> dict[int, int]:
    """rider_id -> finish position (latest result row per rider)."""
    rows = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for res in rows:
        k = (res.competition_id, res.rider_id)
        if k not in lookup or res.result_id > lookup[k][0]:
            lookup[k] = (res.result_id, res.position)
    return {k[1]: v[1] for k, v in lookup.items()}


def _iter_pick_payloads(competition_id: int) -> list[tuple[int, dict]]:
    """All pickers with race/holeshot/wildcard data for this competition."""
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


def _compute_fun_facts(comp: Competition, competition_id: int) -> list[dict[str, str]]:
    from main import _build_crowd_picks_summary

    facts: list[dict[str, str]] = []
    crowd = _build_crowd_picks_summary(competition_id, comp, ensure_snapshots=True)
    n_lineups = int(crowd.get("n_lineups") or 0)
    n_users = int(crowd.get("n_users_with_snapshots_or_picks") or 0)
    picker_n = n_lineups or n_users
    if picker_n <= 0:
        facts.append(
            {
                "id": "no_picks",
                "text": "Inga tips inlämnade för detta race ännu.",
            }
        )
        return facts

    facts.append(
        {
            "id": "picker_count",
            "text": f"Baserat på {picker_n} spelare som lämnat tips",
        }
    )

    actual = _actual_positions(competition_id)
    riders = {r.id: r for r in Rider.query.all()}
    is_wsx = getattr(comp, "series", None) == "WSX"

    def winner_for_class(class_names: tuple[str, ...]) -> tuple[int | None, str]:
        for rid, pos in actual.items():
            if pos != 1:
                continue
            r = riders.get(rid)
            if r and (r.class_name in class_names):
                num = getattr(r, "rider_number", None)
                label = f"#{num} {r.name}" if num else r.name
                return rid, label
        return None, ""

    cls450 = ("wsx_sx1",) if is_wsx else ("450cc",)
    cls250 = ("wsx_sx2",) if is_wsx else ("250cc",)

    win450_id, win450_label = winner_for_class(cls450)
    slots450 = crowd.get("slots_450") or {}

    if win450_id and slots450.get("1"):
        top_slot = slots450["1"]
        if top_slot:
            fav = top_slot[0]
            fav_pct = fav.get("pct", 0)
            fav_name = fav.get("name") or fav.get("short", "?")
            if int(fav.get("rider_id", 0)) == win450_id:
                facts.append(
                    {
                        "id": "p1_crowd_correct",
                        "text": f"{fav_pct:.0f}% hade vinnaren {win450_label} som P1 — fältet hade rätt!",
                    }
                )
            else:
                facts.append(
                    {
                        "id": "p1_crowd_fav",
                        "text": f"Fältets P1-favorit: {fav_name} ({fav_pct:.0f}%)",
                    }
                )
                # How many had actual winner at P1?
                p1_winner_count = 0
                top3_winner_count = 0
                for _uid, payload in _iter_pick_payloads(competition_id):
                    for p in payload.get("race_picks") or []:
                        try:
                            rid = int(p.get("rider_id"))
                            pos = int(p.get("predicted_position"))
                        except (TypeError, ValueError):
                            continue
                        rider = riders.get(rid)
                        if not rider or rider.class_name not in cls450:
                            continue
                        if rid == win450_id:
                            if pos == 1:
                                p1_winner_count += 1
                            if 1 <= pos <= 3:
                                top3_winner_count += 1
                p1_pct = round(100.0 * p1_winner_count / picker_n, 0) if picker_n else 0
                top3_pct = round(100.0 * top3_winner_count / picker_n, 0) if picker_n else 0
                facts.append(
                    {
                        "id": "p1_winner_share",
                        "text": f"Bara {p1_pct:.0f}% hade {win450_label} som P1 · {top3_pct:.0f}% hade honom topp 3",
                    }
                )

    win250_id, win250_label = winner_for_class(cls250)
    slots250 = crowd.get("slots_250") or {}
    if win250_id and slots250.get("1"):
        top_slot = slots250["1"]
        if top_slot:
            fav = top_slot[0]
            if int(fav.get("rider_id", 0)) != win250_id:
                facts.append(
                    {
                        "id": "250_upset",
                        "text": f"250: vinnaren {win250_label} var inte fältets P1-favorit ({fav.get('name', '?')})",
                    }
                )

    holo450 = crowd.get("holeshot_450") or []
    if holo450:
        top_h = holo450[0]
        facts.append(
            {
                "id": "holeshot_crowd",
                "text": f"Holeshot-favorit 450: {top_h.get('name', '?')} ({top_h.get('pct', 0):.0f}%)",
            }
        )

    # Aggregate perfect picks (no names)
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
            facts.append(
                {
                    "id": "perfect_aggregate",
                    "text": f"{perfect_total} perfekta platsgissningar totalt · {pickers_with_perfect} spelare hade minst en fullträff",
                }
            )

    if not is_wsx:
        wc_top = crowd.get("wildcard_top") or []
        if wc_top:
            w = wc_top[0]
            facts.append(
                {
                    "id": "wildcard",
                    "text": f"Wildcard-favorit: P{w.get('position', '?')} {w.get('name', '?')} ({w.get('pct', 0):.0f}%)",
                }
            )

    return facts[:8]


def build_social_recap_data(
    competition_id: int,
    *,
    race_top: int = 3,
    season_top: int = 5,
    include_race: bool = True,
    include_season: bool = True,
    include_facts: bool = True,
    include_rank_delta: bool = True,
) -> dict[str, Any]:
    comp = Competition.query.get(competition_id)
    if not comp:
        raise ValueError("competition_not_found")

    has_results = (
        CompetitionResult.query.filter_by(competition_id=competition_id).first() is not None
    )

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
        "race_top": max(1, min(int(race_top), 15)),
        "season_top": max(1, min(int(season_top), 15)),
        "modules": {
            "race": include_race,
            "season": include_season,
            "facts": include_facts,
            "rank_delta": include_rank_delta,
        },
    }

    if include_race:
        data["race_leaderboard"] = _race_leaderboard(competition_id, data["race_top"])
    else:
        data["race_leaderboard"] = []

    if include_season:
        data["season_leaderboard"] = _season_leaderboard(
            data["season_top"], include_rank_delta
        )
    else:
        data["season_leaderboard"] = []

    if include_facts:
        data["fun_facts"] = _compute_fun_facts(comp, competition_id)
    else:
        data["fun_facts"] = []

    data["caption"] = build_facebook_caption(data)
    return data


def build_facebook_caption(data: dict[str, Any]) -> str:
    lines = [
        f"🏁 {data.get('event_label', 'Race')} — MX Fantasy League",
        "",
    ]

    if data.get("modules", {}).get("race") and data.get("race_leaderboard"):
        lines.append(f"🏆 Topp {len(data['race_leaderboard'])} denna tävling:")
        for row in data["race_leaderboard"]:
            lines.append(f"{row['rank']}. {row['display_name']} — {row['points']} p")
        lines.append("")

    if data.get("modules", {}).get("season") and data.get("season_leaderboard"):
        lines.append("📊 Säsongstoppen:")
        for row in data["season_leaderboard"]:
            delta = ""
            if data.get("modules", {}).get("rank_delta") and row.get("delta_label"):
                dl = row["delta_label"]
                if dl and dl != "—":
                    delta = f" ({dl})"
            lines.append(
                f"{row['rank']}. {row['display_name']} — {row['points']} p{delta}"
            )
        lines.append("")

    for fact in data.get("fun_facts") or []:
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


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_social_recap_png(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    title_font = _load_font(52, bold=True)
    head_font = _load_font(36, bold=True)
    body_font = _load_font(30)
    small_font = _load_font(24)
    medal_colors = [GOLD, (203, 213, 225), (180, 83, 9)]

    y = 48
    draw.text((W // 2, y), "MX FANTASY", font=title_font, fill=CYAN, anchor="mt")
    y += 58
    draw.text((W // 2, y), "RACE RECAP", font=head_font, fill=WHITE, anchor="mt")
    y += 50
    event = (data.get("event_label") or "Race")[:48]
    draw.text((W // 2, y), event, font=body_font, fill=MUTED, anchor="mt")
    y += 56

    def section_header(text: str):
        nonlocal y
        draw.rectangle([60, y, W - 60, y + 4], fill=CYAN)
        y += 16
        draw.text((60, y), text, font=head_font, fill=CYAN)
        y += 48

    def list_rows(rows: list[dict], show_delta: bool = False):
        nonlocal y
        for i, row in enumerate(rows):
            rank = int(row.get("rank", i + 1))
            name = (row.get("display_name") or "?")[:22]
            pts = int(row.get("points", 0))
            color = medal_colors[rank - 1] if rank <= 3 else WHITE
            draw.text((72, y), f"{rank}.", font=body_font, fill=color)
            draw.text((120, y), name, font=body_font, fill=WHITE)
            pts_x = W - 72
            if show_delta and row.get("delta_label") and row["delta_label"] != "—":
                dl = row["delta_label"]
                dcol = GREEN if dl.startswith("↑") else RED if dl.startswith("↓") else MUTED
                draw.text((pts_x - 90, y), dl, font=small_font, fill=dcol, anchor="rt")
            draw.text((pts_x, y), f"{pts} p", font=body_font, fill=CYAN, anchor="rt")
            y += 44
        y += 12

    mods = data.get("modules") or {}
    if mods.get("race") and data.get("race_leaderboard"):
        section_header(f"TOPP {len(data['race_leaderboard'])} — TÄVLING")
        list_rows(data["race_leaderboard"])

    if mods.get("season") and data.get("season_leaderboard"):
        section_header(f"TOPP {len(data['season_leaderboard'])} — SÄSONG")
        list_rows(data["season_leaderboard"], show_delta=bool(mods.get("rank_delta")))

    facts = data.get("fun_facts") or []
    if mods.get("facts") and facts:
        section_header("FÄLTET SÄGER")
        for fact in facts[:5]:
            text = fact.get("text", "")
            if len(text) > 52:
                # wrap roughly
                words = text.split()
                line = ""
                for w in words:
                    if len(line) + len(w) + 1 > 52:
                        draw.text((72, y), line, font=small_font, fill=MUTED)
                        y += 34
                        line = w
                    else:
                        line = f"{line} {w}".strip()
                if line:
                    draw.text((72, y), line, font=small_font, fill=MUTED)
                    y += 34
            else:
                draw.text((72, y), text, font=small_font, fill=MUTED)
                y += 34
        y += 8

    footer = "mxfantasy · Spela med oss"
    draw.text((W // 2, H - 48), footer, font=small_font, fill=MUTED, anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
