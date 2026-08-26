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

    # Prefer Stockholm deadline for Swedish Facebook audience
    deadline_stockholm = None
    if deadline_utc:
        try:
            from zoneinfo import ZoneInfo

            du = deadline_utc
            if getattr(du, "tzinfo", None) is None:
                du = du.replace(tzinfo=ZoneInfo("UTC"))
            se = du.astimezone(ZoneInfo("Europe/Stockholm"))
            months = ["", "jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
            deadline_stockholm = f"{se.day} {months[se.month]} kl {se.strftime('%H:%M')} (Stockholm)"
            deadline_display = deadline_stockholm
        except Exception:
            pass

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
    if not hero:
        try:
            from trackmap_utils import race_background_static_url

            hero = race_background_static_url(comp)
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


def _resolve_hero_path(hero_static: str | None):
    """Return local filesystem path for a static hero/trackmap URL."""
    from pathlib import Path

    if not hero_static:
        return None
    s = str(hero_static).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return None
    s = s.lstrip("/")
    if s.startswith("static/"):
        s = s[len("static/") :]
    p = Path("static") / s
    if p.is_file():
        return p
    return None


def _cover_crop(img, width: int, height: int):
    """Scale image to cover target size, center-crop."""
    from PIL import Image

    src_w, src_h = img.size
    scale = max(width / max(src_w, 1), height / max(src_h, 1))
    nw = max(1, int(src_w * scale))
    nh = max(1, int(src_h * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - width) // 2)
    top = max(0, (nh - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _paint_cinematic_backdrop(width: int, height: int, data: dict[str, Any], accent: tuple[int, int, int]):
    """Trackmap/hero full-bleed + dark cinematic overlays. Falls back to gradient."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    base = Image.new("RGB", (width, height), (10, 14, 28))
    hero_path = _resolve_hero_path(data.get("hero_static"))
    if hero_path:
        try:
            photo = Image.open(hero_path).convert("RGB")
            photo = _cover_crop(photo, width, height)
            # Slightly punchier contrast for “poster” feel
            photo = ImageEnhance.Contrast(photo).enhance(1.12)
            photo = ImageEnhance.Color(photo).enhance(1.08)
            base = photo
        except Exception:
            pass

    # Soft blur on edges only? Keep photo sharp but darken for text.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Left-to-right readability wash (text lives left/center)
    for x in range(width):
        t = x / max(width - 1, 1)
        # Stronger dark on left 55%, photo peeks on right
        a = int(210 * (1 - min(1.0, t * 1.35)) + 90 * min(1.0, t))
        a = max(70, min(230, a))
        od.line([(x, 0), (x, height)], fill=(6, 10, 22, a))

    # Bottom / top vignette bars
    for y in range(height // 3):
        a = int(170 * (1 - y / (height / 3)))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a // 2))
    for i, y in enumerate(range(height - height // 3, height)):
        a = int(200 * (i / max(height // 3, 1)))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))

    # Accent speed streaks (diagonal)
    streak = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streak)
    for i in range(7):
        y0 = int(height * 0.15) + i * 55
        sd.line(
            [(-40, y0), (width + 40, y0 + int(height * 0.18))],
            fill=(accent[0], accent[1], accent[2], 28 - i * 2),
            width=3,
        )
    streak = streak.filter(ImageFilter.GaussianBlur(1.2))

    out = base.convert("RGBA")
    out = Image.alpha_composite(out, overlay)
    out = Image.alpha_composite(out, streak)
    return out.convert("RGB")


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
    img = _paint_cinematic_backdrop(width, height, data, accent)
    draw = ImageDraw.Draw(img)
    margin = 44 if compact else 56

    # Accent top strip
    draw.rectangle([0, 0, width, 7], fill=accent)
    draw.rectangle([0, height - 7, width, height], fill=GOLD)

    # Brand row
    logo = _load_brand_logo(70 if compact else 86)
    brand_y = margin - 2
    if logo:
        # dark plate behind logo for contrast on photo
        draw.rounded_rectangle(
            [margin - 8, brand_y - 8, margin + logo.size[0] + 18 + 280, brand_y + logo.size[1] + 10],
            radius=16,
            fill=(8, 12, 24),
        )
        img.paste(logo, (margin, brand_y), logo)
        brand_x = margin + logo.size[0] + 16
    else:
        brand_x = margin
    _draw_styled_text(
        draw,
        (brand_x, brand_y + 16),
        "MX FANTASY LEAGUE",
        _load_display_font(24 if compact else 28, bold=True),
        accent,
        anchor="lm",
    )
    _draw_styled_text(
        draw,
        (brand_x, brand_y + 46),
        "TIPPA GRATIS · INFÖR RACE",
        _load_font_px(16 if compact else 18, bold=True),
        GOLD,
        anchor="lm",
    )

    # Series pill
    series = _plain_draw_text(data.get("series") or "RACE")
    pill = f"{series} HYPE"
    pf = _load_display_font(20 if compact else 24, bold=True)
    pw = _text_width(pf, pill) + 44
    ph = 46
    px0 = width - margin - pw
    draw.rounded_rectangle(
        [px0, brand_y + 8, px0 + pw, brand_y + 8 + ph],
        radius=23,
        fill=(accent[0] // 4, accent[1] // 4, accent[2] // 4),
        outline=accent,
        width=3,
    )
    _draw_styled_text(draw, (px0 + pw // 2, brand_y + 8 + ph // 2), pill, pf, WHITE, anchor="mm")

    # Hero title — floating over photo (poster style, not a UI card)
    y = brand_y + (95 if compact else 110)
    race_name = _plain_draw_text(data.get("race_name") or "Nästa race")
    race_size = 62 if compact else 82
    rf = _load_display_font(race_size, bold=True)
    for size in (race_size, race_size - 10, race_size - 20, 44):
        rf = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=16 if compact else 18)
        if len(lines) <= 2:
            break

    for line in lines[:2]:
        _draw_styled_text(
            draw,
            (margin + 4, y),
            line,
            rf,
            WHITE,
            anchor="lt",
            stroke=(0, 0, 0),
            stroke_width=6,
            glow=(accent[0] // 2, accent[1] // 2, accent[2] // 2),
        )
        y += size + 6

    meta = data.get("event_date_display") or ""
    if data.get("location_line"):
        meta = f"{meta} · {data.get('location_line')}" if meta else str(data.get("location_line"))
    if meta:
        _draw_styled_text(
            draw,
            (margin + 4, y + 8),
            _plain_draw_text(str(meta)).upper(),
            _load_font_px(22 if compact else 26, bold=True),
            GOLD,
            anchor="lt",
            stroke=(0, 0, 0),
            stroke_width=3,
        )
        y += 38

    when = data.get("deadline_display") or data.get("race_start_display") or ""
    if when:
        _draw_styled_text(
            draw,
            (margin + 4, y + 2),
            f"Deadline {_plain_draw_text(str(when))}",
            _load_font_px(18 if compact else 21, bold=True),
            WHITE,
            anchor="lt",
            stroke=(0, 0, 0),
            stroke_width=2,
        )
        y += 32

    # Countdown — dominant, open over the action photo
    y = max(y + 22, int(height * (0.46 if compact else 0.48)))
    panel_h = 200 if compact else 236
    panel_w = int(width * (0.56 if compact else 0.54))
    # Soft dark plate only behind countdown digits
    draw.rounded_rectangle(
        [margin - 6, y, margin - 6 + panel_w, y + panel_h],
        radius=28,
        fill=(5, 8, 18),
        outline=accent,
        width=3,
    )
    cy = y + 20
    _draw_styled_text(
        draw,
        (margin - 8 + panel_w // 2, cy),
        _plain_draw_text(data.get("countdown_label") or "COUNTDOWN"),
        _load_font_px(18 if compact else 20, bold=True),
        accent2,
        anchor="mt",
    )
    cy += 38

    parts = data.get("countdown_parts") or {}
    units = [
        (int(parts.get("days") or 0), "DAGAR"),
        (int(parts.get("hours") or 0), "TIM"),
        (int(parts.get("minutes") or 0), "MIN"),
    ]
    box_w = 130 if compact else 155
    box_h = 118 if compact else 140
    gap = 16 if compact else 20
    total_w = box_w * 3 + gap * 2
    bx = margin - 8 + (panel_w - total_w) // 2
    by = cy
    for val, label in units:
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=18,
            fill=(4, 8, 18),
            outline=accent2,
            width=2,
        )
        # inner glow bar
        draw.rectangle([bx + 10, by + 8, bx + box_w - 10, by + 12], fill=accent)
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h // 2 - 6),
            f"{val:02d}",
            _load_display_font(46 if compact else 56, bold=True),
            WHITE,
            anchor="mm",
            glow=accent,
        )
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h - 24),
            label,
            _load_font_px(15 if compact else 17, bold=True),
            MUTED,
            anchor="mm",
        )
        bx += box_w + gap

    # Right-side CTA stack (over photo)
    rx = int(width * 0.62)
    ry = int(height * 0.42)
    right_w = width - margin - rx
    draw.rounded_rectangle(
        [rx, ry, width - margin, height - margin],
        radius=24,
        fill=(10, 14, 26),
        outline=GOLD,
        width=2,
    )
    _draw_styled_text(
        draw,
        (rx + right_w // 2, ry + 36),
        _plain_draw_text(data.get("hook") or "Har ni satt era picks?"),
        _load_display_font(26 if compact else 30, bold=True),
        WHITE,
        anchor="mt",
    )
    _draw_styled_text(
        draw,
        (rx + right_w // 2, ry + 90),
        _plain_draw_text(data.get("subhook") or "Topp 6 · Holeshot · Wildcard"),
        _load_font_px(17 if compact else 19),
        accent,
        anchor="mt",
    )

    stats = data.get("picks_stats") or {}
    complete = int(stats.get("complete") or 0)
    started = int(stats.get("started") or 0)
    _draw_styled_text(
        draw,
        (rx + right_w // 2, ry + 140),
        f"{complete} tippare klara",
        _load_font_px(22 if compact else 24, bold=True),
        GOLD,
        anchor="mt",
    )
    if started > complete:
        _draw_styled_text(
            draw,
            (rx + right_w // 2, ry + 176),
            f"{started - complete} tippar just nu",
            _load_font_px(18 if compact else 20),
            MUTED,
            anchor="mt",
        )

    cta = "TIPPA NU"
    cf = _load_display_font(28 if compact else 32, bold=True)
    cw = right_w - 40
    ch = 58 if compact else 68
    cx1 = rx + 20
    cy1 = height - margin - ch - 56
    draw.rounded_rectangle([cx1, cy1, cx1 + cw, cy1 + ch], radius=18, fill=accent, outline=accent2, width=2)
    _draw_styled_text(draw, (cx1 + cw // 2, cy1 + ch // 2), cta, cf, (8, 15, 30), anchor="mm")
    _draw_styled_text(
        draw,
        (rx + right_w // 2, cy1 + ch + 22),
        "mx-fantasy.se",
        _load_font_px(20 if compact else 22, bold=True),
        WHITE,
        anchor="mt",
    )

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
    img = _paint_cinematic_backdrop(width, height, data, accent)
    draw = ImageDraw.Draw(img)
    margin = 56

    draw.rectangle([0, 0, width, 10], fill=accent)
    draw.rectangle([0, height - 10, width, height], fill=GOLD)

    y = 56
    logo = _load_brand_logo(100)
    if logo:
        draw.rounded_rectangle(
            [margin - 10, y - 10, margin + 420, y + logo.size[1] + 14],
            radius=18,
            fill=(8, 12, 24),
        )
        img.paste(logo, (margin, y), logo)
    _draw_styled_text(
        draw, (margin + 120, y + 22), "MX FANTASY LEAGUE", _load_display_font(28, bold=True), accent, anchor="lm"
    )
    _draw_styled_text(draw, (margin + 120, y + 60), "RACE HYPE", _load_font_px(22, bold=True), GOLD, anchor="lm")
    y += 150

    series = _plain_draw_text(data.get("series") or "RACE")
    pill = f"{series} HYPE"
    pf = _load_display_font(28, bold=True)
    pw = _text_width(pf, pill) + 48
    px0 = (width - pw) // 2
    draw.rounded_rectangle([px0, y, px0 + pw, y + 52], radius=26, fill=(12, 16, 30), outline=accent, width=3)
    _draw_styled_text(draw, (width // 2, y + 26), pill, pf, WHITE, anchor="mm")
    y += 84

    race_name = _plain_draw_text(data.get("race_name") or "Nästa race")
    for size in (76, 64, 54, 46):
        rf = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=13)
        if len(lines) <= 3:
            break
    # Title plate
    block_h = (size + 8) * min(3, len(lines)) + 24
    draw.rounded_rectangle(
        [margin, y - 12, width - margin, y + block_h],
        radius=22,
        fill=(6, 10, 20),
        outline=accent,
        width=2,
    )
    for line in lines[:3]:
        _draw_styled_text(
            draw,
            (width // 2, y),
            line,
            rf,
            WHITE,
            anchor="mt",
            stroke=(0, 0, 0),
            stroke_width=4,
            glow=(accent[0] // 3, accent[1] // 3, accent[2] // 3),
        )
        y += size + 6
    y += 28

    _draw_styled_text(
        draw,
        (width // 2, y),
        _plain_draw_text(data.get("countdown_label") or "COUNTDOWN"),
        _load_font_px(22, bold=True),
        accent2,
        anchor="mt",
    )
    y += 42

    parts = data.get("countdown_parts") or {}
    units = [
        (int(parts.get("days") or 0), "D"),
        (int(parts.get("hours") or 0), "H"),
        (int(parts.get("minutes") or 0), "M"),
    ]
    box = 190
    gap = 20
    total = box * 3 + gap * 2
    bx = (width - total) // 2
    for val, label in units:
        draw.rounded_rectangle([bx, y, bx + box, y + 170], radius=22, fill=(8, 12, 26), outline=accent, width=3)
        draw.rectangle([bx + 16, y + 12, bx + box - 16, y + 16], fill=accent)
        _draw_styled_text(
            draw, (bx + box // 2, y + 78), f"{val:02d}", _load_display_font(68, bold=True), WHITE, anchor="mm", glow=accent
        )
        _draw_styled_text(draw, (bx + box // 2, y + 140), label, _load_font_px(24, bold=True), MUTED, anchor="mm")
        bx += box + gap
    y += 210

    when = data.get("deadline_display") or data.get("race_start_display") or ""
    if when:
        _draw_styled_text(draw, (width // 2, y), _plain_draw_text(str(when)), _load_font_px(26, bold=True), GOLD, anchor="mt")
        y += 52

    _draw_styled_text(
        draw,
        (width // 2, y),
        _plain_draw_text(data.get("hook") or "Har ni satt era picks?"),
        _load_display_font(36, bold=True),
        WHITE,
        anchor="mt",
    )
    y += 58
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
    cf = _load_display_font(38, bold=True)
    cw = width - margin * 2
    ch = 88
    draw.rounded_rectangle([margin, y, margin + cw, y + ch], radius=24, fill=accent, outline=accent2, width=3)
    _draw_styled_text(draw, (width // 2, y + ch // 2), cta, cf, (8, 15, 30), anchor="mm")
    y += ch + 30
    _draw_styled_text(draw, (width // 2, y), "mx-fantasy.se", _load_font_px(28, bold=True), WHITE, anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
