"""Race Recap Studio — aggregat och bild/text för sociala delningar."""
from __future__ import annotations

import base64
import io
import json
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

W, H = 1080, 1920
_ROOT = Path(__file__).resolve().parent


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
    rows = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for res in rows:
        k = (res.competition_id, res.rider_id)
        if k not in lookup or res.result_id > lookup[k][0]:
            lookup[k] = (res.result_id, res.position)
    return {k[1]: v[1] for k, v in lookup.items()}


def _rider_podium(
    competition_id: int, class_names: tuple[str, ...], limit: int = 3
) -> list[dict[str, Any]]:
    actual = _actual_positions(competition_id)
    riders = {r.id: r for r in Rider.query.all()}
    found: list[tuple[int, Rider]] = []
    for rid, pos in actual.items():
        if pos is None or pos < 1 or pos > limit:
            continue
        r = riders.get(rid)
        if r and r.class_name in class_names:
            found.append((int(pos), r))
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


def _compute_fun_facts(comp: Competition, competition_id: int) -> list[dict[str, str]]:
    from main import _build_crowd_picks_summary

    facts: list[dict[str, str]] = []
    crowd = _build_crowd_picks_summary(competition_id, comp, ensure_snapshots=True)
    n_lineups = int(crowd.get("n_lineups") or 0)
    n_users = int(crowd.get("n_users_with_snapshots_or_picks") or 0)
    picker_n = n_lineups or n_users
    if picker_n <= 0:
        facts.append({"id": "no_picks", "text": "Inga tips inlämnade för detta race ännu."})
        return facts

    facts.append({"id": "picker_count", "text": f"{picker_n} spelare lämnade tips"})

    actual = _actual_positions(competition_id)
    riders = {r.id: r for r in Rider.query.all()}
    cfg = _class_config(comp)
    cls450 = (cfg["primary"][0],)
    cls250 = (cfg["secondary"][0],)

    def winner_for_class(class_names: tuple[str, ...]) -> tuple[int | None, str]:
        for rid, pos in actual.items():
            if pos != 1:
                continue
            r = riders.get(rid)
            if r and (r.class_name in class_names):
                num = getattr(r, "rider_number", None)
                return rid, f"#{num} {r.name}" if num else r.name
        return None, ""

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
                        "text": f"{fav_pct:.0f}% hade {win450_label} som P1 — fältet hade rätt!",
                    }
                )
            else:
                facts.append(
                    {"id": "p1_crowd_fav", "text": f"Fältets P1-favorit: {fav_name} ({fav_pct:.0f}%)"}
                )
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
                        "text": f"{p1_pct:.0f}% hade {win450_label} P1 · {top3_pct:.0f}% topp 3",
                    }
                )

    win250_id, _ = winner_for_class(cls250)
    slots250 = crowd.get("slots_250") or {}
    if win250_id and slots250.get("1"):
        top_slot = slots250["1"]
        if top_slot and int(top_slot[0].get("rider_id", 0)) != win250_id:
            facts.append(
                {
                    "id": "250_upset",
                    "text": f"{cfg['secondary'][1]}: vinnaren var inte fältets P1-favorit",
                }
            )

    holo450 = crowd.get("holeshot_450") or []
    if holo450:
        top_h = holo450[0]
        facts.append(
            {
                "id": "holeshot_crowd",
                "text": f"Holeshot {cfg['primary'][1]}: {top_h.get('name', '?')} ({top_h.get('pct', 0):.0f}%)",
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
            facts.append(
                {
                    "id": "perfect_aggregate",
                    "text": f"{perfect_total} perfekta gissningar · {pickers_with_perfect} spelare med fullträff",
                }
            )

    if getattr(comp, "series", None) != "WSX":
        wc_top = crowd.get("wildcard_top") or []
        if wc_top:
            w = wc_top[0]
            facts.append(
                {
                    "id": "wildcard",
                    "text": f"Wildcard: P{w.get('position', '?')} {w.get('name', '?')} ({w.get('pct', 0):.0f}%)",
                }
            )

    return facts[:6]


def build_social_recap_data(
    competition_id: int,
    *,
    race_top: int = 3,
    season_top: int = 5,
    include_race: bool = True,
    include_season: bool = True,
    include_facts: bool = True,
    include_rank_delta: bool = True,
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
            "season": include_season,
            "facts": include_facts,
            "rank_delta": include_rank_delta,
            "rider_podium": include_rider_podium,
        },
    }

    if include_rider_podium and has_results:
        data["rider_podium_primary"] = _rider_podium(
            competition_id, (cfg["primary"][0],), limit=3
        )
        data["rider_podium_secondary"] = _rider_podium(
            competition_id, (cfg["secondary"][0],), limit=3
        )
    else:
        data["rider_podium_primary"] = []
        data["rider_podium_secondary"] = []

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

    if data.get("modules", {}).get("season") and data.get("season_leaderboard"):
        lines.append("📊 Säsong:")
        for row in data["season_leaderboard"][:5]:
            delta = ""
            if data.get("modules", {}).get("rank_delta") and row.get("delta_label"):
                dl = row["delta_label"]
                if dl and dl != "—":
                    delta = f" ({dl})"
            lines.append(f"{row['rank']}. {row['display_name']} — {row['points']} p{delta}")
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


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont

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


def _load_rider_thumb(rider_id: int, size: int = 72):
    from PIL import Image

    rider = Rider.query.get(rider_id)
    if not rider:
        return None
    raw = getattr(rider, "rider_image_data", None) or getattr(rider, "image_url", None)
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if s.startswith("data:"):
            b64 = s.split(",", 1)[-1]
            data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
        elif s.startswith("http"):
            return None
        else:
            if not s.startswith(("riders/", "uploads/", "trackmaps/")):
                s = "riders/" + s.lstrip("/")
            p = _ROOT / "static" / s.lstrip("/")
            if not p.exists():
                p = _ROOT / s.lstrip("/")
            if not p.exists():
                return None
            img = Image.open(p).convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


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
        idraw.ellipse([0, 0, radius * 2 - 1, radius * 2 - 1], fill=PANEL)
        f = _load_font(max(18, radius - 8), bold=True)
        idraw.text((radius, radius), initials[:2].upper(), font=f, fill=CYAN, anchor="mm")

    base.paste(ring, (cx - radius - 4, cy - radius - 4), ring)
    base.paste(inner, (cx - radius, cy - radius), inner)


def _draw_vertical_gradient(img) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _draw_panel(draw, xy: tuple[int, int, int, int], title: str | None = None) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=PANEL, outline=PANEL_EDGE, width=2)
    if title:
        tf = _load_font(26, bold=True)
        draw.text((x0 + 16, y0 + 12), title.upper(), font=tf, fill=CYAN)


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

    rank_f = _load_font(22, bold=True)
    draw.text((cx, y0 + 10), rank_label, font=rank_f, fill=medal_color, anchor="mt")

    if is_rider:
        num = entry.get("number")
        initials = str(num) if num else (entry.get("short_name") or "?")[:1]
        _paste_circle_avatar(base_img, cx, y0 - 36, 34, entry.get("rider_id"), initials)
        name = entry.get("short_name") or "?"
        num_s = f"#{num}" if num else ""
    else:
        initials = (entry.get("display_name") or "?")[:1]
        _paste_circle_avatar(base_img, cx, y0 - 36, 32, None, initials)
        name = _short_user_name(entry.get("display_name") or "?")
        num_s = ""

    nf = _load_font(24, bold=True)
    draw.text((cx, floor_y + 12), name, font=nf, fill=WHITE, anchor="mt")
    if num_s and is_rider:
        draw.text((cx, floor_y + 40), num_s, font=_load_font(20), fill=MUTED, anchor="mt")
    elif not is_rider:
        pts = entry.get("points", 0)
        draw.text((cx, floor_y + 38), f"{pts} p", font=_load_font(22, bold=True), fill=CYAN, anchor="mt")


def _draw_rider_podium_row(
    draw,
    base_img,
    x0: int,
    y0: int,
    width: int,
    title: str,
    podium: list[dict],
) -> int:
    """Draw class podium inside panel; return bottom y."""
    panel_h = 300
    _draw_panel(draw, (x0, y0, x0 + width, y0 + panel_h), title)
    if not podium:
        draw.text(
            (x0 + width // 2, y0 + panel_h // 2),
            "Inga resultat",
            font=_load_font(22),
            fill=MUTED,
            anchor="mm",
        )
        return y0 + panel_h

    by_pos = {int(p["position"]): p for p in podium}
    order = [(2, SILVER, 70), (1, GOLD, 95), (3, BRONZE, 58)]
    floor_y = y0 + panel_h - 28
    cx_mid = x0 + width // 2
    spacing = min(130, (width - 40) // 3)
    for pos, color, bh in order:
        entry = by_pos.get(pos)
        off = {1: 0, 2: -spacing, 3: spacing}[pos]
        _draw_podium_block(
            draw,
            base_img,
            cx_mid + off,
            floor_y,
            entry,
            block_w=108,
            block_h=bh,
            medal_color=color,
            rank_label=f"P{pos}",
            is_rider=True,
        )
    return y0 + panel_h


def _draw_user_podium_section(
    draw,
    base_img,
    y0: int,
    title: str,
    leaderboard: list[dict],
    show_delta: bool = False,
) -> int:
    """Podium for top 3 + optional rows 4+."""
    top3 = [r for r in leaderboard if int(r.get("rank", 99)) <= 3]
    extras = [r for r in leaderboard if int(r.get("rank", 99)) > 3]
    panel_h = 300 if not extras else 300 + min(len(extras), 3) * 36 + 8
    _draw_panel(draw, (48, y0, W - 48, y0 + panel_h), title)

    by_pos = {int(r["rank"]): r for r in top3}
    floor_y = y0 + 248 if not extras else y0 + 220
    cx_mid = W // 2
    spacing = 155
    for pos, color, bh in [(2, SILVER, 72), (1, GOLD, 98), (3, BRONZE, 60)]:
        entry = by_pos.get(pos)
        if entry and show_delta and entry.get("delta_label") and entry["delta_label"] != "—":
            entry = dict(entry)
            entry["display_name"] = f"{entry['display_name']} {entry['delta_label']}"
        _draw_podium_block(
            draw,
            base_img,
            cx_mid + {1: 0, 2: -spacing, 3: spacing}[pos],
            floor_y,
            entry,
            block_w=120,
            block_h=bh,
            medal_color=color,
            rank_label=str(pos),
            is_rider=False,
        )

    if extras:
        ey = y0 + panel_h - 16 - len(extras[:3]) * 34
        bf = _load_font(22)
        for row in extras[:3]:
            name = _short_user_name(row.get("display_name") or "?")
            pts = int(row.get("points", 0))
            draw.text((72, ey), f"{row['rank']}.", font=bf, fill=MUTED)
            draw.text((110, ey), name, font=bf, fill=WHITE)
            draw.text((W - 72, ey), f"{pts} p", font=bf, fill=CYAN, anchor="rt")
            ey += 34

    return y0 + panel_h


def _draw_fact_cards(draw, y0: int, facts: list[dict]) -> int:
    shown = [f for f in facts if f.get("text")][:3]
    if not shown:
        return y0
    card_h = 56
    gap = 10
    total_h = len(shown) * (card_h + gap) + 50
    _draw_panel(draw, (48, y0, W - 48, y0 + total_h), "Fältet säger")
    y = y0 + 52
    sf = _load_font(22)
    for fact in shown:
        text = fact.get("text", "")
        draw.rounded_rectangle(
            [64, y, W - 64, y + card_h],
            radius=12,
            fill=(15, 25, 45),
            outline=CYAN_DIM,
            width=1,
        )
        # wrap
        words = text.split()
        line, lines = "", []
        for w in words:
            test = f"{line} {w}".strip()
            if len(test) > 42:
                if line:
                    lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        ty = y + (card_h - len(lines) * 24) // 2 + 4
        for ln in lines[:2]:
            draw.text((80, ty), ln, font=sf, fill=WHITE)
            ty += 24
        y += card_h + gap
    return y0 + total_h


def render_social_recap_png(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    # decorative top stripe
    draw.rectangle([0, 0, W, 6], fill=CYAN)
    draw.rectangle([0, 6, W, 10], fill=CYAN_DIM)

    y = 36
    logo = _load_brand_logo(88)
    if logo:
        img.paste(logo, (W // 2 - 44, y), logo)
        y += 96
    else:
        y += 8

    title_f = _load_font(44, bold=True)
    sub_f = _load_font(28, bold=True)
    event_f = _load_font(26)
    draw.text((W // 2, y), "MX FANTASY", font=title_f, fill=CYAN, anchor="mt")
    y += 48
    draw.text((W // 2, y), "RACE RECAP", font=sub_f, fill=WHITE, anchor="mt")
    y += 40
    draw.text((W // 2, y), (data.get("event_label") or "Race")[:44], font=event_f, fill=MUTED, anchor="mt")
    y += 52

    mods = data.get("modules") or {}
    labels = data.get("class_labels") or {}

    if mods.get("rider_podium") and data.get("has_results"):
        rp = data.get("rider_podium_primary") or []
        rs = data.get("rider_podium_secondary") or []
        if rp or rs:
            gap = 16
            half = (W - 48 * 2 - gap) // 2
            bottom_left = _draw_rider_podium_row(
                draw,
                img,
                48,
                y,
                half,
                f"{labels.get('primary', '450')} SX",
                rp,
            )
            bottom_right = _draw_rider_podium_row(
                draw,
                img,
                48 + half + gap,
                y,
                half,
                f"{labels.get('secondary', '250')} SX",
                rs,
            )
            y = max(bottom_left, bottom_right) + 20

    if mods.get("race") and data.get("race_leaderboard"):
        y = _draw_user_podium_section(
            draw,
            img,
            y,
            "Fantasy — denna tävling",
            data["race_leaderboard"],
            show_delta=False,
        ) + 16

    if mods.get("season") and data.get("season_leaderboard"):
        y = _draw_user_podium_section(
            draw,
            img,
            y,
            "Fantasy — säsong",
            data["season_leaderboard"],
            show_delta=bool(mods.get("rank_delta")),
        ) + 16

    if mods.get("facts") and data.get("fun_facts"):
        y = _draw_fact_cards(draw, y, data["fun_facts"]) + 12

    foot_f = _load_font(22)
    draw.text((W // 2, H - 44), "mxfantasy.se · Spela med oss", font=foot_f, fill=MUTED, anchor="mt")
    draw.rectangle([0, H - 6, W, H], fill=CYAN)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
