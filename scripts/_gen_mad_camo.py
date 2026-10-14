"""Generate a seamless woodland camo SVG (irregular kidney blobs, not circles)."""
from __future__ import annotations

import math
import random
from pathlib import Path

W, H = 1800, 720
OUT = Path(__file__).resolve().parents[1] / "static" / "images" / "mad_camo.svg"

# Fashion/woodland palette — muted olive, khaki, near-black
LAYERS = [
    # (count, rx, ry, color) — big overlapping fields, fashion/woodland
    (14, 320, 175, "#2c3820"),
    (12, 280, 150, "#4a5330"),
    (11, 250, 140, "#1a2210"),
    (10, 220, 120, "#6a6848"),
    (8, 180, 100, "#3d4628"),
    (7, 150, 85, "#8a8460"),
    (6, 120, 70, "#14180e"),
]


def kidney_pts(cx, cy, rx, ry, rot, seed, n=16):
    rng = random.Random(seed)
    phase = rng.uniform(0, math.tau)
    k2 = rng.uniform(0.38, 0.72)
    k3 = rng.uniform(0.10, 0.28)
    k4 = rng.uniform(0.04, 0.14)
    jag = 0.10
    cr, sr = math.cos(rot), math.sin(rot)
    pts = []
    for i in range(n):
        a = math.tau * i / n
        rmod = (
            1.0
            + k2 * math.sin(2 * a + phase)
            + k3 * math.sin(3 * a + phase * 0.6)
            + k4 * math.sin(5 * a + phase * 1.3)
            + rng.uniform(-jag, jag)
        )
        x = rx * math.cos(a) * rmod
        y = ry * math.sin(a) * rmod * rng.uniform(0.82, 1.12)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def to_path(pts):
    n = len(pts)
    d = [f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d.append(f"C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    d.append("Z")
    return " ".join(d)


def wrap_copies(pts):
    """If a blob crosses a tile edge, also draw it on the opposite side."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    copies = [pts]
    shifts = []
    if min(xs) < 0:
        shifts.append((W, 0))
    if max(xs) > W:
        shifts.append((-W, 0))
    if min(ys) < 0:
        shifts.append((0, H))
    if max(ys) > H:
        shifts.append((0, -H))
    # corners
    extra = []
    for dx, dy in shifts:
        extra.append((dx, dy))
    if min(xs) < 0 and min(ys) < 0:
        extra.append((W, H))
    if min(xs) < 0 and max(ys) > H:
        extra.append((W, -H))
    if max(xs) > W and min(ys) < 0:
        extra.append((-W, H))
    if max(xs) > W and max(ys) > H:
        extra.append((-W, -H))
    for dx, dy in extra:
        copies.append([(x + dx, y + dy) for x, y in pts])
    return copies


def main():
    rng = random.Random(20270320)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        '  <filter id="edge" x="-5%" y="-5%" width="110%" height="110%">',
        '    <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="9" result="n"/>',
        '    <feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G"/>',
        '    <feGaussianBlur stdDeviation="1.4"/>',
        "  </filter>",
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="#1a2214"/>',
        '<g filter="url(#edge)">',
    ]
    seed = 1
    for count, rx, ry, color in LAYERS:
        for _ in range(count):
            cx = rng.uniform(-40, W + 40)
            cy = rng.uniform(-40, H + 40)
            rot = rng.uniform(0, math.tau)
            rx_j = rx * rng.uniform(0.75, 1.28)
            ry_j = ry * rng.uniform(0.7, 1.25)
            # mild stretch — kidney/amoeba, not discs and not noodles
            if rng.random() < 0.35:
                rx_j *= rng.uniform(1.1, 1.35)
                ry_j *= rng.uniform(0.72, 0.9)
            pts = kidney_pts(cx, cy, rx_j, ry_j, rot, seed)
            seed += 1
            for copy in wrap_copies(pts):
                parts.append(f'  <path d="{to_path(copy)}" fill="{color}"/>')
    parts.append("</g>")
    parts.append("</svg>")
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
