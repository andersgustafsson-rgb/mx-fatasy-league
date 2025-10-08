#!/usr/bin/env python3
"""
Script to compress track map images and select one per track
"""
import os
import shutil
from pathlib import Path
from PIL import Image

def compress_trackmaps():
    # Create compressed directory
    compressed_dir = Path("static/trackmaps/compressed")
    compressed_dir.mkdir(exist_ok=True)
    
    # Map round numbers to competition names
    ROUND_TO_NAME = {
        1: "Anaheim 1",
        2: "San Diego", 
        3: "Anaheim 2 (Triple Crown)",
        4: "Houston",
        5: "Glendale",
        6: "Seattle",
        7: "Arlington",
        8: "Daytona",
        9: "Indianapolis",
        10: "Birmingham",
        11: "Detroit",
        12: "St. Louis",
        13: "Nashville",
        14: "Cleveland",
        15: "Philadelphia",
        16: "Denver",
        17: "Salt Lake City",
    }
    
    source_dir = Path("static/trackmaps/2026")
    total_saved = 0
    
    print("Compressing track map images...")
    
    for round_num in range(1, 18):
        # Find all images for this round
        pattern = f"Rd{round_num:02d}_*"
        images = list(source_dir.glob(pattern))
        
        if not images:
            print(f"No images found for Round {round_num}")
            continue
            
        # Select the first image (usually the best overview)
        selected_image = images[0]
        competition_name = ROUND_TO_NAME.get(round_num, f"Round {round_num}")
        
        print(f"Processing {competition_name}: {selected_image.name}")
        
        try:
            # Open and compress the image
            with Image.open(selected_image) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize to max 800px width while maintaining aspect ratio
                if img.width > 800:
                    ratio = 800 / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((800, new_height), Image.Resampling.LANCZOS)
                
                # Save with high quality but compressed
                output_path = compressed_dir / f"round_{round_num:02d}_{competition_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.jpg"
                img.save(output_path, 'JPEG', quality=85, optimize=True)
                
                # Calculate size savings
                original_size = selected_image.stat().st_size
                new_size = output_path.stat().st_size
                saved = original_size - new_size
                total_saved += saved
                
                print(f"  Saved: {original_size/1024:.1f}KB -> {new_size/1024:.1f}KB (saved {saved/1024:.1f}KB)")
                
        except Exception as e:
            print(f"  Error processing {selected_image.name}: {e}")
    
    print(f"\nTotal size saved: {total_saved/1024:.1f}KB")
    print(f"Compressed images saved to: {compressed_dir}")

if __name__ == "__main__":
    compress_trackmaps()
