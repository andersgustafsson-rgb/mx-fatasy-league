#!/usr/bin/env python3
"""Set San Diego competition start_time to 9:30 AM PT - Simple version"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting script...")

try:
    print("Importing Flask app...")
    from main import app
    print("Flask app imported")
    
    print("Importing database...")
    from models import db
    print("Database imported")
    
    print("Importing Competition model...")
    from models import Competition
    print("Competition model imported")
    
    print("Importing time...")
    from datetime import time
    print("Time imported")
    
    print("\nCreating app context...")
    with app.app_context():
        print("App context created successfully")
        
        print("\nSearching for San Diego competition...")
        san_diego = Competition.query.filter(
            Competition.name.ilike('%san diego%')
        ).first()
        
        if not san_diego:
            print("❌ San Diego competition not found!")
            print("Available competitions:")
            all_comps = Competition.query.all()
            for comp in all_comps[:10]:  # Show first 10
                print(f"  - {comp.name} (ID: {comp.id})")
            sys.exit(1)
        
        print(f"✅ Found competition: {san_diego.name} (ID: {san_diego.id})")
        print(f"   Current event_date: {san_diego.event_date}")
        print(f"   Current timezone: {san_diego.timezone}")
        print(f"   Current start_time: {san_diego.start_time}")
        
        print("\nUpdating start_time to 11:30 AM PT (deadline for picks: 9:30 AM PT)...")
        db.session.execute(
            db.text("UPDATE competitions SET start_time = :start_time, timezone = :timezone WHERE id = :id"),
            {'start_time': time(11, 30), 'timezone': 'America/Los_Angeles', 'id': san_diego.id}
        )
        print("SQL executed, committing...")
        db.session.commit()
        print("Committed successfully")
        
        # Refresh the object to get updated values
        db.session.refresh(san_diego)
        
        print(f"\n✅ Successfully updated {san_diego.name}:")
        print(f"   start_time: 11:30 AM PT (11:30)")
        print(f"   timezone: America/Los_Angeles")
        print(f"   deadline for picks: 9:30 AM PT (2 hours before race)")
        print(f"\n   New start_time value: {san_diego.start_time}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nScript completed successfully!")
