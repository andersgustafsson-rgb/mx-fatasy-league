"""
Bulk update rider numbers for SMX riders
Handles conflicts by using temporary numbers
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app, db
from models import Rider

# New rider numbers (from user's list)
# Format: "number — Name" (those with * keep their current number)
NEW_NUMBERS = {
    "Cooper Webb": None,  # * - keep current
    "Eli Tomac": None,  # * - keep current
    "Chase Sexton": None,  # * - keep current
    "Jeremy Martin": None,  # * - keep current
    "Aaron Plessinger": None,  # * - keep current
    "Adam Cianciarulo": None,  # * - keep current
    "Seth Hammaker": 10,
    "Kyle Chisholm": None,  # * - keep current
    "Shane McElrath": None,  # * - keep current
    "Julien Beaumer": 13,
    "Dylan Ferrandis": None,  # * - keep current
    "Dean Wilson": None,  # * - keep current
    "Tom Vialle": None,  # * - keep current
    "Joey Savatgy": None,  # * - keep current
    "Jett Lawrence": None,  # * - keep current
    "Maximus Vohland": 19,
    "Jordon Smith": 20,
    "Jason Anderson": None,  # * - keep current
    "Coty Schock": 22,
    "Michael Mosiman": 23,
    "R.J. Hampshire": None,  # * - keep current
    "Nate Thrasher": 25,
    "Jorge Prado": 26,
    "Malcolm Stewart": None,  # * - keep current
    "Christian Craig": None,  # * - keep current
    "Chance Hymas": 29,
    "Jo Shimoda": None,  # * - keep current
    "Mikkel Haarup": 31,
    "Justin Cooper": None,  # * - keep current
    "Austin Forkner": 33,
    "Ryder DiFrancesco": 34,
    "Drew Adams": 35,
    "Garrett Marchbanks": 36,
    "Cole Davies": 37,
    "Haiden Deegan": None,  # * - keep current
    "Valentin Guillod": 39,
    "Parker Ross": 40,
    "Mitchell Harrison": 41,
    "Dilan Schwartz": 42,
    "Lux Turner": 43,
    "Ty Masterpool": 44,
    "Colt Nichols": None,  # * - keep current
    "Justin Hill": None,  # * - keep current
    "Levi Kitchen": None,  # * - keep current
    "Harri Kullas": 48,
    "Cullin Park": 49,
    "Lorenzo Locurcio": 50,
    "Justin Barcia": None,  # * - keep current
    "Mitchell Oldenburg": 52,
    "Henry Miller": 53,
    "Benny Bloss": 54,
    "Benoit Paturel": 55,
    "Jalek Swoll": 56,
    "Avery Long": 57,
    "Daxton Bennick": 58,
    "Casey Cochran": 59,
    "Hunter Yoder": 60,
    "Max Anstie": 61,
    "Grant Harlan": 62,
    "Fredrik Noren": 63,
    "Romain Pape": 64,
    "Marshal Weltin": 65,
    "Cole Thompson": 66,
    "Hardy Munoz": 67,
    "Enzo Lopes": 68,
    "Jack Chambers": 69,
    "Anthony Bourdon": 70,
    "Carson Mumford": 71,
    "Trevor Colip": 72,
    "Gavin Towers": 73,
    "Gage Linville": 74,
    "Lance Kobusch": 75,
    "Kyle Webster": 76,
    "Derek Kelley": 77,
    "Kevin Moranz": 78,
    "Dylan Walsh": 79,
    "Bryce Shelly": 80,
    "Jerry Robin": 81,
    "Caden Dudney": 82,
    "Justin Rodbell": 83,
    "TJ Albright": 84,
    "Alexander Fedortsov": 85,
    "Jett Reynolds": 86,
    "Jeremy Hand": 87,
    "Mark Fineis": 88,
    "Devin Simonson": 89,
    "John Short": 90,
    "Izaih Clark": 91,
    "Enzo Temmerman": 92,
    "Antonio Cairoli": 93,
    "Ken Roczen": None,  # * - keep current
    "Luke Neese": 95,
    "Hunter Lawrence": None,  # * - keep current
    "Brad West": 97,
    "Derek Drake": 98,
    "Kayden Minear": 99,
}

def update_rider_numbers_bulk():
    """Update rider numbers in bulk, handling conflicts"""
    try:
        with app.app_context():
        # Get all SMX riders (450cc and 250cc)
        smx_riders = Rider.query.filter(
            Rider.class_name.in_(['450cc', '250cc'])
        ).all()
        
        print(f"📊 Found {len(smx_riders)} SMX riders in database")
        
        # Create a mapping of name -> rider for easier lookup
        riders_by_name = {}
        for rider in smx_riders:
            # Try exact match first
            if rider.name in NEW_NUMBERS:
                riders_by_name[rider.name] = rider
            else:
                # Try case-insensitive match
                for name, new_num in NEW_NUMBERS.items():
                    if rider.name.lower() == name.lower():
                        riders_by_name[name] = rider
                        break
        
        print(f"📋 Matched {len(riders_by_name)} riders from the list")
        
        # Find all riders that need updates
        updates = []
        for name, new_number in NEW_NUMBERS.items():
            if new_number is None:
                continue  # Skip riders with * (keep current number)
            
            if name not in riders_by_name:
                print(f"⚠️  Warning: Rider '{name}' not found in database")
                continue
            
            rider = riders_by_name[name]
            if rider.rider_number != new_number:
                updates.append({
                    'rider': rider,
                    'current_number': rider.rider_number,
                    'new_number': new_number,
                    'name': name
                })
        
        if not updates:
            print("✅ No riders need number updates")
            return
        
        print(f"📋 Found {len(updates)} riders to update:")
        for update in updates:
            print(f"  {update['name']}: {update['current_number']} → {update['new_number']}")
        
        # Check for conflicts
        # A conflict occurs when:
        # 1. Rider A wants number X, but Rider B currently has number X
        # 2. Rider A and Rider B are swapping numbers
        conflicts = []
        target_numbers = {update['new_number']: update for update in updates}
        
        for update in updates:
            target_num = update['new_number']
            # Check if another rider (not being updated) has this number
            existing_rider = Rider.query.filter_by(
                class_name=update['rider'].class_name,
                rider_number=target_num
            ).filter(Rider.id != update['rider'].id).first()
            
            if existing_rider:
                # Check if this existing rider is also being updated
                existing_in_updates = any(
                    u['rider'].id == existing_rider.id for u in updates
                )
                if not existing_in_updates:
                    conflicts.append({
                        'rider': update['rider'],
                        'target_number': target_num,
                        'conflict_with': existing_rider
                    })
        
        if conflicts:
            print(f"\n⚠️  Found {len(conflicts)} conflicts:")
            for conflict in conflicts:
                print(f"  {conflict['rider'].name} wants #{conflict['target_number']}, but {conflict['conflict_with'].name} already has it")
        
        # Strategy: Use temporary numbers to avoid conflicts
        # Step 1: Move all conflicting riders to temporary numbers (9000+)
        temp_number = 9000
        temp_updates = []
        
        for conflict in conflicts:
            rider = conflict['rider']
            temp_updates.append({
                'rider': rider,
                'old_number': rider.rider_number,
                'temp_number': temp_number
            })
            temp_number += 1
        
        # Step 2: Update all non-conflicting riders first
        print("\n🔄 Step 1: Updating non-conflicting riders...")
        non_conflicting = [
            u for u in updates 
            if not any(c['rider'].id == u['rider'].id for c in conflicts)
        ]
        
        for update in non_conflicting:
            update['rider'].rider_number = update['new_number']
            print(f"  ✅ {update['name']}: {update['current_number']} → {update['new_number']}")
        
        # Step 3: Move conflicting riders to temporary numbers
        if temp_updates:
            print("\n🔄 Step 2: Moving conflicting riders to temporary numbers...")
            for temp_update in temp_updates:
                temp_update['rider'].rider_number = temp_update['temp_number']
                print(f"  ⏳ {temp_update['rider'].name}: {temp_update['old_number']} → {temp_update['temp_number']} (temp)")
        
        db.session.commit()
        
        # Step 4: Now update conflicting riders to their final numbers
        if conflicts:
            print("\n🔄 Step 3: Updating conflicting riders to final numbers...")
            for conflict in conflicts:
                rider = conflict['rider']
                target_num = conflict['target_number']
                # Find the update for this rider
                update = next(u for u in updates if u['rider'].id == rider.id)
                rider.rider_number = update['new_number']
                print(f"  ✅ {rider.name}: {rider.rider_number} → {update['new_number']}")
        
        db.session.commit()
        
        print(f"\n✅ Successfully updated {len(updates)} rider numbers!")
        
        # Verify all updates
        print("\n📊 Verification:")
        for update in updates:
            rider = Rider.query.get(update['rider'].id)
            if rider.rider_number == update['new_number']:
                print(f"  ✅ {rider.name}: #{rider.rider_number}")
            else:
                print(f"  ❌ {rider.name}: Expected #{update['new_number']}, got #{rider.rider_number}")

if __name__ == "__main__":
    print("🚀 Starting bulk rider number update...")
    print("=" * 60)
    update_rider_numbers_bulk()
    print("=" * 60)
    print("✅ Done!")

