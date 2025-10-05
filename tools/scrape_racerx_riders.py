import re
import csv
import time
import pathlib
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://racerxonline.com"
LIST_URL = "https://racerxonline.com/sx/riders"
OUT_DIR = pathlib.Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUT = OUT_DIR / "racerx_riders_2026.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def parse_number(txt: str) -> int | None:
    # Try common formats like "#3", "No. 3", leading number near name
    if not txt:
        return None
    m = re.search(r"(?:^|[#\sNo\.])(\d{1,3})(?:\s|$)", txt, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None

def fetch(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def extract_profile_data(profile_url: str) -> dict:
    """
    Visit a rider profile page and try to extract:
    - name (without city/state)
    - number (if present on the page)
    - headshot image URL
    """
    soup = fetch(profile_url)

    # 1) Name: try h1 or main heading
    name = ""
    h1 = soup.select_one("h1") or soup.select_one("h1.entry-title")
    if h1:
        name = clean_ws(h1.get_text(" "))

    # Some pages may include city/state next to name; try to remove comma+place
    # e.g., "Aaron Plessinger Hamilton, OH" -> "Aaron Plessinger"
    if "," in name:
        name = name.split(",")[0].strip()
    # If location appended without comma, often last two tokens are city/state; we won't guess—leave as is

    # 2) Number: try various hints
    number = None
    # look for a #123 near the name or in meta sections
    num_candidates = []
    # hero/heading blocks
    for el in soup.select("h1, h2, .rider-info, .rider__meta, .meta, .headline"):
        txt = clean_ws(el.get_text(" "))
        if txt:
            num_candidates.append(txt)
    # generic text scan fallback
    page_txt = clean_ws(soup.get_text(" "))
    num_candidates.append(page_txt)

    for txt in num_candidates:
        number = parse_number(txt)
        if number:
            break

    # 3) Headshot image: try common containers
    img_url = ""
    # Try og:image first (often best)
    og = soup.select_one('meta[property="og:image"], meta[name="og:image"]')
    if og and og.get("content"):
        img_url = og.get("content").strip()

    # fallback: try prominent images on the page
    if not img_url:
        # Look for images in hero/profile sections
        for sel in [
            ".rider-hero img",
            ".rider img",
            ".profile img",
            ".entry-content img",
            "img",
        ]:
            img = soup.select_one(sel)
            if img and img.get("src"):
                img_url = urljoin(BASE, img.get("src"))
                break

    return {
        "name_guess": name,
        "number_guess": number,
        "img_url": img_url,
        "profile_url": profile_url,
    }

def main():
    print(f"[INFO] Fetch list {LIST_URL}")
    soup = fetch(LIST_URL)

    # Collect all rider profile links
    links = set()
    for a in soup.select("a[href*='/rider/'], a[href*='/riders/']"):
        href = a.get("href") or ""
        if not href:
            continue
        url = urljoin(BASE, href)
        # Filter to rider detail pages
        if "/rider/" in url:
            links.add(url)

    links = sorted(links)
    print(f"[INFO] Found {len(links)} profile links")

    rows = []
    for i, url in enumerate(links, 1):
        try:
            data = extract_profile_data(url)
            # Keep only if we have at least a name or an image
            if data["name_guess"] or data["img_url"]:
                rows.append(data)
            print(f"[{i}/{len(links)}] {data['name_guess']}  #{data['number_guess']}  img:{'Y' if data['img_url'] else 'N'}")
        except Exception as e:
            print(f"[WARN] {url} -> {e}")
        time.sleep(0.5)  # be polite

    # Deduplicate by (name_guess.lower(), number_guess)
    dedup = {}
    for r in rows:
        key = (clean_ws(r["name_guess"]).lower(), r["number_guess"])
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = r
        else:
            # Prefer one with image
            if not prev["img_url"] and r["img_url"]:
                dedup[key] = r

    out_rows = list(dedup.values())
    out_rows.sort(key=lambda x: (x["name_guess"].lower(), x["number_guess"] or 999))

    # Write CSV
    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name_guess","number_guess","img_url","profile_url"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"[OK] Wrote {CSV_OUT} ({len(out_rows)} riders)")
    print("Next: python tools/import_racerx_images.py")

if __name__ == "__main__":
    main()