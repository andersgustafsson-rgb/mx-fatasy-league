"""Process soldier silhouette PNG: drop white/grid, tint gold for MAD plaque."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "images" / "mad_honor_salute_src.png"
OUT = ROOT / "static" / "images" / "mad_honor_salute.png"

# Pixels darker than this become visible silhouette (0–255 luminance).
DARK_CUTOFF = 95
GOLD = np.array([201, 181, 106], dtype=np.uint8)


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    data = np.array(im, dtype=np.float32)
    lum = 0.299 * data[:, :, 0] + 0.587 * data[:, :, 1] + 0.114 * data[:, :, 2]
    alpha = np.clip((DARK_CUTOFF - lum) / DARK_CUTOFF, 0.0, 1.0)
    alpha = (alpha * 255).astype(np.uint8)

    out = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
    out[:, :, 0] = GOLD[0]
    out[:, :, 1] = GOLD[1]
    out[:, :, 2] = GOLD[2]
    out[:, :, 3] = alpha

    result = Image.fromarray(out, "RGBA")
    bbox = result.getbbox()
    if bbox:
        result = result.crop(bbox)
    result.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({result.size[0]}x{result.size[1]})")


if __name__ == "__main__":
    main()
