"""Test script to check rider number updates"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing...")
    from main import app, db
    from models import Rider
    print("Imports OK")
    
    with app.app_context():
        print("Getting riders...")
        # Get all SMX riders
        smx_riders = Rider.query.filter(
            Rider.class_name.in_(['450cc', '250cc'])
        ).all()
        
        print(f"Found {len(smx_riders)} SMX riders")
        
        # Show first 10 riders
        for rider in smx_riders[:10]:
            print(f"  {rider.name}: #{rider.rider_number} ({rider.class_name})")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

