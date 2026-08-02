"""Race-hype invite card — PNG for Snap/Stories and og:image previews."""
from __future__ import annotations

import io
import textwrap
from datetime import datetime, timedelta
from typing import Any

from models import User, db

W_STORY = 1080
H_STORY = 1920
W_OG = 1200
H_OG = 630


def _format_deadline_countdown(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    if total <= 0:
        return "Stängt"
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def build_invite_card_data(ref: str | None = None, *, prefer_series: str | None = None) -> dict[str, Any]:
    """Aggregate race + inviter context for invite card rendering."""
    from main import _competition_race_schedule, _next_open_picks_competition, get_current_time, get_today
    from models import Competition
    from track_weather import build_picks_weather_tips, get_weather_for_competition

    inviter = None
    ref_clean = (ref or "").strip()
    if ref_clean:
        inviter = User.query.filter(db.func.lower(User.username) == ref_clean.lower()).first()

    prefer = (prefer_series or "").strip().upper() or None
    comp = None
    if prefer == "WSX":
        today = get_today()
        upcoming_wsx = (
            Competition.query.filter(
                Competition.series == "WSX",
                Competition.event_date.isnot(None),
                Competition.event_date >= today,
            )
            .order_by(Competition.event_date.asc())
            .first()
        )
        comp = upcoming_wsx
    if comp is None:
        comp = _next_open_picks_competition()

    race_name = comp.name if comp else "MX Fantasy League"
    series = getattr(comp, "series", None) if comp else None
    event_date = getattr(comp, "event_date", None) if comp else None

    race_start_display = None
    stockholm_display = None
    deadline_countdown = None
    deadline_display = None
    event_countdown = None
    event_date_display = None
    location_line = None

    if event_date:
        try:
            event_date_display = event_date.strftime("%d %b %Y")
        except Exception:
            event_date_display = str(event_date)
        try:
            today = get_today()
            days = (event_date - today).days
            if days > 1:
                event_countdown = f"{days} dagar"
            elif days == 1:
                event_countdown = "I morgon"
            elif days == 0:
                event_countdown = "I dag"
            else:
                event_countdown = None
        except Exception:
            pass

    if series == "WSX" and race_name:
        loc_map = {
            "canadian gp": "Calgary · McMahon Stadium",
            "british gp": "Birmingham",
            "buenos aires": "Buenos Aires",
            "australian gp": "Australia",
            "new zealand": "New Zealand",
            "south african": "South Africa",
            "swedish gp": "Sweden",
        }
        key = race_name.lower()
        for needle, loc in loc_map.items():
            if needle in key:
                location_line = loc
                break
        if not location_line:
            location_line = "World Supercross"

    if comp:
        try:
            sched = _competition_race_schedule(comp)
            race_start_display = sched.get("stockholm_display") or sched.get("race_start_display")
            stockholm_display = sched.get("stockholm_display")
            deadline_display = sched.get("pick_deadline_display")
            deadline_utc = sched.get("deadline_utc")
            if deadline_utc:
                now = get_current_time()
                if getattr(now, "tzinfo", None):
                    now = now.replace(tzinfo=None)
                delta = deadline_utc - now
                if delta.total_seconds() > 0:
                    deadline_countdown = _format_deadline_countdown(delta)
        except Exception:
            pass

    weather_line = None
    weather_tip = None
    if comp:
        weather = get_weather_for_competition(comp)
        if weather.get("available"):
            parts = []
            tmax = weather.get("temp_max_c")
            if tmax is not None:
                parts.append(f"{int(round(float(tmax)))}°C")
            label = (weather.get("label_sv") or "").strip()
            if label:
                parts.append(label)
            if parts:
                weather_line = " · ".join(parts)
            tips = build_picks_weather_tips(weather, series=series)
            if tips:
                weather_tip = tips[0]
            elif series == "SX" and weather_line:
                weather_tip = "Stadium-race — fokusera på form och startrit."

    inviter_name = None
    inviter_username = None
    if inviter:
        inviter_username = inviter.username
        inviter_name = (inviter.display_name or inviter.username or "").strip()

    try:
        from public_url import get_public_base_url

        base_host = get_public_base_url().replace("https://", "").replace("http://", "").rstrip("/")
    except Exception:
        base_host = "mx-fantasy.se"
    host_line = f"{base_host}/start"
    if inviter_username:
        host_line += f"?ref={inviter_username}"

    top5: list[dict[str, Any]] = []
    try:
        from main import calculate_leaderboard_deltas

        for i, row in enumerate(calculate_leaderboard_deltas()[:5], 1):
            name = (row.get("display_name") or row.get("username") or "?").strip()
            username = (row.get("username") or "").strip()
            top5.append(
                {
                    "rank": int(row.get("rank") or i),
                    "name": name,
                    "username": username,
                    "points": int(row.get("total_points") or 0),
                    "is_me": bool(
                        inviter_username
                        and username
                        and username.lower() == inviter_username.lower()
                    ),
                }
            )
    except Exception:
        top5 = []

    return {
        "race_name": race_name,
        "series": series,
        "race_start_display": race_start_display,
        "stockholm_display": stockholm_display,
        "deadline_display": deadline_display,
        "deadline_countdown": deadline_countdown,
        "event_date_display": event_date_display,
        "event_countdown": event_countdown,
        "location_line": location_line,
        "weather_line": weather_line,
        "weather_tip": weather_tip,
        "inviter_name": inviter_name,
        "inviter_username": inviter_username,
        "host_line": host_line,
        "has_race": comp is not None,
        "top5": top5,
        "is_wsx_hype": series == "WSX",
    }


def render_invite_card_png(data: dict[str, Any], *, layout: str = "story") -> bytes:
    """Render race-hype invite card PNG (story 1080x1920 or og 1200x630)."""
    layout = (layout or "story").lower()
    if layout == "og":
        return _render_og_card(data)
    if data.get("is_wsx_hype") or (data.get("series") or "").upper() == "WSX":
        return _render_wsx_story_card(data)
    return _render_story_card(data)


def _render_wsx_story_card(data: dict[str, Any]) -> bytes:
    """Vertical 9:16 WSX season-hype card for Snap / IG Stories / Reels stills."""
    from PIL import Image, ImageDraw

    from social_recap_service import (
        CYAN,
        GOLD,
        MUTED,
        WHITE,
        _draw_styled_text,
        _font_height,
        _footer,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
        _text_width,
    )

    # Deep night + ember accents — feels more “championship night” than default cyan card.
    bg_top = (12, 8, 28)
    bg_bot = (6, 14, 32)
    ember = (255, 90, 40)
    ember_soft = (255, 140, 70)
    panel = (18, 22, 44)
    panel_edge = (70, 55, 110)

    img = Image.new("RGB", (W_STORY, H_STORY), bg_bot)
    # Manual vertical blend
    px = img.load()
    for y in range(H_STORY):
        t = y / max(H_STORY - 1, 1)
        r = int(bg_top[0] * (1 - t) + bg_bot[0] * t)
        g = int(bg_top[1] * (1 - t) + bg_bot[1] * t)
        b = int(bg_top[2] * (1 - t) + bg_bot[2] * t)
        for x in range(W_STORY):
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)

    margin = 56
    draw.rectangle([0, 0, W_STORY, 12], fill=ember)
    draw.rectangle([0, H_STORY - 12, W_STORY, H_STORY], fill=CYAN)

    y = 56
    logo = _load_brand_logo(110)
    if logo:
        img.paste(logo, (margin, y), logo)
    brand_f = _load_display_font(30, bold=True)
    _draw_styled_text(
        draw, (margin + 130, y + 24), "MX FANTASY LEAGUE", brand_f, CYAN, anchor="lm"
    )
    _draw_styled_text(
        draw, (margin + 130, y + 64), "TIPPA WSX GRATIS", _load_font_px(22), MUTED, anchor="lm"
    )
    y += 150

    # Season pill
    pill_f = _load_display_font(30, bold=True)
    pill_text = "WSX 2026"
    pill_w = _text_width(pill_f, pill_text) + 56
    pill_h = 56
    px0 = (W_STORY - pill_w) // 2
    draw.rounded_rectangle(
        [px0, y, px0 + pill_w, y + pill_h], radius=28, fill=(48, 18, 12), outline=ember, width=3
    )
    _draw_styled_text(draw, (W_STORY // 2, y + pill_h // 2), pill_text, pill_f, ember_soft, anchor="mm")
    y += pill_h + 42

    race_name = _plain_draw_text(data.get("race_name") or "World Supercross")
    race_f = _load_display_font(78, bold=True)
    for size in (78, 68, 58, 48):
        race_f = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=14)
        if len(lines) <= 2:
            break
    line_h = _font_height(race_f, "Ay") + 10
    for line in lines[:2]:
        _draw_styled_text(
            draw,
            (W_STORY // 2, y),
            line,
            race_f,
            WHITE,
            anchor="mt",
            stroke=(20, 10, 8),
            stroke_width=4,
        )
        y += line_h
    y += 12

    loc = _plain_draw_text(data.get("location_line") or "World Supercross")
    _draw_styled_text(draw, (W_STORY // 2, y), loc.upper(), _load_font_px(30, bold=True), GOLD, anchor="mt")
    y += 48

    # Countdown panel
    panel_x1, panel_x2 = margin, W_STORY - margin
    panel_y1 = y
    panel_y2 = panel_y1 + 300
    draw.rounded_rectangle(
        [panel_x1, panel_y1, panel_x2, panel_y2], radius=28, fill=panel, outline=panel_edge, width=2
    )
    py = panel_y1 + 36
    event_cd = data.get("event_countdown")
    if event_cd:
        _draw_styled_text(draw, (W_STORY // 2, py), "COUNTDOWN", _load_font_px(24), MUTED, anchor="mt")
        py += 40
        _draw_styled_text(
            draw,
            (W_STORY // 2, py),
            _plain_draw_text(event_cd).upper(),
            _load_display_font(64, bold=True),
            ember_soft,
            anchor="mt",
        )
        py += 84
    when = data.get("stockholm_display") or data.get("race_start_display") or data.get("event_date_display")
    if when:
        _draw_styled_text(
            draw, (W_STORY // 2, py), _plain_draw_text(when), _load_font_px(28), CYAN, anchor="mt"
        )
        py += 44
    picks_cd = data.get("deadline_countdown")
    if picks_cd:
        _draw_styled_text(
            draw,
            (W_STORY // 2, py),
            f"Picks stänger om {_plain_draw_text(picks_cd)}",
            _load_font_px(26, bold=True),
            GOLD,
            anchor="mt",
        )
        py += 40
    else:
        _draw_styled_text(
            draw,
            (W_STORY // 2, py),
            "Sätt picks innan gate drop",
            _load_font_px(26, bold=True),
            GOLD,
            anchor="mt",
        )

    y = panel_y2 + 48
    inviter = data.get("inviter_name") or data.get("inviter_username")
    if inviter:
        hook = f"{inviter} tippar WSX."
        sub = "Hänger du med?"
    else:
        hook = "Säsongen sparkar igång."
        sub = "Tippa topp 6 · holeshot · wildcard"
    _draw_styled_text(draw, (W_STORY // 2, y), hook, _load_font_px(34, bold=True), WHITE, anchor="mt")
    y += 48
    _draw_styled_text(draw, (W_STORY // 2, y), sub, _load_font_px(28), CYAN, anchor="mt")
    y += 56

    btn_w = W_STORY - margin * 2
    btn_h = 80
    draw.rounded_rectangle(
        [margin, y, margin + btn_w, y + btn_h], radius=20, fill=ember, outline=ember_soft, width=2
    )
    _draw_styled_text(
        draw,
        (W_STORY // 2, y + btn_h // 2),
        "TIPPA WSX NU",
        _load_display_font(36, bold=True),
        WHITE,
        anchor="mm",
    )
    y += btn_h + 40

    top5 = data.get("top5") or []
    if top5 and y < H_STORY - 320:
        y = _draw_top5_panel(draw, y, top5, margin=margin)

    host = _plain_draw_text(data.get("host_line") or "mx-fantasy.se/start")
    _draw_styled_text(draw, (W_STORY // 2, H_STORY - 110), host, _load_font_px(22), MUTED, anchor="mt")
    _footer(img, draw, H_STORY, bar_h=0)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_story_card(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        CYAN,
        CYAN_DIM,
        GOLD,
        MUTED,
        PANEL,
        PANEL_EDGE,
        WHITE,
        _draw_styled_text,
        _draw_vertical_gradient,
        _font_height,
        _footer,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
        _text_width,
    )

    img = Image.new("RGB", (W_STORY, H_STORY), (8, 15, 35))
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)

    margin = 56
    y = 0
    draw.rectangle([0, 0, W_STORY, 10], fill=CYAN)
    y = 48

    logo = _load_brand_logo(120)
    if logo:
        img.paste(logo, (margin, y), logo)
    brand_f = _load_display_font(34, bold=True)
    sub_f = _load_font_px(22)
    _draw_styled_text(
        draw, (margin + 140, y + 28), "MX FANTASY LEAGUE", brand_f, CYAN, anchor="lm"
    )
    _draw_styled_text(draw, (margin + 140, y + 72), "GRATIS FANTASY MOTOCROSS", sub_f, MUTED, anchor="lm")
    y += 150

    pill_f = _load_display_font(28, bold=True)
    pill_text = "NÄSTA RACE"
    pill_w = _text_width(pill_f, pill_text) + 48
    pill_h = 52
    px = (W_STORY - pill_w) // 2
    draw.rounded_rectangle(
        [px, y, px + pill_w, y + pill_h], radius=26, fill=(45, 38, 12), outline=GOLD, width=2
    )
    _draw_styled_text(draw, (W_STORY // 2, y + pill_h // 2), pill_text, pill_f, GOLD, anchor="mm")
    y += pill_h + 36

    race_name = _plain_draw_text(data.get("race_name") or "MX Fantasy League")
    race_f = _load_display_font(72, bold=True)
    for size in (72, 64, 56, 48):
        race_f = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=16)
        if len(lines) <= 2:
            break
    line_h = _font_height(race_f, "Ay") + 8
    for line in lines[:2]:
        _draw_styled_text(
            draw,
            (W_STORY // 2, y),
            line,
            race_f,
            WHITE,
            anchor="mt",
            stroke=(10, 18, 38),
            stroke_width=3,
        )
        y += line_h
    y += 20

    date_f = _load_font_px(30)
    when = data.get("stockholm_display") or data.get("race_start_display")
    if when:
        when = _plain_draw_text(when)
        _draw_styled_text(draw, (W_STORY // 2, y), when, date_f, CYAN, anchor="mt")
        y += _font_height(date_f) + 28

    panel_x1 = margin
    panel_x2 = W_STORY - margin
    panel_y1 = y
    panel_y2 = panel_y1 + 280
    draw.rounded_rectangle(
        [panel_x1, panel_y1, panel_x2, panel_y2], radius=24, fill=PANEL, outline=PANEL_EDGE, width=2
    )
    py = panel_y1 + 32
    info_f = _load_font_px(28)
    bold_f = _load_font_px(30, bold=True)

    countdown = data.get("deadline_countdown")
    if countdown:
        _draw_styled_text(draw, (W_STORY // 2, py), "PICKS STÄNGER OM", info_f, MUTED, anchor="mt")
        py += 40
        cd_f = _load_display_font(52, bold=True)
        _draw_styled_text(draw, (W_STORY // 2, py), _plain_draw_text(countdown), cd_f, GOLD, anchor="mt")
        py += 72

    weather_line = data.get("weather_line")
    if weather_line:
        _draw_styled_text(
            draw, (W_STORY // 2, py), _plain_draw_text(weather_line), bold_f, WHITE, anchor="mt"
        )
        py += 42

    weather_tip = data.get("weather_tip")
    if weather_tip:
        tip_f = _load_font_px(24)
        for line in textwrap.wrap(_plain_draw_text(weather_tip), width=38)[:2]:
            _draw_styled_text(draw, (W_STORY // 2, py), line, tip_f, MUTED, anchor="mt")
            py += 34

    y = panel_y2 + 40

    inviter = data.get("inviter_name") or data.get("inviter_username")
    hook_f = _load_font_px(32, bold=True)
    if inviter:
        hook = f"{inviter} har satt picks."
        sub = "Har du?"
    else:
        hook = "Picks öppna inför helgen."
        sub = "Gratis — klart på några minuter."
    _draw_styled_text(draw, (W_STORY // 2, y), hook, hook_f, WHITE, anchor="mt")
    y += 44
    _draw_styled_text(draw, (W_STORY // 2, y), sub, _load_font_px(28), CYAN, anchor="mt")
    y += 48

    btn_w = W_STORY - margin * 2
    btn_h = 72
    draw.rounded_rectangle(
        [margin, y, margin + btn_w, y + btn_h], radius=18, fill=CYAN, outline=CYAN_DIM, width=2
    )
    btn_f = _load_display_font(34, bold=True)
    _draw_styled_text(
        draw, (W_STORY // 2, y + btn_h // 2), "SÄTT DINA PICKS", btn_f, (8, 15, 35), anchor="mm"
    )
    y += btn_h + 36

    top5 = data.get("top5") or []
    if top5:
        y = _draw_top5_panel(draw, y, top5, margin=margin)

    url_f = _load_font_px(22)
    host = _plain_draw_text(data.get("host_line") or "")
    _draw_styled_text(draw, (W_STORY // 2, H_STORY - 120), host, url_f, MUTED, anchor="mt")

    _footer(img, draw, H_STORY, bar_h=8)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_top5_panel(draw, y: int, top5: list[dict[str, Any]], *, margin: int = 56) -> int:
    """Draw season top 5 leaderboard into the story card empty space."""
    from social_recap_service import (
        BRONZE,
        CYAN,
        GOLD,
        MUTED,
        PANEL,
        PANEL_EDGE,
        SILVER,
        WHITE,
        _draw_styled_text,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
    )

    row_h = 58
    header_h = 44
    pad = 20
    panel_h = pad + header_h + row_h * len(top5[:5]) + pad
    x1, x2 = margin, W_STORY - margin
    draw.rounded_rectangle(
        [x1, y, x2, y + panel_h], radius=20, fill=PANEL, outline=PANEL_EDGE, width=2
    )

    title_f = _load_display_font(26, bold=True)
    _draw_styled_text(
        draw, (W_STORY // 2, y + pad + 8), "TOPPLISTA · TOP 5", title_f, GOLD, anchor="mt"
    )

    name_f = _load_font_px(26, bold=True)
    pts_f = _load_font_px(24, bold=True)
    rank_f = _load_font_px(26, bold=True)
    medals = {1: GOLD, 2: SILVER, 3: BRONZE}

    ry = y + pad + header_h
    for row in top5[:5]:
        rank = int(row.get("rank") or 0)
        name = _plain_draw_text(str(row.get("name") or "?"))
        if len(name) > 22:
            name = name[:21] + "…"
        pts = int(row.get("points") or 0)
        is_me = bool(row.get("is_me"))
        medal = medals.get(rank, MUTED)

        if is_me:
            draw.rounded_rectangle(
                [x1 + 12, ry, x2 - 12, ry + row_h - 6],
                radius=12,
                fill=(14, 116, 144),
                outline=CYAN,
                width=2,
            )

        _draw_styled_text(draw, (x1 + 44, ry + row_h // 2 - 3), f"#{rank}", rank_f, medal, anchor="lm")
        _draw_styled_text(draw, (x1 + 110, ry + row_h // 2 - 3), name, name_f, WHITE, anchor="lm")
        _draw_styled_text(
            draw, (x2 - 36, ry + row_h // 2 - 3), f"{pts}p", pts_f, CYAN if is_me else MUTED, anchor="rm"
        )
        ry += row_h

    return y + panel_h + 16


def _render_og_card(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        CYAN,
        GOLD,
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
        _plain_draw_text,
        _text_width,
    )

    img = Image.new("RGB", (W_OG, H_OG), (8, 15, 35))
    _draw_vertical_gradient(img)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W_OG, 8], fill=CYAN)

    margin = 40
    logo = _load_brand_logo(88)
    if logo:
        img.paste(logo, (margin, 36), logo)

    brand_f = _load_display_font(28, bold=True)
    _draw_styled_text(draw, (margin + 100, 52), "MX FANTASY LEAGUE", brand_f, CYAN, anchor="lm")

    race_name = _plain_draw_text(data.get("race_name") or "MX Fantasy League").upper()
    race_f = _load_display_font(48, bold=True)
    _draw_styled_text(
        draw, (margin + 100, 96), race_name[:42], race_f, WHITE, anchor="lm", stroke=(10, 18, 38), stroke_width=2
    )

    right_x = W_OG - margin
    pill_f = _load_font_px(20, bold=True)
    _draw_styled_text(draw, (right_x, 48), "NÄSTA RACE", pill_f, GOLD, anchor="rm")

    panel_y1 = 168
    panel_y2 = H_OG - 36
    draw.rounded_rectangle(
        [margin, panel_y1, W_OG - margin, panel_y2], radius=20, fill=PANEL, outline=PANEL_EDGE, width=2
    )

    py = panel_y1 + 28
    cx = W_OG // 2
    when = data.get("stockholm_display") or data.get("race_start_display")
    if when:
        _draw_styled_text(draw, (cx, py), _plain_draw_text(when), _load_font_px(24), CYAN, anchor="mt")
        py += 38

    countdown = data.get("deadline_countdown")
    if countdown:
        _draw_styled_text(draw, (cx, py), f"Picks stänger om {_plain_draw_text(countdown)}", _load_font_px(26, bold=True), GOLD, anchor="mt")
        py += 40

    weather_line = data.get("weather_line")
    if weather_line:
        _draw_styled_text(draw, (cx, py), _plain_draw_text(weather_line), _load_font_px(22), WHITE, anchor="mt")
        py += 34

    inviter = data.get("inviter_name") or data.get("inviter_username")
    if inviter:
        hook = f"{inviter} har satt picks — har du?"
    else:
        hook = "Gratis fantasy motocross — sätt picks inför helgen"
    _draw_styled_text(draw, (cx, panel_y2 - 36), hook, _load_font_px(24, bold=True), WHITE, anchor="mb")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
