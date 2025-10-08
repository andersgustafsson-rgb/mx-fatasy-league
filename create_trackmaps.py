#!/usr/bin/env python3
"""
Manually create CompetitionImage records for the 7 compressed track maps
"""
from main import app, db, Competition, CompetitionImage

def create_trackmaps():
    with app.app_context():
        print("Creating CompetitionImage records for compressed track maps...")
        
    # Map competition names to image files
    COMP_TO_IMAGE = {
        "Anaheim 1": "anaheim1.jpg",
        "San Diego": "sandiego.jpg", 
        "Anaheim 2 (Triple Crown)": "anaheim2.jpg",
        "Houston": "houston.jpg",
        "Glendale": "glendale.jpg",
        "Seattle": "seattle.jpg",
        "Arlington": "arlington.jpg",
        "Indianapolis": "indianapolis.jpg",
        "Birmingham": "birmingham.jpg",
        "Detroit": "detroit.jpg",
        "St. Louis": "stlouis.jpg",
        "Nashville": "nashville.jpg",
        "Cleveland": "cleveland.jpg",
        "Philadelphia": "philadelphia.jpg",
        "Denver": "denver.jpg",
        "Salt Lake City": "saltlakecity.jpg"
    }
        
        # Get all competitions
        competitions = Competition.query.all()
        print(f"Found {len(competitions)} competitions")
        
        total_created = 0
        
        for comp in competitions:
            if comp.name in COMP_TO_IMAGE:
                # Clear existing images for this competition
                CompetitionImage.query.filter_by(competition_id=comp.id).delete()
                
                # Create new image record
                image_url = f"trackmaps/compressed/{COMP_TO_IMAGE[comp.name]}"
                ci = CompetitionImage(
                    competition_id=comp.id,
                    image_url=image_url,
                    sort_order=0
                )
                db.session.add(ci)
                total_created += 1
                print(f"Created image for {comp.name}: {image_url}")
        
        db.session.commit()
        print(f"Total CompetitionImage records created: {total_created}")

if __name__ == "__main__":
    create_trackmaps()
