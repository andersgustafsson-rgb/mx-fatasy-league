#!/usr/bin/env python3
"""
Debug script to check track maps setup
"""
import os
from pathlib import Path
from main import app, db, Competition, CompetitionImage

def debug_trackmaps():
    with app.app_context():
        print("=== DEBUGGING TRACK MAPS ===")
        
        # Check competitions
        competitions = Competition.query.all()
        print(f"Found {len(competitions)} competitions")
        for comp in competitions[:3]:
            print(f"  - {comp.id}: {comp.name}")
        
        # Check track images directory
        track_dir = Path("static/trackmaps/2026")
        print(f"\nTrack directory exists: {track_dir.exists()}")
        if track_dir.exists():
            image_files = list(track_dir.glob("*.jpg")) + list(track_dir.glob("*.png"))
            print(f"Found {len(image_files)} image files")
            for img in image_files[:3]:
                print(f"  - {img.name}")
        
        # Check existing competition images
        existing_images = CompetitionImage.query.all()
        print(f"\nExisting CompetitionImage records: {len(existing_images)}")
        for img in existing_images[:3]:
            print(f"  - Competition {img.competition_id}: {img.image_url}")
        
        # Test mapping
        print("\n=== TESTING MAPPING ===")
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
        
        for comp in competitions[:3]:
            round_num = NAME_TO_ROUND.get(comp.name)
            print(f"  - {comp.name} -> Round {round_num}")

if __name__ == "__main__":
    debug_trackmaps()
