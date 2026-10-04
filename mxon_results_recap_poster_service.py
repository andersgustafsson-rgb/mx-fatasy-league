"""MXoN post-race recap poster — official nations + Sweden callout + fantasy top."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from hype_poster_service import H_FB, H_STORY, W_FB, W_STORY
from mxon_power_ranking_poster_service import (
    BG_CARD,
    CYAN,
    EMERALD,
    LINE,
    MEDAL_COLORS,
    ROW_BG,
    _backdrop,
    _flag_filename,
    _paste_flag,
    _resolve_mxon_competition,
)
from social_recap_service import (
    MUTED,
    WHITE,
    _draw_styled_text,
    _load_brand_logo,
    _load_display_font,
    _load_font_px,
    _plain_draw_text,
    _race_leaderboard,
    _text_width,
)

_ROOT = Path(__file__).resolve().parent

# Official FIM points from Ernée 2026 combined (Racer X) — display only
_ERNEE_2026_NATION_PTS: dict[str, int] = {
    "BEL": 23, "ESP": 26, "NED": 34, "LAT": 52, "USA": 53,
    "ITA": 69, "GBR": 82, "SUI": 82, "AUS": 87, "FRA": 90,
    "SWE": 95, "EST": 109, "SLO": 110, "CAN": 110, "RSA": 112,
    "GER": 127, "BRA": 133, "SVK": 142, "AUT": 145, "DEN": 94,
}


def _txt(
    draw,
    pos: tuple[int, int],
    text: str,
    font,
    fill: tuple[int, int, int],
    *,
    anchor: str = "lt",
) -> None:
    _draw_styled_text(draw, pos, _plain_draw_text(str(text or "")), font, fill, anchor=anchor)


def build_mxon_results_recap_data(competition_id: int | None = None) -> dict[str, Any]:
    from models import MxonNation, MxonNationResult
    from mxon_fantasy import get_class_results, mxon_has_official_results

    comp = _resolve_mxon_competition(competition_id)
    cid = int(comp.id)
    if not mxon_has_official_results(cid):
        raise ValueError("Inga officiella MXoN-resultat sparade ännu")

    rows = (
        MxonNationResult.query.filter_by(competition_id=cid)
        .order_by(MxonNationResult.position.asc())
        .all()
    )
    nations: list[dict[str, Any]] = []
    sweden: dict[str, Any] | None = None
    for r in rows:
        n = r.nation or MxonNation.query.get(r.nation_id)
        code = (n.code if n else "") or ""
        item = {
            "place": int(r.position),
            "code": code.upper(),
            "name": (n.name if n else code) or "?",
            "flag": _flag_filename(code),
            "pts": _ERNEE_2026_NATION_PTS.get(code.upper()),
        }
        nations.append(item)
        if code.upper() == "SWE":
            sweden = item

    class_results = get_class_results(cid)
    class_winners: list[dict[str, Any]] = []
    for key, label in (("mxgp", "MXGP"), ("mx2", "MX2"), ("open", "OPEN")):
        cr = class_results.get(key) or {}
        code = (cr.get("code") or "").upper()
        rider = cr.get("rider_name") or cr.get("name") or "—"
        if cr.get("is_tba"):
            rider = cr.get("name") or "—"
        class_winners.append(
            {
                "class": label,
                "code": code,
                "name": cr.get("name") or code,
                "rider": rider,
                "flag": _flag_filename(code),
            }
        )

    fantasy = _race_leaderboard(cid, limit=10)
    date_str = ""
    if comp.event_date:
        date_str = comp.event_date.strftime("%Y-%m-%d")

    caption = (
        f"MXoN Ernée 2026 — Resultat!\n"
        f"1) {(nations[0]['name'] if nations else '?')} · "
        f"2) {(nations[1]['name'] if len(nations) > 1 else '?')} · "
        f"3) {(nations[2]['name'] if len(nations) > 2 else '?')}\n"
    )
    if sweden:
        caption += f"Sverige: plats {sweden['place']}\n"
    if fantasy:
        caption += (
            f"Fantasy: 1) {fantasy[0].get('display_name') or fantasy[0].get('username')} "
            f"{fantasy[0].get('points')}p"
        )
        if len(fantasy) > 1 and fantasy[0].get("points") == fantasy[1].get("points"):
            caption += (
                f" (delat med {fantasy[1].get('display_name') or fantasy[1].get('username')})"
            )
        caption += "\n"
    caption += "mx-fantasy.se"

    return {
        "competition_id": cid,
        "race_name": comp.name or "MXoN",
        "date": date_str,
        "nations": nations,
        "sweden": sweden,
        "class_winners": class_winners,
        "fantasy": fantasy,
        "caption": caption,
    }


def _rounded_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, outline=None, radius: int = 18):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 0)


def _medal_color(place: int) -> tuple[int, int, int]:
    return MEDAL_COLORS.get(int(place), MUTED)


def render_mxon_results_recap_png(data: dict[str, Any], *, layout: str = "facebook") -> bytes:
    layout = (layout or "facebook").lower()
    story = layout == "story"
    width, height = (W_STORY, H_STORY) if story else (W_FB, H_FB)

    img = _backdrop(width, height)
    draw = ImageDraw.Draw(img)
    margin = 36 if story else 40

    logo = _load_brand_logo(72 if story else 84)
    if logo:
        img.paste(logo, (margin, margin - 4), logo)
        brand_x = margin + logo.size[0] + 14
    else:
        brand_x = margin
    _txt(draw, (brand_x, margin + 8), "MX FANTASY LEAGUE", _load_display_font(22 if story else 26), CYAN)
    _txt(draw, (brand_x, margin + 36), "mx-fantasy.se", _load_font_px(18 if story else 20), MUTED)

    y = margin + (88 if story else 78)
    _txt(draw, (margin, y), "MXoN ERNEE 2026", _load_display_font(42 if story else 48), WHITE)
    y += 48 if story else 52
    f_kicker = _load_font_px(22 if story else 24, bold=True)
    _txt(draw, (margin, y), "RESULTAT · NATIONER · FANTASY", f_kicker, EMERALD)
    if data.get("date"):
        dw = _text_width(f_kicker, data["date"])
        _txt(draw, (width - margin - dw, y), data["date"], f_kicker, MUTED)
    y += 36 if story else 40

    nations = list(data.get("nations") or [])
    fantasy = list(data.get("fantasy") or [])
    sweden = data.get("sweden")
    class_winners = list(data.get("class_winners") or [])

    if story:
        y = _draw_nations_panel(
            img, draw, nations[:8], margin, y, width - margin * 2,
            title="NATIONSORDNING", max_rows=8, story=True,
        )
        y += 16
        if sweden:
            y = _draw_sweden_banner(img, draw, sweden, margin, y, width - margin * 2, story=True)
            y += 16
        y = _draw_class_row(img, draw, class_winners, margin, y, width - margin * 2, story=True)
        y += 18
        _draw_fantasy_panel(
            img, draw, fantasy[:8], margin, y, width - margin * 2,
            height - margin - 20, story=True,
        )
    else:
        gap = 28
        left_w = int((width - margin * 2 - gap) * 0.56)
        right_w = width - margin * 2 - gap - left_w
        left_x = margin
        right_x = margin + left_w + gap

        col_y = y
        col_y = _draw_nations_panel(
            img, draw, nations[:8], left_x, col_y, left_w,
            title="NATIONSORDNING", max_rows=8, story=False,
        )
        col_y += 14
        if sweden:
            col_y = _draw_sweden_banner(img, draw, sweden, left_x, col_y, left_w, story=False)
            col_y += 14
        _draw_class_row(img, draw, class_winners, left_x, col_y, left_w, story=False)

        _draw_fantasy_panel(
            img, draw, fantasy[:10], right_x, y, right_w,
            height - margin - 16, story=False,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_nations_panel(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    nations: list[dict],
    x: int,
    y: int,
    w: int,
    *,
    title: str,
    max_rows: int,
    story: bool,
) -> int:
    row_h = 48 if story else 52
    head_h = 40
    pad = 14
    h = head_h + pad + row_h * min(len(nations), max_rows) + pad
    _rounded_card(draw, (x, y, x + w, y + h), BG_CARD, outline=LINE, radius=16)
    f_h = _load_font_px(18 if story else 20, bold=True)
    _txt(draw, (x + 16, y + 12), title, f_h, CYAN)

    cy = y + head_h
    f_rank = _load_display_font(22 if story else 24)
    f_name = _load_font_px(20 if story else 22, bold=True)
    f_pts = _load_font_px(18 if story else 20, bold=True)
    flag_h = 28 if story else 30
    flag_w = int(flag_h * 1.5)

    for i, n in enumerate(nations[:max_rows]):
        ry = cy + i * row_h
        if i % 2 == 0:
            draw.rectangle([x + 8, ry, x + w - 8, ry + row_h - 4], fill=ROW_BG)
        place = int(n.get("place") or i + 1)
        mc = _medal_color(place)
        _txt(draw, (x + 18, ry + 10), f"{place}", f_rank, mc)
        fx = x + 56
        fy = ry + (row_h - 4 - flag_h) // 2
        _paste_flag(img, n.get("flag"), (fx, fy, fx + flag_w, fy + flag_h))
        name = n.get("name") or n.get("code") or "?"
        _txt(draw, (fx + flag_w + 12, ry + 12), name, f_name, WHITE)
        pts = n.get("pts")
        if pts is not None:
            label = f"{pts}p"
            tw = _text_width(f_pts, label)
            _txt(draw, (x + w - 18 - tw, ry + 14), label, f_pts, MUTED)

    return y + h


def _draw_sweden_banner(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    sweden: dict,
    x: int,
    y: int,
    w: int,
    *,
    story: bool,
) -> int:
    h = 64 if story else 68
    _rounded_card(draw, (x, y, x + w, y + h), (12, 28, 48), outline=(251, 191, 36), radius=14)
    flag_h = 34
    flag_w = int(flag_h * 1.5)
    fx, fy = x + 16, y + (h - flag_h) // 2
    _paste_flag(img, sweden.get("flag") or "se.png", (fx, fy, fx + flag_w, fy + flag_h))
    f_t = _load_font_px(18 if story else 20, bold=True)
    f_b = _load_display_font(26 if story else 28)
    _txt(draw, (fx + flag_w + 14, y + 10), "SVERIGE", f_t, (251, 191, 36))
    place = sweden.get("place")
    pts = sweden.get("pts")
    line = f"Plats {place}"
    if pts is not None:
        line += f"  ·  {pts}p"
    _txt(draw, (fx + flag_w + 14, y + 32), line, f_b, WHITE)
    return y + h


def _draw_class_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    winners: list[dict],
    x: int,
    y: int,
    w: int,
    *,
    story: bool,
) -> int:
    if not winners:
        return y
    gap = 10
    cw = (w - gap * (len(winners) - 1)) // max(len(winners), 1)
    h = 86 if story else 90
    f_cls = _load_font_px(14, bold=True)
    f_name = _load_font_px(16 if story else 17, bold=True)
    f_rider = _load_font_px(14 if story else 15)
    flag_h = 22
    flag_w = int(flag_h * 1.5)

    for i, cwinner in enumerate(winners):
        cx = x + i * (cw + gap)
        _rounded_card(draw, (cx, y, cx + cw, y + h), BG_CARD, outline=LINE, radius=12)
        _txt(draw, (cx + 12, y + 8), cwinner.get("class") or "", f_cls, EMERALD)
        fx, fy = cx + 12, y + 32
        _paste_flag(img, cwinner.get("flag"), (fx, fy, fx + flag_w, fy + flag_h))
        code = cwinner.get("code") or ""
        _txt(draw, (fx + flag_w + 8, y + 32), code, f_name, WHITE)
        rider = (cwinner.get("rider") or "")[:22]
        _txt(draw, (cx + 12, y + 60), rider, f_rider, MUTED)
    return y + h


def _draw_fantasy_panel(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    fantasy: list[dict],
    x: int,
    y: int,
    w: int,
    y_bottom: int,
    *,
    story: bool,
) -> int:
    h = max(120, y_bottom - y)
    _rounded_card(draw, (x, y, x + w, y + h), BG_CARD, outline=LINE, radius=16)
    f_h = _load_font_px(18 if story else 20, bold=True)
    _txt(draw, (x + 16, y + 12), "FANTASY TOPPEN", f_h, CYAN)

    row_h = 44 if story else 48
    cy = y + 42
    f_rank = _load_display_font(20 if story else 22)
    f_name = _load_font_px(18 if story else 20, bold=True)
    f_pts = _load_font_px(18 if story else 20, bold=True)

    max_rows = max(1, (h - 56) // row_h)
    for i, row in enumerate(fantasy[:max_rows]):
        ry = cy + i * row_h
        if ry + row_h > y + h - 8:
            break
        if i % 2 == 0:
            draw.rectangle([x + 8, ry, x + w - 8, ry + row_h - 4], fill=ROW_BG)
        rank = int(row.get("rank") or i + 1)
        mc = _medal_color(rank)
        _txt(draw, (x + 18, ry + 10), f"{rank}", f_rank, mc)
        name = row.get("display_name") or row.get("username") or "?"
        max_name_w = w - 120
        while _text_width(f_name, name) > max_name_w and len(name) > 3:
            name = name[:-2] + "…"
        _txt(draw, (x + 52, ry + 12), name, f_name, WHITE)
        pts = f"{int(row.get('points') or 0)}p"
        tw = _text_width(f_pts, pts)
        _txt(draw, (x + w - 18 - tw, ry + 12), pts, f_pts, CYAN)

    return y + h
