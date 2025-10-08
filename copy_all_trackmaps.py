#!/usr/bin/env python3
"""
Copy ALL track map images (one per round) to compressed folder
"""
import shutil
from pathlib import Path

source_dir = Path("static/trackmaps/2026")
target_dir = Path("static/trackmaps/compressed")

# Map round numbers to competition names
ROUND_TO_NAME = {
    1: "anaheim1.jpg",
    2: "sandiego.jpg",
    3: "anaheim2.jpg",
    4: "houston.jpg",
    5: "glendale.jpg",
    6: "seattle.jpg",
    7: "arlington.jpg",
    8: "daytona.jpg",
    9: "indianapolis.jpg",
    10: "birmingham.jpg",
    11: "detroit.jpg",
    12: "stlouis.jpg",
    13: "nashville.jpg",
    14: "cleveland.jpg",
    15: "philadelphia.jpg",
    16: "denver.jpg",
    17: "saltlakecity.jpg",
}

print(f"Copying track maps from {source_dir} to {target_dir}")
print(f"Source exists: {source_dir.exists()}")

if not source_dir.exists():
    print("ERROR: Source directory does not exist!")
    exit(1)

target_dir.mkdir(exist_ok=True)

total_copied = 0

for round_num, target_filename in ROUND_TO_NAME.items():
    # Find first image for this round
    pattern = f"*_Rd{round_num:02d}_*"
    images = list(source_dir.glob(pattern))
    
    if images:
        source_file = images[0]
        target_file = target_dir / target_filename
        
        # Copy the file
        shutil.copy2(source_file, target_file)
        total_copied += 1
        print(f"Round {round_num:2d}: {source_file.name} -> {target_filename}")
    else:
        print(f"Round {round_num:2d}: NO IMAGE FOUND")

print(f"\nTotal files copied: {total_copied}/{len(ROUND_TO_NAME)}")

