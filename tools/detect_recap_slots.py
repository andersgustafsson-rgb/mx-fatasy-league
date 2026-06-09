"""Detect grey avatar circles and name plates on recap graphic template."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GRAPHIC = ROOT / "static/recap_templates/recap_fb_graphic.png"


def grey_mask(px, x, y):
    r, g, b = px[x, y]
    return 88 < r < 178 and abs(r - g) < 24 and abs(g - b) < 24


def find_blobs(path: Path, y0: int, y1: int, x0: int, x1: int) -> list[dict]:
    im = Image.open(path).convert("RGB")
    px = im.load()
    w, h = im.size
    visited: set[tuple[int, int]] = set()
    blobs: list[dict] = []
    for y in range(max(0, y0), min(y1, h)):
        for x in range(max(0, x0), min(x1, w)):
            if (x, y) in visited or not grey_mask(px, x, y):
                continue
            stack = [(x, y)]
            pts: list[tuple[int, int]] = []
            while stack and len(pts) < 25000:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                visited.add((cx, cy))
                pts.append((cx, cy))
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if x0 <= nx < x1 and y0 <= ny < y1 and (nx, ny) not in visited:
                        if grey_mask(px, nx, ny):
                            stack.append((nx, ny))
            if 800 < len(pts) < 12000:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                r = (max(xs) - min(xs) + max(ys) - min(ys)) / 4
                blobs.append(
                    {
                        "cx": int(round(cx)),
                        "cy": int(round(cy)),
                        "r": int(round(r)),
                        "n": len(pts),
                        "x0": min(xs),
                        "x1": max(xs),
                        "y0": min(ys),
                        "y1": max(ys),
                    }
                )
    return sorted(blobs, key=lambda b: (b["cy"], b["cx"]))


def find_name_plates(px, y0, y1, x0, x1) -> list[dict]:
    plates = []
    for y in range(y0, y1):
        segs = []
        s = None
        for x in range(x0, x1):
            r, g, b = px[x, y]
            if r > 200 and g > 200 and b > 200:
                if s is None:
                    s = x
            elif s is not None:
                if x - s >= 40:
                    segs.append((s, x - 1))
                s = None
        if s is not None and x1 - s >= 40:
            segs.append((s, x1 - 1))
        for a, b in segs:
            if 50 < b - a < 220:
                plates.append({"x0": a, "x1": b, "y0": y, "y1": y, "cx": (a + b) // 2})
    # cluster by cx
    by_cx: dict[int, dict] = {}
    for p in plates:
        k = round(p["cx"] / 30) * 30
        if k not in by_cx:
            by_cx[k] = {"x0": p["x0"], "x1": p["x1"], "y0": p["y0"], "y1": p["y0"], "cx": p["cx"]}
        else:
            cur = by_cx[k]
            cur["x0"] = min(cur["x0"], p["x0"])
            cur["x1"] = max(cur["x1"], p["x1"])
            cur["y0"] = min(cur["y0"], p["y0"])
            cur["y1"] = max(cur["y1"], p["y0"])
    return sorted(by_cx.values(), key=lambda p: p["cx"])


if __name__ == "__main__":
    im = Image.open(GRAPHIC).convert("RGB")
    px = im.load()
    print("size", im.size)
    for label, x0, x1, y0, y1 in [
        ("450 riders", 40, 1080, 280, 520),
        ("250 riders", 1110, 2160, 280, 520),
        ("fantasy", 40, 1100, 1000, 1350),
    ]:
        print(f"\n=== {label} avatars ===")
        for b in find_blobs(GRAPHIC, y0, y1, x0, x1):
            print(b)
    print("\n=== 450 name plates ===")
    for p in find_name_plates(px, 720, 800, 40, 1080):
        print(p)
    print("=== 250 name plates ===")
    for p in find_name_plates(px, 720, 800, 1110, 2160):
        print(p)
