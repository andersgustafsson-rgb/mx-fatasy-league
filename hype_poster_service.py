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
        lines.append("")
        lines.append("Tippa topp 6, holeshot" + ("" if series_tag == "WSX" else " & wildcard") + " — gratis.")
    else:
        lines.append("Picks är stängda — dags att följa racet 🏁")
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
            photo = ImageEnhance.Contrast(photo).enhance(1.14)
            photo = ImageEnhance.Color(photo).enhance(1.1)
            base = photo
        except Exception:
            pass

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Soft overall dim so photo stays visible but text cards read cleanly
    od.rectangle([0, 0, width, height], fill=(4, 8, 18, 55))

    # Top vignette (brand area)
    top_band = max(120, height // 5)
    for y in range(top_band):
        a = int(160 * (1 - y / top_band))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))

    # Strong bottom fade into title-card zone
    bot_band = int(height * 0.55)
    for i, y in enumerate(range(height - bot_band, height)):
        t = i / max(bot_band - 1, 1)
        a = int(40 + 200 * (t ** 1.35))
        od.line([(0, y), (width, y)], fill=(4, 8, 18, min(230, a)))

    # Subtle accent wash
    streak = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streak)
    for i in range(5):
        y0 = int(height * 0.2) + i * 70
        sd.line(
            [(-40, y0), (width + 40, y0 + int(height * 0.12))],
            fill=(accent[0], accent[1], accent[2], 22 - i * 3),
            width=2,
        )
    streak = streak.filter(ImageFilter.GaussianBlur(1.4))

    out = base.convert("RGBA")
    out = Image.alpha_composite(out, overlay)
    out = Image.alpha_composite(out, streak)
    return out.convert("RGB")


def _draw_title_card(
    img,
    draw,
    data: dict[str, Any],
    *,
    box: tuple[int, int, int, int],
    accent: tuple[int, int, int],
    accent2: tuple[int, int, int],
    compact: bool,
    story: bool = False,
) -> None:
    """Single inset panel: race + meta + countdown + CTA. No tippare counts."""
    from social_recap_service import (
        GOLD,
        MUTED,
        WHITE,
        _draw_styled_text,
        _load_display_font,
        _load_font_px,
        _plain_draw_text,
    )

    x0, y0, x1, y1 = box
    pad = 28 if compact else (36 if not story else 40)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=22, fill=(8, 12, 24), outline=(accent[0], accent[1], accent[2]), width=2)
    draw.rectangle([x0 + 18, y0, x1 - 18, y0 + 4], fill=GOLD)

    y = y0 + (20 if compact else 24)

    series = _plain_draw_text(data.get("series") or "RACE")
    _draw_styled_text(
        draw,
        (x0 + pad, y),
        f"{series} HYPE",
        _load_font_px(14 if compact else 16, bold=True),
        accent2,
        anchor="lt",
    )
    y += 26 if compact else 30

    race_name = _plain_draw_text(data.get("race_name") or "Nästa race")
    max_size = 40 if compact else (52 if not story else 56)
    wrap_w = 16 if story else (26 if compact else 30)
    for size in (max_size, max_size - 8, max_size - 14, 32):
        rf = _load_display_font(size, bold=True)
        lines = textwrap.wrap(race_name.upper(), width=wrap_w)
        if len(lines) <= (3 if story else 2):
            break
    for line in lines[: (3 if story else 2)]:
        if story:
            _draw_styled_text(draw, ((x0 + x1) // 2, y), line, rf, WHITE, anchor="mt")
        else:
            _draw_styled_text(draw, (x0 + pad, y), line, rf, WHITE, anchor="lt")
        y += size + 2

    meta_bits = []
    if data.get("event_date_display"):
        meta_bits.append(str(data["event_date_display"]))
    if data.get("location_line") and not story:
        meta_bits.append(str(data["location_line"]))
    when = data.get("deadline_display") or data.get("race_start_display") or ""
    if when:
        meta_bits.append(f"Deadline {when}")
    meta_line = "  ·  ".join(_plain_draw_text(b) for b in meta_bits if b)
    if meta_line:
        y += 8
        anchor = "mt" if story else "lt"
        pos = ((x0 + x1) // 2, y) if story else (x0 + pad, y)
        _draw_styled_text(
            draw,
            pos,
            meta_line,
            _load_font_px(15 if compact else 18, bold=True),
            GOLD,
            anchor=anchor,
        )
        y += 28 if compact else 32

    # Divider
    draw.line([(x0 + pad, y), (x1 - pad, y)], fill=(accent[0] // 2, accent[1] // 2, accent[2] // 2), width=2)
    y += 16

    _draw_styled_text(
        draw,
        ((x0 + x1) // 2, y) if story else (x0 + pad, y),
        _plain_draw_text(data.get("countdown_label") or "PICKS STÄNGER OM"),
        _load_font_px(14 if compact else 16, bold=True),
        accent2,
        anchor="mt" if story else "lt",
    )
    y += 26 if compact else 28

    parts = data.get("countdown_parts") or {}
    units = [
        (int(parts.get("days") or 0), "DAGAR" if not story else "D"),
        (int(parts.get("hours") or 0), "TIM" if not story else "H"),
        (int(parts.get("minutes") or 0), "MIN" if not story else "M"),
    ]

    if story:
        box_w, box_h, gap = 150, 120, 16
        total = box_w * 3 + gap * 2
        bx = (x0 + x1 - total) // 2
    else:
        box_w = 100 if compact else 118
        box_h = 86 if compact else 96
        gap = 12
        bx = x0 + pad
    by = y
    for val, label in units:
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=14,
            fill=(14, 20, 36),
            outline=accent,
            width=2,
        )
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h // 2 - 10),
            f"{val:02d}",
            _load_display_font(34 if compact else (42 if not story else 48), bold=True),
            WHITE,
            anchor="mm",
        )
        _draw_styled_text(
            draw,
            (bx + box_w // 2, by + box_h - 18),
            label,
            _load_font_px(13 if compact else 14, bold=True),
            MUTED,
            anchor="mm",
        )
        bx += box_w + gap

    # CTA — full width under countdown on story; beside countdown on landscape
    hook = _plain_draw_text(data.get("hook") or "Har ni satt era picks?")
    sub = _plain_draw_text(data.get("subhook") or "Topp 6 · Holeshot · Wildcard")

    if story:
        y = by + box_h + 28
        _draw_styled_text(draw, ((x0 + x1) // 2, y), hook, _load_display_font(28, bold=True), WHITE, anchor="mt")
        y += 44
        btn_h = 72
        draw.rounded_rectangle([x0 + pad, y, x1 - pad, y + btn_h], radius=16, fill=accent)
        _draw_styled_text(
            draw,
            ((x0 + x1) // 2, y + btn_h // 2),
            "TIPPA NU · mx-fantasy.se",
            _load_display_font(26, bold=True),
            (8, 15, 30),
            anchor="mm",
        )
        y += btn_h + 22
        _draw_styled_text(draw, ((x0 + x1) // 2, y), sub, _load_font_px(18, bold=True), MUTED, anchor="mt")
    else:
        cta_x0 = bx + 20
        cta_x1 = x1 - pad
        if cta_x1 - cta_x0 < 220:
            cta_x0 = x0 + pad
            cta_y0 = by + box_h + 16
            cta_h = 56 if compact else 64
            _draw_styled_text(draw, (cta_x0, cta_y0), hook, _load_font_px(15 if compact else 17, bold=True), WHITE, anchor="lt")
            cta_y0 += 26
            draw.rounded_rectangle([cta_x0, cta_y0, cta_x1, cta_y0 + cta_h], radius=14, fill=accent)
            _draw_styled_text(
                draw,
                ((cta_x0 + cta_x1) // 2, cta_y0 + cta_h // 2),
                "TIPPA NU · mx-fantasy.se",
                _load_display_font(18 if compact else 20, bold=True),
                (8, 15, 30),
                anchor="mm",
            )
            _draw_styled_text(
                draw,
                ((x0 + x1) // 2, y1 - 22),
                sub,
                _load_font_px(13 if compact else 14, bold=True),
                MUTED,
                anchor="mm",
            )
        else:
            # Side CTA aligned with countdown boxes
            mid = by + box_h // 2
            _draw_styled_text(draw, (cta_x0, mid - 28), hook, _load_font_px(16 if compact else 18, bold=True), WHITE, anchor="lt")
            btn_h = 48 if compact else 54
            draw.rounded_rectangle([cta_x0, mid - 2, cta_x1, mid - 2 + btn_h], radius=14, fill=accent)
            _draw_styled_text(
                draw,
                ((cta_x0 + cta_x1) // 2, mid - 2 + btn_h // 2),
                "TIPPA NU · mx-fantasy.se",
                _load_display_font(17 if compact else 19, bold=True),
                (8, 15, 30),
                anchor="mm",
            )
            _draw_styled_text(
                draw,
                ((x0 + x1) // 2, y1 - 20),
                sub,
                _load_font_px(13 if compact else 14, bold=True),
                MUTED,
                anchor="mm",
            )


def _render_landscape(data: dict[str, Any], width: int, height: int, *, compact: bool) -> bytes:
    from PIL import ImageDraw

    from social_recap_service import (
        GOLD,
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
    margin = 36 if compact else 44

    # Slim brand strip over photo
    top_h = 70 if compact else 78
    draw.rectangle([0, 0, width, top_h], fill=(6, 10, 20))
    draw.rectangle([0, top_h, width, top_h + 4], fill=accent)

    logo = _load_brand_logo(48 if compact else 56)
    if logo:
        img.paste(logo, (margin, (top_h - logo.size[1]) // 2), logo)
        brand_x = margin + logo.size[0] + 12
    else:
        brand_x = margin
    _draw_styled_text(
        draw,
        (brand_x, top_h // 2 - 8),
        "MX FANTASY LEAGUE",
        _load_display_font(20 if compact else 24, bold=True),
        accent,
        anchor="lm",
    )
    _draw_styled_text(
        draw,
        (brand_x, top_h // 2 + 14),
        "TIPPA GRATIS",
        _load_font_px(14 if compact else 15, bold=True),
        GOLD,
        anchor="lm",
    )

    series = _plain_draw_text(data.get("series") or "RACE")
    pill = f"{series} · HYPE"
    pf = _load_font_px(15 if compact else 16, bold=True)
    pw = _text_width(pf, pill) + 26
    ph = 30
    draw.rounded_rectangle(
        [width - margin - pw, (top_h - ph) // 2, width - margin, (top_h - ph) // 2 + ph],
        radius=15,
        fill=(accent[0] // 5, accent[1] // 5, accent[2] // 5),
        outline=accent,
        width=2,
    )
    _draw_styled_text(draw, (width - margin - pw // 2, top_h // 2), pill, pf, WHITE, anchor="mm")

    # One inset title card — photo stays dominant above/around it
    panel_h = 285 if compact else 305
    panel_top = height - margin - panel_h
    _draw_title_card(
        img,
        draw,
        data,
        box=(margin, panel_top, width - margin, height - margin),
        accent=accent,
        accent2=accent2,
        compact=compact,
        story=False,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_story(data: dict[str, Any]) -> bytes:
    from PIL import ImageDraw

    from social_recap_service import (
        GOLD,
        _draw_styled_text,
        _load_brand_logo,
        _load_display_font,
        _load_font_px,
    )

    accent, accent2 = _series_colors(data.get("series") or "")
    width, height = W_STORY, H_STORY
    img = _paint_cinematic_backdrop(width, height, data, accent)
    draw = ImageDraw.Draw(img)
    margin = 40

    top_h = 100
    draw.rectangle([0, 0, width, top_h], fill=(6, 10, 20))
    draw.rectangle([0, top_h, width, top_h + 5], fill=accent)
    logo = _load_brand_logo(64)
    if logo:
        img.paste(logo, (margin, (top_h - logo.size[1]) // 2), logo)
        brand_x = margin + logo.size[0] + 14
    else:
        brand_x = margin
    _draw_styled_text(
        draw, (brand_x, top_h // 2 - 10), "MX FANTASY LEAGUE", _load_display_font(26, bold=True), accent, anchor="lm"
    )
    _draw_styled_text(draw, (brand_x, top_h // 2 + 18), "TIPPA GRATIS", _load_font_px(17, bold=True), GOLD, anchor="lm")

    # Tall inset card — all copy inside, photo frames it
    panel_top = int(height * 0.38)
    _draw_title_card(
        img,
        draw,
        data,
        box=(margin, panel_top, width - margin, height - margin),
        accent=accent,
        accent2=accent2,
        compact=False,
        story=True,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

