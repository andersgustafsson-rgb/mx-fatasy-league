#!/usr/bin/env python3
"""
Simple test to check if track maps are working
"""
from main import app, db, Competition, CompetitionImage

def test_trackmaps():
    with app.app_context():
        competitions = Competition.query.all()
        print(f"Found {len(competitions)} competitions")
        
        for comp in competitions[:3]:
            images = comp.images.all()
            print(f"{comp.name}: {len(images)} images")
            for img in images:
                print(f"  - {img.image_url}")

if __name__ == "__main__":
    test_trackmaps()
