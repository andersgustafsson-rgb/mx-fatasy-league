"""Import + resize MX Fantasy wordmark for site header and posters."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ALT = Path(
    r"C:\Users\agrac\.cursor\projects\c-projects-MittFantasySpel\assets"
    r"\c__Users_agrac_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_ChatGPT_Image_1_sep._2026_12_59_14-7d34de78-8506-4f37-81f5-0f14a4dd801d.png"
)
SRC_LEGACY = Path(
    r"C:\Users\agrac\.cursor\projects\c-projects-MittFantasySpel\assets"
    r"\c__Users_agrac_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_ChatGPT_Image_1_sep._2026_12_47_02-63986823-1c91-4c52-83ac-7b1b6a591cc5.png"
)


def _resolve_src() -> Path:
    for p in (
        ROOT / "static" / "images" / "mx_fantasy_logo_source.png",
        SRC_ALT,
        SRC_LEGACY,
    ):
        if p.is_file():
            return p
    raise FileNotFoundError("Logo source not found")


def _is_cyan_border(r: int, g: int, b: int) -> bool:
    return b > 110 and g > 85 and r < 100 and (g + b) > r * 2.2


def _is_bright_content(r: int, g: int, b: int) -> bool:
    lum = r + g + b
    return lum > 120 or (lum > 70 and b > r + 25)


def _crop_inner_frame(img):
    """Crop to the glowing inner badge frame — ignore outer black + streaks."""
    from PIL import Image

    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    # Focus on central band (ignore corner streaks)
    x0_band = int(w * 0.08)
    x1_band = int(w * 0.92)

    row_cyan = []
    row_bright = []
    for y in range(h):
        cyan = 0
        bright = 0
        for x in range(x0_band, x1_band):
            r, g, b = px[x, y]
            if _is_cyan_border(r, g, b):
                cyan += 1
            if _is_bright_content(r, g, b):
                bright += 1
        row_cyan.append(cyan)
        row_bright.append(bright)

    band_w = x1_band - x0_band
    # Top/bottom cyan border lines of inner frame
    top = None
    bottom = None
    for y, c in enumerate(row_cyan):
        if c >= max(8, band_w * 0.12):
            top = y if top is None else top
            bottom = y
    # Fallback: bright content block (text area)
    if top is None:
        for y, b in enumerate(row_bright):
            if b >= max(12, band_w * 0.04):
                top = y if top is None else top
                bottom = y

    if top is None or bottom is None:
        return _trim_content(img, threshold=35)

    # Horizontal: cyan vertical edges of frame
    col_cyan = []
    for x in range(w):
        c = sum(1 for y in range(top, bottom + 1) if _is_cyan_border(*px[x, y]))
        col_cyan.append(c)

    left = None
    right = None
    frame_h = bottom - top + 1
    for x, c in enumerate(col_cyan):
        if c >= max(4, frame_h * 0.08):
            left = x if left is None else left
            right = x

    if left is None or right is None:
        left, right = x0_band, x1_band

    pad_x, pad_y = 2, 2
    return img.crop(
        (
            max(0, left - pad_x),
            max(0, top - pad_y),
            min(w, right + pad_x + 1),
            min(h, bottom + pad_y + 1),
        )
    )


def _trim_content(img, *, threshold: int = 22):
    """Crop near-black margins (fallback)."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r + g + b > threshold * 3:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x <= min_x:
        return img
    pad = 2
    return img.crop(
        (
            max(0, min_x - pad),
            max(0, min_y - pad),
            min(w, max_x + pad + 1),
            min(h, max_y + pad + 1),
        )
    )


def _resize(img, max_w: int, max_h: int):
    from PIL import Image

    out = img.copy()
    out.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return out


def main() -> None:
    from PIL import Image

    src = _resolve_src()
    raw = Image.open(src).convert("RGBA")
    raw.save(ROOT / "static" / "images" / "mx_fantasy_logo_source.png", optimize=True)

    tight = _crop_inner_frame(raw)

    out = ROOT / "static" / "images"
    out.mkdir(parents=True, exist_ok=True)

    sidebar = _resize(tight, 720, 160)
    sidebar.save(out / "mx_fantasy_logo_sm.png", optimize=True)

    full = _resize(tight, 960, 200)
    full.save(out / "mx_fantasy_logo.png", optimize=True)

    md = _resize(tight, 600, 140)
    md.save(out / "mx_fantasy_logo_md.png", optimize=True)

    for name in ("mx_fantasy_logo_sm.png", "mx_fantasy_logo.png", "mx_fantasy_logo_md.png"):
        p = out / name
        im = Image.open(p)
        print(f"{name}: {im.size}, {p.stat().st_size} bytes")
    print(f"crop box from source: inner frame {tight.size}")


if __name__ == "__main__":
    main()
