"""
Scrape WSX rider images from WSX official website.
Similar structure to scrape_racerx_riders.py but adapted for WSX.
"""
import re
import csv
import time
import pathlib
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# Update these URLs when you find the actual WSX riders page
BASE = "https://www.wsxchampionship.com"  # or wherever WSX riders are listed
LIST_URL = "https://www.wsxchampionship.com/riders"  # Update this URL

OUT_DIR = pathlib.Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUT = OUT_DIR / "wsx_riders_2025.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def parse_number(txt: str) -> int | None:
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
    Visit a WSX rider profile page and extract:
    - name
    - number (if present)
    - headshot image URL
    """
    soup = fetch(profile_url)

    # 1) Name: try h1 or main heading
    name = ""
    h1 = soup.select_one("h1") or soup.select_one("h1.page-title") or soup.select_one(".rider-name")
    if h1:
        name = clean_ws(h1.get_text(" "))

    # Remove location if present (city, state/country)
    if "," in name:
        name = name.split(",")[0].strip()

    # 2) Number: try various hints
    number = None
    num_candidates = []
    for el in soup.select("h1, h2, .rider-info, .rider-number, .number, .meta"):
        txt = clean_ws(el.get_text(" "))
        if txt:
            num_candidates.append(txt)
    page_txt = clean_ws(soup.get_text(" "))
    num_candidates.append(page_txt)

    for txt in num_candidates:
        number = parse_number(txt)
        if number:
            break

    # 3) Headshot image: try common selectors
    img_url = ""
    # Try og:image first
    og = soup.select_one('meta[property="og:image"], meta[name="og:image"]')
    if og and og.get("content"):
        img_url = og.get("content").strip()

    # Fallback: try image selectors common on rider pages
    if not img_url:
        for sel in [
            ".rider-image img",
            ".rider-photo img",
            ".profile-image img",
            ".hero img",
            ".rider-hero img",
            ".entry-content img",
            "img[alt*='rider']",
            "img[alt*='Rider']",
            "img",
        ]:
            img = soup.select_one(sel)
            if img and img.get("src"):
                src = img.get("src")
                if not src.startswith(("http://", "https://")):
                    src = urljoin(BASE, src)
                img_url = src
                # Prefer images that look like headshots (smaller, square-ish)
                if img.get("width") or img.get("class"):
                    break

    return {
        "name_guess": name,
        "number_guess": number,
        "img_url": img_url,
        "profile_url": profile_url,
    }

def main():
    print(f"[INFO] Fetching WSX riders list from {LIST_URL}")
    
    try:
        soup = fetch(LIST_URL)
    except Exception as e:
        print(f"[ERROR] Could not fetch {LIST_URL}: {e}")
        print("\nPlease update LIST_URL in this script to the correct WSX riders page URL.")
        return

    # Collect all rider profile links - adjust selectors based on actual WSX site structure
    links = set()
    for a in soup.select("a[href*='/rider/'], a[href*='/riders/'], a[href*='/rider-'], .rider-link a, .rider-card a"):
        href = a.get("href") or ""
        if not href:
            continue
        url = urljoin(BASE, href)
        # Filter to rider detail pages (adjust pattern as needed)
        if "/rider" in url.lower() and url not in links:
            links.add(url)

    if not links:
        print("[WARN] No rider links found. Trying alternative selectors...")
        # Alternative: look for any links that might be riders
        for a in soup.select("a"):
            href = a.get("href", "")
            text = clean_ws(a.get_text())
            # Heuristic: if link text looks like a name and goes to a detail page
            if text and len(text.split()) <= 3 and ("/" in href):
                url = urljoin(BASE, href)
                if url not in links and len(url.split("/")) > 3:
                    links.add(url)
                    print(f"[DEBUG] Added potential rider link: {url}")

    links = sorted(links)
    print(f"[INFO] Found {len(links)} profile links")

    if not links:
        print("[ERROR] No rider links found. Please check:")
        print("  1. Is LIST_URL correct?")
        print("  2. Does WSX site require login or JavaScript rendering?")
        print("  3. Try inspecting the page HTML to find rider link patterns")
        return

    rows = []
    for i, url in enumerate(links, 1):
        try:
            data = extract_profile_data(url)
            if data["name_guess"] or data["img_url"]:
                rows.append(data)
            print(f"[{i}/{len(links)}] {data['name_guess']}  #{data['number_guess']}  img:{'Y' if data['img_url'] else 'N'}")
        except Exception as e:
            print(f"[WARN] {url} -> {e}")
        time.sleep(0.5)  # be polite

    # Deduplicate
    dedup = {}
    for r in rows:
        key = (clean_ws(r["name_guess"]).lower(), r["number_guess"])
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = r
        else:
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
    print("Next: python tools/import_wsx_images.py")

if __name__ == "__main__":
    main()

