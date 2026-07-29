"""Download WSX rider cards from worldsupercrosschampionship.com into static/riders/wsx/.

Also sets Rider.image_url for official WSX 2026 roster rows (local DB).
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

BASE = "https://worldsupercrosschampionship.com"
RIDERS_URL = f"{BASE}/riders/"
OUT_DIR = Path("static/riders/wsx")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Skip placeholders / non-rider media
SKIP_NAME_FRAGMENTS = (
    "silhouette",
    "logo",
    "asset-",
    "g891",
    "tc_logo",
)

# Official roster names we care about (match main._WSX_2026_ROSTER)
ROSTER_NAMES = {
    "Cooper Webb",
    "Justin Hill",
    "Joey Savatgy",
    "Christian Craig",
    "Jason Anderson",
    "Colt Nichols",
    "Vince Friese",
    "Jorge Zaragoza",
    "Greg Aranda",
    "Kevin Moranz",
    "Austin Politelli",
    "Enzo Lopes",
    "Luke Clout",
    "Mitchell Harrison",
    "Maxime Desprey",
    "Jordi Tixier",
    "Max Anstie",
    "Devin Simonson",
    "Shane McElrath",
    "Cole Thompson",
    "Calvin Fonvieille",
    "Ryan Breece",
    "Robbie Wageman",
    "Henry Miller",
    "Jake Cannon",
    "Michael Hicks",
    "Brian Hsu",
    "Kyle Peters",
    "Crockett Myers",
    "Hector Assuncao",
    "Nico Koch",
    "Mike Alessi",
    "Tom Vialle",
    "Dean Wilson",
    "Jack Chambers",
    "Luke Fauser",
    "Cameron McAdoo",
    "Brodie Connolly",
}

# Alternate spellings on WSX site → our DB name
NAME_ALIASES = {
    "hector assunção": "Hector Assuncao",
    "hector assuncao": "Hector Assuncao",
    "cameron mcadoo": "Cameron McAdoo",
}


def slug_nospace(name: str) -> str:
    nl = (name or "").lower().strip().replace(".", "")
    return "".join(c for c in nl if c.isalnum())


def normalize_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip())
    # Title case if jammed together: JasonAnderson → Jason Anderson
    if " " not in s and re.search(r"[a-z][A-Z]", s):
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    key = s.lower()
    if key in NAME_ALIASES:
        return NAME_ALIASES[key]
    # Match roster ignoring accents / punctuation
    def fold(x: str) -> str:
        x = x.lower()
        for a, b in (("ã", "a"), ("á", "a"), ("ç", "c"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
            x = x.replace(a, b)
        return re.sub(r"[^a-z0-9]", "", x)

    folded = fold(s)
    for official in ROSTER_NAMES:
        if fold(official) == folded:
            return official
    return s


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def abs_url(u: str) -> str:
    u = unescape(u.strip())
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u


def fullsize_candidates(url: str) -> list[str]:
    """Prefer original upload over WP resized -396x600 variants."""
    out: list[str] = []
    u = abs_url(url)
    out.append(u)
    stripped = re.sub(r"-\d+x\d+(?=\.(?:png|jpe?g|webp))", "", u, flags=re.I)
    if stripped != u:
        out.insert(0, stripped)
    # also try .jpg if .png card
    return list(dict.fromkeys(out))


def parse_rider_cards(html: str) -> dict[str, str]:
    """name -> headshot URL from riders listing."""
    mapping: dict[str, str] = {}
    # Each rider-entry article
    for block in re.findall(
        r'<article[^>]*class="[^"]*rider-entry[^"]*"[\s\S]*?</article>',
        html,
        flags=re.I,
    ):
        title_m = re.search(r'title="([^"]+)"', block)
        name_m = re.search(
            r'class="rider-entry-name[^"]*"[^>]*>\s*<[^>]+>\s*([^<]+)',
            block,
            flags=re.I,
        )
        # fallback: permalink title or h3 text
        name = None
        if title_m:
            name = title_m.group(1)
        if not name and name_m:
            name = name_m.group(1)
        if not name:
            h = re.search(r"<h[123][^>]*>(.*?)</h[123]>", block, flags=re.I | re.S)
            if h:
                name = re.sub(r"<[^>]+>", "", h.group(1))
        if not name:
            continue
        name = normalize_name(unescape(name))

        img_m = re.search(
            r'class="rider-entry-headshot"[^>]*>\s*<img[^>]+src="([^"]+)"',
            block,
            flags=re.I,
        )
        if not img_m:
            img_m = re.search(
                r'rider-entry-headshot[\s\S]{0,400}?src="([^"]+\.(?:png|jpe?g|webp)[^"]*)"',
                block,
                flags=re.I,
            )
        if not img_m:
            continue
        src = abs_url(img_m.group(1))
        low = src.lower()
        if any(s in low for s in SKIP_NAME_FRAGMENTS):
            # Keep silhouette mapped only if we have nothing else — mark skip
            continue
        mapping[name] = src
    return mapping


def download_best(url: str) -> tuple[bytes, str] | None:
    last_err = None
    for cand in fullsize_candidates(url):
        try:
            data = fetch(cand)
            if len(data) < 2000:
                continue
            # Always store as real JPEG for `slug (1).jpg` convention
            from io import BytesIO

            from PIL import Image

            im = Image.open(BytesIO(data)).convert("RGB")
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue(), ".jpg"
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            last_err = e
            continue
    if last_err:
        print(f"  [fail] {url}: {last_err}")
    return None


def main() -> int:
    print(f"Fetching {RIDERS_URL} ...")
    html = fetch(RIDERS_URL).decode("utf-8", "replace")
    cards = parse_rider_cards(html)
    print(f"Parsed {len(cards)} rider cards with photos")
    for n, u in sorted(cards.items()):
        print(f"  {n}: {u}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}  # name -> relative path riders/wsx/...

    for name, url in sorted(cards.items()):
        slug = slug_nospace(name)
        # Keep app convention: "<slug> (1).jpg" (even for png source — convert name)
        # Prefer writing actual extension that browsers accept; frontend tries .jpg first
        # so we save as .jpg filename when possible by keeping png bytes under .jpg only if jpeg,
        # else save real ext AND a (1).jpg copy isn't needed if we also set image_url.
        result = download_best(url)
        if not result:
            print(f"[SKIP] no image for {name}")
            continue
        data, ext = result
        primary = OUT_DIR / f"{slug}.jpg"
        primary.write_bytes(data)
        # Drop legacy numbered / spaced variants
        for old in OUT_DIR.glob(f"{slug} (*).*"):
            try:
                old.unlink()
            except OSError:
                pass
        for old in OUT_DIR.glob(f"{slug}_*.*"):
            if old.resolve() == primary.resolve():
                continue
            # keep only if different slug prefix accidentally — skip
            pass
        underscore = "".join(
            c if c.isalnum() else "_" for c in name.lower().replace(".", "")
        ).strip("_")
        underscore = re.sub(r"_+", "_", underscore)
        if underscore and underscore != slug:
            for old in OUT_DIR.glob(f"{underscore} (*).*"):
                try:
                    old.unlink()
                except OSError:
                    pass
            underscored = OUT_DIR / f"{underscore}.jpg"
            if underscored.exists() and underscored.resolve() != primary.resolve():
                try:
                    underscored.unlink()
                except OSError:
                    pass
        rel = f"riders/wsx/{slug}.jpg"
        saved[name] = rel
        print(f"[OK] {name} -> {primary.name} ({len(data)} bytes)")

    missing_roster = sorted(n for n in ROSTER_NAMES if n not in saved)
    print("\nRoster without WSX site photo:", ", ".join(missing_roster) or "(none)")

    # Fill-ins / riders not on WSX cards — try RacerX CDN headshot.
    if missing_roster:
        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from app.portrait_urls import lookup_racerx_portrait_by_name, normalize_racerx_portrait_url

        try:
            from app.routes.admin import _fetch_racerx_og_image
        except Exception:
            _fetch_racerx_og_image = None  # type: ignore[assignment]

        for name in missing_roster:
            url = lookup_racerx_portrait_by_name(name)
            if not url and _fetch_racerx_og_image:
                url = _fetch_racerx_og_image(name)
            url = normalize_racerx_portrait_url(url) if url else None
            if not url:
                print(f"[RacerX SKIP] {name}")
                continue
            result = download_best(url)
            if not result:
                print(f"[RacerX FAIL] {name} ({url})")
                continue
            data, _ext = result
            slug = slug_nospace(name)
            primary = OUT_DIR / f"{slug}.jpg"
            primary.write_bytes(data)
            rel = f"riders/wsx/{slug}.jpg"
            saved[name] = rel
            print(f"[RacerX OK] {name} -> {primary.name} ({len(data)} bytes)")

    # Update local DB image_url for WSX riders
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.apply_racerx_bio import _make_app
    from models import Rider, db

    app = _make_app()
    updated = 0
    with app.app_context():
        for name, rel in saved.items():
            rows = (
                Rider.query.filter(
                    Rider.name == name,
                    Rider.class_name.in_(("wsx_sx1", "wsx_sx2")),
                ).all()
            )
            for r in rows:
                # Prefer static path; clear blob so file is used
                if (r.image_url or "").strip() != rel:
                    r.image_url = rel
                    updated += 1
                if getattr(r, "rider_image_data", None):
                    r.rider_image_data = None
                    updated += 1
        db.session.commit()
    print(f"DB rows touched: {updated}")
    print(f"Files in {OUT_DIR}: {len(list(OUT_DIR.glob('*.jpg')))}")

    try:
        from tools.generate_wsx_avatars import main as gen_avatars

        gen_avatars()
    except Exception as exc:
        print(f"Avatar generation skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
