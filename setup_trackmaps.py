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
        
        # Get all track images
        track_dir = Path("static/trackmaps/2026")
        if not track_dir.exists():
            print(f"Track directory {track_dir} not found!")
            return
            
        image_files = list(track_dir.glob("*.jpg")) + list(track_dir.glob("*.png"))
        print(f"Found {len(image_files)} image files")
        
        # Group images by round number and select one per round
        by_round = {}
        for img_file in image_files:
            # Extract round number from filename (e.g., "Rd01_", "Rd12_")
            match = re.search(r'Rd(\d+)_', img_file.name)
            if match:
                round_num = int(match.group(1))
                if round_num not in by_round:
                    # Only keep the first (usually best) image for each round
                    by_round[round_num] = [img_file.name]
        
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

