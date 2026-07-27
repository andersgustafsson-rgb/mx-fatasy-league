"""Generate square face-crop avatars from WSX promo cards.

Usage:
  py -3 tools/generate_wsx_avatars.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path("static/riders/wsx")
OUT = SRC / "avatars"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(SRC.glob("*.jpg")):
        im = Image.open(p).convert("RGB")
        w, h = im.size
        band = im.crop((0, 0, w, int(h * 0.58)))
        bw, bh = band.size
        side = min(bw, bh)
        left = max(0, (bw - side) // 2)
        top = max(0, int(bh * 0.05))
        if top + side > bh:
            top = max(0, bh - side)
        sq = band.crop((left, top, left + side, top + side))
        sq = sq.resize((512, 512), Image.Resampling.LANCZOS)
        dest = OUT / p.name
        sq.save(dest, format="JPEG", quality=90, optimize=True)
        n += 1
        print(f"[OK] {dest.name} ({dest.stat().st_size} bytes)")
    print(f"Wrote {n} avatars → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
