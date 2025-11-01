"""Kopiera WSX race-illustrationer med rätt filnamn"""
import shutil
from pathlib import Path

# Mapping: competition name -> filnamn (utan mellanslag, lowercase)
COMPETITION_TO_FILENAME = {
    "Buenos Aires City GP": "buenosaireacitygp",
    "Canadian GP": "canadiangp",
    "Australian GP": "australiangp",
    "Swedish GP": "swedishgp",
    "South African GP": "southafricangp",
}

# Källor från downloaded_wsx_race_images
SOURCE_DIR = Path("downloaded_wsx_race_images")
# Destinationskatalog
DEST_DIR = Path("static/trackmaps/compressed")

# Source filer och deras destinationer
FILES_TO_COPY = [
    ("Buenos_aires.png", "buenosaireacitygp.png"),
    ("canada.png", "canadiangp.png"),
    ("Australia.jpg", "australiangp.jpg"),
    ("Sweden.jpg", "swedishgp.jpg"),
    ("South_Africa.png", "southafricangp.png"),
]

def main():
    import sys
    output_lines = []
    
    output_lines.append("=" * 60)
    output_lines.append("WSX Race Images - Kopiera till static/trackmaps/compressed/")
    output_lines.append("=" * 60)
    
    # Force output immediately
    sys.stdout.write("\n".join(output_lines) + "\n")
    sys.stdout.flush()
    output_lines = []
    
    if not SOURCE_DIR.exists():
        msg = f"[ERROR] Source-mappen finns inte: {SOURCE_DIR}"
        print(msg)
        sys.stdout.flush()
        return
    
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    
    output_lines.append(f"\n[INFO] Kopierar från: {SOURCE_DIR}")
    output_lines.append(f"[INFO] Kopierar till: {DEST_DIR}\n")
    sys.stdout.write("\n".join(output_lines) + "\n")
    sys.stdout.flush()
    output_lines = []
    
    copied = 0
    for source_name, dest_name in FILES_TO_COPY:
        source_path = SOURCE_DIR / source_name
        dest_path = DEST_DIR / dest_name
        
        if not source_path.exists():
            msg = f"[SKIP] Källfil finns inte: {source_name}"
            print(msg)
            sys.stdout.flush()
            continue
        
        try:
            shutil.copy2(source_path, dest_path)
            msg = f"[OK]  {source_name} -> {dest_name}"
            print(msg)
            sys.stdout.flush()
            copied += 1
        except Exception as e:
            msg = f"[ERROR] Kunde inte kopiera {source_name}: {e}"
            print(msg)
            sys.stdout.flush()
    
    output_lines.append(f"\n{'=' * 60}")
    output_lines.append(f"[KLART] Kopierade {copied}/{len(FILES_TO_COPY)} filer")
    output_lines.append(f"[INFO] Bilderna ligger nu i: {DEST_DIR.resolve()}")
    output_lines.append("=" * 60)
    sys.stdout.write("\n".join(output_lines) + "\n")
    sys.stdout.flush()

if __name__ == "__main__":
    main()


