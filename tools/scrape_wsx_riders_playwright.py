"""
Scrape WSX rider images from the official site using Playwright (renders JS).
Outputs: data/wsx_riders_2025.csv with columns: name_guess,number_guess,img_url,profile_url
Source: https://worldsupercrosschampionship.com/riders/
"""
import csv
import re
import time
import pathlib
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

BASE = "https://worldsupercrosschampionship.com"
LIST_URL = "https://worldsupercrosschampionship.com/riders/"

OUT_DIR = pathlib.Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUT = OUT_DIR / "wsx_riders_2025.csv"


def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_number(txt: str) -> int | None:
    if not txt:
        return None
    m = re.search(r"(?:^|[#\sNo\.])(\d{1,3})(?:\s|$)", txt, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_profile(page, profile_url: str) -> dict:
    page.goto(profile_url, wait_until="domcontentloaded")
    # allow images/meta to load
    page.wait_for_timeout(500)

    name = ""
    # try common selectors
    for sel in ["h1", "h1.page-title", ".rider-name", "main h1", "article h1"]:
        el = page.query_selector(sel)
        if el:
            name = clean_ws(el.inner_text())
            break
    if "," in name:
        name = name.split(",")[0].strip()

    # number: try text on page
    number = None
    text_blobs = []
    for sel in ["h1", "h2", ".rider-info", ".rider-number", ".number", "body"]:
        el = page.query_selector(sel)
        if el:
            text_blobs.append(clean_ws(el.inner_text()))
    for txt in text_blobs:
        number = parse_number(txt)
        if number:
            break

    # image: prefer og:image
    img_url = ""
    og = page.query_selector("meta[property='og:image'], meta[name='og:image']")
    if og:
        content = (og.get_attribute("content") or "").strip()
        if content:
            img_url = content
    # fallback: first prominent image
    if not img_url:
        for sel in [
            ".rider-image img", ".rider-photo img", ".profile-image img",
            ".hero img", ".rider-hero img", "article img", "img"
        ]:
            img = page.query_selector(sel)
            if img:
                src = img.get_attribute("src") or ""
                if src:
                    if not src.startswith(("http://", "https://")):
                        src = urljoin(BASE, src)
                    img_url = src
                    break

    return {
        "name_guess": name,
        "number_guess": number,
        "img_url": img_url,
        "profile_url": profile_url,
    }


def main():
    print(f"[INFO] WSX Playwright scrape: {LIST_URL}")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LIST_URL, wait_until="domcontentloaded")
        # dump rendered HTML for debugging selectors
        rendered = page.content()
        (OUT_DIR / "wsx_riders_riders_page.html").write_text(rendered, encoding="utf-8")
        print("[DEBUG] Saved rendered riders page HTML -> data/wsx_riders_riders_page.html")
        # ge JS lite tid att fylla listan
        for _ in range(10):
            # leta efter rider-kort
        cards = page.query_selector_all("a[href*='/rider'], a[href*='/riders/'], .rider-card a, .riders a")
            if cards:
                break
            page.wait_for_timeout(300)
        cards = page.query_selector_all("a[href*='/rider'], a[href*='/riders/'], .rider-card a, .riders a")

        links = []
        for a in cards:
            href = a.get_attribute("href") or ""
            if not href:
                continue
            url = urljoin(BASE, href)
            low = url.lower()
            # accept profile-like URLs (exclude anchor-only and list page)
            if ("/rider" in low) or ("/riders/" in low and low.rstrip("/") != LIST_URL.rstrip("/") and low.count("/") >= 4):
                if url not in links:
                    links.append(url)
        print(f"[INFO] Found {len(links)} potential profile links")
        # fallback: scan all anchors from DOM if too few found
        if len(links) < 5:
            all_as = page.query_selector_all("a")
            for a in all_as:
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                url = urljoin(BASE, href)
                low = url.lower()
                if ("/rider" in low) and "/share" not in low and "?" not in low:
                    if url not in links:
                        links.append(url)
            print(f"[INFO] Fallback found {len(links)} total profile links")

        # besök varje profil
        for i, url in enumerate(links, 1):
            try:
                data = extract_profile(page, url)
                if data["name_guess"] or data["img_url"]:
                    rows.append(data)
                print(f"[{i}/{len(links)}] {data['name_guess']}  #{data['number_guess']}  img:{'Y' if data['img_url'] else 'N'}")
            except Exception as e:
                print(f"[WARN] {url} -> {e}")
                continue
            finally:
                # var snäll
                page.wait_for_timeout(200)

        browser.close()

    # dedupe
    dedup = {}
    for r in rows:
        key = (clean_ws(r["name_guess"]).lower(), r["number_guess"])
        prev = dedup.get(key)
        if prev is None or (not prev.get("img_url") and r.get("img_url")):
            dedup[key] = r

    out_rows = list(dedup.values())
    out_rows.sort(key=lambda x: (x["name_guess"].lower(), x["number_guess"] or 999))

    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name_guess","number_guess","img_url","profile_url"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"[OK] Wrote {CSV_OUT} ({len(out_rows)} riders)")


if __name__ == "__main__":
    main()
