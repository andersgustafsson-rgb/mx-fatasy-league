"""MXoN crowd power-ranking posters for Facebook feed + Stories."""
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
    _load_font_px,
    _plain_draw_text,
    _text_width,
)

_ROOT = Path(__file__).resolve().parent

ACCENT = (250, 204, 21)  # MXoN gold
ACCENT2 = (52, 211, 153)  # emerald
BG_CARD = (8, 12, 24)
ROW_BG = (14, 20, 36)

MEDAL_COLORS = {
    1: GOLD,
    2: SILVER,
    3: BRONZE,
}


def _resolve_mxon_competition(competition_id: int | None = None):
    from models import Competition

    if competition_id:
        c = Competition.query.get(int(competition_id))
        if c and (c.series or "").upper() == "MXON":
            return c
        raise ValueError("competition_id is not an MXoN race")

    # Prefer upcoming / latest MXoN competition
    q = Competition.query.filter(Competition.series == "MXON")
    c = q.order_by(Competition.event_date.desc().nullslast(), Competition.id.desc()).first()
    if not c:
        raise ValueError("Ingen MXoN-tävling hittades")
    return c


def _flag_filename(code: str | None) -> str | None:
    from mxon_fantasy import alpha2_for_code

    a2 = alpha2_for_code(code or "")
    if not a2:
        return None
    name = f"{a2.lower()}.png"
    path = _ROOT / "static" / "images" / "mxon" / "flags" / name
    return name if path.is_file() else None


def _paste_flag(base: Image.Image, flag_file: str | None, box: tuple[int, int, int, int]) -> None:
    if not flag_file:
        return
    path = _ROOT / "static" / "images" / "mxon" / "flags" / flag_file
    if not path.is_file():
        return
    try:
        flag = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = box
        tw, th = max(1, x1 - x0), max(1, y1 - y0)
        flag = flag.resize((tw, th), Image.Resampling.LANCZOS)
        border = Image.new("RGBA", (tw + 4, th + 4), (0, 0, 0, 180))
        base.paste(border, (x0 - 2, y0 - 2), border)
        base.paste(flag, (x0, y0), flag)
    except Exception:
        pass


def _backdrop(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), (10, 14, 28))
    hero = _ROOT / "static" / "images" / "mxon" / "ernee_aerial.jpg"
    if hero.is_file():
        try:
            photo = Image.open(hero).convert("RGB")
            photo = _cover_crop(photo, width, height)
            photo = ImageEnhance.Contrast(photo).enhance(1.12)
            photo = ImageEnhance.Color(photo).enhance(1.08)
            base = photo
        except Exception:
            pass

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 0, width, height], fill=(4, 8, 18, 55))
    top_band = max(100, height // 6)
    for y in range(top_band):
        a = int(175 * (1 - y / top_band))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))
    bot_band = int(height * 0.68)
    for i, y in enumerate(range(height - bot_band, height)):
        t = i / max(bot_band - 1, 1)
        a = int(55 + 200 * (t**1.25))
        od.line([(0, y), (width, y)], fill=(4, 8, 18, min(240, a)))

    streak = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streak)
    for i in range(6):
        y0 = int(height * 0.16) + i * 55
        sd.line(
            [(-40, y0), (width + 40, y0 + int(height * 0.09))],
            fill=(ACCENT[0], ACCENT[1], ACCENT[2], 18 - i * 2),
            width=2,
        )
    streak = streak.filter(ImageFilter.GaussianBlur(1.2))
    out = base.convert("RGBA")
    out = Image.alpha_composite(out, overlay)
    out = Image.alpha_composite(out, streak)
    return out.convert("RGB")


def _build_caption(nations: list[dict], classes: list[dict], event_name: str) -> str:
    lines = [
        f"🏁 {event_name} — Crowd power rankings!",
        "",
        "Vilka nationer tippar MX Fantasy-gänget högst just nu?",
        "",
    ]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for n in nations[:5]:
        rank = int(n.get("rank") or 0)
        prefix = medals.get(rank, f"#{rank}")
        lines.append(f"{prefix} {n.get('name') or n.get('code') or '—'}")
    if classes:
        lines.append("")
        lines.append("Klassfavoriter:")
        for cl in classes:
            rider = cl.get("rider_label") or "TBA"
            label = cl.get("class_label") or cl.get("class_name") or ""
            nation = cl.get("name") or cl.get("code") or ""
            lines.append(f"• {label}: {rider} ({nation})")
    lines.extend(
        [
            "",
            "Ordning utifrån tipparnas topp 5 — ingen statistik, inga odds.",
            "Tippa gratis: mx-fantasy.se",
            "",
            "👉 mx-fantasy.se",
            "",
            "#MXoN #MotocrossOfNations #Ernée2026 #MXFantasy #PowerRankings",
        ]
    )
    return "\n".join(lines)


def build_mxon_power_ranking_poster_data(
    competition_id: int | None = None,
) -> dict[str, Any]:
    """Live crowd ranking payload + FB caption for poster studio."""
    from mxon_fantasy import MXON_CLASS_KEYS, MXON_CLASS_LABELS, build_mxon_crowd_ranking

    comp = _resolve_mxon_competition(competition_id)
    crowd = build_mxon_crowd_ranking(int(comp.id))
    if not crowd.get("ok"):
        raise ValueError(crowd.get("error") or "Kunde inte bygga MXoN-ranking")
    if not crowd.get("has_tips"):
        raise ValueError("Inga MXoN-tips ännu — poster behöver minst några tippare")

    nations_raw = list(crowd.get("nations") or [])[:5]
    nations: list[dict[str, Any]] = []
    for n in nations_raw:
        code = n.get("code")
        nations.append(
            {
                "rank": int(n.get("rank") or 0),
                "nation_id": n.get("nation_id"),
                "code": code,
                "name": n.get("name") or code or "—",
                "flag_file": _flag_filename(code),
            }
        )

    classes: list[dict[str, Any]] = []
    class_map = crowd.get("classes") or {}
    for key in MXON_CLASS_KEYS:
        cl = class_map.get(key)
        if not cl:
            continue
        is_tba = bool(cl.get("is_tba"))
        rider_name = (cl.get("rider_name") or "").strip()
        num = cl.get("rider_number")
        if is_tba or not rider_name:
            rider_label = "TBA"
        elif num is not None:
            rider_label = f"#{num} {rider_name}"
        else:
            rider_label = rider_name
        code = cl.get("code")
        classes.append(
            {
                "class_name": key,
                "class_label": cl.get("class_label") or MXON_CLASS_LABELS.get(key, key.upper()),
                "nation_id": cl.get("nation_id"),
                "code": code,
                "name": cl.get("name") or code,
                "flag_file": _flag_filename(code),
                "rider_name": rider_name or None,
                "rider_number": num,
                "rider_label": rider_label,
                "is_tba": is_tba,
            }
        )

    event_name = (comp.name or "MXoN Ernée 2026").strip()
    caption = _build_caption(nations, classes, event_name)

    return {
        "ok": True,
        "competition_id": int(comp.id),
        "competition_name": event_name,
        "event_date": comp.event_date.isoformat() if comp.event_date else None,
        "picks_locked": bool(crowd.get("picks_locked")),
        "nations": nations,
        "classes": classes,
        "caption": caption,
        "method": crowd.get("method"),
        "title": "CROWD POWER RANKINGS",
        "subtitle": "Tipparnas nationstopp · Ernée 2026",
    }


def _draw_brand_strip(img: Image.Image, draw: ImageDraw.ImageDraw, *, width: int, story: bool) -> int:
    margin = 40 if story else 44
    top_h = 96 if story else 78
    draw.rectangle([0, 0, width, top_h], fill=(6, 10, 20))
    draw.rectangle([0, top_h, width, top_h + 4], fill=ACCENT)

    logo = _load_brand_logo(60 if story else 54)
    if logo:
        img.paste(logo, (margin, (top_h - logo.size[1]) // 2), logo)
        brand_x = margin + logo.size[0] + 14
    else:
        brand_x = margin
    _draw_styled_text(
        draw,
        (brand_x, top_h // 2 - 10),
        "MX FANTASY LEAGUE",
        _load_display_font(22 if story else 24, bold=True),
        ACCENT,
        anchor="lm",
    )
    _draw_styled_text(
        draw,
        (brand_x, top_h // 2 + 16),
        "TIPPA GRATIS · mx-fantasy.se",
        _load_font_px(15 if story else 14, bold=True),
        GOLD,
        anchor="lm",
    )

    pill = "MXoN · ERNÉE 2026"
    pf = _load_font_px(15 if story else 16, bold=True)
    pw = _text_width(pf, pill) + 28
    ph = 32
    draw.rounded_rectangle(
        [width - margin - pw, (top_h - ph) // 2, width - margin, (top_h - ph) // 2 + ph],
        radius=16,
        fill=(ACCENT[0] // 6, ACCENT[1] // 6, ACCENT[2] // 6),
        outline=ACCENT,
        width=2,
    )
    _draw_styled_text(draw, (width - margin - pw // 2, top_h // 2), pill, pf, WHITE, anchor="mm")
    return top_h + 4


def _medal_label(rank: int) -> str:
    return {1: "#1", 2: "#2", 3: "#3"}.get(rank, f"#{rank}")


def _draw_nation_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x0: int,
    x1: int,
    y: int,
    row_h: int,
    nation: dict[str, Any],
    story: bool,
) -> ImageDraw.ImageDraw:
    rank = int(nation.get("rank") or 0)
    draw.rounded_rectangle(
        [x0, y, x1, y + row_h],
        radius=12,
        fill=ROW_BG,
        outline=(ACCENT[0] // 2, ACCENT[1] // 2, ACCENT[2] // 2),
        width=1,
    )
    medal_color = MEDAL_COLORS.get(rank, MUTED)
    _draw_styled_text(
        draw,
        (x0 + 18, y + row_h // 2),
        _medal_label(rank),
        _load_display_font(18 if story else 20, bold=True),
        medal_color,
        anchor="lm",
    )
    flag_w, flag_h = (46, 30) if story else (44, 28)
    fx = x0 + (70 if story else 68)
    _paste_flag(img, nation.get("flag_file"), (fx, y + (row_h - flag_h) // 2, fx + flag_w, y + (row_h - flag_h) // 2 + flag_h))
    draw = ImageDraw.Draw(img)
    _draw_styled_text(
        draw,
        (fx + flag_w + 14, y + row_h // 2),
        _plain_draw_text(str(nation.get("name") or "—")),
        _load_display_font(20 if story else 22, bold=True),
        WHITE,
        anchor="lm",
    )
    return draw


def _draw_class_card(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    box: tuple[int, int, int, int],
    cl: dict[str, Any],
    story: bool,
) -> ImageDraw.ImageDraw:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=14,
        fill=ROW_BG,
        outline=(ACCENT2[0] // 2, ACCENT2[1] // 2, ACCENT2[2] // 2),
        width=1,
    )
    _draw_styled_text(
        draw,
        (x0 + 14, y0 + 12),
        str(cl.get("class_label") or "").upper(),
        _load_font_px(13 if story else 14, bold=True),
        ACCENT2,
        anchor="lt",
    )
    rider = _plain_draw_text(str(cl.get("rider_label") or "TBA"))
    _draw_styled_text(
        draw,
        (x0 + 14, y0 + (42 if story else 38)),
        rider,
        _load_display_font(18 if story else 20, bold=True),
        WHITE,
        anchor="lt",
    )
    flag_file = cl.get("flag_file")
    nation = _plain_draw_text(str(cl.get("name") or cl.get("code") or ""))
    fy = y1 - 36
    if flag_file:
        _paste_flag(img, flag_file, (x0 + 14, fy, x0 + 14 + 34, fy + 22))
        draw = ImageDraw.Draw(img)
        _draw_styled_text(
            draw,
            (x0 + 56, fy + 11),
            nation,
            _load_font_px(14, bold=True),
            MUTED,
            anchor="lm",
        )
    else:
        _draw_styled_text(
            draw,
            (x0 + 14, fy + 11),
            nation,
            _load_font_px(14, bold=True),
            MUTED,
            anchor="lm",
        )
    return draw


def render_mxon_power_ranking_poster_png(
    data: dict[str, Any] | None = None,
    *,
    competition_id: int | None = None,
    layout: str = "facebook",
) -> bytes:
    """Render Facebook or Story PNG from crowd ranking data."""
    if data is None:
        data = build_mxon_power_ranking_poster_data(competition_id)

    layout = (layout or "facebook").strip().lower()
    story = layout == "story"
    width, height = (W_STORY, H_STORY) if story else (W_FB, H_FB)
    margin = 40 if story else 44

    img = _backdrop(width, height)
    draw = ImageDraw.Draw(img)
    top = _draw_brand_strip(img, draw, width=width, story=story)

    nations = list(data.get("nations") or [])[:5]
    classes = list(data.get("classes") or [])[:3]

    if story:
        card = (margin, top + 28, width - margin, height - margin)
        x0, y0, x1, y1 = card
        draw.rounded_rectangle([x0, y0, x1, y1], radius=22, fill=BG_CARD, outline=ACCENT, width=2)
        draw.rectangle([x0 + 20, y0, x1 - 20, y0 + 4], fill=GOLD)

        y = y0 + 24
        cx = (x0 + x1) // 2
        _draw_styled_text(
            draw,
            (cx, y),
            "CROWD POWER RANKINGS",
            _load_display_font(28, bold=True),
            WHITE,
            anchor="mt",
        )
        y += 40
        _draw_styled_text(
            draw,
            (cx, y),
            _plain_draw_text(str(data.get("subtitle") or "Tipparnas nationstopp")),
            _load_font_px(16, bold=True),
            ACCENT2,
            anchor="mt",
        )
        y += 36

        _draw_styled_text(
            draw,
            (x0 + 28, y),
            "NATIONER",
            _load_font_px(13, bold=True),
            GOLD,
            anchor="lt",
        )
        y += 28
        row_h = 64
        for n in nations:
            draw = _draw_nation_row(img, draw, x0=x0 + 24, x1=x1 - 24, y=y, row_h=row_h, nation=n, story=True)
            y += row_h + 10

        y += 12
        _draw_styled_text(
            draw,
            (x0 + 28, y),
            "KLASSFAVORITER",
            _load_font_px(13, bold=True),
            GOLD,
            anchor="lt",
        )
        y += 26
        card_h = 110
        gap = 12
        for cl in classes:
            draw = _draw_class_card(
                img,
                draw,
                box=(x0 + 24, y, x1 - 24, y + card_h),
                cl=cl,
                story=True,
            )
            y += card_h + gap

        # CTA near bottom of card
        btn_h = 56
        btn_y = min(y + 8, y1 - btn_h - 28)
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=16, fill=ACCENT)
        _draw_styled_text(
            draw,
            (cx, btn_y + btn_h // 2),
            "TIPPA MXoN · mx-fantasy.se",
            _load_display_font(20, bold=True),
            (8, 15, 30),
            anchor="mm",
        )
    else:
        # Facebook landscape: two-column card
        card = (margin, top + 18, width - margin, height - margin)
        x0, y0, x1, y1 = card
        draw.rounded_rectangle([x0, y0, x1, y1], radius=22, fill=BG_CARD, outline=ACCENT, width=2)
        draw.rectangle([x0 + 24, y0, x1 - 24, y0 + 4], fill=GOLD)

        y = y0 + 20
        _draw_styled_text(
            draw,
            (x0 + 36, y),
            "CROWD POWER RANKINGS",
            _load_display_font(34, bold=True),
            WHITE,
            anchor="lt",
        )
        _draw_styled_text(
            draw,
            (x1 - 36, y + 8),
            _plain_draw_text(str(data.get("competition_name") or "MXoN")),
            _load_font_px(16, bold=True),
            MUTED,
            anchor="rt",
        )
        y += 42
        _draw_styled_text(
            draw,
            (x0 + 36, y),
            _plain_draw_text(str(data.get("subtitle") or "Tipparnas nationstopp · Ernée 2026")),
            _load_font_px(16, bold=True),
            ACCENT2,
            anchor="lt",
        )
        y += 34

        mid = (x0 + x1) // 2
        left_x0, left_x1 = x0 + 28, mid - 16
        right_x0, right_x1 = mid + 16, x1 - 28

        _draw_styled_text(
            draw,
            (left_x0 + 8, y),
            "NATIONER — TIPPARNAS TOPP",
            _load_font_px(13, bold=True),
            GOLD,
            anchor="lt",
        )
        _draw_styled_text(
            draw,
            (right_x0 + 8, y),
            "KLASSFAVORITER",
            _load_font_px(13, bold=True),
            GOLD,
            anchor="lt",
        )
        y += 26

        row_h = 58
        ny = y
        for n in nations:
            draw = _draw_nation_row(
                img, draw, x0=left_x0, x1=left_x1, y=ny, row_h=row_h, nation=n, story=False
            )
            ny += row_h + 10

        # Class cards stacked on the right
        avail_h = (y1 - 90) - y
        n_cls = max(1, len(classes))
        gap = 10
        card_h = max(88, (avail_h - gap * (n_cls - 1)) // n_cls)
        card_h = min(card_h, 120)
        cy = y
        for cl in classes:
            draw = _draw_class_card(
                img,
                draw,
                box=(right_x0, cy, right_x1, cy + card_h),
                cl=cl,
                story=False,
            )
            cy += card_h + gap

        # Bottom CTA strip
        btn_h = 54
        btn_y = y1 - 28 - btn_h
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=14, fill=ACCENT)
        _draw_styled_text(
            draw,
            ((x0 + x1) // 2, btn_y + btn_h // 2),
            "TIPPA TOPP 5 + KLASSFAVORITER · mx-fantasy.se",
            _load_display_font(20, bold=True),
            (8, 15, 30),
            anchor="mm",
        )
        _draw_styled_text(
            draw,
            ((x0 + x1) // 2, y1 - 12),
            "Ordning utifrån tipparnas topp 5 — utan antal. Inte odds.",
            _load_font_px(13, bold=True),
            MUTED,
            anchor="mm",
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
