"""
Download WSX rider images directly to static/riders/wsx/
Run this script and paste the HTML/JSON data or manually provide rider URLs.
"""
import os
import re
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://worldsupercrosschampionship.com"
DEST_DIR = Path("static/riders/wsx")
DEST_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def slugify(s):
    if not s:
        return "unknown"
    return re.sub(r"[^a-z0-9_]", "", s.lower().replace(" ", "_").replace(".", "")).strip("_")

def download_image(url, dest_path):
    """Download an image and verify it's a valid image file."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        
        # Check content type
        content_type = resp.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            print(f"   ⚠️ {dest_path.name} är inte en bild (type: {content_type})")
            return False
        
        # Save file
        dest_path.write_bytes(resp.content)
        
        # Verify it's actually an image by checking file signature
        with dest_path.open('rb') as f:
            header = f.read(4)
            if header.startswith(b'\xff\xd8\xff'):  # JPEG
                return True
            elif header.startswith(b'\x89PNG'):  # PNG
                return True
            else:
                print(f"   ⚠️ {dest_path.name} ser inte ut som en bildfil")
                dest_path.unlink()
                return False
    except Exception as e:
        print(f"   ❌ Fel vid nedladdning: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False

def extract_riders_from_page():
    """Extract rider data from the WSX riders page."""
    from bs4 import BeautifulSoup
    
    print(f"📡 Hämtar WSX riders-sidan...")
    url = f"{BASE_URL}/riders/"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"❌ Kunde inte hämta sidan: {e}")
        return []
    
    riders = []
    print(f"📸 Söker efter rider-bilder...")
    
    # Hitta alla bilder
    images = soup.find_all('img')
    print(f"   Hittade {len(images)} bilder totalt")
    
    for img in images:
        img_src = img.get('src') or img.get('data-src') or ''
        if not img_src:
            continue
        
        # Hoppa över placeholders, ikoner, logotyper
        if any(skip in img_src.lower() for skip in ['placeholder', 'logo', 'icon', 'svg', 'banner', 'hero']):
            continue
        
        # Gör URL absolut
        if img_src.startswith('//'):
            img_src = 'https:' + img_src
        elif img_src.startswith('/'):
            img_src = urljoin(BASE_URL, img_src)
        
        # Hitta namn och nummer i närheten av bilden
        parent = img.parent
        name = None
        number = None
        
        # Gå uppåt i DOM-trädet
        for _ in range(10):
            if not parent:
                break
            
            text = parent.get_text()
            
            # Hitta nummer
            if not number:
                num_match = re.search(r'\b([1-9]\d{0,2})\b', text)
                if num_match:
                    num_val = int(num_match.group(1))
                    if 1 <= num_val <= 999:  # Rimligt förarnummer
                        number = num_val
            
            # Hitta namn (efter nummer)
            if number and not name:
                parts = text.split(str(number))
                if len(parts) > 1:
                    # Text efter nummer, före komma eller radbrytning
                    candidate = parts[1].split(',')[0].split('\n')[0].strip()
                    # Filtrera bort onödiga ord
                    if (candidate and len(candidate) >= 2 and len(candidate) <= 40 and
                        re.match(r'^[a-zA-Z\s]+$', candidate) and
                        candidate.upper() not in ['RIDERS', 'CHAMPIONSHIP', 'ROUND', 'GP']):
                        name = candidate
                        break
            
            # Alternativ: leta efter h1-h4 eller namn-element
            if not name:
                name_el = parent.find(['h1', 'h2', 'h3', 'h4', 'h5'], class_=re.compile(r'name|title', re.I))
                if name_el:
                    name_text = name_el.get_text().split(',')[0].split('\n')[0].strip()
                    # Filtrera bort rubriker
                    if (name_text and len(name_text) >= 2 and len(name_text) <= 40 and
                        not re.match(r'^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER)', name_text, re.I)):
                        name = name_text
                        break
            
            parent = parent.parent if hasattr(parent, 'parent') else None
        
        # Rensa namn
        if name:
            name = re.sub(r'^(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER)\s+', '', name, flags=re.I)
            name = re.sub(r'\s+(CHAMPIONSHIP|RIDERS|ROUND|GP|ON SALE|RESULTS|AFTER)$', '', name, flags=re.I)
            name = name.strip()
        
        # Om vi har namn eller nummer, spara
        if name or number:
            riders.append({
                'name': name,
                'number': number,
                'img_url': img_src
            })
    
    # Deduplicera
    seen = set()
    unique = []
    for r in riders:
        if r['img_url'] not in seen:
            seen.add(r['img_url'])
            unique.append(r)
    
    print(f"✅ Hittade {len(unique)} unika riders")
    return unique

def main():
    print("🚀 WSX Image Downloader")
    print("=" * 50)
    
    # Prova att extrahera från sidan
    riders = extract_riders_from_page()
    
    if not riders:
        print("\n❌ Kunde inte hitta riders automatiskt.")
        print("\n💡 Alternativ: Lägg in rider-data manuellt")
        print("   Redigera scriptet och lägg till rider-dictionary manuellt")
        return
    
    # Visa vad som hittades
    print(f"\n📋 Hittade {len(riders)} riders:")
    for i, r in enumerate(riders[:10], 1):  # Visa första 10
        print(f"   {i}. #{r['number'] or '?'} {r['name'] or 'Okänt'}")
    if len(riders) > 10:
        print(f"   ... och {len(riders) - 10} till")
    
    # Fråga om nedladdning
    print(f"\n📥 Laddar ner bilder till: {DEST_DIR.absolute()}")
    
    success = 0
    failed = 0
    
    for i, rider in enumerate(riders, 1):
        name = rider.get('name') or f"rider_{i}"
        number = rider.get('number')
        img_url = rider['img_url']
        
        # Skapa filnamn
        filename = f"{number}_{slugify(name)}.jpg" if number else f"{slugify(name)}.jpg"
        dest_path = DEST_DIR / filename
        
        # Hoppa över om filen redan finns
        if dest_path.exists():
            print(f"   [⏭️] {filename} finns redan, hoppar över")
            continue
        
        print(f"   [{i}/{len(riders)}] {filename}...", end=" ")
        
        if download_image(img_url, dest_path):
            print("✅")
            success += 1
        else:
            print("❌")
            failed += 1
    
    print(f"\n✅ Klart!")
    print(f"   ✓ Lyckades: {success}")
    print(f"   ✗ Misslyckades: {failed}")
    print(f"\n📁 Bilder ligger i: {DEST_DIR.absolute()}")

if __name__ == "__main__":
    try:
        import bs4
    except ImportError:
        print("❌ BeautifulSoup4 saknas. Installera med: pip install beautifulsoup4")
        exit(1)
    
    main()

