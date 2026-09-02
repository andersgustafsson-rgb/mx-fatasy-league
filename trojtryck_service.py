"""Generate DTF-ready print files for jersey name/number designs."""
from __future__ import annotations

import base64
import functools
import io
import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# Svemo Motocross §3.6.1 — ryggnummer (mm)
SVEMO_NUMBER_HEIGHT_MM = 200
SVEMO_STROKE_MM = 30
SVEMO_GAP_MM = 15
SVEMO_ONE_DIGIT_WIDTH_MM = 100
SVEMO_TWO_DIGIT_WIDTH_MM = 200
SVEMO_THREE_DIGIT_WIDTH_MM = 250

DEFAULT_DPI = 300


def mm_to_px(mm: float, dpi: int = DEFAULT_DPI) -> int:
    return max(1, int(round(mm / 25.4 * dpi)))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    l1, l2 = _relative_luminance(c1), _relative_luminance(c2)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_hex(color: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = (color or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return fallback
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _load_block_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _normalize_font_key(font: str) -> str:
    return (font or "Black Ops One").strip().lower()


def _load_jersey_font(font: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Same Google Fonts as preview (static/fonts/trojtryck)."""
    key = _normalize_font_key(font)
    path = _jersey_font_files().get(key)
    if path and path.is_file():
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError as exc:
            print(f"jersey font load error ({font}): {exc}")
    return _load_block_font(size)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    if hasattr(draw, "textbbox"):
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]
    return draw.textsize(text, font=font)  # type: ignore[attr-defined]


def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    outline_px: int,
    anchor: str = "mm",
) -> None:
    stroke = max(1, int(outline_px))
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke,
        stroke_fill=outline,
    )


def svemo_presets() -> list[dict[str, Any]]:
    return [
        {
            "id": "open_mx1",
            "label": "Open MX1",
            "fill": "#111111",
            "outline": "#FFFFFF",
            "plate": "Vit botten / svart siffra",
        },
        {
            "id": "open_mx2",
            "label": "Open MX2",
            "fill": "#FFFFFF",
            "outline": "#111111",
            "plate": "Svart botten / vit siffra",
        },
        {
            "id": "women",
            "label": "Women Nationell",
            "fill": "#FFFFFF",
            "outline": "#1D4ED8",
            "plate": "Blå botten / vit siffra",
        },
        {
            "id": "ungdom",
            "label": "Ungdom",
            "fill": "#111111",
            "outline": "#FFFFFF",
            "plate": "Vit botten / svart siffra",
        },
        {
            "id": "guldhjalm",
            "label": "Guldhjälm",
            "fill": "#FFFFFF",
            "outline": "#111111",
            "plate": "Svart botten / vit siffra",
        },
        {
            "id": "sidvagn",
            "label": "Sidvagn",
            "fill": "#111111",
            "outline": "#FACC15",
            "plate": "Gul botten / svart siffra",
        },
    ]


def print_tiers() -> list[dict[str, Any]]:
    """Tryckpaket — pris inkl. namn + nummer enligt Svemo."""
    return [
        {
            "id": "motoaction_brand",
            "label": "Motoaction-logga",
            "badge": "Billigast",
            "price": 179,
            "description": "Namn + nummer + liten motoaction.se-logga tryckt på ryggen. Rabatterat — ni får synas hos oss.",
            "includes_brand_logo": True,
            "allows_custom_logo": False,
        },
        {
            "id": "standard",
            "label": "Standard",
            "badge": "Vanligast",
            "price": 249,
            "description": "Endast namn och startnummer på ryggen. Ingen extra logotyp.",
            "includes_brand_logo": False,
            "allows_custom_logo": False,
        },
        {
            "id": "custom_back_logo",
            "label": "Egen rygglogga",
            "badge": "Premium",
            "price": 349,
            "description": "Namn + nummer + ladda upp egen logga (team/sponsor). Vi granskar filen före tryck.",
            "includes_brand_logo": False,
            "allows_custom_logo": True,
        },
    ]


def mock_jerseys() -> list[dict[str, Any]]:
    """Demo catalog — real Motoaction products with local product photos for preview."""
    return [
        {
            "id": "thor-prime-strike",
            "brand": "THOR",
            "name": "Prime Strike",
            "variant": "Grå/Gul/Svart",
            "price": 557,
            "article_id": "2126257",
            "motoaction_url": "https://www.motoaction.se/crosstroja-prime-strike-gra-gul-svart-thor-p2128349",
            "color": "Grå/Gul/Svart",
            "fabric": "#f8fafc",
            "images": {
                "back": "product_thor_prime_back.png",
                "thumb": "thumb_thor_prime_strike.png",
            },
            "print_zone": {"left": 16, "top": 20, "right": 16, "bottom": 36},
            "preview_crop": {"width_pct": 172, "offset_x_pct": -36, "offset_y_pct": -9},
            "name_scale": 0.16,
            "number_scale": 0.50,
        },
        {
            "id": "alpinestars-racer-graphite",
            "brand": "Alpinestars",
            "name": "Racer Graphite",
            "variant": "Svart/Grå",
            "price": 578,
            "article_id": "2379221",
            "motoaction_url": "https://www.motoaction.se/crosstroja-racer-graphite-svart-gra-alpinestars-p2379895",
            "color": "Svart/Grå",
            "fabric": "#111111",
            "images": {
                "back": "product_alpinestars_racer_graphite_back.png",
                "thumb": "thumb_alpinestars_racer_graphite.png",
            },
            "print_zone": {"left": 18, "top": 18, "right": 18, "bottom": 38},
            "preview_crop": {"width_pct": 158, "offset_x_pct": -29, "offset_y_pct": -6},
            "name_scale": 0.14,
            "number_scale": 0.44,
        },
    ]


def validate_design(
    *,
    name: str,
    number: str,
    fill: str,
    outline: str,
    jersey_fabric: str,
) -> dict[str, Any]:
    name_clean = (name or "").strip().upper()[:18]
    digits = "".join(ch for ch in (number or "") if ch.isdigit())[:3]
    fill_rgb = _parse_hex(fill, (255, 255, 255))
    outline_rgb = _parse_hex(outline, (0, 0, 0))
    fabric_rgb = _parse_hex(jersey_fabric, (20, 20, 20))

    issues: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    if not digits:
        issues.append("Ange minst ett siffertecken (1–999).")
    elif not (1 <= int(digits) <= 999):
        issues.append("Startnummer måste vara 1–999.")

    if not name_clean:
        warnings.append("Efternamn saknas — krävs vid FIM/VM-tävlingar.")

    if contrast_ratio(fill_rgb, fabric_rgb) < 3.0:
        issues.append("För låg kontrast mellan siffra och tröjfärg (Svemo: tydligt synligt).")
    else:
        ok.append("Kontrast siffra ↔ tröja ser OK ut.")

    if contrast_ratio(outline_rgb, fill_rgb) < 2.5:
        warnings.append("Kantlinje kontrasterar svagt mot siffran — överväg tydligare outline.")
    else:
        ok.append("Outline kontrasterar mot siffran.")

    digit_count = len(digits)
    if digit_count == 1:
        ok.append(f"Sifferbredd ~{SVEMO_ONE_DIGIT_WIDTH_MM} mm (1 siffra).")
    elif digit_count == 2:
        ok.append(f"Sifferbredd ~{SVEMO_TWO_DIGIT_WIDTH_MM} mm (2 siffror).")
    elif digit_count == 3:
        ok.append(f"Sifferbredd ~{SVEMO_THREE_DIGIT_WIDTH_MM} mm (3 siffror).")

    ok.append(f"Exporteras i {SVEMO_NUMBER_HEIGHT_MM} mm sifferhöjd @ {DEFAULT_DPI} DPI.")
    ok.append("Blocktyp — inga dekorativa fonter (Svemo §3.6).")

    return {
        "name": name_clean,
        "number": digits,
        "issues": issues,
        "warnings": warnings,
        "ok": ok,
        "valid": not issues,
    }


LOGO_HEIGHT_MM = 64
LOGO_WIDTH_MM = 190
NAME_NUMBER_GAP_MM = 18
NUMBER_LOGO_GAP_MM = 14
CUT_INSET_MM = 1
REG_MARK_MM = 5

JERSEY_FONT_FILES: dict[str, Path] = {}


def _jersey_font_files() -> dict[str, Path]:
    global JERSEY_FONT_FILES
    if JERSEY_FONT_FILES:
        return JERSEY_FONT_FILES
    fonts_dir = Path(__file__).resolve().parent / "static" / "fonts" / "trojtryck"
    JERSEY_FONT_FILES = {
        "black ops one": fonts_dir / "BlackOpsOne-Regular.ttf",
        "racing sans one": fonts_dir / "RacingSansOne-Regular.ttf",
        "orbitron": fonts_dir / "Orbitron-Bold.ttf",
    }
    return JERSEY_FONT_FILES


# Populate on import
JERSEY_FONT_FILES = _jersey_font_files()

_ROOT = Path(__file__).resolve().parent
MOTOACTION_LOGO_BLACK_EPS = _ROOT / "static" / "images" / "trojtryck" / "motoaction_logo_black.eps"
MOTOACTION_LOGO_WHITE_EPS = _ROOT / "static" / "images" / "trojtryck" / "motoaction_logo_white.eps"
MOTOACTION_LOGO_ASPECT = {
    "black": 402 / 145,
    "white": 346 / 102,
}

ArtLayer = tuple[Image.Image, int, int, str]  # image, x, y, kind: text | brand_logo | custom_logo

LOGO_PLATE_PAD_MM = 3


def _ghostscript_binary() -> Path | None:
    for candidate in (
        _ROOT / "tools" / "gs" / "bin" / "gswin64c.exe",
        _ROOT / "tools" / "gs" / "bin" / "gswin32c.exe",
        Path(os.environ.get("GS_PROG", "")),
    ):
        if candidate.is_file():
            return candidate
    found = shutil.which("gswin64c") or shutil.which("gswin32c") or shutil.which("gs")
    return Path(found) if found else None


def _configure_eps_ghostscript() -> None:
    gs = _ghostscript_binary()
    if not gs:
        return
    from PIL import EpsImagePlugin

    EpsImagePlugin.gs_windows_binary = str(gs)


def _motoaction_logo_variant(fabric_hex: str) -> str:
    fabric_rgb = _parse_hex(fabric_hex, (248, 250, 252))
    if _relative_luminance(fabric_rgb) > 0.45:
        return "black"
    return "white"


def _motoaction_eps_path(variant: str) -> Path:
    return MOTOACTION_LOGO_BLACK_EPS if variant == "black" else MOTOACTION_LOGO_WHITE_EPS


def _prepare_logo_rgba(img: Image.Image, variant: str) -> Image.Image:
    """Drop EPS page background; keep only logo ink."""
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 16:
                px[x, y] = (0, 0, 0, 0)
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > 245:
                px[x, y] = (0, 0, 0, 0)
            elif variant == "white":
                px[x, y] = (255, 255, 255, 255) if lum > 120 else (255, 255, 255, 255)
            else:
                px[x, y] = (30, 41, 59, 255) if lum < 220 else (0, 0, 0, 0)
    bbox = rgba.split()[-1].getbbox()
    return rgba.crop(bbox) if bbox else rgba


@functools.lru_cache(maxsize=32)
def _render_motoaction_logo_rgba_cached(variant: str, max_w: int, max_h: int) -> bytes:
    logo = _render_motoaction_logo_rgba_uncached(variant=variant, max_w=max_w, max_h=max_h)
    if logo is None:
        raise RuntimeError(f"Kunde inte rendera Motoaction-logga ({variant}).")
    buf = io.BytesIO()
    logo.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_motoaction_logo_rgba(*, variant: str, max_w: int, max_h: int) -> Image.Image | None:
    try:
        data = _render_motoaction_logo_rgba_cached(variant, max_w, max_h)
    except RuntimeError:
        return None
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _render_motoaction_logo_rgba_uncached(*, variant: str, max_w: int, max_h: int) -> Image.Image | None:
    """Rasterize vector EPS on demand at the requested pixel size (scalable source)."""
    if variant not in MOTOACTION_LOGO_ASPECT:
        return None
    path = _motoaction_eps_path(variant)
    if not path.is_file():
        return None
    if not _ghostscript_binary():
        raise RuntimeError(
            "Ghostscript saknas — behövs för att skala EPS-loggan. "
            "Installera gs eller kör med tools/gs/bin/gswin64c.exe."
        )
    _configure_eps_ghostscript()
    try:
        with Image.open(path) as im:
            bw, bh = im.size
            if bw <= 0 or bh <= 0:
                return None
            scale = min(max_w / bw, max_h / bh)
            im.load(scale=max(scale, 0.05))
            rgba = _prepare_logo_rgba(im, variant)
            rgba.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            return rgba
    except Exception as exc:
        print(f"motoaction EPS render error ({variant}): {exc}")
        return None


def render_motoaction_logo_png(*, variant: str, max_w: int, max_h: int) -> bytes:
    return _render_motoaction_logo_png_cached(variant, max_w, max_h)


@functools.lru_cache(maxsize=24)
def _render_motoaction_logo_png_cached(variant: str, max_w: int, max_h: int) -> bytes:
    return _render_motoaction_logo_rgba_cached(variant, max_w, max_h)


def _load_motoaction_brand_logo(
    *,
    fabric_hex: str,
    max_w: int,
    max_h: int,
    logo_variant: str | None = None,
) -> Image.Image | None:
    if logo_variant in ("black", "white"):
        variant = logo_variant
    else:
        variant = _motoaction_logo_variant(fabric_hex)
    return render_motoaction_logo_rgba(variant=variant, max_w=max_w, max_h=max_h)


def _load_image_rgba(source: str | bytes | None, max_w: int, max_h: int) -> Image.Image | None:
    if not source:
        return None
    try:
        if isinstance(source, bytes):
            img = Image.open(io.BytesIO(source)).convert("RGBA")
        else:
            path = Path(source)
            if not path.is_file():
                return None
            img = Image.open(path).convert("RGBA")
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


def _render_glyph_layer(
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    outline_px: int,
) -> Image.Image:
    pad = outline_px + 4
    probe = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(probe)
    tw, th = _text_size(pdraw, text, font)
    layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _draw_outlined_text(
        draw,
        (layer.size[0] // 2, layer.size[1] // 2),
        text,
        font,
        fill,
        outline,
        outline_px,
        anchor="mm",
    )
    return layer


def _stack_artwork(
    *,
    name: str,
    number: str,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    dpi: int,
    font: str = "Black Ops One",
    bottom_logo: Image.Image | None = None,
    bottom_logo_kind: str | None = None,
    with_layers: bool = False,
) -> Image.Image | tuple[Image.Image, list[ArtLayer]]:
    """MX layout: namn överst, nummer i mitten, logga längst ner."""
    work_dpi = 96
    work, layers = _stack_artwork_work(
        name=name,
        number=number,
        fill=fill,
        outline=outline,
        dpi=work_dpi,
        font=font,
        bottom_logo=_scale_logo_for_dpi(bottom_logo, work_dpi, dpi) if bottom_logo else None,
        bottom_logo_kind=bottom_logo_kind,
    )

    target_w = mm_to_px(
        {
            1: SVEMO_ONE_DIGIT_WIDTH_MM,
            2: SVEMO_TWO_DIGIT_WIDTH_MM,
            3: SVEMO_THREE_DIGIT_WIDTH_MM,
        }.get(len("".join(ch for ch in (number or "") if ch.isdigit())[:3]), SVEMO_TWO_DIGIT_WIDTH_MM),
        dpi,
    )
    logo_extra = mm_to_px(LOGO_HEIGHT_MM + NUMBER_LOGO_GAP_MM, dpi) if bottom_logo else 0
    name_extra = mm_to_px(55 + NAME_NUMBER_GAP_MM, dpi) if (name or "").strip() else 0
    target_h = mm_to_px(SVEMO_NUMBER_HEIGHT_MM, dpi) + name_extra + logo_extra + mm_to_px(16, dpi)
    scale = max(target_w / max(work.size[0], 1), target_h / max(work.size[1], 1))
    out_w = max(1, int(work.size[0] * scale))
    out_h = max(1, int(work.size[1] * scale))
    scaled = work.resize((out_w, out_h), Image.Resampling.LANCZOS)
    if not with_layers:
        return scaled

    scaled_layers: list[ArtLayer] = []
    for layer, lx, ly, kind in layers:
        sw = max(1, int(round(layer.size[0] * scale)))
        sh = max(1, int(round(layer.size[1] * scale)))
        scaled_layers.append(
            (
                layer.resize((sw, sh), Image.Resampling.LANCZOS),
                int(round(lx * scale)),
                int(round(ly * scale)),
                kind,
            )
        )
    return scaled, scaled_layers


def _scale_logo_for_dpi(logo: Image.Image, target_dpi: int, source_dpi: int) -> Image.Image:
    if target_dpi == source_dpi:
        return logo
    ratio = target_dpi / source_dpi
    return logo.resize(
        (max(1, int(logo.size[0] * ratio)), max(1, int(logo.size[1] * ratio))),
        Image.Resampling.LANCZOS,
    )


def _stack_artwork_work(
    *,
    name: str,
    number: str,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    dpi: int,
    font: str = "Black Ops One",
    bottom_logo: Image.Image | None = None,
    bottom_logo_kind: str | None = None,
) -> tuple[Image.Image, list[ArtLayer]]:
    name_clean = (name or "").strip().upper()[:18]
    digits = "".join(ch for ch in (number or "") if ch.isdigit())[:3]
    if not digits:
        raise ValueError("number required")

    outline_px = max(2, mm_to_px(15, dpi))
    gap_num = mm_to_px(NAME_NUMBER_GAP_MM, dpi)
    gap_logo = mm_to_px(NUMBER_LOGO_GAP_MM, dpi)
    pad = mm_to_px(8, dpi)

    num_h = mm_to_px(SVEMO_NUMBER_HEIGHT_MM, dpi)
    name_h = mm_to_px(55, dpi) if name_clean else 0
    logo_h = bottom_logo.size[1] if bottom_logo else 0
    logo_w = bottom_logo.size[0] if bottom_logo else 0

    num_font = _load_jersey_font(font, max(24, int(num_h * 0.92)))
    name_font = _load_jersey_font(font, max(16, int(name_h * 0.85))) if name_clean else None

    probe = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(probe)
    tw, th = _text_size(pdraw, digits, num_font)
    if len(digits) > 1:
        tw += mm_to_px(SVEMO_GAP_MM, dpi) * max(0, len(digits) - 1)
    nw, nh = (0, 0)
    if name_font and name_clean:
        nw, nh = _text_size(pdraw, name_clean, name_font)

    content_w = max(tw, nw, logo_w) + pad * 2 + outline_px * 4
    content_h = (
        ((nh + outline_px * 2 + gap_num) if name_clean else 0)
        + th + outline_px * 2
        + (gap_logo + logo_h if bottom_logo else 0)
        + pad * 2
        + outline_px * 2
    )

    art = Image.new("RGBA", (content_w, content_h), (0, 0, 0, 0))
    layers: list[ArtLayer] = []
    cx = content_w // 2
    y = pad + outline_px * 2

    if name_font and name_clean:
        name_layer = _render_glyph_layer(
            name_clean,
            name_font,
            fill,
            outline,
            max(2, outline_px // 2),
        )
        nx = cx - name_layer.size[0] // 2
        ny = y
        layers.append((name_layer, nx, ny, "text"))
        art.paste(name_layer, (nx, ny), name_layer)
        y = ny + name_layer.size[1] + gap_num

    digit_gap = mm_to_px(SVEMO_GAP_MM, dpi)
    digit_layers: list[tuple[Image.Image, int]] = []
    for d in digits:
        digit_layer = _render_glyph_layer(d, num_font, fill, outline, outline_px)
        digit_layers.append((digit_layer, digit_layer.size[0]))

    total_w = sum(w for _, w in digit_layers) + digit_gap * max(0, len(digit_layers) - 1)
    x_cursor = cx - total_w // 2
    max_digit_h = max(layer.size[1] for layer, _ in digit_layers)
    for digit_layer, layer_w in digit_layers:
        dx = x_cursor
        dy = y + (max_digit_h - digit_layer.size[1]) // 2
        layers.append((digit_layer, dx, dy, "text"))
        art.paste(digit_layer, (dx, dy), digit_layer)
        x_cursor += layer_w + digit_gap
    y += max_digit_h

    if bottom_logo:
        y += gap_logo
        lx = (content_w - bottom_logo.size[0]) // 2
        kind = bottom_logo_kind or "custom_logo"
        layers.append((bottom_logo, lx, y, kind))
        art.paste(bottom_logo, (lx, y), bottom_logo)

    return art, layers


def _resolve_bottom_logo(
    *,
    dpi: int,
    include_brand_logo: bool,
    custom_logo_bytes: bytes | None,
    jersey_fabric: str = "#f8fafc",
    logo_variant: str | None = None,
) -> Image.Image | None:
    if custom_logo_bytes:
        return _load_image_rgba(
            custom_logo_bytes,
            mm_to_px(LOGO_WIDTH_MM, dpi),
            mm_to_px(LOGO_HEIGHT_MM, dpi),
        )
    if include_brand_logo:
        return _load_motoaction_brand_logo(
            fabric_hex=jersey_fabric,
            max_w=mm_to_px(LOGO_WIDTH_MM, dpi),
            max_h=mm_to_px(LOGO_HEIGHT_MM, dpi),
            logo_variant=logo_variant,
        )
    return None


def _alpha_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    alpha = img.split()[-1]
    return alpha.getbbox() or (0, 0, img.size[0], img.size[1])


def _dilate_mask(mask: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return mask
    out = mask
    remaining = radius
    while remaining > 0:
        k = min(remaining * 2 + 1, 31)
        if k % 2 == 0:
            k += 1
        out = out.filter(ImageFilter.MaxFilter(k))
        remaining -= k // 2
    return out


def _erode_mask(mask: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return mask
    out = mask
    remaining = radius
    while remaining > 0:
        k = min(remaining * 2 + 1, 31)
        if k % 2 == 0:
            k += 1
        out = out.filter(ImageFilter.MinFilter(k))
        remaining -= k // 2
    return out


def _cut_contour_mask(alpha: Image.Image, inset_px: int) -> Image.Image:
    """Kiss-cut line ~inset_px inside the outer artwork edge (avoids white halo when weeding)."""
    w, h = alpha.size
    work = alpha
    scale_back = 1.0
    max_dim = max(w, h)
    if max_dim > 960:
        scale_back = max_dim / 960.0
        work = alpha.resize((max(1, int(w / scale_back)), max(1, int(h / scale_back))), Image.Resampling.BILINEAR)
        inset_px = max(1, int(round(inset_px / scale_back)))

    mask = work.point(lambda a: 255 if a > 20 else 0, mode="L")
    inset = max(1, inset_px)
    inner_edge = _erode_mask(mask, inset)
    inner_fill = _erode_mask(inner_edge, max(1, 2))
    contour = ImageChops.subtract(inner_edge, inner_fill)
    if scale_back > 1.0:
        contour = contour.resize((w, h), Image.Resampling.NEAREST)
    return contour


def _cut_contour_logo_plate(width: int, height: int, inset_px: int) -> Image.Image:
    """Rektangulär skärlinje ~inset_px innanför plattans ytterkant (logga med bakgrund)."""
    w, h = max(1, width), max(1, height)
    inset = max(1, inset_px)
    full = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(full)
    draw.rectangle((0, 0, w - 1, h - 1), fill=255)
    inner = Image.new("L", (w, h), 0)
    inner_draw = ImageDraw.Draw(inner)
    ix0, iy0 = inset, inset
    ix1, iy1 = w - 1 - inset, h - 1 - inset
    if ix1 > ix0 and iy1 > iy0:
        inner_draw.rectangle((ix0, iy0, ix1, iy1), fill=255)
    return ImageChops.subtract(full, inner)


def _compose_brand_logo_plate(
    logo: Image.Image,
    variant: str,
    dpi: int,
) -> tuple[Image.Image, int, int]:
    """Solid bakgrundsplatta runt loggan — som i EPS-filerna (en enkel weed-yta)."""
    alpha = logo.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return logo, 0, 0

    bx0, by0, bx1, by1 = bbox
    pad = mm_to_px(LOGO_PLATE_PAD_MM, dpi)
    plate_w = (bx1 - bx0) + pad * 2
    plate_h = (by1 - by0) + pad * 2
    bg = (0, 0, 0, 255) if variant == "white" else (255, 255, 255, 255)

    plate = Image.new("RGBA", (plate_w, plate_h), bg)
    plate.paste(logo, (pad - bx0, pad - by0), logo)
    return plate, bx0 - pad, by0 - pad


def _prepare_production_artwork(
    art: Image.Image,
    layers: list[ArtLayer],
    logo_variant: str | None,
    dpi: int,
) -> tuple[Image.Image, list[ArtLayer]]:
    """Byter ut transparent Motoaction-logga mot solid platta i produktionsfilen."""
    variant = logo_variant if logo_variant in ("black", "white") else "black"
    art = art.copy()
    prepared: list[ArtLayer] = []

    for layer, lx, ly, kind in layers:
        if kind != "brand_logo":
            prepared.append((layer, lx, ly, kind))
            continue
        plate, off_x, off_y = _compose_brand_logo_plate(layer, variant, dpi)
        px, py = lx + off_x, ly + off_y
        art.paste(plate, (px, py), plate)
        prepared.append((plate, px, py, kind))

    return art, prepared


def _paste_layer_cut_contours(
    sheet: Image.Image,
    *,
    layers: list[ArtLayer],
    origin_x: int,
    origin_y: int,
    cut_inset: int,
    color: tuple[int, int, int, int] = (255, 0, 255, 255),
) -> tuple[int, int, int, int] | None:
    stroke = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    bounds: list[tuple[int, int, int, int]] = []
    for layer, lx, ly, kind in layers:
        if kind == "brand_logo":
            contour = _cut_contour_logo_plate(layer.size[0], layer.size[1], cut_inset)
        else:
            contour = _cut_contour_mask(layer.split()[-1], cut_inset)
        bb = contour.getbbox()
        if not bb:
            continue
        cut_img = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        cut_img.paste(color, mask=contour)
        px = origin_x + lx
        py = origin_y + ly
        stroke.paste(cut_img, (px, py), cut_img)
        bounds.append((px + bb[0], py + bb[1], px + bb[2], py + bb[3]))
    sheet.alpha_composite(stroke)
    if not bounds:
        return None
    return (
        min(b[0] for b in bounds),
        min(b[1] for b in bounds),
        max(b[2] for b in bounds),
        max(b[3] for b in bounds),
    )


def _draw_registration_marks(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, mark: int) -> None:
    cyan = (0, 180, 255, 255)
    segments = [
        [(x0 - mark, y0), (x0, y0), (x0, y0 - mark)],
        [(x1, y0 - mark), (x1, y0), (x1 + mark, y0)],
        [(x0 - mark, y1), (x0, y1), (x0, y1 + mark)],
        [(x1, y1 + mark), (x1, y1), (x1 + mark, y1)],
    ]
    for seg in segments:
        draw.line(seg[:2], fill=cyan, width=max(2, mark // 8))
        draw.line(seg[1:], fill=cyan, width=max(2, mark // 8))


def render_print_png(
    *,
    name: str,
    number: str,
    fill: str = "#FFFFFF",
    outline: str = "#111111",
    dpi: int = DEFAULT_DPI,
    include_name: bool = True,
    include_brand_logo: bool = False,
    custom_logo_bytes: bytes | None = None,
    jersey_fabric: str = "#f8fafc",
    logo_variant: str | None = None,
    font: str = "Black Ops One",
) -> bytes:
    """Transparent PNG — ren tryckyta (DTF), namn + nummer + ev. logga under."""
    fill_rgb = _parse_hex(fill, (255, 255, 255))
    outline_rgb = _parse_hex(outline, (0, 0, 0))
    logo = _resolve_bottom_logo(
        dpi=dpi,
        include_brand_logo=include_brand_logo,
        custom_logo_bytes=custom_logo_bytes,
        jersey_fabric=jersey_fabric,
        logo_variant=logo_variant,
    )

    art = _stack_artwork(
        name=name if include_name else "",
        number=number,
        fill=fill_rgb,
        outline=outline_rgb,
        dpi=dpi,
        font=font,
        bottom_logo=logo,
    )
    buf = io.BytesIO()
    art.save(buf, format="PNG", dpi=(dpi, dpi), optimize=True)
    return buf.getvalue()


def render_production_png(
    *,
    name: str,
    number: str,
    fill: str = "#FFFFFF",
    outline: str = "#111111",
    dpi: int = DEFAULT_DPI,
    include_brand_logo: bool = False,
    custom_logo_bytes: bytes | None = None,
    jersey_fabric: str = "#f8fafc",
    logo_variant: str | None = None,
    font: str = "Black Ops One",
    order_label: str = "",
) -> bytes:
    """Produktionsunderlag: tryck + magenta skärlinje + registreringsmarkeringar."""
    fill_rgb = _parse_hex(fill, (255, 255, 255))
    outline_rgb = _parse_hex(outline, (0, 0, 0))
    logo = _resolve_bottom_logo(
        dpi=dpi,
        include_brand_logo=include_brand_logo,
        custom_logo_bytes=custom_logo_bytes,
        jersey_fabric=jersey_fabric,
        logo_variant=logo_variant,
    )
    bottom_logo_kind: str | None = None
    if include_brand_logo:
        bottom_logo_kind = "brand_logo"
    elif custom_logo_bytes:
        bottom_logo_kind = "custom_logo"

    art, layers = _stack_artwork(
        name=name,
        number=number,
        fill=fill_rgb,
        outline=outline_rgb,
        dpi=dpi,
        font=font,
        bottom_logo=logo,
        bottom_logo_kind=bottom_logo_kind,
        with_layers=True,
    )

    variant = (
        logo_variant
        if logo_variant in ("black", "white")
        else _motoaction_logo_variant(jersey_fabric)
    )
    art, layers = _prepare_production_artwork(art, layers, variant, dpi)

    bx0, by0, bx1, by1 = _alpha_bbox(art)
    cut_inset = mm_to_px(CUT_INSET_MM, dpi)
    reg = mm_to_px(REG_MARK_MM, dpi)
    label_h = mm_to_px(14, dpi)
    margin = mm_to_px(10, dpi)

    pad = mm_to_px(6, dpi)
    cut_x0 = bx0 - pad
    cut_y0 = by0 - pad
    cut_x1 = bx1 + pad
    cut_y1 = by1 + pad

    sheet_w = cut_x1 - cut_x0 + margin * 2 + reg * 2
    sheet_h = cut_y1 - cut_y0 + margin * 2 + reg * 2 + label_h

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (245, 247, 250, 255))

    ox = margin + reg - cut_x0
    oy = margin + reg - cut_y0
    sheet.paste(art, (ox, oy), art)

    cut_bounds = _paste_layer_cut_contours(
        sheet,
        layers=layers,
        origin_x=ox,
        origin_y=oy,
        cut_inset=cut_inset,
    )
    draw = ImageDraw.Draw(sheet)
    if cut_bounds:
        _draw_registration_marks(draw, *cut_bounds, reg)

    meta_font = _load_block_font(max(10, mm_to_px(3.5, dpi)))
    label = order_label or f"{name} #{number} · nummer {SVEMO_NUMBER_HEIGHT_MM} mm · {dpi} DPI"
    draw.text(
        (margin, sheet_h - label_h),
        f"SKÄRLINJE = magenta · 1 mm innanför ytterkant · {label}",
        fill=(30, 41, 59, 255),
        font=meta_font,
    )
    draw.text(
        (margin, sheet_h - label_h + mm_to_px(5, dpi)),
        (
            "Logga: en platta med bakgrund (rektangulär skärlinje). "
            "Namn/nummer: skärlinje per tecken."
            if include_brand_logo
            else "Namn/nummer: skärlinje per tecken."
        ),
        fill=(100, 116, 139, 255),
        font=meta_font,
    )

    buf = io.BytesIO()
    sheet.save(buf, format="PNG", dpi=(dpi, dpi), optimize=True)
    return buf.getvalue()
