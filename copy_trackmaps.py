#!/usr/bin/env python3
"""
Script to copy one track map per competition to compressed folder
"""
import os
import shutil
from pathlib import Path

def copy_trackmaps():
    # Map competition names to round numbers
    NAME_TO_ROUND = {
        "Anaheim 1": 1,
        "San Diego": 2,
        "Anaheim 2 (Triple Crown)": 3,
        "Houston": 4,
        "Glendale": 5,
        "Seattle": 6,
        "Arlington": 7,
        "Daytona": 8,
        "Indianapolis": 9,
        "Birmingham": 10,
        "Detroit": 11,
        "St. Louis": 12,
        "Nashville": 13,
        "Cleveland": 14,
        "Philadelphia": 15,
        "Denver": 16,
        "Salt Lake City": 17,
    }
    
    source_dir = Path("static/trackmaps/2026")
    target_dir = Path("static/trackmaps/compressed")
    
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    print(f"Source exists: {source_dir.exists()}")
    
    # Create target directory if it doesn't exist
    target_dir.mkdir(exist_ok=True)
    
    print("Copying track maps to compressed folder...")
    
    for comp_name, round_num in NAME_TO_ROUND.items():
        # Find the first image for this round
        pattern = f"*Rd{round_num:02d}_*"
        images = list(source_dir.glob(pattern))
        
        if images:
            # Take the first image
            source_file = images[0]
            
            # Create a simple filename
            filename = comp_name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('.', '') + '.jpg'
            target_file = target_dir / filename
            
            # Copy the file
            shutil.copy2(source_file, target_file)
            print(f"Copied {comp_name}: {source_file.name} -> {filename}")
        else:
            print(f"No image found for {comp_name} (Round {round_num})")
    
    print(f"\nTrack maps copied to: {target_dir}")
    print("These files are now small enough for GitHub!")

if __name__ == "__main__":
    copy_trackmaps()
