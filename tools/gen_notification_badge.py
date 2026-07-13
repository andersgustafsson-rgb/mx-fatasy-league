"""Generate Android status-bar notification badge (sparse white silhouette)."""
from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "icons" / "mx_fantasy_app_icon_192.png"
OUT = ROOT / "static" / "icons" / "mx_notification_badge.png"
OUT_B64 = ROOT / "static" / "icons" / "mx_notification_badge.b64.txt"


def _silhouette_from_app(src_path: Path, canvas: int, content_max: int) -> Image.Image:
    """Helmet/goggles only — exclude MX FANTASY text at bottom of app icon."""
    src = Image.open(src_path).convert("RGBA")
    w, h = src.size
    top = src.crop((0, 0, w, int(h * 0.62)))

    mask = Image.new("L", top.size, 0)
    sp = top.load()
    mp = mask.load()
    tw, th = top.size
    for y in range(th):
        for x in range(tw):
            r, g, b, a = sp[x, y]
            if a < 40:
                continue
            lum = r * 0.299 + g * 0.587 + b * 0.114
            if lum < 55 and max(r, g, b) < 75:
                continue
            strength = int(min(255, a * (0.45 + lum / 190.0) * 1.15))
            if strength > 28:
                mp[x, y] = max(mp[x, y], strength)

    bbox = mask.getbbox()
    if not bbox:
        return _draw_simple_goggles(canvas, content_max)

    cropped = mask.crop(bbox)
    cw, ch = cropped.size
    scale = min(content_max / cw, content_max / ch)
    nw = max(1, int(cw * scale))
    nh = max(1, int(ch * scale))
    resized = cropped.resize((nw, nh), Image.LANCZOS)

    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ox = (canvas - nw) // 2
    oy = (canvas - nh) // 2
    op = out.load()
    rp = resized.load()
    for y in range(nh):
        for x in range(nw):
            if rp[x, y] > 64:
                op[ox + x, oy + y] = (255, 255, 255, 255)
    return out


def _draw_simple_goggles(canvas: int, content_max: int) -> Image.Image:
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    cx, cy = canvas // 2, canvas // 2
    s = content_max / 96.0
    lw = max(2, int(5 * s))
    r = int(14 * s)
    draw.ellipse((cx - int(34 * s), cy - r, cx - int(8 * s), cy + r), fill=(255, 255, 255, 255))
    draw.ellipse((cx + int(8 * s), cy - r, cx + int(34 * s), cy + r), fill=(255, 255, 255, 255))
    draw.rectangle(
        (cx - int(8 * s), cy - int(4 * s), cx + int(8 * s), cy + int(4 * s)),
        fill=(255, 255, 255, 255),
    )
    draw.line((cx - int(42 * s), cy, cx - int(34 * s), cy), fill=(255, 255, 255, 255), width=lw)
    draw.line((cx + int(34 * s), cy, cx + int(42 * s), cy), fill=(255, 255, 255, 255), width=lw)
    return out


def make_badge(src_path: Path, out_path: Path, canvas: int = 192, content_max: int = 64) -> None:
    out = _silhouette_from_app(src_path, canvas, content_max)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, optimize=True)
    data = base64.b64encode(out_path.read_bytes()).decode("ascii")
    OUT_B64.write_text(data, encoding="utf-8")
    opaque = sum(1 for p in out.getdata() if p[3] > 0)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes, opaque={opaque}/{canvas * canvas})")
    print(f"Wrote {OUT_B64} ({len(data)} chars b64)")


if __name__ == "__main__":
    make_badge(SRC, OUT)
