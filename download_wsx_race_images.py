import os
import re
import sys
import pathlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# WSX URL - Huvudsidan med alla races
URL = "https://worldsupercrosschampionship.com/"  # Eller specifik sida med races

# Konfig
OUT_DIR = pathlib.Path("downloaded_wsx_race_images")
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# Mapping av race-namn för att matcha mot databasen
RACE_NAME_MAP = {
    "buenos aires": "buenosaires",
    "buenos aires city gp": "buenosaires",
    "argentina": "buenosaires",  # Alternativt namn
    "canadian gp": "canadian",
    "canada": "canadian",
    "australian gp": "australian",
    "australia": "australian",
    "swedish gp": "swedish",
    "sweden": "swedish",
    "south african gp": "southafrican",
    "south africa": "southafrican",
}

# Filtrering
IMG_EXT_RE = re.compile(r"\.(png|jpe?g|webp)(?:\?.*)?$", re.I)
LIKELY_THUMB_WORDS = re.compile(r"(thumb|thumbnail|small|icon|logo|avatar)", re.I)
# Filtrera bort MAPTEXT, kartor, porträtt och liknande
EXCLUDE_WORDS = re.compile(r"(maptext|map-text|layout|diagram|scheme|map|track.*map|portrait|rider.*photo|headshot|profile)", re.I)
# Hitta stora bilder (race-illustrationer brukar vara stora)
MIN_SIZE_HINT = 1000  # Minst 1000px bred eller liknande

def pick_largest_from_srcset(srcset_value: str, base_url: str) -> str | None:
    """Välj största URL från ett srcset-attribut"""
    if not srcset_value:
        return None
    parts = [p.strip() for p in srcset_value.split(",") if p.strip()]
    best = None
    best_w = -1
    for p in parts:
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
        u_abs = urljoin(base_url, u)
        if w > best_w:
            best_w = w
            best = u_abs
    return best

def collect_race_images(html: str, base_url: str) -> dict[str, str]:
    """
    Hitta race-illustrationer och mappa dem till race-namn.
    Returnerar en dict: {race_name: image_url}
    """
    soup = BeautifulSoup(html, "html.parser")
    race_images = {}
    
    # Strategi 1: Leta efter event cards/kort som innehåller både race-info och bilder
    # Dessa brukar ligga i containers med race-namn och bilder
    event_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'(event|race|card|gp|round)', re.I))
    
    if not event_containers:
        # Fallback: Leta efter alla stora bilder på sidan
        event_containers = soup.find_all(['div', 'article'], class_=True)
    
    print(f"[INFO] Hittade {len(event_containers)} potentiella event-containers")
    
    for container in event_containers:
        # Hitta race-namn i containern
        race_name = None
        
        # Försök hitta race-namn från text (mer intelligent sökning)
        text_content = container.get_text().lower()
        
        # Försök hitta FIM Round eller specifika race-namn
        fim_round_match = re.search(r'fim\s+round\s+(\d+)', text_content, re.I)
        if fim_round_match:
            # Map round numbers till race-namn om möjligt
            round_map = {1: "buenosaires", 2: "canadian", 3: "australian", 4: "swedish", 5: "southafrican"}
            round_num = int(fim_round_match.group(1))
            if round_num in round_map:
                race_name = round_map[round_num]
        
        # Om inte hittat via round, sök efter race-namn i text
        if not race_name:
            for key, value in RACE_NAME_MAP.items():
                if key in text_content:
                    race_name = value
                    break
        
        # Om inget hittades, försök från class eller data-attribut
        if not race_name:
            classes = ' '.join(container.get('class', []))
            for key in RACE_NAME_MAP.keys():
                if key.replace(' ', '').replace('_', '') in classes.lower():
                    race_name = RACE_NAME_MAP[key]
                    break
        
        # Hitta bilder i containern
        images = container.find_all("img")
        bg_images = container.find_all(style=re.compile(r"background.*image", re.I))
        
        best_image_url = None
        best_size = 0
        
        # 1. Kolla img-taggar
        for img in images:
            candidates = []
            
            # src eller data-src
            for attr in ("src", "data-src", "data-lazy-src", "data-original"):
                v = img.get(attr)
                if v:
                    candidates.append(urljoin(base_url, v))
            
            # srcset (ta största)
            srcset = img.get("srcset")
            largest = pick_largest_from_srcset(srcset, base_url)
            if largest:
                candidates.append(largest)
            
            # Filtrera bort thumbnails och MAPTEXT-bilder
            for u in candidates:
                if (IMG_EXT_RE.search(u) and 
                    not LIKELY_THUMB_WORDS.search(u) and 
                    not EXCLUDE_WORDS.search(u)):
                    # Gissa storlek från URL eller dimensioner
                    # Race-illustrationer brukar vara stora (1200px+)
                    size_hint = 0
                    
                    # Kolla dimensioner i URL (t.ex. "1200x683", "1920x1080")
                    size_match = re.search(r'(\d{3,4})x(\d{3,4})', u)
                    if size_match:
                        width = int(size_match.group(1))
                        height = int(size_match.group(2))
                        size_hint = max(width, height)
                    elif '1200' in u or '1920' in u or 'large' in u.lower() or 'full' in u.lower():
                        size_hint = 1500
                    elif '600' in u or '800' in u:
                        size_hint = 800  # Mindre, men kanske okej
                    
                    # Ta bara stora bilder (inte thumbnails)
                    if size_hint >= MIN_SIZE_HINT and size_hint > best_size:
                        best_size = size_hint
                        best_image_url = u
        
        # 2. Kolla CSS background images
        for elem in bg_images:
            style = elem.get("style", "")
            bg_urls = re.findall(r"url\(['\"]?([^'\"()]+)['\"]?\)", style, re.I)
            for u in bg_urls:
                u_abs = urljoin(base_url, u)
                if (IMG_EXT_RE.search(u_abs) and 
                    not LIKELY_THUMB_WORDS.search(u_abs) and 
                    not EXCLUDE_WORDS.search(u_abs)):
                    # Kolla dimensioner i URL
                    size_hint = 0
                    size_match = re.search(r'(\d{3,4})x(\d{3,4})', u_abs)
                    if size_match:
                        width = int(size_match.group(1))
                        height = int(size_match.group(2))
                        size_hint = max(width, height)
                    else:
                        size_hint = 1500  # Default för background images
                    
                    # Ta bara stora bilder
                    if size_hint >= MIN_SIZE_HINT and size_hint > best_size:
                        best_size = size_hint
                        best_image_url = u_abs
        
        # Spara om vi hittade både race-namn och bild (och bilden är tillräckligt stor)
        if race_name and best_image_url and best_size >= MIN_SIZE_HINT:
            if race_name not in race_images:
                race_images[race_name] = best_image_url
                print(f"[INFO] Mappat {race_name} -> {best_image_url} (size hint: {best_size})")
            else:
                # Om vi redan har en bild, välj den största
                existing_url = race_images[race_name]
                # Kolla storlek på befintlig bild
                existing_size = 0
                size_match = re.search(r'(\d{3,4})x(\d{3,4})', existing_url)
                if size_match:
                    existing_size = max(int(size_match.group(1)), int(size_match.group(2)))
                
                if best_size > existing_size:
                    race_images[race_name] = best_image_url
                    print(f"[INFO] Uppdaterat {race_name} med större bild -> {best_image_url} (size: {best_size} > {existing_size})")
                else:
                    print(f"[INFO] Redan har större bild för {race_name}, behåller första")
    
    # Strategi 2: Om vi inte hittade något via containers, sök bredare
    if not race_images:
        print("[INFO] Försöker bredare sökning efter bilder...")
        all_images = soup.find_all("img")
        for img in all_images:
            candidates = []
            for attr in ("src", "data-src", "data-lazy-src"):
                v = img.get(attr)
                if v:
                    candidates.append(urljoin(base_url, v))
            
            srcset = img.get("srcset")
            largest = pick_largest_from_srcset(srcset, base_url)
            if largest:
                candidates.append(largest)
            
            for u in candidates:
                if (IMG_EXT_RE.search(u) and 
                    not LIKELY_THUMB_WORDS.search(u) and 
                    not EXCLUDE_WORDS.search(u)):
                    # Kolla bildstorlek - race-illustrationer är stora
                    size_hint = 0
                    size_match = re.search(r'(\d{3,4})x(\d{3,4})', u)
                    if size_match:
                        width = int(size_match.group(1))
                        height = int(size_match.group(2))
                        size_hint = max(width, height)
                    
                    # Ta bara stora bilder (minst 1000px)
                    if size_hint < MIN_SIZE_HINT:
                        continue
                    
                    # Försök matcha mot race-namn från URL eller alt-text
                    alt_text = (img.get("alt", "") or "").lower()
                    url_lower = u.lower()
                    
                    for key, value in RACE_NAME_MAP.items():
                        if key in alt_text or key in url_lower:
                            if value not in race_images:
                                race_images[value] = u
                                print(f"[INFO] Mappat {value} via alt/URL -> {u} (size: {size_hint})")
                            break
    
    return race_images

def sanitize_name(name: str) -> str:
    name = name.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._\-]+", "_", name)

def download(url: str, dest_dir: pathlib.Path, filename: str) -> pathlib.Path | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        
        # Försök behålla filändelse från URL
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        if not ext.startswith('.'):
            ext = '.jpg'
        
        out_path = dest_dir / f"{filename}{ext}"
        out_path.write_bytes(r.content)
        return out_path
    except Exception as e:
        print(f"[MISS] {url} -> {e}")
        return None

def main():
    print("=" * 60)
    print("WSX Race Images Downloader")
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
        print("3. Sajten kanske blockerar scraping")
        sys.exit(1)
    
    race_images = collect_race_images(resp.text, URL)
    
    if not race_images:
        print("[INFO] Hittade inga race-bilder.")
        print("\nTips:")
        print("1. Kontrollera att URL är korrekt")
        print("2. Kanske behöver mappningen justeras (RACE_NAME_MAP)")
        print("3. Prova att öppna sidan i webbläsaren och inspektera strukturen (F12)")
        print("\nDu kan också:")
        print("- Öppna sidan i webbläsaren")
        print("- Högerklicka på varje race-bild -> Kopiera bildadress")
        print("- Spara bilderna manuellt med rätt namn")
        return
    
    print(f"\n[INFO] Hittade {len(race_images)} race-bilder:")
    for race, url in race_images.items():
        print(f"  - {race}: {url}")
    
    print(f"\n[INFO] Laddar ner till: {OUT_DIR.resolve()}\n")
    ok = 0
    for race_name, url in race_images.items():
        p = download(url, OUT_DIR, race_name)
        if p:
            ok += 1
            print(f"[OK]  [{ok}/{len(race_images)}] {race_name} -> {p.name}")
        else:
            print(f"[MISS] Misslyckades med: {race_name} ({url})")
    
    print(f"\n{'=' * 60}")
    print(f"[KLART] Laddade ner {ok}/{len(race_images)} bilder")
    print(f"[INFO] Bilderna ligger i: {OUT_DIR.resolve()}")
    print("\n[INFO] Nästa steg:")
    print("1. Kontrollera bilderna och deras namn")
    print("2. Kopiera till static/trackmaps/compressed/ med rätt namn")
    print("3. Filnamn ska matcha tävlingarnas namn i databasen")
    print("   (t.ex. 'buenosaires.jpg' för 'Buenos Aires City GP')")
    print("=" * 60)

if __name__ == "__main__":
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

