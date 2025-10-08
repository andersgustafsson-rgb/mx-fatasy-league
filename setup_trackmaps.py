#!/usr/bin/env python3
"""
Simple script to assign track images to competitions
"""
import os
import re
from pathlib import Path
from main import app, db, Competition, CompetitionImage

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

def main():
    with app.app_context():
        print("Setting up track images...")
        
        # Get all competitions
        competitions = Competition.query.all()
        print(f"Found {len(competitions)} competitions")
        
        # Debug: print competition names
        for comp in competitions:
            print(f"  - {comp.name} (Round {NAME_TO_ROUND.get(comp.name, 'Unknown')})")
        
        # Debug: print existing CompetitionImage records
        existing_images = CompetitionImage.query.all()
        print(f"DEBUG: Found {len(existing_images)} existing CompetitionImage records")
        for img in existing_images:
            print(f"  - Competition {img.competition_id}: {img.image_url}")
        
        # Get all track images (try compressed first, then fallback to 2026)
        track_dir = Path("static/trackmaps/compressed")
        if not track_dir.exists():
            track_dir = Path("static/trackmaps/2026")
            if not track_dir.exists():
                print(f"Track directory {track_dir} not found!")
                return
            
        image_files = list(track_dir.glob("*.jpg")) + list(track_dir.glob("*.png"))
        print(f"Found {len(image_files)} image files in {track_dir}")
        
        # Group images by round number and select one per round
        by_round = {}
        for img_file in image_files:
            # Try to extract round number from filename (e.g., "Rd01_", "Rd12_")
            match = re.search(r'Rd(\d+)_', img_file.name)
            if match:
                round_num = int(match.group(1))
                if round_num not in by_round:
                    # Only keep the first (usually best) image for each round
                    by_round[round_num] = [img_file.name]
            else:
                # Handle compressed folder with simple names (anaheim1.jpg, etc.)
                filename = img_file.stem.lower()  # Remove extension
                for comp_name, round_num in NAME_TO_ROUND.items():
                    comp_key = comp_name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('.', '')
                    if filename == comp_key:
                        if round_num not in by_round:
                            by_round[round_num] = [img_file.name]
                        break
        
        print(f"Images grouped by round: {list(by_round.keys())}")
        
        # Create CompetitionImage records
        total_created = 0
        for comp in competitions:
            round_num = NAME_TO_ROUND.get(comp.name)
            if not round_num:
                print(f"No round mapping for competition: {comp.name}")
                continue
                
            images = by_round.get(round_num, [])
            if not images:
                print(f"No images found for round {round_num} ({comp.name})")
                continue
            
            # Clear existing images for this competition
            CompetitionImage.query.filter_by(competition_id=comp.id).delete()
            
            # Add new images
            for idx, img_name in enumerate(sorted(images)):
                # Use the correct path based on which directory we're using
                if "compressed" in str(track_dir):
                    image_url = f"trackmaps/compressed/{img_name}"
                else:
                    image_url = f"trackmaps/2026/{img_name}"
                ci = CompetitionImage(
                    competition_id=comp.id,
                    image_url=image_url,
                    sort_order=idx
                )
                db.session.add(ci)
                total_created += 1
            
            print(f"Added {len(images)} images for {comp.name} (Round {round_num})")
        
        db.session.commit()
        print(f"Total CompetitionImage records created: {total_created}")

if __name__ == "__main__":
    main()

