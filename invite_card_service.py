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


def _fit_centered_title(
    text: str,
    *,
    max_width: int,
    sizes: tuple[int, ...] = (72, 64, 56, 48, 40, 34),
    max_lines: int = 2,
) -> tuple[Any, list[str]]:
    """Pick display font + wrap so each line fits max_width (avoids edge clipping)."""
    from social_recap_service import _load_display_font, _plain_draw_text, _text_width

    title = _plain_draw_text(text or "").upper() or "MX FANTASY"
    font = _load_display_font(sizes[-1], bold=True)
    lines = [title]

    for size in sizes:
        font = _load_display_font(size, bold=True)
        # Prefer natural word wrap; fall back to tighter char wrap if needed
        for wrap_w in (18, 14, 11, 9):
            candidate = textwrap.wrap(title, width=wrap_w) or [title]
            if len(candidate) > max_lines:
                continue
            if all(_text_width(font, line) <= max_width for line in candidate):
                return font, candidate[:max_lines]
        # Single-line shrink path
        if _text_width(font, title) <= max_width:
            return font, [title]

    # Last resort: hard-trim longest lines
    lines = textwrap.wrap(title, width=10) or [title]
    lines = lines[:max_lines]
    safe: list[str] = []
    for line in lines:
        while len(line) > 3 and _text_width(font, line) > max_width:
            line = line[:-1]
        safe.append(line)
    return font, safe or [title[:12]]


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

        base = get_public_base_url().rstrip("/")
        base_host = base.replace("https://", "").replace("http://", "").rstrip("/")
    except Exception:
        base = "https://mx-fantasy.se"
        base_host = "mx-fantasy.se"
    host_line = f"{base_host}/start"
    invite_url = f"{base}/start"
    if inviter_username:
        host_line += f"?ref={inviter_username}"
        invite_url += f"?ref={inviter_username}"

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
        "invite_url": invite_url,
        "has_race": comp is not None,
        "top5": top5,
        "is_wsx_hype": series == "WSX",
    }


def _invite_absolute_url(data: dict[str, Any]) -> str:
    url = (data.get("invite_url") or "").strip()
    if url.startswith("http"):
        return url
    host = (data.get("host_line") or "mx-fantasy.se/start").strip()
    if host.startswith("http"):
        return host
    return f"https://{host.lstrip('/')}"


def _make_invite_qr(url: str, *, pixel: int = 220) -> Any:
    """Return a PIL RGB image with a scannable QR for Stories (no clickable link from iOS share)."""
    import qrcode
    from PIL import Image

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    raw = qr.make_image(fill_color="#020617", back_color="#ffffff").convert("RGB")
    return raw.resize((pixel, pixel), Image.Resampling.NEAREST)


def _draw_story_link_block(img: Any, draw: Any, data: dict[str, Any], *, margin: int = 56) -> None:
    """Footer with big URL + QR — Snap/IG Stories from web cannot embed a tappable link."""
    from social_recap_service import (
        CYAN,
        GOLD,
        WHITE,
        _draw_styled_text,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
    )

    url = _invite_absolute_url(data)
    display = (data.get("host_line") or url.replace("https://", "").replace("http://", "")).strip()
    display = _plain_draw_text(display)

    qr_size = 200
    pad = 22
    block_h = qr_size + pad * 2 + 8
    top = H_STORY - block_h - 28
    left = margin
    right = W_STORY - margin

    draw.rounded_rectangle(
        [left, top, right, top + block_h],
        radius=22,
        fill=(10, 18, 36),
        outline=CYAN,
        width=3,
    )

    try:
        qr_img = _make_invite_qr(url, pixel=qr_size)
        img.paste(qr_img, (right - pad - qr_size, top + pad))
        # Light frame around QR
        draw.rectangle(
            [
                right - pad - qr_size - 4,
                top + pad - 4,
                right - pad + 4,
                top + pad + qr_size + 4,
            ],
            outline=GOLD,
            width=2,
        )
    except Exception:
        qr_size = 0

    text_right = right - pad - (qr_size + 28 if qr_size else 0)
    y = top + pad + 8
    _draw_styled_text(
        draw, (left + pad, y), "SKANNA ELLER ÖPPNA", _load_font_px(22, bold=True), GOLD, anchor="lt"
    )
    y += 36
    _draw_styled_text(
        draw, (left + pad, y), "Tippa gratis här:", _load_font_px(26), WHITE, anchor="lt"
    )
    y += 40
    # URL — wrap if long
    url_font = _load_display_font(28, bold=True)
    max_chars = 28 if qr_size else 36
    for line in textwrap.wrap(display, width=max_chars)[:3]:
        _draw_styled_text(draw, (left + pad, y), line, url_font, CYAN, anchor="lt")
        y += 34


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
    race_f, lines = _fit_centered_title(
        race_name,
        max_width=W_STORY - margin * 2 - 24,
        sizes=(78, 68, 58, 48, 40, 34),
        max_lines=2,
    )
    line_h = _font_height(race_f, "Ay") + 10
    for line in lines:
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
    if top5 and y < H_STORY - 420:
        y = _draw_top5_panel(draw, y, top5, margin=margin)

    _draw_story_link_block(img, draw, data, margin=margin)
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
    race_f, lines = _fit_centered_title(
        race_name,
        max_width=W_STORY - margin * 2 - 24,
        sizes=(72, 64, 56, 48, 40, 34),
        max_lines=2,
    )
    line_h = _font_height(race_f, "Ay") + 8
    for line in lines:
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
    if top5 and y < H_STORY - 420:
        y = _draw_top5_panel(draw, y, top5, margin=margin)

    _draw_story_link_block(img, draw, data, margin=margin)

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


def render_din_kvall_card_png(data: dict[str, Any]) -> bytes:
    """Personal «Din kväll» share card (9:16) — same broadcast theme as Race Recap list."""
    from PIL import Image, ImageDraw

    from social_recap_service import (
        CYAN,
        GOLD,
        MUTED,
        WHITE,
        _list_draw_atmosphere,
        _list_draw_kind_icon,
        _list_kind_colors,
        _list_paste,
        _list_series_theme,
        _load_font_px,
        _load_motoaction_logo,
        _load_mx_fantasy_logo,
        _plain_draw_text,
        _short_user_name,
    )

    theme = _list_series_theme(data.get("series"))
    accent = theme["accent"]
    W, H = W_STORY, H_STORY
    footer_reserve = 140
    img = Image.new("RGBA", (W, H), (8, 15, 35, 255))
    _list_draw_atmosphere(img, theme)
    draw = ImageDraw.Draw(img)
    margin = 48
    me_uid = int(data.get("user_id") or 0)

    # Header logos
    mx_logo = _load_mx_fantasy_logo(88)
    y = 40
    if mx_logo is not None:
        _list_paste(img, mx_logo, margin, y)
        brand_x = margin + mx_logo.width + 16
    else:
        brand_x = margin
        draw.text(
            (margin, y + 24),
            "MX FANTASY",
            font=_load_font_px(32, bold=True),
            fill=accent,
            anchor="lm",
        )
        brand_x = margin + 220

    pill = "DIN KVÄLL"
    pf = _load_font_px(18, bold=True)
    pw = int(draw.textlength(pill, font=pf)) + 28
    ph = 34
    draw.rounded_rectangle(
        [brand_x, y + 22, brand_x + pw, y + 22 + ph],
        radius=17,
        fill=(248, 250, 252, 235),
    )
    draw.text(
        (brand_x + pw // 2, y + 22 + ph // 2),
        pill,
        font=pf,
        fill=(15, 23, 42),
        anchor="mm",
    )

    sb = theme.get("badge") or (data.get("series") or "MX")
    sbf = _load_font_px(16, bold=True)
    sbw = int(draw.textlength(str(sb), font=sbf)) + 24
    sx0 = brand_x + pw + 12
    draw.rounded_rectangle(
        [sx0, y + 22, sx0 + sbw, y + 22 + ph],
        radius=17,
        outline=accent,
        width=2,
    )
    draw.text(
        (sx0 + sbw // 2, y + 22 + ph // 2),
        str(sb),
        font=sbf,
        fill=accent,
        anchor="mm",
    )

    y = 148
    draw.rectangle([margin, y, W - margin, y + 4], fill=accent)
    y += 24

    race = _plain_draw_text(data.get("race_name") or "Race").upper()
    race_f = _load_font_px(44, bold=True)
    for size in range(44, 26, -2):
        race_f = _load_font_px(size, bold=True)
        if draw.textlength(race, font=race_f) <= (W - margin * 2):
            break
    draw.text((W // 2, y), race, font=race_f, fill=WHITE, anchor="mt")
    y += 52

    uname = _plain_draw_text(data.get("display_name") or data.get("username") or "")
    if uname:
        label = uname if uname.startswith("@") else f"@{uname}"
        draw.text(
            (W // 2, y),
            label,
            font=_load_font_px(22, bold=True),
            fill=MUTED,
            anchor="mt",
        )
        y += 36
    else:
        draw.text(
            (W // 2, y),
            theme.get("tagline") or "MX Fantasy · Din kväll",
            font=_load_font_px(16),
            fill=MUTED,
            anchor="mt",
        )
        y += 32

    # Big points panel
    panel_h = 200
    plate = Image.new("RGBA", (W - margin * 2, panel_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.rounded_rectangle(
        [0, 0, W - margin * 2 - 1, panel_h - 1],
        radius=18,
        fill=(12, 18, 34, 230),
        outline=accent + (200,),
        width=2,
    )
    pd.rectangle([0, 0, W - margin * 2 - 1, 8], fill=accent + (255,))
    img.alpha_composite(plate, (margin, y))

    pts = data.get("points")
    pts_txt = f"{int(pts)} p" if pts is not None else "—"
    draw.text(
        (W // 2, y + 32),
        "DINA POÄNG",
        font=_load_font_px(20, bold=True),
        fill=MUTED,
        anchor="mt",
    )
    draw.text(
        (W // 2, y + 72),
        pts_txt,
        font=_load_font_px(68, bold=True),
        fill=GOLD,
        anchor="mt",
    )

    rank = data.get("race_rank")
    field = data.get("field_size")
    rank_txt = f"#{rank}" if rank is not None else "—"
    if field:
        rank_txt = f"{rank_txt} / {field}"
    vs = _plain_draw_text(data.get("vs_avg_label") or "")
    season_rank = data.get("season_rank")
    season_delta = _plain_draw_text(data.get("season_delta_label") or "")

    col_y = y + 152
    draw.text(
        (margin + 40, col_y),
        "PLATS",
        font=_load_font_px(14, bold=True),
        fill=MUTED,
        anchor="lt",
    )
    draw.text(
        (margin + 40, col_y + 24),
        rank_txt,
        font=_load_font_px(26, bold=True),
        fill=WHITE,
        anchor="lt",
    )
    right_label = "SÄSONG"
    right_val = f"#{season_rank}" if season_rank is not None else (vs or "—")
    if season_delta and season_rank is not None:
        right_val = f"#{season_rank}  {season_delta}"
    elif vs and season_rank is None:
        right_label = "VS SNITT"
        right_val = vs
    draw.text(
        (W - margin - 40, col_y),
        right_label,
        font=_load_font_px(14, bold=True),
        fill=MUTED,
        anchor="rt",
    )
    draw.text(
        (W - margin - 40, col_y + 24),
        right_val,
        font=_load_font_px(24, bold=True),
        fill=CYAN,
        anchor="rt",
    )
    y += panel_h + 24

    # Weekly badges (raket / ankare / kung·queen)
    badges = list(data.get("weekly_badges") or [])[:2]
    if badges and y < H - footer_reserve - 120:
        draw.rectangle([margin, y, margin + 8, y + 26], fill=accent)
        draw.text(
            (margin + 18, y + 13),
            "DU TOG HEM",
            font=_load_font_px(20, bold=True),
            fill=WHITE,
            anchor="lm",
        )
        y += 38
        for badge in badges:
            if y >= H - footer_reserve - 90:
                break
            color = _list_kind_colors(badge, accent)
            bh = 80
            card = Image.new("RGBA", (W - margin * 2, bh), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle(
                [0, 0, W - margin * 2 - 1, bh - 1],
                radius=14,
                fill=(12, 18, 34, 220),
                outline=color + (210,),
                width=2,
            )
            cd.rectangle([0, 0, 8, bh - 1], fill=color + (255,))
            img.alpha_composite(card, (margin, y))
            icx, icy = margin + 48, y + bh // 2
            draw.ellipse(
                [icx - 22, icy - 22, icx + 22, icy + 22],
                fill=(8, 15, 35),
                outline=color,
                width=2,
            )
            _list_draw_kind_icon(
                draw,
                str(badge.get("kind") or badge.get("icon") or ""),
                icx,
                icy,
                26,
                color,
                is_queen=bool(badge.get("is_queen")),
            )
            draw.text(
                (margin + 84, y + 20),
                str(badge.get("title") or "").upper()[:28],
                font=_load_font_px(15, bold=True),
                fill=color,
                anchor="lm",
            )
            draw.text(
                (margin + 84, y + 48),
                _plain_draw_text(badge.get("detail") or "Bra jobbat!")[:40],
                font=_load_font_px(18, bold=True),
                fill=WHITE,
                anchor="lm",
            )
            y += bh + 10
        y += 6

    # Personal highlights only if no weekly badge (avoid overcrowding)
    highlights = list(data.get("highlights") or [])[:2] if not badges else []
    if highlights and y < H - footer_reserve - 100:
        draw.rectangle([margin, y, margin + 8, y + 26], fill=GOLD)
        draw.text(
            (margin + 18, y + 13),
            "HIGHLIGHTS",
            font=_load_font_px(20, bold=True),
            fill=WHITE,
            anchor="lm",
        )
        y += 38
        for h in highlights:
            if y >= H - footer_reserve - 70:
                break
            text = _plain_draw_text((h.get("text") if isinstance(h, dict) else h) or "")
            if not text:
                continue
            bh = 58
            plate = Image.new("RGBA", (W - margin * 2, bh), (0, 0, 0, 0))
            pd = ImageDraw.Draw(plate)
            pd.rounded_rectangle(
                [0, 0, W - margin * 2 - 1, bh - 1],
                radius=12,
                fill=(12, 18, 34, 210),
                outline=(51, 65, 85, 160),
                width=1,
            )
            img.alpha_composite(plate, (margin, y))
            draw.text(
                (margin + 22, y + bh // 2),
                text[:52],
                font=_load_font_px(18, bold=True),
                fill=WHITE,
                anchor="lm",
            )
            y += bh + 8
        y += 4

    # Series highscore top 5 (WSX / SMX / AMA depending on race)
    season_top = list(data.get("season_top") or [])[:5]
    if season_top and y < H - footer_reserve - 80:
        title = (data.get("season_board_title") or "Säsongstoppen").upper()
        draw.rectangle([margin, y, margin + 8, y + 26], fill=GOLD)
        draw.text(
            (margin + 18, y + 13),
            title,
            font=_load_font_px(18, bold=True),
            fill=WHITE,
            anchor="lm",
        )
        y += 36
        for i, row in enumerate(season_top):
            if y >= H - footer_reserve - 52:
                break
            rank_n = int(row.get("rank") or (i + 1))
            name = _short_user_name(row.get("display_name") or row.get("username") or "?")
            pts_row = int(row.get("points") or 0)
            is_me = me_uid and int(row.get("user_id") or 0) == me_uid
            bh = 48
            plate = Image.new("RGBA", (W - margin * 2, bh), (0, 0, 0, 0))
            pd = ImageDraw.Draw(plate)
            fill = (30, 58, 80, 230) if is_me else (12, 18, 34, 210)
            pd.rounded_rectangle(
                [0, 0, W - margin * 2 - 1, bh - 1],
                radius=10,
                fill=fill,
                outline=(accent + (200,)) if is_me else (51, 65, 85, 140),
                width=2 if is_me else 1,
            )
            bar = (
                GOLD
                if rank_n == 1
                else (
                    (203, 213, 225)
                    if rank_n == 2
                    else ((217, 119, 6) if rank_n == 3 else accent)
                )
            )
            pd.rectangle([0, 0, 7, bh - 1], fill=bar + (255,))
            img.alpha_composite(plate, (margin, y))
            draw.text(
                (margin + 20, y + bh // 2),
                f"{rank_n:02d}",
                font=_load_font_px(20, bold=True),
                fill=bar if rank_n <= 3 else WHITE,
                anchor="lm",
            )
            draw.text(
                (margin + 72, y + bh // 2),
                name + ("  ← du" if is_me else ""),
                font=_load_font_px(18, bold=True),
                fill=WHITE,
                anchor="lm",
            )
            draw.text(
                (W - margin - 20, y + bh // 2),
                f"{pts_row} p",
                font=_load_font_px(18, bold=True),
                fill=CYAN,
                anchor="rm",
            )
            y += bh + 6

    rival = _plain_draw_text(data.get("rival_line") or "")
    if rival and y < H - footer_reserve - 80:
        y += 6
        bh = 64
        plate = Image.new("RGBA", (W - margin * 2, bh), (0, 0, 0, 0))
        pd = ImageDraw.Draw(plate)
        pd.rounded_rectangle(
            [0, 0, W - margin * 2 - 1, bh - 1],
            radius=12,
            fill=(40, 24, 12, 230),
            outline=(217, 119, 6, 200),
            width=2,
        )
        img.alpha_composite(plate, (margin, y))
        for i, line in enumerate(textwrap.wrap(rival, width=38)[:2]):
            draw.text(
                (W // 2, y + 18 + i * 24),
                line,
                font=_load_font_px(18, bold=True),
                fill=GOLD,
                anchor="mt",
            )

    # Footer
    footer_top = H - 118
    promo_h = 56
    promo = Image.new("RGBA", (W - margin * 2, promo_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(promo)
    pd.rounded_rectangle(
        [0, 0, W - margin * 2 - 1, promo_h - 1],
        radius=12,
        fill=(8, 15, 35, 230),
        outline=accent + (180,),
        width=2,
    )
    img.alpha_composite(promo, (margin, footer_top))
    foot_logo = _load_mx_fantasy_logo(40)
    tx = margin + 14
    if foot_logo is not None:
        _list_paste(img, foot_logo, tx, footer_top + (promo_h - foot_logo.height) // 2)
        tx += foot_logo.width + 12
    draw.text(
        (tx, footer_top + promo_h // 2),
        "mx-fantasy.se",
        font=_load_font_px(18, bold=True),
        fill=WHITE,
        anchor="lm",
    )
    ma = _load_motoaction_logo(34)
    if ma is not None:
        _list_paste(
            img,
            ma,
            W - margin - 14 - ma.width,
            footer_top + (promo_h - ma.height) // 2,
        )
    draw.rectangle([0, H - 6, W, H], fill=accent)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
