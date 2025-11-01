import os
import re
import sys
import json
import pathlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# WSX URL - UPPDATERA DENNA TILL RÄTT WSX TRACKMAPS SIDA
URL = "https://worldsupercrosschampionship.com/tracks/"  # Exempel - ändra till rätt sida

# Konfig
OUT_DIR = pathlib.Path("downloaded_wsx_trackmaps")
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# Filtrering - uppdatera dessa för att matcha WSX-sidans struktur
IMG_EXT_RE = re.compile(r"\.(png|jpe?g)(?:\?.*)?$", re.I)
LIKELY_TRACK_WORDS = re.compile(r"(track|map|layout|course|wsx|world.*supercross)", re.I)
LIKELY_THUMB_WORDS = re.compile(r"(thumb|thumbnail|small|icon|logo)", re.I)

def pick_largest_from_srcset(srcset_value: str, base_url: str) -> str | None:
    """
    Välj största URL från ett srcset-attribut.
    srcset format: "url1 300w, url2 768w, url3 1200w"
    """
    if not srcset_value:
        return None
    parts = [p.strip() for p in srcset_value.split(",") if p.strip()]
    best = None
    best_w = -1
    for p in parts:
        # Delas upp i "url width"
        items = p.split()
        if not items:
            continue
        u = items[0]
        w = 0
        if len(items) > 1 and items[1].endswith("w"):
            try:
                w = int(items[1][:-1])
            except ValueError:
                w = 0
        # Absolutifiera
        u_abs = urljoin(base_url, u)
        if w > best_w:
            best_w = w
            best = u_abs
    return best

def collect_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    # 1) img-taggar: src, data-src, srcset
    for img in soup.find_all("img"):
        candidates = []

        # src eller data-src
        for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-srcset"):
            v = img.get(attr)
            if v:
                candidates.append(urljoin(base_url, v))

        # srcset (ta största)
        srcset = img.get("srcset")
        largest = pick_largest_from_srcset(srcset, base_url)
        if largest:
            candidates.append(largest)

        for u in candidates:
            if IMG_EXT_RE.search(u):
                urls.add(u)

    # 2) länkar (<a>) som pekar på bild
    for a in soup.find_all("a", href=True):
        u = urljoin(base_url, a["href"])
        if IMG_EXT_RE.search(u):
            urls.add(u)

    # 3) CSS background images (style="background-image: url(...)")
    for elem in soup.find_all(style=True):
        style = elem.get("style", "")
        # Matcha url(...) i CSS
        bg_urls = re.findall(r"url\(['\"]?([^'\"()]+)['\"]?\)", style, re.I)
        for u in bg_urls:
            u_abs = urljoin(base_url, u)
            if IMG_EXT_RE.search(u_abs):
                urls.add(u_abs)

    # Grov filtrering: sannolika track maps
    likely = [u for u in urls if LIKELY_TRACK_WORDS.search(u) and not LIKELY_THUMB_WORDS.search(u)]

    # Om filtreringen blev tom (sajtens namnmatchning skiljer sig), fall tillbaka till alla bilder
    final = likely if likely else list(urls)

    # Deduplicera på filnamn om många varianter
    by_name = {}
    for u in final:
        name = os.path.basename(urlparse(u).path)
        # välj den längsta (ofta högre upplösning)
        if name not in by_name or len(u) > len(by_name[name]):
            by_name[name] = u

    return list(by_name.values())

def sanitize_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    # rensa bort tecken som inte är tillåtna i filsystem
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", name)

def download(url: str, dest_dir: pathlib.Path, index: int) -> pathlib.Path | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        # filnamn från url
        name = os.path.basename(urlparse(url).path)
        name = sanitize_name(name) or f"wsx_track_{index:03d}.jpg"
        # prefixera index
        out_path = dest_dir / f"{index:03d}_{name}"
        out_path.write_bytes(r.content)
        return out_path
    except Exception as e:
        print(f"[MISS] {url} -> {e}")
        return None

def main():
    print("=" * 60)
    print("WSX Trackmaps Downloader")
    print("=" * 60)
    print(f"\n[INFO] Target URL: {URL}")
    print(f"[INFO] Output directory: {OUT_DIR.resolve()}\n")
    
    OUT_DIR.mkdir(exist_ok=True)
    
    try:
        print(f"[INFO] Hämtar: {URL}")
        resp = requests.get(URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[HTTP-FEL] Kunde inte hämta sidan: {e}")
        print("\nTips:")
        print("1. Kontrollera att URL är korrekt")
        print("2. Kontrollera internetanslutning")
        print("3. Sajten kanske blockerar scraping - prova att öppna URL i webbläsaren")
        sys.exit(1)

    urls = collect_image_urls(resp.text, URL)
    if not urls:
        print("[INFO] Hittade inga bild-URL:er. Kanske behöver filtret justeras.")
        print("\nTips:")
        print("1. Kontrollera att URL är korrekt")
        print("2. Kanske behöver regex-filtrering justeras")
        print("3. Prova att öppna sidan i webbläsaren och inspektera bilderna (F12)")
        return

    print(f"[INFO] Hittade {len(urls)} kandidatbilder:\n")
    for i, u in enumerate(urls, start=1):
        print(f"  {i}. {u}")

    print(f"\n[INFO] Laddar ner till: {OUT_DIR.resolve()}\n")
    ok = 0
    for i, u in enumerate(urls, start=1):
        p = download(u, OUT_DIR, i)
        if p:
            ok += 1
            print(f"[OK]  [{ok}/{len(urls)}] {p.name}")
        else:
            print(f"[MISS] [{i}/{len(urls)}] Misslyckades med: {u}")

    print(f"\n{'=' * 60}")
    print(f"[KLART] Laddade ner {ok}/{len(urls)} bilder")
    print(f"[INFO] Bilderna ligger i: {OUT_DIR.resolve()}")
    print("=" * 60)

if __name__ == "__main__":
    # beroenden: pip install requests beautifulsoup4
    try:
        main()
    except KeyboardInterrupt:
        print("\n[AVBRUTET] Användaren avbröt nedladdningen")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FEL] Oväntat fel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

