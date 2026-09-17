"""SMX Playoff 2 promo poster — tippa CTA for mx-fantasy.se.

Inspired by official Playoff 2 LA energy: neon lime, stadium backdrop, hero riders.

Usage (repo root):
  py -3 scripts/render_smx_playoff2_promo_poster.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from hype_poster_service import W_FB, H_FB, W_STORY, H_STORY, _cover_crop
from social_recap_service import (
    WHITE,
    _draw_styled_text,
    _load_brand_logo,
    _load_display_font,
    _load_font_px,
    _text_width,
)

# Neon lime like official Playoff 2 art
LIME = (196, 255, 0)
LIME_SOFT = (160, 220, 40)
DARK = (6, 10, 16)

RIDERS = [
    {"name": "KEN ROCZEN", "file": "static/riders/94_ken_roczen.jpg"},
    {"name": "ELI TOMAC", "file": "static/riders/3_eli_tomac.png"},
    {"name": "HAIDEN DEEGAN", "file": "static/riders/38_haiden_deegan.png"},
]


def _open_rgb(rel: str) -> Image.Image | None:
    p = ROOT / rel
    if not p.is_file():
        return None
    try:
        return Image.open(p).convert("RGBA")
    except Exception:
        return None


def _paint_splash(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color, alpha: int = 90) -> None:
    x0, y0, x1, y1 = box
    # Soft diagonal smear
    for i in range(8):
        ox = i * 10
        draw.polygon(
            [
                (x0 + ox, y0),
                (x1 + ox // 2, y0 + 20 + i * 4),
                (x1 - 30 + ox // 3, y1),
                (x0 - 10, y1 - 10),
            ],
            fill=(*color, max(20, alpha - i * 8)),
        )


def _backdrop(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), DARK)
    for cand in (
        "static/trackmaps/smx/smx_playoff2_carson_poster.jpg",
        "static/trackmaps/smx/smx_playoff2_carson.jpg",
        "static/posters/smx_2026_seed_backdrop.png",
    ):
        p = ROOT / cand
        if not p.is_file():
            continue
        try:
            photo = Image.open(p).convert("RGB")
            photo = _cover_crop(photo, width, height)
            photo = ImageEnhance.Contrast(photo).enhance(1.18)
            photo = ImageEnhance.Color(photo).enhance(1.12)
            photo = ImageEnhance.Brightness(photo).enhance(0.78)
            base = photo
            break
        except Exception:
            continue

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 0, width, height], fill=(4, 8, 14, 70))

    # Top / bottom vignettes
    for y in range(int(height * 0.28)):
        a = int(200 * (1 - y / max(1, height * 0.28)))
        od.line([(0, y), (width, y)], fill=(0, 0, 0, a))
    bot = int(height * 0.55)
    for i, y in enumerate(range(height - bot, height)):
        t = i / max(bot - 1, 1)
        od.line([(0, y), (width, y)], fill=(4, 8, 14, int(40 + 200 * (t**1.15))))

    # Neon corner splashes
    _paint_splash(od, (-40, -20, int(width * 0.28), int(height * 0.18)), LIME, 70)
    _paint_splash(
        od,
        (int(width * 0.72), int(height * 0.78), width + 60, height + 40),
        LIME,
        55,
    )

    out = Image.alpha_composite(base.convert("RGBA"), overlay)
    return out.convert("RGB")


def _cutout_rider(src: Image.Image, target_h: int) -> Image.Image:
    """Portrait → tall hero cutout with soft edge fade at bottom."""
    # Prefer upper body / head
    w, h = src.size
    # Center-weighted crop to ~3:4 then scale
    target_aspect = 0.72
    crop_h = h
    crop_w = int(crop_h * target_aspect)
    if crop_w > w:
        crop_w = w
        crop_h = int(crop_w / target_aspect)
    left = max(0, (w - crop_w) // 2)
    top = max(0, int((h - crop_h) * 0.08))
    face = src.crop((left, top, left + crop_w, min(h, top + crop_h)))
    nh = target_h
    nw = max(1, int(face.size[0] * (nh / max(face.size[1], 1))))
    face = face.resize((nw, nh), Image.Resampling.LANCZOS)

    # Soft bottom fade into poster
    alpha = face.split()[-1] if face.mode == "RGBA" else Image.new("L", face.size, 255)
    fade = Image.new("L", face.size, 255)
    fd = ImageDraw.Draw(fade)
    band = max(40, nh // 5)
    for i in range(band):
        a = int(255 * (1 - i / max(band - 1, 1)))
        fd.line([(0, nh - band + i), (nw, nh - band + i)], fill=a)
    alpha = Image.composite(fade, Image.new("L", face.size, 0), alpha)
    face.putalpha(alpha)

    # Subtle rim light
    rim = Image.new("RGBA", face.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    rd.rectangle([0, 0, nw - 1, nh - 1], outline=(*LIME, 70), width=2)
    face = Image.alpha_composite(face, rim)
    return face


def render_promo(*, layout: str = "facebook") -> bytes:
    story = (layout or "").lower() == "story"
    width, height = (W_STORY, H_STORY) if story else (W_FB, H_FB)
    img = _backdrop(width, height).convert("RGBA")
    draw = ImageDraw.Draw(img)
    m = 48 if story else 44

    # Brand chip top-left
    logo = _load_brand_logo(72 if story else 64)
    chip_h = 92 if story else 78
    chip_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip_layer)
    cd.rectangle([0, 0, width, chip_h], fill=(6, 10, 16, 210))
    cd.rectangle([0, chip_h, width, chip_h + 5], fill=(*LIME, 255))
    img = Image.alpha_composite(img, chip_layer)
    draw = ImageDraw.Draw(img)

    bx = m
    if logo:
        img.paste(logo, (m, (chip_h - logo.size[1]) // 2), logo)
        bx = m + logo.size[0] + 16
    _draw_styled_text(
        draw,
        (bx, chip_h // 2 - 12),
        "MX FANTASY LEAGUE",
        _load_display_font(26 if story else 28, bold=True),
        LIME,
        anchor="lm",
        stroke=(0, 0, 0),
        stroke_width=2,
    )
    _draw_styled_text(
        draw,
        (bx, chip_h // 2 + 16),
        "TIPPA GRATIS  ·  mx-fantasy.se",
        _load_font_px(16 if story else 15, bold=True),
        WHITE,
        anchor="lm",
    )

    # Title block
    title_y = chip_h + (70 if story else 36)
    playoff_f = _load_display_font(92 if story else 108, bold=True)
    num_f = _load_display_font(120 if story else 140, bold=True)
    _draw_styled_text(
        draw,
        (m, title_y),
        "PLAYOFF",
        playoff_f,
        WHITE,
        anchor="lt",
        stroke=(0, 0, 0),
        stroke_width=4,
        glow=(0, 0, 0),
    )
    # Measure PLAYOFF width to place the neon 2
    pw = _text_width(playoff_f, "PLAYOFF")
    _draw_styled_text(
        draw,
        (m + pw + (18 if story else 22), title_y - (8 if story else 12)),
        "2",
        num_f,
        LIME,
        anchor="lt",
        stroke=(0, 0, 0),
        stroke_width=4,
        glow=LIME_SOFT,
    )

    sub_y = title_y + (100 if story else 112)
    _draw_styled_text(
        draw,
        (m, sub_y),
        "LOS ANGELES, CA",
        _load_display_font(28 if story else 30, bold=True),
        WHITE,
        anchor="lt",
        stroke=(0, 0, 0),
        stroke_width=2,
    )
    _draw_styled_text(
        draw,
        (m, sub_y + (36 if story else 38)),
        "DIGNITY HEALTH SPORTS PARK  |  ",
        _load_font_px(20 if story else 22, bold=True),
        WHITE,
        anchor="lt",
    )
    venue_w = _text_width(_load_font_px(20 if story else 22, bold=True), "DIGNITY HEALTH SPORTS PARK  |  ")
    _draw_styled_text(
        draw,
        (m + venue_w, sub_y + (36 if story else 38)),
        "SEPT 19",
        _load_font_px(20 if story else 22, bold=True),
        LIME,
        anchor="lt",
        stroke=(0, 0, 0),
        stroke_width=2,
    )

    # Rider heroes
    rider_h = int(height * (0.48 if story else 0.58))
    gap = 18 if story else 22
    portraits = []
    for r in RIDERS:
        raw = _open_rgb(r["file"])
        if raw is None:
            continue
        portraits.append((_cutout_rider(raw, rider_h), r["name"]))

    if portraits:
        total_w = sum(p.size[0] for p, _ in portraits) + gap * (len(portraits) - 1)
        start_x = max(m, (width - total_w) // 2)
        base_y = height - rider_h - (210 if story else 130)
        x = start_x
        for port, name in portraits:
            # Soft ground shadow
            shadow = Image.new("RGBA", (port.size[0] + 40, 36), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.ellipse([0, 0, shadow.size[0], shadow.size[1]], fill=(0, 0, 0, 110))
            shadow = shadow.filter(ImageFilter.GaussianBlur(8))
            img.paste(
                shadow,
                (x - 20, base_y + port.size[1] - 28),
                shadow,
            )
            img.paste(port, (x, base_y), port)
            x += port.size[0] + gap

        # Names under riders
        name_f = _load_display_font(22 if story else 26, bold=True)
        x = start_x
        name_y = base_y + rider_h + (8 if story else 4)
        draw = ImageDraw.Draw(img)
        for port, name in portraits:
            cx = x + port.size[0] // 2
            _draw_styled_text(
                draw,
                (cx, name_y),
                name,
                name_f,
                WHITE,
                anchor="mt",
                stroke=(0, 0, 0),
                stroke_width=3,
            )
            x += port.size[0] + gap

    # CTA bar
    cta_h = 88 if story else 74
    cta_y = height - cta_h
    bar = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rectangle([0, cta_y, width, height], fill=(6, 10, 16, 235))
    bd.rectangle([0, cta_y, width, cta_y + 5], fill=(*LIME, 255))
    img = Image.alpha_composite(img.convert("RGBA"), bar)
    draw = ImageDraw.Draw(img)

    _draw_styled_text(
        draw,
        (width // 2, cta_y + cta_h // 2 - (10 if story else 8)),
        "TIPPA PLAYOFF 2 NU",
        _load_display_font(28 if story else 30, bold=True),
        LIME,
        anchor="mm",
        stroke=(0, 0, 0),
        stroke_width=2,
    )
    _draw_styled_text(
        draw,
        (width // 2, cta_y + cta_h // 2 + (18 if story else 16)),
        "mx-fantasy.se  ·  gratis konto  ·  SMX World Championship",
        _load_font_px(15 if story else 16, bold=True),
        WHITE,
        anchor="mm",
    )

    out = img.convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> int:
    out_dir = ROOT / "static" / "posters"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "facebook": out_dir / "smx_playoff2_promo_fb.png",
        "story": out_dir / "smx_playoff2_promo_story.png",
    }
    for layout, path in paths.items():
        data = render_promo(layout=layout)
        path.write_bytes(data)
        print(f"Wrote {path} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
