"""SMX Playoffs seeding poster — Combined points, seed 1–20 vs LCQ 21–30."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from official_smx_2026 import OFFICIAL_SMX_250_2026, OFFICIAL_SMX_450_2026

# Re-use brand helpers from social recap
W_FB = 1620
H_FB = 1080
W_STORY = 1080
H_STORY = 1920

VIOLET = (167, 139, 250)
VIOLET_DIM = (109, 40, 217)
AMBER = (251, 191, 36)
AMBER_BG = (69, 46, 10)
EMERALD = (52, 211, 153)
EMERALD_BG = (6, 55, 40)


def _seed_adjustment_points(rank: int) -> int:
    """Official SMX playoff seed points for ranks 1–20 (AMA scale)."""
    table = {
        1: 25, 2: 22, 3: 20, 4: 18, 5: 17, 6: 16, 7: 15, 8: 14, 9: 13, 10: 12,
        11: 11, 12: 10, 13: 9, 14: 8, 15: 7, 16: 6, 17: 5, 18: 4, 19: 3, 20: 2,
    }
    return table.get(rank, 0)


def build_smx_seed_poster_data() -> dict[str, Any]:
    """Rows from official Combined snapshot + rider numbers from DB when available."""
    num_by_name: dict[str, int | None] = {}
    try:
        from models import Rider

        for r in Rider.query.filter(Rider.class_name.in_(("450cc", "250cc"))).all():
            key = (r.name or "").strip().lower()
            if key and key not in num_by_name:
                num_by_name[key] = r.rider_number
    except Exception:
        pass

    def rows_for(official: list[tuple[str, int, int]], *, class_key: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, (name, sx, mx) in enumerate(official, start=1):
            total = int(sx) + int(mx)
            zone = "seeded" if i <= 20 else "lcq"
            out.append(
                {
                    "rank": i,
                    "name": name,
                    "number": num_by_name.get(name.strip().lower()),
                    "sx": int(sx),
                    "mx": int(mx),
                    "total": total,
                    "seed_pts": _seed_adjustment_points(i) if zone == "seeded" else 0,
                    "zone": zone,
                    "class_key": class_key,
                }
            )
        return out

    return {
        "title": "SMX PLAYOFFS 2026",
        "subtitle": "Combined seeding efter Ironman",
        "tagline": "Topp 20 seedade · 21–30 LCQ / Wild Card",
        "450": rows_for(OFFICIAL_SMX_450_2026, class_key="450"),
        "250": rows_for(OFFICIAL_SMX_250_2026, class_key="250"),
        "url": "mx-fantasy.se",
    }


def render_smx_seed_poster_png(*, layout: str = "facebook") -> bytes:
    layout = (layout or "facebook").lower()
    data = build_smx_seed_poster_data()
    if layout == "story":
        # Two stacked classes — generate 450 story by default; use class= via landscape for both
        return _render_story(data, class_key="450")
    if layout == "story250":
        return _render_story(data, class_key="250")
    return _render_landscape(data)


def render_smx_seed_story_pair() -> dict[str, bytes]:
    data = build_smx_seed_poster_data()
    return {
        "450": _render_story(data, class_key="450"),
        "250": _render_story(data, class_key="250"),
        "facebook": _render_landscape(data),
    }


def _render_landscape(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        BG_BOTTOM,
        BG_TOP,
        MUTED,
        PANEL,
        PANEL_EDGE,
        WHITE,
        _draw_styled_text,
        _draw_vertical_gradient,
        _font_height,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
        _text_width,
    )

    img = Image.new("RGB", (W_FB, H_FB), BG_TOP)
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    # Soft violet wash
    wash = Image.new("RGBA", (W_FB, H_FB), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash)
    wd.rectangle([0, 0, W_FB, H_FB], fill=(88, 28, 135, 35))
    img = Image.alpha_composite(img.convert("RGBA"), wash).convert("RGB")
    draw = ImageDraw.Draw(img)

    margin = 36
    y = 22
    draw.rectangle([0, 0, W_FB, 8], fill=VIOLET)

    logo = _load_brand_logo(72)
    if logo:
        img.paste(logo, (margin, y), logo)
    brand_f = _load_display_font(28, bold=True)
    _draw_styled_text(draw, (margin + 88, y + 18), "MX FANTASY LEAGUE", brand_f, VIOLET, anchor="lm")
    _draw_styled_text(
        draw, (margin + 88, y + 48), data.get("url") or "mx-fantasy.se", _load_font_px(18), MUTED, anchor="lm"
    )

    title_f = _load_display_font(42, bold=True)
    _draw_styled_text(draw, (W_FB // 2, y + 8), data["title"], title_f, WHITE, anchor="mt")
    sub_f = _load_font_px(22)
    _draw_styled_text(draw, (W_FB // 2, y + 56), data["subtitle"], sub_f, MUTED, anchor="mt")
    tag_f = _load_font_px(20, bold=True)
    _draw_styled_text(draw, (W_FB // 2, y + 86), data["tagline"], tag_f, AMBER, anchor="mt")

    y = 130
    col_w = (W_FB - margin * 3) // 2
    _draw_class_column(
        img,
        draw,
        x=margin,
        y=y,
        width=col_w,
        height=H_FB - y - 48,
        title="450cc",
        rows=data["450"],
    )
    _draw_class_column(
        img,
        draw,
        x=margin * 2 + col_w,
        y=y,
        width=col_w,
        height=H_FB - y - 48,
        title="250cc",
        rows=data["250"],
    )

    foot = _load_font_px(16)
    _draw_styled_text(
        draw,
        (W_FB // 2, H_FB - 18),
        "Tippa bland topp 30 · LCQ måste kvala in via Wild Card · annars 0 p",
        foot,
        MUTED,
        anchor="mm",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_class_column(img, draw, *, x: int, y: int, width: int, height: int, title: str, rows: list[dict]):
    from social_recap_service import (
        PANEL,
        PANEL_EDGE,
        WHITE,
        _draw_styled_text,
        _load_display_font,
        _load_font_px,
    )

    seeded = [r for r in rows if r["zone"] == "seeded"]
    lcq = [r for r in rows if r["zone"] == "lcq"]

    draw.rounded_rectangle(
        [x, y, x + width, y + height], radius=16, fill=PANEL, outline=PANEL_EDGE, width=2
    )

    pad = 12
    cy = y + 10
    head = _load_display_font(24, bold=True)
    _draw_styled_text(draw, (x + pad, cy), title, head, VIOLET, anchor="lt")
    cy += 24
    seed_lbl = _load_font_px(13, bold=True)
    _draw_styled_text(draw, (x + pad, cy), "DIREKTKVAL · SEED 1–20", seed_lbl, EMERALD, anchor="lt")
    cy += 18

    row_f = _load_font_px(13)
    row_b = _load_font_px(13, bold=True)
    pts_f = _load_font_px(12, bold=True)
    line_h = 19

    # Reserve enough space for all 10 LCQ rows + amber panel chrome
    lcq_block_h = 36 + len(lcq) * line_h + 16
    seed_bottom = y + height - lcq_block_h - 8

    for r in seeded:
        if cy + line_h > seed_bottom:
            break
        _draw_rider_line(
            draw,
            x=x + pad,
            y=cy,
            width=width - pad * 2,
            row=r,
            row_f=row_f,
            row_b=row_b,
            pts_f=pts_f,
            accent=EMERALD,
            show_seed_pts=True,
        )
        cy += line_h

    # LCQ panel — always shows ranks 21–30 separately from seeded
    lcq_top = seed_bottom + 4
    draw.rounded_rectangle(
        [x + 6, lcq_top, x + width - 6, y + height - 8],
        radius=12,
        fill=AMBER_BG,
        outline=AMBER,
        width=2,
    )
    cy = lcq_top + 8
    _draw_styled_text(
        draw,
        (x + pad + 2, cy),
        "LCQ / WILD CARD · 21–30 (ej direktkvalade)",
        seed_lbl,
        AMBER,
        anchor="lt",
    )
    cy += 18
    for r in lcq:
        _draw_rider_line(
            draw,
            x=x + pad + 2,
            y=cy,
            width=width - pad * 2 - 4,
            row=r,
            row_f=row_f,
            row_b=row_b,
            pts_f=pts_f,
            accent=AMBER,
            show_seed_pts=False,
        )
        cy += line_h


def _draw_rider_line(
    draw,
    *,
    x: int,
    y: int,
    width: int,
    row: dict,
    row_f,
    row_b,
    pts_f,
    accent,
    show_seed_pts: bool,
):
    from social_recap_service import MUTED, WHITE, _draw_styled_text, _text_width

    rank = row["rank"]
    num = row.get("number")
    num_s = f"#{num} " if num else ""
    name = row["name"]
    total = row["total"]
    left = f"{rank:>2}. {num_s}{name}"
    right = f"{total}p"
    if show_seed_pts and row.get("seed_pts"):
        right = f"{total}p · seed {row['seed_pts']}"

    _draw_styled_text(draw, (x, y), left[:42], row_b if rank <= 3 else row_f, WHITE, anchor="lt")
    _draw_styled_text(draw, (x + width, y), right, pts_f, accent, anchor="rt")


def _render_story(data: dict[str, Any], *, class_key: str) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        MUTED,
        PANEL,
        PANEL_EDGE,
        WHITE,
        _draw_styled_text,
        _draw_vertical_gradient,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
    )

    rows = data["450"] if class_key == "450" else data["250"]
    cls_title = "450cc" if class_key == "450" else "250cc"

    img = Image.new("RGB", (W_STORY, H_STORY), (8, 15, 35))
    _draw_vertical_gradient(img)
    wash = Image.new("RGBA", (W_STORY, H_STORY), (88, 28, 135, 40))
    img = Image.alpha_composite(img.convert("RGBA"), wash).convert("RGB")
    draw = ImageDraw.Draw(img)

    margin = 48
    y = 36
    draw.rectangle([0, 0, W_STORY, 10], fill=VIOLET)
    logo = _load_brand_logo(100)
    if logo:
        img.paste(logo, (margin, y), logo)
    _draw_styled_text(
        draw, (margin + 120, y + 24), "MX FANTASY LEAGUE", _load_display_font(30, bold=True), VIOLET, anchor="lm"
    )
    _draw_styled_text(draw, (margin + 120, y + 64), "SMX PLAYOFFS 2026", _load_font_px(22), MUTED, anchor="lm")
    y += 130

    _draw_styled_text(
        draw, (W_STORY // 2, y), f"{cls_title} SEEDING", _load_display_font(44, bold=True), WHITE, anchor="mt"
    )
    y += 56
    _draw_styled_text(
        draw, (W_STORY // 2, y), "Combined SX + MX · efter Ironman", _load_font_px(24), MUTED, anchor="mt"
    )
    y += 48

    seeded = [r for r in rows if r["zone"] == "seeded"]
    lcq = [r for r in rows if r["zone"] == "lcq"]

    # Seeded panel
    panel_h = 980
    draw.rounded_rectangle(
        [margin, y, W_STORY - margin, y + panel_h], radius=20, fill=PANEL, outline=PANEL_EDGE, width=2
    )
    py = y + 20
    _draw_styled_text(
        draw, (margin + 24, py), "DIREKTKVAL · SEED 1–20", _load_font_px(22, bold=True), EMERALD, anchor="lt"
    )
    py += 36
    row_f = _load_font_px(22)
    row_b = _load_font_px(22, bold=True)
    pts_f = _load_font_px(20, bold=True)
    for r in seeded:
        _draw_rider_line(
            draw,
            x=margin + 24,
            y=py,
            width=W_STORY - margin * 2 - 48,
            row=r,
            row_f=row_f,
            row_b=row_b,
            pts_f=pts_f,
            accent=EMERALD,
            show_seed_pts=True,
        )
        py += 44

    y = y + panel_h + 24
    # LCQ panel
    lcq_h = H_STORY - y - 80
    draw.rounded_rectangle(
        [margin, y, W_STORY - margin, y + lcq_h],
        radius=20,
        fill=AMBER_BG,
        outline=AMBER,
        width=3,
    )
    py = y + 20
    _draw_styled_text(
        draw,
        (margin + 24, py),
        "LCQ / WILD CARD · 21–30",
        _load_font_px(24, bold=True),
        AMBER,
        anchor="lt",
    )
    py += 32
    _draw_styled_text(
        draw,
        (margin + 24, py),
        "Ej direktkvalade — måste kvala in (annars 0 p i tippet)",
        _load_font_px(18),
        MUTED,
        anchor="lt",
    )
    py += 36
    for r in lcq:
        if py + 40 > y + lcq_h - 20:
            break
        _draw_rider_line(
            draw,
            x=margin + 24,
            y=py,
            width=W_STORY - margin * 2 - 48,
            row=r,
            row_f=row_f,
            row_b=row_b,
            pts_f=pts_f,
            accent=AMBER,
            show_seed_pts=False,
        )
        py += 42

    _draw_styled_text(
        draw, (W_STORY // 2, H_STORY - 36), "mx-fantasy.se · tippa SMX bland topp 30", _load_font_px(20), MUTED, anchor="mm"
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def save_smx_seed_posters(out_dir: str | Path | None = None) -> dict[str, Path]:
    """Write facebook + story PNGs under static/posters/."""
    out = Path(out_dir or Path("static") / "posters")
    out.mkdir(parents=True, exist_ok=True)
    pair = render_smx_seed_story_pair()
    paths = {
        "facebook": out / "smx_2026_seeding_facebook.png",
        "story_450": out / "smx_2026_seeding_story_450.png",
        "story_250": out / "smx_2026_seeding_story_250.png",
    }
    paths["facebook"].write_bytes(pair["facebook"])
    paths["story_450"].write_bytes(pair["450"])
    paths["story_250"].write_bytes(pair["250"])
    return paths
