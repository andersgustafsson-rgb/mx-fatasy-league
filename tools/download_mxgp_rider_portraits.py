"""Download MXGP rider photos from mxgp.com team pages into static/riders/mxgp/.

Source: https://www.mxgp.com/teams?race_category=1 (MXGP) and race_category=3 (MX2).
Each team page lists official riders with headshots.

Optionally sets Rider.image_url for rows from mxgp_fantasy.mxgp_roster_query() (local DB).

Usage:
  python tools/download_mxgp_rider_portraits.py --dry-run
  python tools/download_mxgp_rider_portraits.py --update-db
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///fantasy_mx_local.db")
os.environ.pop("RENDER", None)

BASE = "https://www.mxgp.com"
TEAMS_URL = f"{BASE}/teams"
OUT_DIR = Path("static/riders/mxgp")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Names in mxgp_fantasy._MXGP_2026_ROSTER (extend when site has more riders)
ROSTER_ALIASES = {
    "ruben fernández": "Ruben Fernandez",
    "ruben fernandez": "Ruben Fernandez",
    "brent van doninck": "Brent Van doninck",
    "janis martins reisulis": "Janis Martins Reisulis",
    "karlis alberts reisulis": "Karlis Alberts Reisulis",
    "karlis reisulis": "Karlis Alberts Reisulis",
    "janis reisulis": "Janis Martins Reisulis",
    "lucas coenen": "Lucas Coenen",
    "romain febvre": "Romain Febvre",
    "kay karssemakers": "Kay Karssemakers",
    "guillem farres": "Guillem Farres",
    "camden mclellan": "Camden McLellan",
    "sacha coenen": "Sacha Coenen",
    "simon längenfelder": "Simon Längenfelder",
    "simon langenfelder": "Simon Längenfelder",
    "liam everts": "Liam Everts",
    "valerio lata": "Valerio Lata",
    "julius mikula": "Julius Mikula",
    "mathis valin": "Mathis Valin",
    "ferruccio zanchi": "Ferruccio Zanchi",
    "maxime grau": "Maxime Grau",
    "noel zanocz": "Noel Zanocz",
}


def fold_name(x: str) -> str:
    x = x.lower()
    for a, b in (
        ("ã", "a"),
        ("á", "a"),
        ("ä", "a"),
        ("ç", "c"),
        ("é", "e"),
        ("è", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ö", "o"),
        ("ú", "u"),
        ("ü", "u"),
        ("ñ", "n"),
    ):
        x = x.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", x)


def slug_nospace(name: str) -> str:
    nl = fold_name((name or "").lower().strip().replace(".", ""))
    return nl or "rider"


def normalize_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", unescape((raw or "").strip()))
    key = s.lower()
    if key in ROSTER_ALIASES:
        return ROSTER_ALIASES[key]
    folded = fold_name(s)
    for alias_key, official in ROSTER_ALIASES.items():
        if fold_name(alias_key) == folded:
            return official
    try:
        from mxgp_fantasy import _MXGP_2026_ROSTER  # noqa: PLC2701

        for name, *_ in _MXGP_2026_ROSTER:
            if fold_name(name) == folded:
                return name
    except Exception:
        pass
    return s


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def abs_url(path: str) -> str:
    u = unescape(path.strip())
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u


def hires_rider_url(thumb_url: str) -> str:
    """Prefer full upload under /sites/default/files/rider/image/ (no Drupal style)."""
    u = abs_url(thumb_url)
    m = re.search(
        r"/sites/default/files/(?:styles/[^/]+/public/)?rider/image/([^?\"]+)",
        u,
        flags=re.I,
    )
    if not m:
        return u.replace("/styles/list_item_202x115/", "/styles/list_page_default/")
    file_part = urllib.parse.unquote(m.group(1))
    return f"{BASE}/sites/default/files/rider/image/{urllib.parse.quote(file_part, safe='/')}"


def parse_team_links(html: str) -> list[str]:
    links: set[str] = set()
    for href in re.findall(r'href="([^"]+)"', html, flags=re.I):
        h = href.split("?")[0].strip()
        if re.search(r"/teams/", h, re.I) and "race_category" not in h:
            if h.startswith("/"):
                links.add(abs_url(h))
            elif h.startswith("http"):
                links.add(h)
    return sorted(links)


def parse_team_riders(html: str) -> dict[str, str]:
    """name -> thumbnail or detail image URL."""
    out: dict[str, str] = {}
    pat = re.compile(
        r"field-rider-image[\s\S]*?"
        r'src="(https://www\.mxgp\.com/sites/default/files/[^"]+rider/image/[^"]+)"'
        r"[\s\S]*?"
        r"views-field-title[\s\S]*?"
        r"<a[^>]*>([^<]+)</a>",
        flags=re.I,
    )
    for img_m, title_m in pat.findall(html):
        name = normalize_name(title_m)
        if name:
            out[name] = img_m
    return out


def team_page_urls(first_html: str, team_url: str) -> list[str]:
    """Team rider lists are paginated (?page=1,2,…)."""
    base = team_url.split("?")[0].rstrip("/")
    pages: set[int] = {0}
    for href in re.findall(r'href="([^"]+)"', first_html, flags=re.I):
        full = abs_url(href)
        if full.split("?")[0].rstrip("/") != base:
            continue
        q = urllib.parse.urlparse(full).query
        for part in q.split("&"):
            if part.startswith("page="):
                try:
                    pages.add(int(part.split("=", 1)[1]))
                except ValueError:
                    pass
    out: list[str] = []
    for p in sorted(pages):
        out.append(base if p == 0 else f"{base}?page={p}")
    return out


def crawl_riders(categories: list[str]) -> dict[str, str]:
    """category id (1=MXGP, 3=MX2) -> merged rider map."""
    merged: dict[str, str] = {}
    for cat in categories:
        url = f"{TEAMS_URL}?race_category={cat}"
        print(f"Fetching teams ({cat}) … {url}")
        html = fetch(url)
        teams = parse_team_links(html)
        print(f"  {len(teams)} team links")
        for i, team_url in enumerate(teams, 1):
            try:
                thtml = fetch(team_url)
            except (HTTPError, URLError, TimeoutError) as e:
                print(f"  [skip team] {team_url}: {e}")
                continue
            riders: dict[str, str] = {}
            for page_url in team_page_urls(thtml, team_url):
                if page_url != team_url:
                    try:
                        thtml = fetch(page_url)
                    except (HTTPError, URLError, TimeoutError) as e:
                        print(f"  [skip page] {page_url}: {e}")
                        continue
                riders.update(parse_team_riders(thtml))
            for name, img in riders.items():
                merged.setdefault(name, img)
            if riders:
                print(f"  [{i}/{len(teams)}] {team_url.split('/')[-1]}: {len(riders)} riders")
    return merged


def save_jpeg(name: str, url: str, dry_run: bool) -> str | None:
    hires = hires_rider_url(url)
    if dry_run:
        print(f"  [dry] {name} <- {hires}")
        return f"riders/mxgp/{slug_nospace(name)}.jpg"
    try:
        data = fetch_bytes(hires)
        if len(data) < 1500:
            data = fetch_bytes(url)
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        print(f"  [fail] {name}: {e}")
        return None
    from io import BytesIO

    from PIL import Image

    im = Image.open(BytesIO(data)).convert("RGB")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{slug_nospace(name)}.jpg"
    path = OUT_DIR / fname
    im.save(path, format="JPEG", quality=88, optimize=True)
    rel = f"riders/mxgp/{fname}"
    print(f"  [ok] {name} -> {rel} ({path.stat().st_size // 1024} KB)")
    return rel


def update_db(name_to_rel: dict[str, str]) -> None:
    from app import create_app
    from models import Rider, db
    from mxgp_fantasy import ensure_mxgp_2026_roster, mxgp_roster_query

    app = create_app()
    with app.app_context():
        ensure_mxgp_2026_roster()
        db.session.commit()
        roster = {normalize_name(r.name): r for r in mxgp_roster_query().all()}
        updated = 0
        missing_roster: list[str] = []
        for name, rel in name_to_rel.items():
            r = roster.get(normalize_name(name))
            if not r:
                missing_roster.append(name)
                continue
            if (r.image_url or "").strip() != rel:
                r.image_url = rel
                updated += 1
            if getattr(r, "rider_image_data", None):
                r.rider_image_data = None
                updated += 1
        if updated:
            db.session.commit()
        print(f"DB: updated image_url on {updated} MXGP roster riders")
        if missing_roster:
            print("Not in mxgp roster (files saved, DB skipped):", ", ".join(sorted(missing_roster)))
        no_file = [n for n in roster if n not in {normalize_name(k) for k in name_to_rel}]
        if no_file:
            print(f"Roster without MXGP.com photo ({len(no_file)}):", ", ".join(sorted(no_file)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download MXGP rider portraits from mxgp.com")
    parser.add_argument(
        "--categories",
        default="1,3",
        help="race_category values (1=MXGP, 3=MX2). Default: 1,3",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only list URLs, do not download")
    parser.add_argument("--update-db", action="store_true", help="Set Rider.image_url for mxgp roster")
    args = parser.parse_args()
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]

    riders = crawl_riders(cats)
    print(f"\nTotal unique riders with photos: {len(riders)}")
    for n in sorted(riders):
        print(f"  {n}")

    saved: dict[str, str] = {}
    if not args.dry_run:
        print("\nDownloading …")
    for name, url in sorted(riders.items()):
        rel = save_jpeg(name, url, dry_run=args.dry_run)
        if rel:
            saved[name] = rel

    if args.update_db and not args.dry_run:
        update_db(saved)

    if args.dry_run:
        print("\n(dry-run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
