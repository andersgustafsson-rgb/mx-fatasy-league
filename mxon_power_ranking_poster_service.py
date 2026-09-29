"""MXoN crowd power-ranking posters for Facebook feed + Stories."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from hype_poster_service import H_FB, H_STORY, W_FB, W_STORY, _cover_crop
from social_recap_service import (
    MUTED,
    WHITE,
    _draw_styled_text,
    _load_brand_logo,
    _load_display_font,
    _load_font_px,
    _plain_draw_text,
    _text_width,
)

_ROOT = Path(__file__).resolve().parent

# Cool modern palette — no loud yellow chrome
CYAN = (103, 232, 249)       # ice cyan accent
EMERALD = (52, 211, 153)     # class / secondary
LINE = (51, 65, 85)          # slate border
LINE_SOFT = (71, 85, 105)
BG_CARD = (10, 14, 26)
ROW_BG = (16, 22, 38)
CTA_BG = (15, 118, 110)      # deep teal button
CTA_TEXT = (236, 253, 245)

MEDAL_COLORS = {
    1: (251, 191, 36),   # gold — ranks only
    2: (226, 232, 240),  # bright silver
    3: (217, 119, 6),    # bronze
}


def _resolve_competition(competition_id: int | None = None):
    from models import Competition

    if competition_id:
        c = Competition.query.get(int(competition_id))
        if not c:
            raise ValueError("Tävlingen hittades inte")
        return c
    raise ValueError("competition_id krävs")


def _resolve_mxon_competition(competition_id: int | None = None):
    from models import Competition

    if competition_id:
        c = Competition.query.get(int(competition_id))
        if c and (c.series or "").upper() == "MXON":
            return c
        raise ValueError("competition_id is not an MXoN race")

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
    for i in range(5):
        y0 = int(height * 0.18) + i * 58
        sd.line(
            [(-40, y0), (width + 40, y0 + int(height * 0.08))],
            fill=(CYAN[0], CYAN[1], CYAN[2], 14 - i * 2),
            width=2,
        )
    streak = streak.filter(ImageFilter.GaussianBlur(1.4))
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
        "kind": "mxon_crowd",
        "series": "MXON",
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
        "pill": "MXoN · ERNÉE 2026",
    }


def _rider_rows_for_caption(rows: list[dict] | None, label: str) -> list[str]:
    lines: list[str] = []
    if not rows:
        return lines
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines.append(f"{label}:")
    for r in rows[:3]:
        rank = int(r.get("rank") or 0)
        prefix = medals.get(rank, f"#{rank}")
        num = r.get("number")
        name = r.get("name") or "—"
        pct = r.get("strength_pct")
        num_s = f"#{num} " if num is not None else ""
        pct_s = f" ({pct}%)" if pct is not None else ""
        lines.append(f"{prefix} {num_s}{name}{pct_s}")
    return lines


def _build_rider_power_poster_data(competition_id: int) -> dict[str, Any]:
    """AMA / WSX / MXGP / SMX power ranking poster from build_power_ranking_payload."""
    from models import Competition

    # Import from main lazily (Flask app module)
    from main import build_power_ranking_payload

    comp = Competition.query.get(int(competition_id))
    if not comp:
        raise ValueError("Tävlingen hittades inte")
    series = (comp.series or "").upper()
    if series == "MXON":
        raise ValueError("Use mxon crowd builder for MXoN")

    payload = build_power_ranking_payload(comp)
    if not payload.get("ok"):
        raise ValueError("Kunde inte bygga power ranking")

    label_450 = payload.get("label_450") or "450cc"
    label_250 = payload.get("label_250") or "250cc"
    riders_450 = list(payload.get("riders_450") or [])[:3]
    riders_250 = list(payload.get("riders_250") or [])[:3]
    riders_250_east = list(payload.get("riders_250_east") or [])[:3]
    riders_250_west = list(payload.get("riders_250_west") or [])[:3]

    has_any = bool(riders_450 or riders_250 or riders_250_east or riders_250_west)
    if not has_any:
        raise ValueError("Ingen power-ranking-data för den här tävlingen ännu")

    event_name = (comp.name or series).strip()
    caption_lines = [
        f"🏁 {event_name} — Power rankings!",
        "",
        "Form + tipparnas picks — inte odds.",
        "",
    ]
    caption_lines.extend(_rider_rows_for_caption(riders_450, label_450))
    if riders_250_east or riders_250_west:
        caption_lines.append("")
        caption_lines.extend(_rider_rows_for_caption(riders_250_east, f"{label_250} East"))
        caption_lines.append("")
        caption_lines.extend(_rider_rows_for_caption(riders_250_west, f"{label_250} West"))
    elif riders_250:
        caption_lines.append("")
        caption_lines.extend(_rider_rows_for_caption(riders_250, label_250))
    locked = "låsta" if payload.get("crowd_picks_locked") else "öppna"
    caption_lines.extend(
        [
            "",
            f"Picks {locked} · tippa gratis på mx-fantasy.se",
            "",
            "👉 mx-fantasy.se",
            "",
            f"#MXFantasy #PowerRankings #{series} #{event_name.replace(' ', '')}",
        ]
    )

    hero_static = None
    try:
        from trackmap_utils import resolve_competition_hero_static_url

        hero_static = resolve_competition_hero_static_url(comp)
    except Exception:
        hero_static = None

    return {
        "ok": True,
        "kind": "rider_power",
        "series": series,
        "competition_id": int(comp.id),
        "competition_name": event_name,
        "event_date": comp.event_date.isoformat() if comp.event_date else None,
        "picks_locked": bool(payload.get("crowd_picks_locked")),
        "label_450": label_450,
        "label_250": label_250,
        "riders_450": riders_450,
        "riders_250": riders_250,
        "riders_250_east": riders_250_east,
        "riders_250_west": riders_250_west,
        "caption": "\n".join(caption_lines),
        "method": payload.get("method"),
        "form_scope_label": payload.get("form_scope_label"),
        "title": "POWER RANKINGS",
        "subtitle": payload.get("form_scope_label")
        or "Form + tipparnas picks",
        "pill": f"{series} · {event_name}"[:42],
        "hero_static": hero_static,
        "crowd_users": payload.get("crowd_users"),
    }


def build_power_ranking_poster_data(competition_id: int | None = None) -> dict[str, Any]:
    """
    Unified poster data for any series.
    MXoN → crowd nations/classes; others → rider power rankings.
    """
    if competition_id is None:
        # Backward-compat: default to latest MXoN if no id (old studio / script)
        return build_mxon_power_ranking_poster_data(None)

    comp = _resolve_competition(int(competition_id))
    series = (comp.series or "").upper()
    if series == "MXON":
        return build_mxon_power_ranking_poster_data(int(comp.id))
    return _build_rider_power_poster_data(int(comp.id))


def _draw_brand_strip(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    story: bool,
    pill: str = "POWER RANKINGS",
    accent: tuple[int, int, int] = CYAN,
) -> int:
    margin = 40 if story else 44
    top_h = 96 if story else 78
    draw.rectangle([0, 0, width, top_h], fill=(6, 10, 20))
    draw.rectangle([0, top_h, width, top_h + 2], fill=accent)

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
        WHITE,
        anchor="lm",
    )
    _draw_styled_text(
        draw,
        (brand_x, top_h // 2 + 16),
        "TIPPA GRATIS · mx-fantasy.se",
        _load_font_px(15 if story else 14, bold=True),
        accent,
        anchor="lm",
    )

    pill_txt = (pill or "POWER RANKINGS").strip()
    pf = _load_font_px(15 if story else 16, bold=True)
    pw = min(_text_width(pf, pill_txt) + 28, width - margin * 2 - 220)
    ph = 32
    draw.rounded_rectangle(
        [width - margin - pw, (top_h - ph) // 2, width - margin, (top_h - ph) // 2 + ph],
        radius=16,
        fill=(8, 24, 32),
        outline=accent,
        width=1,
    )
    _draw_styled_text(
        draw,
        (width - margin - pw // 2, top_h // 2),
        _plain_draw_text(pill_txt),
        pf,
        WHITE,
        anchor="mm",
    )
    return top_h + 2


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
        radius=10,
        fill=ROW_BG,
        outline=LINE,
        width=1,
    )
    # Subtle left accent for top 3
    if rank in (1, 2, 3):
        draw.rounded_rectangle(
            [x0, y + 6, x0 + 4, y + row_h - 6],
            radius=2,
            fill=MEDAL_COLORS[rank],
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
        radius=12,
        fill=ROW_BG,
        outline=LINE_SOFT,
        width=1,
    )
    _draw_styled_text(
        draw,
        (x0 + 14, y0 + 12),
        str(cl.get("class_label") or "").upper(),
        _load_font_px(13 if story else 14, bold=True),
        EMERALD,
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


def _accent_for_series(series: str) -> tuple[int, int, int]:
    try:
        from hype_poster_service import _series_colors

        return _series_colors(series)[0]
    except Exception:
        return CYAN


def _paste_rider_portrait(
    base: Image.Image,
    image_url: str | None,
    box: tuple[int, int, int, int],
) -> None:
    if not image_url:
        return
    try:
        from hype_poster_service import _resolve_hero_path

        path = _resolve_hero_path(image_url)
        if path is None:
            # relative riders/... under static
            s = str(image_url).strip().lstrip("/")
            if s.startswith("static/"):
                s = s[len("static/") :]
            path = _ROOT / "static" / s
            if not path.is_file():
                return
        av = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = box
        tw, th = max(1, x1 - x0), max(1, y1 - y0)
        # cover-crop square-ish face
        side = min(av.size)
        left = (av.size[0] - side) // 2
        top = max(0, (av.size[1] - side) // 5)
        av = av.crop((left, top, left + side, top + side))
        av = av.resize((tw, th), Image.Resampling.LANCZOS)
        # circular mask
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, tw - 1, th - 1], fill=255)
        base.paste(av, (x0, y0), mask)
    except Exception:
        pass


def _draw_rider_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x0: int,
    x1: int,
    y: int,
    row_h: int,
    rider: dict[str, Any],
    accent: tuple[int, int, int],
) -> ImageDraw.ImageDraw:
    rank = int(rider.get("rank") or 0)
    draw.rounded_rectangle([x0, y, x1, y + row_h], radius=10, fill=ROW_BG, outline=LINE, width=1)
    if rank in (1, 2, 3):
        draw.rounded_rectangle(
            [x0, y + 6, x0 + 4, y + row_h - 6],
            radius=2,
            fill=MEDAL_COLORS[rank],
        )
    _draw_styled_text(
        draw,
        (x0 + 16, y + row_h // 2),
        _medal_label(rank),
        _load_display_font(18, bold=True),
        MEDAL_COLORS.get(rank, MUTED),
        anchor="lm",
    )
    av_size = row_h - 16
    ax = x0 + 58
    _paste_rider_portrait(
        img,
        rider.get("image_url"),
        (ax, y + (row_h - av_size) // 2, ax + av_size, y + (row_h - av_size) // 2 + av_size),
    )
    draw = ImageDraw.Draw(img)
    num = rider.get("number")
    name = rider.get("name") or "—"
    label = f"#{num} {_plain_draw_text(str(name))}" if num is not None else _plain_draw_text(str(name))
    _draw_styled_text(
        draw,
        (ax + av_size + 12, y + row_h // 2),
        label,
        _load_display_font(18, bold=True),
        WHITE,
        anchor="lm",
    )
    pct = rider.get("strength_pct")
    if pct is not None:
        _draw_styled_text(
            draw,
            (x1 - 14, y + row_h // 2),
            f"{pct}%",
            _load_font_px(16, bold=True),
            accent,
            anchor="rm",
        )
    return draw


def _render_rider_power_poster(data: dict[str, Any], *, layout: str) -> bytes:
    from hype_poster_service import _paint_cinematic_backdrop, _series_colors

    story = layout == "story"
    width, height = (W_STORY, H_STORY) if story else (W_FB, H_FB)
    margin = 40 if story else 44
    series = str(data.get("series") or "")
    accent, accent2 = _series_colors(series)
    # Prefer cool cyan for chrome; keep series accent for highlights
    chrome = CYAN if series.upper() in ("SX", "MX", "SMX", "WSX", "MXGP") else accent

    backdrop_data = {
        "hero_static": data.get("hero_static"),
        "series": series,
        "competition_name": data.get("competition_name"),
    }
    try:
        img = _paint_cinematic_backdrop(width, height, backdrop_data, accent)
    except Exception:
        img = Image.new("RGB", (width, height), (10, 14, 28))

    draw = ImageDraw.Draw(img)
    top = _draw_brand_strip(
        img,
        draw,
        width=width,
        story=story,
        pill=str(data.get("pill") or series),
        accent=chrome,
    )

    label_450 = str(data.get("label_450") or "450cc")
    label_250 = str(data.get("label_250") or "250cc")
    riders_450 = list(data.get("riders_450") or [])[:3]
    riders_250 = list(data.get("riders_250") or [])[:3]
    riders_250_east = list(data.get("riders_250_east") or [])[:3]
    riders_250_west = list(data.get("riders_250_west") or [])[:3]
    split_250 = bool(riders_250_east or riders_250_west)

    card = (margin, top + (28 if story else 18), width - margin, height - margin)
    x0, y0, x1, y1 = card
    draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=BG_CARD, outline=LINE_SOFT, width=1)
    draw.rectangle([x0 + 28, y0, x1 - 28, y0 + 3], fill=chrome)

    y = y0 + 20
    title = str(data.get("title") or "POWER RANKINGS")
    if story:
        cx = (x0 + x1) // 2
        _draw_styled_text(draw, (cx, y), title, _load_display_font(28, bold=True), WHITE, anchor="mt")
        y += 38
        _draw_styled_text(
            draw,
            (cx, y),
            _plain_draw_text(str(data.get("subtitle") or "")),
            _load_font_px(15, bold=True),
            accent2,
            anchor="mt",
        )
        y += 32
        sections: list[tuple[str, list]] = [(label_450, riders_450)]
        if split_250:
            sections.append((f"{label_250} East", riders_250_east))
            sections.append((f"{label_250} West", riders_250_west))
        else:
            sections.append((label_250, riders_250))
        row_h = 56
        for sec_label, rows in sections:
            if not rows:
                continue
            _draw_styled_text(
                draw, (x0 + 28, y), sec_label.upper(), _load_font_px(13, bold=True), chrome, anchor="lt"
            )
            y += 24
            for r in rows:
                draw = _draw_rider_row(
                    img, draw, x0=x0 + 24, x1=x1 - 24, y=y, row_h=row_h, rider=r, accent=chrome
                )
                y += row_h + 8
            y += 10
        btn_h = 52
        btn_y = min(y + 4, y1 - btn_h - 24)
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=12, fill=CTA_BG)
        _draw_styled_text(
            draw,
            (cx, btn_y + btn_h // 2),
            "TIPPA NU · mx-fantasy.se",
            _load_display_font(18, bold=True),
            CTA_TEXT,
            anchor="mm",
        )
    else:
        _draw_styled_text(draw, (x0 + 36, y), title, _load_display_font(34, bold=True), WHITE, anchor="lt")
        _draw_styled_text(
            draw,
            (x1 - 36, y + 8),
            _plain_draw_text(str(data.get("competition_name") or "")),
            _load_font_px(15, bold=True),
            MUTED,
            anchor="rt",
        )
        y += 40
        _draw_styled_text(
            draw,
            (x0 + 36, y),
            _plain_draw_text(str(data.get("subtitle") or "")),
            _load_font_px(15, bold=True),
            accent2,
            anchor="lt",
        )
        y += 30

        mid = (x0 + x1) // 2
        left_x0, left_x1 = x0 + 28, mid - 14
        right_x0, right_x1 = mid + 14, x1 - 28
        row_h = 62

        _draw_styled_text(
            draw, (left_x0 + 6, y), label_450.upper(), _load_font_px(13, bold=True), chrome, anchor="lt"
        )
        right_title = (
            f"{label_250} EAST / WEST" if split_250 else label_250.upper()
        )
        _draw_styled_text(
            draw, (right_x0 + 6, y), right_title, _load_font_px(13, bold=True), chrome, anchor="lt"
        )
        y += 24

        ly = y
        for r in riders_450:
            draw = _draw_rider_row(
                img, draw, x0=left_x0, x1=left_x1, y=ly, row_h=row_h, rider=r, accent=chrome
            )
            ly += row_h + 8

        ry = y
        if split_250:
            half = (row_h * 3 + 16) // 2
            for r in riders_250_east:
                draw = _draw_rider_row(
                    img, draw, x0=right_x0, x1=right_x1, y=ry, row_h=half - 4, rider=r, accent=chrome
                )
                ry += half
            for r in riders_250_west:
                draw = _draw_rider_row(
                    img, draw, x0=right_x0, x1=right_x1, y=ry, row_h=half - 4, rider=r, accent=chrome
                )
                ry += half
        else:
            for r in riders_250:
                draw = _draw_rider_row(
                    img, draw, x0=right_x0, x1=right_x1, y=ry, row_h=row_h, rider=r, accent=chrome
                )
                ry += row_h + 8

        btn_h = 50
        btn_y = y1 - 26 - btn_h
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=12, fill=CTA_BG)
        _draw_styled_text(
            draw,
            ((x0 + x1) // 2, btn_y + btn_h // 2),
            "TIPPA NU · mx-fantasy.se",
            _load_display_font(18, bold=True),
            CTA_TEXT,
            anchor="mm",
        )
        method = data.get("method")
        if method:
            _draw_styled_text(
                draw,
                ((x0 + x1) // 2, y1 - 12),
                _plain_draw_text(str(method)[:110]),
                _load_font_px(12, bold=True),
                MUTED,
                anchor="mm",
            )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_mxon_crowd_poster(data: dict[str, Any], *, layout: str) -> bytes:
    story = layout == "story"
    width, height = (W_STORY, H_STORY) if story else (W_FB, H_FB)
    margin = 40 if story else 44

    img = _backdrop(width, height)
    draw = ImageDraw.Draw(img)
    top = _draw_brand_strip(
        img,
        draw,
        width=width,
        story=story,
        pill=str(data.get("pill") or "MXoN · ERNÉE 2026"),
        accent=CYAN,
    )

    nations = list(data.get("nations") or [])[:5]
    classes = list(data.get("classes") or [])[:3]

    if story:
        card = (margin, top + 28, width - margin, height - margin)
        x0, y0, x1, y1 = card
        draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=BG_CARD, outline=LINE_SOFT, width=1)
        draw.rectangle([x0 + 24, y0, x1 - 24, y0 + 3], fill=CYAN)

        y = y0 + 24
        cx = (x0 + x1) // 2
        _draw_styled_text(
            draw,
            (cx, y),
            str(data.get("title") or "CROWD POWER RANKINGS"),
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
            EMERALD,
            anchor="mt",
        )
        y += 36

        _draw_styled_text(draw, (x0 + 28, y), "NATIONER", _load_font_px(13, bold=True), CYAN, anchor="lt")
        y += 28
        row_h = 64
        for n in nations:
            draw = _draw_nation_row(img, draw, x0=x0 + 24, x1=x1 - 24, y=y, row_h=row_h, nation=n, story=True)
            y += row_h + 10

        y += 12
        _draw_styled_text(
            draw, (x0 + 28, y), "KLASSFAVORITER", _load_font_px(13, bold=True), CYAN, anchor="lt"
        )
        y += 26
        card_h = 110
        gap = 12
        for cl in classes:
            draw = _draw_class_card(
                img, draw, box=(x0 + 24, y, x1 - 24, y + card_h), cl=cl, story=True
            )
            y += card_h + gap

        btn_h = 56
        btn_y = min(y + 8, y1 - btn_h - 28)
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=14, fill=CTA_BG)
        _draw_styled_text(
            draw,
            (cx, btn_y + btn_h // 2),
            "TIPPA MXoN · mx-fantasy.se",
            _load_display_font(20, bold=True),
            CTA_TEXT,
            anchor="mm",
        )
    else:
        card = (margin, top + 18, width - margin, height - margin)
        x0, y0, x1, y1 = card
        draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=BG_CARD, outline=LINE_SOFT, width=1)
        draw.rectangle([x0 + 28, y0, x1 - 28, y0 + 3], fill=CYAN)

        y = y0 + 20
        _draw_styled_text(
            draw,
            (x0 + 36, y),
            str(data.get("title") or "CROWD POWER RANKINGS"),
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
            EMERALD,
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
            CYAN,
            anchor="lt",
        )
        _draw_styled_text(
            draw, (right_x0 + 8, y), "KLASSFAVORITER", _load_font_px(13, bold=True), CYAN, anchor="lt"
        )
        y += 26

        row_h = 58
        ny = y
        for n in nations:
            draw = _draw_nation_row(
                img, draw, x0=left_x0, x1=left_x1, y=ny, row_h=row_h, nation=n, story=False
            )
            ny += row_h + 10

        avail_h = (y1 - 90) - y
        n_cls = max(1, len(classes))
        gap = 10
        card_h = max(88, (avail_h - gap * (n_cls - 1)) // n_cls)
        card_h = min(card_h, 120)
        cy = y
        for cl in classes:
            draw = _draw_class_card(
                img, draw, box=(right_x0, cy, right_x1, cy + card_h), cl=cl, story=False
            )
            cy += card_h + gap

        btn_h = 52
        btn_y = y1 - 28 - btn_h
        draw.rounded_rectangle([x0 + 28, btn_y, x1 - 28, btn_y + btn_h], radius=12, fill=CTA_BG)
        _draw_styled_text(
            draw,
            ((x0 + x1) // 2, btn_y + btn_h // 2),
            "TIPPA TOPP 5 + KLASSFAVORITER · mx-fantasy.se",
            _load_display_font(20, bold=True),
            CTA_TEXT,
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


def render_power_ranking_poster_png(
    data: dict[str, Any] | None = None,
    *,
    competition_id: int | None = None,
    layout: str = "facebook",
) -> bytes:
    """Render Facebook/Story PNG for MXoN crowd or rider power rankings."""
    if data is None:
        data = build_power_ranking_poster_data(competition_id)
    layout = (layout or "facebook").strip().lower()
    kind = (data.get("kind") or "mxon_crowd").lower()
    if kind == "rider_power":
        return _render_rider_power_poster(data, layout=layout)
    return _render_mxon_crowd_poster(data, layout=layout)


def render_mxon_power_ranking_poster_png(
    data: dict[str, Any] | None = None,
    *,
    competition_id: int | None = None,
    layout: str = "facebook",
) -> bytes:
    """Backward-compatible alias."""
    return render_power_ranking_poster_png(
        data, competition_id=competition_id, layout=layout
    )
