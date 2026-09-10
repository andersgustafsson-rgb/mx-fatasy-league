"""Render MXoN Facebook promo poster — last year's winners + Ernée 2026 tippa CTA.

Usage (repo root):
  py -3 scripts/render_mxon_promo_poster.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from hype_poster_service import W_FB, H_FB, W_STORY, H_STORY, _cover_crop
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

# 2025 MXoN (Ironman) — official nations classification
PODIUM_2025 = [
    {"place": 1, "code": "AUS", "name": "Australia", "pts": 19, "flag": "au.png"},
    {"place": 2, "code": "USA", "name": "USA", "pts": 33, "flag": "us.png"},
    {"place": 3, "code": "FRA", "name": "France", "pts": 33, "flag": "fr.png"},
]
SWEDEN_2025 = {"place": 7, "code": "SWE", "name": "Sverige", "pts": 84, "flag": "se.png"}

ACCENT = (250, 204, 21)  # nations gold
ACCENT2 = (52, 211, 153)


def _flag_path(filename: str) -> Path | None:
    p = ROOT / "static" / "images" / "mxon" / "flags" / filename
    return p if p.is_file() else None


def _paste_flag(base: Image.Image, flag_file: str, box: tuple[int, int, int, int]) -> None:
    path = _flag_path(flag_file)
    if not path:
        return
    try:
        flag = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = box
        tw, th = max(1, x1 - x0), max(1, y1 - y0)
        flag = flag.resize((tw, th), Image.Resampling.LANCZOS)
        # subtle border
        border = Image.new("RGBA", (tw + 4, th + 4), (0, 0, 0, 180))
        base.paste(border, (x0 - 2, y0 - 2), border)
        base.paste(flag, (x0, y0), flag)
    except Exception:
        pass


def _backdrop(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), (10, 14, 28))
    hero = ROOT / "static" / "images" / "mxon" / "ernee_aerial.jpg"
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
    od.rectangle([0, 0, width, height], fill=(4, 8, 18, 50))
    top_band = max(100, height // 6)
    for y in range(top_band):
        a = int(170 * (1 - y / top_band))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))
    bot_band = int(height * 0.62)
    for i, y in enumerate(range(height - bot_band, height)):
        t = i / max(bot_band - 1, 1)
        a = int(50 + 195 * (t**1.3))
        od.line([(0, y), (width, y)], fill=(4, 8, 18, min(235, a)))

    streak = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streak)
    for i in range(6):
        y0 = int(height * 0.18) + i * 60
        sd.line(
            [(-40, y0), (width + 40, y0 + int(height * 0.1))],
            fill=(ACCENT[0], ACCENT[1], ACCENT[2], 20 - i * 2),
            width=2,
        )
    streak = streak.filter(ImageFilter.GaussianBlur(1.2))
    out = base.convert("RGBA")
    out = Image.alpha_composite(out, overlay)
    out = Image.alpha_composite(out, streak)
    return out.convert("RGB")


def render_mxon_promo(*, layout: str = "facebook") -> bytes:
    layout = (layout or "facebook").lower()
    if layout == "story":
        width, height = W_STORY, H_STORY
        story = True
    else:
        width, height = W_FB, H_FB
        story = False

    img = _backdrop(width, height)
    draw = ImageDraw.Draw(img)
    margin = 40 if story else 44

    # Brand strip
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

    # Main card
    if story:
        card = (margin, int(height * 0.32), width - margin, height - margin)
    else:
        card = (margin, height - margin - 430, width - margin, height - margin)
    x0, y0, x1, y1 = card
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=22,
        fill=(8, 12, 24),
        outline=ACCENT,
        width=2,
    )
    draw.rectangle([x0 + 20, y0, x1 - 20, y0 + 4], fill=GOLD)

    y = y0 + 22
    cx = (x0 + x1) // 2
    _draw_styled_text(
        draw,
        (cx if story else x0 + 36, y),
        "FÖRRA ÅRETS MÄSTARE",
        _load_font_px(14 if story else 15, bold=True),
        ACCENT2,
        anchor="mt" if story else "lt",
    )
    y += 28

    title = "AUSTRALIA TOG GULD 2025"
    tf = _load_display_font(36 if story else 40, bold=True)
    if story:
        _draw_styled_text(draw, (cx, y), _plain_draw_text(title), tf, WHITE, anchor="mt")
    else:
        _draw_styled_text(draw, (x0 + 36, y), _plain_draw_text(title), tf, WHITE, anchor="lt")
    y += 48 if story else 46

    _draw_styled_text(
        draw,
        (cx if story else x0 + 36, y),
        _plain_draw_text("Ironman · tvåa USA · trea Frankrike · Sverige 7:a"),
        _load_font_px(15 if story else 17, bold=True),
        GOLD,
        anchor="mt" if story else "lt",
    )
    y += 36

    # Podium rows with flags
    row_h = 58 if story else 52
    for row in PODIUM_2025:
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row["place"], "")
        # Avoid emoji on Windows rendering issues — use text medals
        medal_txt = {1: "#1", 2: "#2", 3: "#3"}[row["place"]]
        ry = y
        draw.rounded_rectangle(
            [x0 + 28, ry, x1 - 28, ry + row_h],
            radius=12,
            fill=(14, 20, 36),
            outline=(ACCENT[0] // 2, ACCENT[1] // 2, ACCENT[2] // 2),
            width=1,
        )
        flag_box = (x0 + 40, ry + 12, x0 + 40 + 44, ry + 12 + 28)
        _paste_flag(img, row["flag"], flag_box)
        draw = ImageDraw.Draw(img)  # refresh after paste
        _draw_styled_text(
            draw,
            (x0 + 100, ry + row_h // 2),
            f"{medal_txt}  {row['name']}",
            _load_display_font(20 if story else 22, bold=True),
            WHITE,
            anchor="lm",
        )
        _draw_styled_text(
            draw,
            (x1 - 44, ry + row_h // 2),
            f"{row['pts']} p",
            _load_font_px(18, bold=True),
            GOLD,
            anchor="rm",
        )
        y += row_h + 10

    # Sweden callout
    draw.rounded_rectangle(
        [x0 + 28, y, x1 - 28, y + 44],
        radius=12,
        fill=(6, 40, 30),
        outline=ACCENT2,
        width=2,
    )
    _paste_flag(img, SWEDEN_2025["flag"], (x0 + 40, y + 8, x0 + 40 + 40, y + 8 + 26))
    draw = ImageDraw.Draw(img)
    _draw_styled_text(
        draw,
        (x0 + 96, y + 22),
        _plain_draw_text(f"Sverige #{SWEDEN_2025['place']} 2025 — kan vi klättra i Ernée?"),
        _load_font_px(15 if story else 16, bold=True),
        WHITE,
        anchor="lm",
    )
    y += 58

    # CTA
    hook = "Nu kör vi MXoN Fantasy 2026"
    _draw_styled_text(
        draw,
        (cx if story else x0 + 36, y),
        _plain_draw_text(hook),
        _load_display_font(22 if story else 24, bold=True),
        WHITE,
        anchor="mt" if story else "lt",
    )
    y += 36

    btn_h = 58
    if story:
        draw.rounded_rectangle([x0 + 36, y, x1 - 36, y + btn_h], radius=16, fill=ACCENT)
        _draw_styled_text(
            draw,
            (cx, y + btn_h // 2),
            "TIPPA TOPP 5 NATIONER · mx-fantasy.se",
            _load_display_font(20, bold=True),
            (8, 15, 30),
            anchor="mm",
        )
        y += btn_h + 18
        _draw_styled_text(
            draw,
            (cx, y),
            "Klassfavoriter MXGP / MX2 / OPEN · gratis",
            _load_font_px(16, bold=True),
            MUTED,
            anchor="mt",
        )
    else:
        draw.rounded_rectangle([x0 + 36, y, x1 - 36, y + btn_h], radius=14, fill=ACCENT)
        _draw_styled_text(
            draw,
            (cx, y + btn_h // 2),
            "TIPPA NU · mx-fantasy.se",
            _load_display_font(22, bold=True),
            (8, 15, 30),
            anchor="mm",
        )
        _draw_styled_text(
            draw,
            (cx, y1 - 22),
            "Topp 5 nationer · Klassfavoriter · Picks låses före lördagens kval",
            _load_font_px(14, bold=True),
            MUTED,
            anchor="mm",
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


CAPTION = """🏁 MXoN Ernée 2026 — tippa Nations!

Förra året på Ironman:
🥇 Australia
🥈 USA
🥉 France
🇸🇪 Sverige slutade 7:a — kan vi klättra i Frankrike?

Tippa topp 5 nationer + klassfavoriter (MXGP / MX2 / OPEN).
Gratis på mx-fantasy.se

👉 mx-fantasy.se

#MXoN #MotocrossOfNations #Ernée2026 #MXFantasy #Nations #Australia
"""


def main() -> int:
    out_dir = ROOT / "static" / "posters"
    out_dir.mkdir(parents=True, exist_ok=True)
    fb = render_mxon_promo(layout="facebook")
    story = render_mxon_promo(layout="story")
    (out_dir / "mxon_ernee_2026_promo_fb.png").write_bytes(fb)
    (out_dir / "mxon_ernee_2026_promo_story.png").write_bytes(story)
    (out_dir / "mxon_ernee_2026_promo_caption.txt").write_text(CAPTION, encoding="utf-8")
    print(f"Wrote {out_dir / 'mxon_ernee_2026_promo_fb.png'} ({len(fb)} bytes)")
    print(f"Wrote {out_dir / 'mxon_ernee_2026_promo_story.png'} ({len(story)} bytes)")
    print("--- Facebook text ---")
    print(CAPTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
