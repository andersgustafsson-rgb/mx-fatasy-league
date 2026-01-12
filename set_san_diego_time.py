#!/usr/bin/env python3
"""Set San Diego competition start_time to 9:30 AM PT"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Loading modules...")
    from main import app, db
    from models import Competition
    from datetime import time
    print("Modules loaded successfully")
    
    with app.app_context():
        print("App context created")
        # Find San Diego competition
        san_diego = Competition.query.filter(
            Competition.name.ilike('%san diego%')
        ).first()
        
        if not san_diego:
            print("❌ San Diego competition not found!")
            sys.exit(1)
        
        print(f"📅 Found competition: {san_diego.name} (ID: {san_diego.id})")
        print(f"   Current event_date: {san_diego.event_date}")
        print(f"   Current timezone: {san_diego.timezone}")
        print(f"   Current start_time: {san_diego.start_time}")
        
        # Set start_time to 9:30 AM (09:30) and ensure timezone is PT
        db.session.execute(
            db.text("UPDATE competitions SET start_time = :start_time, timezone = :timezone WHERE id = :id"),
            {'start_time': time(9, 30), 'timezone': 'America/Los_Angeles', 'id': san_diego.id}
        )
        db.session.commit()
        
        # Refresh the object to get updated values
        db.session.refresh(san_diego)
        
        print(f"\n✅ Updated {san_diego.name}:")
        print(f"   start_time: 9:30 AM PT (09:30)")
        print(f"   timezone: America/Los_Angeles")
        print(f"   deadline for picks: 7:30 AM PT (2 hours before race)")
        print(f"\n   New start_time value: {san_diego.start_time}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
