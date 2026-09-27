"""AMA season champion / totalställning hype poster for Facebook + Stories."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from hype_poster_service import H_FB, H_STORY, W_FB, W_STORY, _cover_crop
from social_recap_service import (
    BRONZE,
    GOLD,
    MUTED,
    SILVER,
    WHITE,
    _draw_styled_text,
    _load_brand_logo,
    _load_display_font,
    _make_initials_avatar,
    _paste_user_avatar,
    _text_width,
)

_ROOT = Path(__file__).resolve().parent

BG = (6, 10, 18)
AMBER = (251, 191, 36)
AMBER_HOT = (253, 224, 71)
CYAN = (34, 211, 238)


def build_season_champion_poster_data(*, year: int = 2026) -> dict[str, Any]:
    """Top of AMA tippa year total (SX + MX + SMX) for poster + FB caption."""
    from ama_season_totals import _build_ama_year_total

    year = int(year)
    ama = _build_ama_year_total(year)
    if not ama or not ama.get("all_users"):
        raise ValueError(f"Ingen AMA-totalställning för {year}")

    board = ama["all_users"]
    top = board[:10]
    champ = top[0] if top else None
    if not champ:
        raise ValueError(f"Ingen vinnare i totalställningen {year}")

    part_labels = [
        (p.get("display_name") or p.get("name") or "").strip()
        for p in (ama.get("parts") or [])
    ]
    parts_line = " · ".join([x for x in part_labels if x]) or "SX · MX · SMX Playoffs"

    caption_lines = [
        f"🏆 AMA Fantasy {year} — Totalställningen är klar!",
        "",
        f"🥇 {champ['display_name']} — {champ['total_points']}p",
    ]
    if len(top) > 1:
        caption_lines.append(f"🥈 {top[1]['display_name']} — {top[1]['total_points']}p")
    if len(top) > 2:
        caption_lines.append(f"🥉 {top[2]['display_name']} — {top[2]['total_points']}p")
    caption_lines.extend(
        [
            "",
            f"Samma poäng som live-highscoren hela säsongen ({parts_line}).",
            "Grattis till alla som tippat — och till vinnaren! 🔥",
            "",
            "Se hela arkivet: mx-fantasy.se/finished_series",
            "#MXFantasy #AMA #Supercross #Motocross #SMX",
        ]
    )

    return {
        "year": year,
        "title": f"AMA {year}",
        "subtitle": "TOTALSTÄLLNING",
        "tagline": parts_line,
        "champion": {
            "user_id": champ["user_id"],
            "display_name": champ["display_name"],
            "username": champ.get("username") or "",
            "total_points": int(champ["total_points"] or 0),
            "competitions_participated": int(champ.get("competitions_participated") or 0),
        },
        "podium": [
            {
                "rank": i + 1,
                "user_id": row["user_id"],
                "display_name": row["display_name"],
                "total_points": int(row["total_points"] or 0),
            }
            for i, row in enumerate(top[:3])
        ],
        "top10": [
            {
                "rank": i + 1,
                "user_id": row["user_id"],
                "display_name": row["display_name"],
                "total_points": int(row["total_points"] or 0),
            }
            for i, row in enumerate(top)
        ],
        "total_users": int(ama.get("total_users") or len(board)),
        "total_competitions": int(ama.get("total_competitions") or 0),
        "from_archive": bool(ama.get("from_archive")),
        "caption": "\n".join(caption_lines),
        "site": "mx-fantasy.se",
    }


def _backdrop(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), BG)
    for cand in (
        "static/posters/smx_2026_seed_backdrop.png",
        "static/trackmaps/smx/smx_playoff2_carson_poster.jpg",
        "static/trackmaps/smx/smx_final_ridgedale.jpg",
    ):
        p = _ROOT / cand
        if not p.is_file():
            continue
        try:
            photo = Image.open(p).convert("RGB")
            photo = _cover_crop(photo, width, height)
            photo = ImageEnhance.Contrast(photo).enhance(1.2)
            photo = ImageEnhance.Color(photo).enhance(0.85)
            photo = ImageEnhance.Brightness(photo).enhance(0.55)
            photo = photo.filter(ImageFilter.GaussianBlur(radius=1.2))
            base = photo
            break
        except Exception:
            continue

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Warm gold wash (championship vibe — not purple)
    od.rectangle([0, 0, width, height], fill=(20, 12, 4, 55))
    for y in range(int(height * 0.32)):
        a = int(210 * (1 - y / max(1, height * 0.32)))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))
    bot = int(height * 0.5)
    for i, y in enumerate(range(height - bot, height)):
        t = i / max(bot - 1, 1)
        od.line([(0, y), (width, y)], fill=(4, 8, 14, int(50 + 200 * (t**1.1))))
    # Soft gold rays from top-center
    cx = width // 2
    for i in range(12):
        x_off = (i - 6) * int(width * 0.04)
        od.polygon(
            [
                (cx, -20),
                (cx + x_off - 40, height // 2),
                (cx + x_off + 40, height // 2),
            ],
            fill=(251, 191, 36, 10 + (i % 3) * 4),
        )
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    return base


def _safe_paste_avatar(base, cx: int, cy: int, radius: int, user_id, display_name: str) -> None:
    """Paste profile avatar; fall back to initials if DB/image load fails."""
    try:
        _paste_user_avatar(base, cx, cy, radius, user_id, display_name)
        return
    except Exception:
        pass
    from PIL import Image, ImageDraw

    thumb = _make_initials_avatar(display_name, int(user_id or 0), radius * 2)
    ring = Image.new("RGBA", (radius * 2 + 8, radius * 2 + 8), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([0, 0, radius * 2 + 7, radius * 2 + 7], fill=(*CYAN, 200))
    mask = Image.new("L", (radius * 2, radius * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, radius * 2 - 1, radius * 2 - 1], fill=255)
    thumb.putalpha(mask)
    base.paste(ring, (cx - radius - 4, cy - radius - 4), ring)
    base.paste(thumb, (cx - radius, cy - radius), thumb)


def _medal_color(rank: int) -> tuple[int, int, int]:
    if rank == 1:
        return GOLD
    if rank == 2:
        return SILVER
    if rank == 3:
        return BRONZE
    return MUTED


def _draw_crown(draw: ImageDraw.ImageDraw, cx: int, top: int, scale: float = 1.0) -> None:
    s = scale
    pts = [
        (cx - int(48 * s), top + int(28 * s)),
        (cx - int(36 * s), top + int(4 * s)),
        (cx - int(18 * s), top + int(22 * s)),
        (cx, top),
        (cx + int(18 * s), top + int(22 * s)),
        (cx + int(36 * s), top + int(4 * s)),
        (cx + int(48 * s), top + int(28 * s)),
        (cx + int(40 * s), top + int(42 * s)),
        (cx - int(40 * s), top + int(42 * s)),
    ]
    draw.polygon(pts, fill=AMBER_HOT)
    draw.ellipse(
        [cx - int(6 * s), top + int(14 * s), cx + int(6 * s), top + int(26 * s)],
        fill=(180, 83, 9),
    )


def render_season_champion_poster_png(
    data: dict[str, Any] | None = None,
    *,
    year: int = 2026,
    layout: str = "facebook",
) -> bytes:
    layout = (layout or "facebook").strip().lower()
    if data is None:
        data = build_season_champion_poster_data(year=year)

    if layout == "story":
        img = _render_story(data)
    else:
        img = _render_facebook(data)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_facebook(data: dict[str, Any]) -> Image.Image:
    img = _backdrop(W_FB, H_FB)
    draw = ImageDraw.Draw(img)
    margin = 48

    # Top accent bar
    draw.rectangle([0, 0, W_FB, 6], fill=AMBER)

    logo = _load_brand_logo(72)
    if logo:
        img.paste(logo, (margin, 28), logo)

    year = data["year"]
    _draw_styled_text(
        draw,
        (W_FB - margin, 36),
        f"AMA FANTASY {year}",
        _load_display_font(28, bold=True),
        AMBER,
        anchor="rt",
    )
    _draw_styled_text(
        draw,
        (W_FB - margin, 68),
        "SÄSONGSKLAR",
        _load_display_font(22, bold=True),
        MUTED,
        anchor="rt",
    )

    _draw_styled_text(
        draw,
        (W_FB // 2, 110),
        data["subtitle"],
        _load_display_font(56, bold=True),
        WHITE,
        anchor="mt",
    )
    _draw_styled_text(
        draw,
        (W_FB // 2, 172),
        data["tagline"],
        _load_display_font(26, bold=True),
        MUTED,
        anchor="mt",
    )

    # Left: champion hero
    champ = data["champion"]
    podium = data["podium"]
    left_cx = int(W_FB * 0.32)
    avatar_y = 430
    _draw_crown(draw, left_cx, 210, scale=1.35)
    _safe_paste_avatar(
        img,
        left_cx,
        avatar_y,
        110,
        champ["user_id"],
        champ["display_name"],
    )
    # Gold ring boost
    ring = Image.new("RGBA", (W_FB, H_FB), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse(
        [left_cx - 118, avatar_y - 118, left_cx + 118, avatar_y + 118],
        outline=(*AMBER, 220),
        width=6,
    )
    img = Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB")
    draw = ImageDraw.Draw(img)

    _draw_styled_text(
        draw,
        (left_cx, 570),
        "CHAMPION",
        _load_display_font(22, bold=True),
        AMBER,
        anchor="mt",
    )
    name = champ["display_name"]
    name_size = 44
    name_f = _load_display_font(name_size, bold=True)
    while _text_width(name_f, name) > 520 and name_size > 28:
        name_size -= 2
        name_f = _load_display_font(name_size, bold=True)
    _draw_styled_text(draw, (left_cx, 602), name, name_f, WHITE, anchor="mt")
    _draw_styled_text(
        draw,
        (left_cx, 658),
        f"{champ['total_points']} poäng",
        _load_display_font(36, bold=True),
        AMBER_HOT,
        anchor="mt",
    )

    # Flanking 2nd / 3rd
    for slot, dx, radius, y_av in (
        (1, -210, 58, 520),
        (2, 210, 58, 520),
    ):
        if slot >= len(podium):
            continue
        row = podium[slot]
        cx = left_cx + dx
        color = _medal_color(row["rank"])
        _safe_paste_avatar(img, cx, y_av, radius, row["user_id"], row["display_name"])
        badge = f"#{row['rank']}"
        _draw_styled_text(
            draw,
            (cx, y_av + radius + 18),
            badge,
            _load_display_font(20, bold=True),
            color,
            anchor="mt",
        )
        short = row["display_name"]
        if len(short) > 14:
            short = short[:13] + "…"
        _draw_styled_text(
            draw,
            (cx, y_av + radius + 42),
            short,
            _load_display_font(20, bold=True),
            WHITE,
            anchor="mt",
        )
        _draw_styled_text(
            draw,
            (cx, y_av + radius + 66),
            f"{row['total_points']}p",
            _load_display_font(18, bold=True),
            MUTED,
            anchor="mt",
        )

    # Right panel: top 10
    panel_x0 = int(W_FB * 0.58)
    panel_y0 = 210
    panel_x1 = W_FB - margin
    panel_y1 = H_FB - 70
    panel = Image.new("RGBA", (W_FB, H_FB), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle(
        [panel_x0, panel_y0, panel_x1, panel_y1],
        radius=18,
        fill=(8, 12, 22, 200),
        outline=(*AMBER, 90),
        width=2,
    )
    img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
    draw = ImageDraw.Draw(img)

    _draw_styled_text(
        draw,
        ((panel_x0 + panel_x1) // 2, panel_y0 + 22),
        "TOP 10",
        _load_display_font(26, bold=True),
        AMBER,
        anchor="mt",
    )
    row_y = panel_y0 + 70
    for row in data["top10"]:
        color = _medal_color(row["rank"])
        rank_s = f"{row['rank']:>2}"
        _draw_styled_text(
            draw,
            (panel_x0 + 28, row_y),
            rank_s,
            _load_display_font(24, bold=True),
            color,
            anchor="lt",
        )
        nm = row["display_name"]
        if len(nm) > 18:
            nm = nm[:17] + "…"
        _draw_styled_text(
            draw,
            (panel_x0 + 70, row_y),
            nm,
            _load_display_font(24, bold=True),
            WHITE,
            anchor="lt",
        )
        _draw_styled_text(
            draw,
            (panel_x1 - 28, row_y),
            f"{row['total_points']}",
            _load_display_font(24, bold=True),
            AMBER_HOT if row["rank"] == 1 else MUTED,
            anchor="rt",
        )
        row_y += 52

    # Footer
    _draw_styled_text(
        draw,
        (margin, H_FB - 28),
        f"{data['total_users']} tippare · {data['total_competitions']} race",
        _load_display_font(20, bold=True),
        MUTED,
        anchor="lb",
    )
    _draw_styled_text(
        draw,
        (W_FB - margin, H_FB - 28),
        data["site"],
        _load_display_font(22, bold=True),
        CYAN,
        anchor="rb",
    )
    return img


def _render_story(data: dict[str, Any]) -> Image.Image:
    img = _backdrop(W_STORY, H_STORY)
    draw = ImageDraw.Draw(img)
    margin = 48

    draw.rectangle([0, 0, W_STORY, 8], fill=AMBER)
    logo = _load_brand_logo(88)
    if logo:
        img.paste(logo, ((W_STORY - logo.width) // 2, 48), logo)

    _draw_styled_text(
        draw,
        (W_STORY // 2, 160),
        f"AMA FANTASY {data['year']}",
        _load_display_font(28, bold=True),
        AMBER,
        anchor="mt",
    )
    _draw_styled_text(
        draw,
        (W_STORY // 2, 210),
        "TOTALSTÄLLNING",
        _load_display_font(52, bold=True),
        WHITE,
        anchor="mt",
    )
    _draw_styled_text(
        draw,
        (W_STORY // 2, 275),
        data["tagline"],
        _load_display_font(24, bold=True),
        MUTED,
        anchor="mt",
    )

    champ = data["champion"]
    cx = W_STORY // 2
    _draw_crown(draw, cx, 320, scale=1.5)
    _safe_paste_avatar(img, cx, 560, 130, champ["user_id"], champ["display_name"])
    ring = Image.new("RGBA", (W_STORY, H_STORY), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - 140, 420, cx + 140, 700], outline=(*AMBER, 230), width=7)
    img = Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB")
    draw = ImageDraw.Draw(img)

    _draw_styled_text(
        draw, (cx, 720), "CHAMPION", _load_display_font(26, bold=True), AMBER, anchor="mt"
    )
    _draw_styled_text(
        draw,
        (cx, 760),
        champ["display_name"],
        _load_display_font(48, bold=True),
        WHITE,
        anchor="mt",
    )
    _draw_styled_text(
        draw,
        (cx, 825),
        f"{champ['total_points']} poäng",
        _load_display_font(40, bold=True),
        AMBER_HOT,
        anchor="mt",
    )

    # 2 / 3
    podium = data["podium"]
    y_av = 1020
    for row, x in zip(podium[1:3], (cx - 220, cx + 220)):
        color = _medal_color(row["rank"])
        _safe_paste_avatar(img, x, y_av, 64, row["user_id"], row["display_name"])
        _draw_styled_text(
            draw,
            (x, y_av + 90),
            f"#{row['rank']}  {row['total_points']}p",
            _load_display_font(22, bold=True),
            color,
            anchor="mt",
        )
        nm = row["display_name"]
        if len(nm) > 14:
            nm = nm[:13] + "…"
        _draw_styled_text(
            draw, (x, y_av + 120), nm, _load_display_font(22, bold=True), WHITE, anchor="mt"
        )

    # Compact top list
    y = 1220
    _draw_styled_text(
        draw, (cx, y), "TOP 8", _load_display_font(24, bold=True), AMBER, anchor="mt"
    )
    y += 50
    for row in data["top10"][:8]:
        color = _medal_color(row["rank"])
        left = f"{row['rank']}. {row['display_name']}"
        if len(left) > 26:
            left = left[:25] + "…"
        _draw_styled_text(
            draw, (margin + 20, y), left, _load_display_font(26, bold=True), WHITE, anchor="lt"
        )
        _draw_styled_text(
            draw,
            (W_STORY - margin - 20, y),
            f"{row['total_points']}",
            _load_display_font(26, bold=True),
            color if row["rank"] <= 3 else MUTED,
            anchor="rt",
        )
        y += 48

    _draw_styled_text(
        draw,
        (cx, H_STORY - 48),
        data["site"],
        _load_display_font(28, bold=True),
        CYAN,
        anchor="mb",
    )
    return img
