"""Render demo jersey back PNGs for /trojtryck prototype."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "images" / "trojtryck"


def _draw_jersey_back(
    *,
    body_top: tuple[int, int, int],
    body_bottom: tuple[int, int, int],
    panel: tuple[int, int, int],
    panel2: tuple[int, int, int] | None,
    label: str,
) -> Image.Image:
    w, h = 720, 960
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Soft shadow
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([120, 860, 600, 940], fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    # Body
    body = [
        (110, 90),
        (610, 90),
        (650, 180),
        (680, 320),
        (660, 520),
        (640, 860),
        (80, 860),
        (60, 520),
        (40, 320),
        (70, 180),
    ]
    for i in range(len(body)):
        x1, y1 = body[i]
        x2, y2 = body[(i + 1) % len(body)]
        draw.line([(x1, y1), (x2, y2)], fill=(0, 0, 0, 40), width=3)
    draw.polygon(body, fill=body_top)

    # Gradient wash
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(120, h):
        t = (y - 120) / (h - 120)
        c = tuple(int(body_top[i] * (1 - t) + body_bottom[i] * t) for i in range(3))
        od.line([(80, y), (640, y)], fill=(*c, 180))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Shoulders
    draw.polygon([(110, 90), (220, 70), (360, 58), (500, 70), (610, 90), (560, 150), (360, 130), (160, 150)], fill=panel)
    if panel2:
        draw.polygon([(160, 150), (360, 130), (560, 150), (520, 250), (360, 235), (200, 250)], fill=panel2)

    # Side panels
    draw.polygon([(60, 520), (120, 540), (130, 820), (80, 860)], fill=(*panel, 180))
    draw.polygon([(640, 520), (600, 540), (590, 820), (640, 860)], fill=(*panel, 180))

    # Collar
    draw.arc([300, 70, 420, 150], start=200, end=-20, fill=(255, 255, 255, 40), width=4)

    # Print zone hint (subtle)
    draw.rounded_rectangle([170, 300, 550, 700], radius=18, outline=(255, 255, 255, 25), width=2)

    # Brand strip
    draw.text((360, 820), label, fill=(255, 255, 255, 90), anchor="mm")

    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    alpine = _draw_jersey_back(
        body_top=(45, 12, 18),
        body_bottom=(18, 6, 8),
        panel=(210, 38, 46),
        panel2=(140, 24, 30),
        label="Alpinestars · Fluid Race",
    )
    alpine.save(OUT / "jersey_alpinestars_back.png", optimize=True)

    fox = _draw_jersey_back(
        body_top=(15, 23, 42),
        body_bottom=(8, 12, 24),
        panel=(14, 116, 190),
        panel2=(56, 189, 248),
        label="Fox Racing · Flexair Pryme",
    )
    fox.save(OUT / "jersey_fox_back.png", optimize=True)

    # Thumbnails for product cards (front-ish mini)
    for src, thumb in (
        (alpine, "thumb_alpinestars.png"),
        (fox, "thumb_fox.png"),
    ):
        t = src.copy()
        t.thumbnail((320, 420), Image.Resampling.LANCZOS)
        t.save(OUT / thumb, optimize=True)

    print("Wrote jersey PNGs to", OUT)


if __name__ == "__main__":
    main()
