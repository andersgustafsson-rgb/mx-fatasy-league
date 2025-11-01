"""
Manuell nedladdare för WSX race-illustrationer.
Använd detta efter att du kört F12 scriptet och fått URL:erna.
"""

import os
import sys
import pathlib
import requests
from urllib.parse import urlparse

# Lista URL:er för varje race (uppdatera dessa med URL:er från F12 scriptet)
RACE_URLS = {
    "buenosaires": "",  # Klistra in URL här
    "canadian": "",     # Klistra in URL här
    "australian": "",   # Klistra in URL här
    "swedish": "",      # Klistra in URL här
    "southafrican": "", # Klistra in URL här
}

OUT_DIR = pathlib.Path("downloaded_wsx_race_images")
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def download(url: str, filename: str) -> bool:
    """Ladda ner en bild"""
    if not url:
        print(f"[SKIP] Ingen URL för {filename}")
        return False
    
    try:
        print(f"[INFO] Laddar ner {filename}...")
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        
        # Behåll filändelse från URL
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        if not ext.startswith('.'):
            ext = '.jpg'
        
        out_path = OUT_DIR / f"{filename}{ext}"
        out_path.write_bytes(r.content)
        print(f"[OK]  {filename}{ext} ({len(r.content)} bytes)")
        return True
    except Exception as e:
        print(f"[ERROR] Kunde inte ladda ner {filename}: {e}")
        return False

def main():
    print("=" * 60)
    print("WSX Race Images - Manual Downloader")
    print("=" * 60)
    print("\n[INFO] Använd detta script efter att du:")
    print("1. Körde extract_wsx_images_f12.js i F12 Console")
    print("2. Kopierade URL:erna för de rätta bilderna")
    print("3. Uppdaterade RACE_URLS i detta script\n")
    
    # Kolla om alla URL:er är satta
    missing = [race for race, url in RACE_URLS.items() if not url]
    if missing:
        print(f"⚠️  VARNING: Följande races saknar URL:er:")
        for race in missing:
            print(f"   - {race}")
        print("\n[INFO] Uppdatera RACE_URLS i scriptet med URL:er från F12 scriptet.")
        print("       Kör scriptet igen när alla URL:er är satta.\n")
        
        response = input("Fortsätt ändå med de URL:er som finns? (j/n): ")
        if response.lower() != 'j':
            return
    else:
        print("✅ Alla URL:er är satta!\n")
    
    OUT_DIR.mkdir(exist_ok=True)
    
    print(f"[INFO] Laddar ner till: {OUT_DIR.resolve()}\n")
    print("-" * 60)
    
    ok = 0
    for race_name, url in RACE_URLS.items():
        if url:
            if download(url, race_name):
                ok += 1
            print()
    
    print("=" * 60)
    print(f"[KLART] Laddade ner {ok}/{len([u for u in RACE_URLS.values() if u])} bilder")
    print(f"[INFO] Bilderna ligger i: {OUT_DIR.resolve()}")
    print("\n[INFO] Nästa steg:")
    print("1. Kontrollera bilderna")
    print("2. Kopiera till static/trackmaps/compressed/ med rätt namn")
    print("3. Filnamn ska matcha tävlingarnas namn i databasen")
    print("   (buenosaires.jpg, canadian.jpg, australian.jpg, swedish.jpg, southafrican.jpg)")
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

