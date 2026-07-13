"""Generate white-on-transparent Android notification badge from app icon."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "icons" / "mx_fantasy_app_icon_192.png"
OUT = ROOT / "static" / "icons" / "mx_notification_badge.png"


def make_badge(src_path: Path, out_path: Path, size: int = 96) -> None:
    img = Image.open(src_path).convert("RGBA").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    src_px = img.load()
    out_px = out.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = src_px[x, y]
            if a < 40:
                continue
            lum = r * 0.299 + g * 0.587 + b * 0.114
            if lum < 50 and max(r, g, b) < 70:
                continue
            alpha = int(min(255, a * (0.35 + lum / 220.0) * 1.35))
            if alpha > 24:
                out_px[x, y] = (255, 255, 255, alpha)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    make_badge(SRC, OUT)
