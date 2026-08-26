"""Admin Hype Poster — säljande pre-race Facebook/Story-bilder med nedräkning + picks-status."""
from __future__ import annotations

import io
import textwrap
from datetime import datetime, timedelta
from typing import Any

from models import (
    Competition,
    HoleshotPick,
    RacePick,
    Rider,
    User,
    WildcardPick,
    db,
)

W_FB = 1620
H_FB = 900
W_STORY = 1080
H_STORY = 1920
W_OG = 1200
H_OG = 630


def _format_parts(delta: timedelta) -> dict[str, int]:
    total = max(0, int(delta.total_seconds()))
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return {"days": days, "hours": hours, "minutes": minutes, "seconds": seconds}


def _format_countdown_short(delta: timedelta) -> str:
    p = _format_parts(delta)
    if p["days"] <= 0 and p["hours"] <= 0 and p["minutes"] <= 0:
        return "Stängt"
    if p["days"] > 0:
        return f"{p['days']}d {p['hours']}h"
    if p["hours"] > 0:
        return f"{p['hours']}h {p['minutes']}m"
    return f"{p['minutes']}m"


def _user_has_complete_picks(user_id: int, comp: Competition) -> bool:
    is_wsx = (comp.series or "").upper() == "WSX"
    picks = (
        db.session.query(RacePick, Rider.class_name)
        .join(Rider, Rider.id == RacePick.rider_id)
        .filter(RacePick.user_id == user_id, RacePick.competition_id == comp.id)
        .all()
    )
    if not picks:
        return False

    c450 = 0
    c250 = 0
    seen = set()
    for pick, cls in picks:
        cls = cls or ""
        key = (pick.rider_id, cls, pick.predicted_position)
        if key in seen:
            continue
        seen.add(key)
        if cls in ("450cc", "wsx_sx1"):
            c450 += 1
        elif cls in ("250cc", "wsx_sx2"):
            c250 += 1

    if c450 < 6 or c250 < 6:
        return False

    hs = HoleshotPick.query.filter_by(user_id=user_id, competition_id=comp.id).count()
    if hs < 2:
        return False

    if is_wsx:
        return True
    wc = WildcardPick.query.filter_by(user_id=user_id, competition_id=comp.id).first()
    return bool(wc and wc.rider_id)


def _picks_stats(comp: Competition) -> dict[str, Any]:
    """Count tippare with any picks vs complete lineups for this race."""
    user_ids_with_any = {
        uid
        for (uid,) in db.session.query(RacePick.user_id)
        .filter(RacePick.competition_id == comp.id)
        .distinct()
        .all()
    }
    total_users = User.query.count()
    complete = 0
    for uid in user_ids_with_any:
        if _user_has_complete_picks(uid, comp):
            complete += 1

    started = len(user_ids_with_any)
    missing_complete = max(0, started - complete)
    # Also count users with zero picks among active tippare interest:
    # for hype we emphasize "have you set picks" vs those who already did.
    pct = round(100.0 * complete / started, 0) if started else 0.0
    return {
        "total_users": total_users,
        "started": started,
        "complete": complete,
        "incomplete": missing_complete,
        "pct_complete_of_started": pct,
    }


def build_hype_poster_data(competition_id: int) -> dict[str, Any]:
    from main import _competition_race_schedule, get_current_time
    from trackmap_utils import resolve_competition_hero_static_url

    comp = Competition.query.get(competition_id)
    if not comp:
        raise ValueError("competition_not_found")

    series = (comp.series or "").upper()
    race_name = comp.name or "MX Fantasy"
    event_date = comp.event_date
    event_date_display = event_date.strftime("%d %b %Y") if event_date else ""

    sched = {}
    try:
        sched = _competition_race_schedule(comp) or {}
    except Exception:
        sched = {}

    race_start_display = sched.get("stockholm_display") or sched.get("race_start_display") or ""
    deadline_display = sched.get("pick_deadline_display") or ""
    deadline_utc = sched.get("deadline_utc")
    race_start_utc = sched.get("race_utc")

    now = get_current_time()
    if getattr(now, "tzinfo", None):
        now = now.replace(tzinfo=None)

    deadline_delta = None
    race_delta = None
    if deadline_utc:
        try:
            du = deadline_utc.replace(tzinfo=None) if getattr(deadline_utc, "tzinfo", None) else deadline_utc
            deadline_delta = du - now
        except Exception:
            deadline_delta = None
    if race_start_utc:
        try:
            ru = race_start_utc.replace(tzinfo=None) if getattr(race_start_utc, "tzinfo", None) else race_start_utc
            race_delta = ru - now
        except Exception:
            race_delta = None

    # Prefer pick-deadline countdown for urgency; fall back to race start
    primary_delta = deadline_delta if deadline_delta and deadline_delta.total_seconds() > 0 else race_delta
    countdown_parts = _format_parts(primary_delta) if primary_delta else {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}
    countdown_label = "PICKS STÄNGER OM" if (deadline_delta and deadline_delta.total_seconds() > 0) else "RACET STARTAR OM"
    if primary_delta and primary_delta.total_seconds() <= 0:
        countdown_label = "DEADLINE PASSERAD"
        countdown_parts = {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}

    stats = _picks_stats(comp)

    location_line = None
    if series == "WSX":
        location_line = "World Supercross"
        try:
            from email_utils import pick_reminder_race_copy

            copy = pick_reminder_race_copy(comp) or {}
            location_line = copy.get("location") or location_line
        except Exception:
            pass

    hero = None
    try:
        hero = resolve_competition_hero_static_url(comp)
    except Exception:
        hero = None

    caption = build_facebook_caption(
        race_name=race_name,
        series=series,
        countdown_short=_format_countdown_short(primary_delta) if primary_delta else "snart",
        deadline_display=deadline_display or race_start_display,
        stats=stats,
        still_open=bool(primary_delta and primary_delta.total_seconds() > 0),
    )

    return {
        "competition_id": comp.id,
        "race_name": race_name,
        "series": series,
        "event_date_display": event_date_display,
        "race_start_display": race_start_display,
        "deadline_display": deadline_display,
        "countdown_label": countdown_label,
        "countdown_parts": countdown_parts,
        "countdown_short": _format_countdown_short(primary_delta) if primary_delta else "—",
        "location_line": location_line,
        "picks_stats": stats,
        "hero_static": hero,
        "caption": caption,
        "cta_url": "mx-fantasy.se",
        "hook": "Har ni satt era picks?",
        "subhook": "Topp 6 · Holeshot" + ("" if series == "WSX" else " · Wildcard"),
    }


def build_facebook_caption(
    *,
    race_name: str,
    series: str,
    countdown_short: str,
    deadline_display: str,
    stats: dict[str, Any],
    still_open: bool,
) -> str:
    series_tag = series or "MX"
    complete = int(stats.get("complete") or 0)
    started = int(stats.get("started") or 0)

    lines = [
        f"🔥 {race_name} — {series_tag}",
        "",
    ]
    if still_open:
        lines.append(f"⏳ Picks stänger om {countdown_short}")
        if deadline_display:
            lines.append(f"📅 Deadline: {deadline_display}")
        lines.append("")
        lines.append("Har ni satt era picks ännu?")
        if started > 0:
            lines.append(f"✅ {complete} tippare är redan klara" + (f" ({started} har börjat)" if started > complete else ""))
        lines.append("")
        lines.append("Tippa topp 6, holeshot" + ("" if series_tag == "WSX" else " & wildcard") + " — gratis.")
    else:
        lines.append("Picks är stängda — dags att följa racet 🏁")
        if complete:
            lines.append(f"{complete} tippare är med i leken.")
        lines.append("")

    lines.extend(
        [
            "👉 mx-fantasy.se",
            "",
            "#MXFantasy #Motocross #Supercross #FantasyLeague",
        ]
    )
    return "\n".join(lines)


def render_hype_poster_png(data: dict[str, Any], *, layout: str = "facebook") -> bytes:
    layout = (layout or "facebook").lower()
    if layout == "story":
        return _render_story(data)
    if layout == "og":
        return _render_landscape(data, W_OG, H_OG, compact=True)
    return _render_landscape(data, W_FB, H_FB, compact=False)


def _series_colors(series: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    s = (series or "").upper()
    if s == "WSX":
        return (255, 90, 40), (255, 140, 70)
    if s == "SMX":
        return (167, 139, 250), (192, 132, 252)
    if s == "SX":
        return (34, 211, 238), (6, 182, 212)
    if s == "MX":
        return (52, 211, 153), (16, 185, 129)
    return (34, 211, 238), (251, 191, 36)


def _render_landscape(data: dict[str, Any], width: int, height: int, *, compact: bool) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        GOLD,
        MUTED,
        WHITE,
        _draw_styled_text,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
        _text_width,
    )

    accent, accent2 = _series_colors(data.get("series") or "")
    bg_top = (8, 12, 28)
    bg_bot = (15, 23, 42)
    panel = (17, 24, 39)

    img = Image.new("RGB", (width, height), bg_bot)
    px = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(bg_top[0] * (1 - t) + bg_bot[0] * t)
        g = int(bg_top[1] * (1 - t) + bg_bot[1] * t)
        b = int(bg_top[2] * (1 - t) + bg_bot[2] * t)
        for x in range(width):
            # subtle left vignette glow
            glow = max(0, 1 - abs(x - width * 0.25) / (width * 0.55))
            rr = min(255, int(r + accent[0] * 0.08 * glow))
            gg = min(255, int(g + accent[1] * 0.05 * glow))
            bb = min(255, int(b + accent[2] * 0.08 * glow))
            px[x, y] = (rr, gg, bb)

    draw = ImageDraw.Draw(img)
    margin = 48 if compact else 56

    # Top / bottom bars
    draw.rectangle([0, 0, width, 8], fill=accent)
    draw.rectangle([0, height - 8, width, height], fill=accent2)

    # Brand
    logo = _load_brand_logo(72 if compact else 88)
    brand_y = margin - 4
    if logo:
        img.paste(logo, (margin, brand_y), logo)
        brand_x = margin + logo.size[0] + 18
    else:
        brand_x = margin
    _draw_styled_text(
        draw,
        (brand_x, brand_y + 18),
        "MX FANTASY LEAGUE",
        _load_display_font(26 if compact else 30, bold=True),
        accent,
        anchor="lm",
    )
    _draw_styled_text(
        draw,
        (brand_x, brand_y + 48),
        "TIPPA GRATIS",
        _load_font_px(18 if compact else 20),
        MUTED,
        anchor="lm",
    )

    # Series pill (right)
    series = _plain_draw_text(data.get("series") or "RACE")
    pill = f"{series} HYPE"
    pf = _load_display_font(22 if compact else 26, bold=True)
    pw = _text_width(pf, pill) + 40
    ph = 44
    px0 = width - margin - pw
    draw.rounded_rectangle(
        [px0, brand_y + 10, px0 + pw, brand_y + 10 + ph],
        radius=22,
        fill=(accent[0] // 5, accent[1] // 5, accent[2] // 5),
        outline=accent,
        width=2,
    )
    _draw_styled_text(draw, (px0 + pw // 2, brand_y + 10 + ph // 2), pill, pf, accent2, anchor="mm")

    # Race name
    y = brand_y + 100 if compact else brand_y + 115
    race_name = _plain_draw_text(data.get("race_name") or "Nästa race")
    race_size = 54 if compact else 68
    for size in (race_size, race_size - 8, race_size - 16, 40):
        rf = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=22 if compact else 26)
        if len(lines) <= 2:
            break
    for line in lines[:2]:
        _draw_styled_text(
            draw,
            (margin, y),
            line,
            rf,
            WHITE,
            anchor="lt",
            stroke=(10, 14, 24),
            stroke_width=3,
        )
        y += size + 8

    loc = data.get("location_line") or data.get("event_date_display") or ""
    if loc:
        _draw_styled_text(
            draw,
            (margin, y + 4),
            _plain_draw_text(str(loc)).upper(),
            _load_font_px(22 if compact else 24, bold=True),
            GOLD,
            anchor="lt",
        )
        y += 36

    when = data.get("deadline_display") or data.get("race_start_display") or ""
    if when:
        _draw_styled_text(
            draw,
            (margin, y),
            f"Deadline: {_plain_draw_text(str(when))}",
            _load_font_px(20 if compact else 22),
            MUTED,
            anchor="lt",
        )
        y += 34

    # Countdown panel
    y += 10 if compact else 16
    panel_h = 200 if compact else 230
    panel_x1, panel_x2 = margin, width - margin
    draw.rounded_rectangle(
        [panel_x1, y, panel_x2, y + panel_h],
        radius=24,
        fill=panel,
        outline=(accent[0] // 2, accent[1] // 2, accent[2] // 2),
        width=2,
    )
    cy = y + 22
    _draw_styled_text(
        draw,
        (width // 2, cy),
        _plain_draw_text(data.get("countdown_label") or "COUNTDOWN"),
        _load_font_px(18 if compact else 20, bold=True),
        MUTED,
        anchor="mt",
    )
    cy += 36

    parts = data.get("countdown_parts") or {}
    units = [
        (int(parts.get("days") or 0), "DAGAR"),
        (int(parts.get("hours") or 0), "TIMMAR"),
        (int(parts.get("minutes") or 0), "MIN"),
    ]
    box_w = 160 if compact else 200
    box_h = 110 if compact else 130
    gap = 24 if compact else 32
    total_w = box_w * 3 + gap * 2
    bx = (width - total_w) // 2
    by = cy
    for val, label in units:
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=18,
            fill=(8, 15, 30),
            outline=accent,
            width=2,
        )
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h // 2 - 10),
            f"{val:02d}",
            _load_display_font(48 if compact else 58, bold=True),
            accent2,
            anchor="mm",
        )
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h - 22),
            label,
            _load_font_px(16 if compact else 18, bold=True),
            MUTED,
            anchor="mm",
        )
        bx += box_w + gap

    y = y + panel_h + (18 if compact else 24)

    # Hook + picks stats
    _draw_styled_text(
        draw,
        (margin, y),
        _plain_draw_text(data.get("hook") or "Har ni satt era picks?"),
        _load_display_font(32 if compact else 38, bold=True),
        WHITE,
        anchor="lt",
    )
    y += 42 if compact else 50
    _draw_styled_text(
        draw,
        (margin, y),
        _plain_draw_text(data.get("subhook") or "Topp 6 · Holeshot · Wildcard"),
        _load_font_px(20 if compact else 22),
        accent,
        anchor="lt",
    )

    stats = data.get("picks_stats") or {}
    complete = int(stats.get("complete") or 0)
    started = int(stats.get("started") or 0)
    stats_line = f"{complete} tippare klara"
    if started > complete:
        stats_line += f" · {started - complete} håller på"
    # Right-aligned stats chip
    sf = _load_font_px(20 if compact else 22, bold=True)
    sw = _text_width(sf, stats_line) + 36
    sh = 44
    sx1 = width - margin - sw
    sy1 = y - 8
    draw.rounded_rectangle(
        [sx1, sy1, sx1 + sw, sy1 + sh],
        radius=14,
        fill=(6, 78, 59) if complete else (30, 41, 59),
        outline=(52, 211, 153) if complete else MUTED,
        width=2,
    )
    _draw_styled_text(draw, (sx1 + sw // 2, sy1 + sh // 2), stats_line, sf, WHITE, anchor="mm")

    # CTA button bottom-rightish / center-bottom
    cta = "TIPPA NU → mx-fantasy.se"
    cf = _load_display_font(26 if compact else 30, bold=True)
    cw = _text_width(cf, cta) + 56
    ch = 56 if compact else 64
    cx1 = width - margin - cw
    cy1 = height - margin - ch - 4
    draw.rounded_rectangle(
        [cx1, cy1, cx1 + cw, cy1 + ch],
        radius=18,
        fill=accent,
        outline=accent2,
        width=2,
    )
    _draw_styled_text(draw, (cx1 + cw // 2, cy1 + ch // 2), cta, cf, (8, 15, 30), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_story(data: dict[str, Any]) -> bytes:
    from PIL import Image, ImageDraw

    from social_recap_service import (
        GOLD,
        MUTED,
        WHITE,
        _draw_styled_text,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
        _text_width,
    )

    accent, accent2 = _series_colors(data.get("series") or "")
    width, height = W_STORY, H_STORY
    bg_top = (10, 8, 26)
    bg_bot = (8, 16, 34)
    panel = (18, 22, 44)

    img = Image.new("RGB", (width, height), bg_bot)
    px = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(bg_top[0] * (1 - t) + bg_bot[0] * t)
        g = int(bg_top[1] * (1 - t) + bg_bot[1] * t)
        b = int(bg_top[2] * (1 - t) + bg_bot[2] * t)
        for x in range(width):
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img)
    margin = 56
    draw.rectangle([0, 0, width, 10], fill=accent)
    draw.rectangle([0, height - 10, width, height], fill=accent2)

    y = 56
    logo = _load_brand_logo(100)
    if logo:
        img.paste(logo, (margin, y), logo)
    _draw_styled_text(
        draw, (margin + 120, y + 22), "MX FANTASY LEAGUE", _load_display_font(28, bold=True), accent, anchor="lm"
    )
    _draw_styled_text(draw, (margin + 120, y + 60), "RACE HYPE", _load_font_px(22), MUTED, anchor="lm")
    y += 140

    series = _plain_draw_text(data.get("series") or "RACE")
    pill = f"{series}"
    pf = _load_display_font(28, bold=True)
    pw = _text_width(pf, pill) + 48
    px0 = (width - pw) // 2
    draw.rounded_rectangle([px0, y, px0 + pw, y + 52], radius=26, fill=(20, 20, 40), outline=accent, width=3)
    _draw_styled_text(draw, (width // 2, y + 26), pill, pf, accent2, anchor="mm")
    y += 80

    race_name = _plain_draw_text(data.get("race_name") or "Nästa race")
    for size in (72, 62, 52, 44):
        rf = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=14)
        if len(lines) <= 3:
            break
    for line in lines[:3]:
        _draw_styled_text(draw, (width // 2, y), line, rf, WHITE, anchor="mt", stroke=(12, 10, 20), stroke_width=4)
        y += size + 6
    y += 16

    _draw_styled_text(
        draw,
        (width // 2, y),
        _plain_draw_text(data.get("countdown_label") or "COUNTDOWN"),
        _load_font_px(22, bold=True),
        MUTED,
        anchor="mt",
    )
    y += 40

    parts = data.get("countdown_parts") or {}
    units = [
        (int(parts.get("days") or 0), "D"),
        (int(parts.get("hours") or 0), "H"),
        (int(parts.get("minutes") or 0), "M"),
    ]
    box = 180
    gap = 24
    total = box * 3 + gap * 2
    bx = (width - total) // 2
    for val, label in units:
        draw.rounded_rectangle([bx, y, bx + box, y + 160], radius=22, fill=panel, outline=accent, width=2)
        _draw_styled_text(
            draw, (bx + box // 2, y + 70), f"{val:02d}", _load_display_font(64, bold=True), accent2, anchor="mm"
        )
        _draw_styled_text(draw, (bx + box // 2, y + 130), label, _load_font_px(24, bold=True), MUTED, anchor="mm")
        bx += box + gap
    y += 200

    when = data.get("deadline_display") or data.get("race_start_display") or ""
    if when:
        _draw_styled_text(draw, (width // 2, y), _plain_draw_text(str(when)), _load_font_px(26), GOLD, anchor="mt")
        y += 48

    _draw_styled_text(
        draw,
        (width // 2, y),
        _plain_draw_text(data.get("hook") or "Har ni satt era picks?"),
        _load_display_font(36, bold=True),
        WHITE,
        anchor="mt",
    )
    y += 56
    stats = data.get("picks_stats") or {}
    complete = int(stats.get("complete") or 0)
    _draw_styled_text(
        draw,
        (width // 2, y),
        f"{complete} tippare redan klara",
        _load_font_px(28, bold=True),
        accent,
        anchor="mt",
    )
    y += 70

    cta = "TIPPA NU"
    cf = _load_display_font(36, bold=True)
    cw = width - margin * 2
    ch = 84
    draw.rounded_rectangle([margin, y, margin + cw, y + ch], radius=22, fill=accent, outline=accent2, width=2)
    _draw_styled_text(draw, (width // 2, y + ch // 2), cta, cf, WHITE, anchor="mm")
    y += ch + 28
    _draw_styled_text(draw, (width // 2, y), "mx-fantasy.se", _load_font_px(28, bold=True), MUTED, anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
