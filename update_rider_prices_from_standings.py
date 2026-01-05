#!/usr/bin/env python3
"""
Update rider prices based on previous year's point standings
Prices are set to balance the 1,500,000 budget for 4 riders (2x450cc + 2x250cc)
Average price per rider: ~375,000
"""

import sys
import pathlib
from collections import defaultdict

# Add parent directory to path to import models
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Try to import from main.py (Flask app)
try:
    from main import app
    from models import db, Rider
except ImportError:
    # Fallback to app.py if main.py doesn't exist
    from app import app
    from models import db, Rider

def calculate_price_for_budget(position: int, points: int, class_name: str, total_riders_in_class: int = 30):
    """
    Calculate price based on position, optimized for 1.5M budget
    Budget: 1,500,000 kr for 4 riders (2x450cc + 2x250cc)
    Average: ~375,000 kr per rider
    
    Strategy:
    - Top riders should be expensive but not so expensive you can buy all top riders
    - Example: Top 450cc rider ~450k, top 250cc rider ~400k = 850k for 2 top riders
    - Then you have 650k left for 2 more riders (average 325k each)
    - This forces strategic choices - can't just buy all top riders
    """
    
    if class_name == '450cc':
        # 450cc pricing - higher prices for top riders
        # Top riders should cost more, but still allow strategic team building
        
        if position == 1:
            # Champion: Most expensive
            return 450000
        elif position == 2:
            # 2nd place: Very expensive
            return 420000
        elif position == 3:
            # 3rd place: Very expensive
            return 400000
        elif position <= 5:
            # Top 5: Expensive (350k-380k)
            return 380000 - (position - 4) * 10000
        elif position <= 10:
            # Top 10: High price (280k-350k)
            return 350000 - (position - 6) * 14000
        elif position <= 15:
            # Top 15: Medium-high (200k-280k)
            return 280000 - (position - 11) * 16000
        elif position <= 20:
            # Top 20: Medium (150k-200k)
            return 200000 - (position - 16) * 10000
        elif points > 50:
            # Some points: Lower-medium (120k-150k)
            return 150000
        elif points > 0:
            # Few points: Low (100k-120k)
            return 100000
        else:
            # No points: Default price
            return 100000  # Default for riders without standings
    
    else:  # 250cc
        # 250cc pricing - slightly lower than 450cc
        
        if position == 1:
            # Champion: Most expensive
            return 400000
        elif position == 2:
            # 2nd place: Very expensive
            return 380000
        elif position == 3:
            # 3rd place: Very expensive
            return 360000
        elif position <= 5:
            # Top 5: Expensive (300k-340k)
            return 340000 - (position - 4) * 10000
        elif position <= 10:
            # Top 10: High price (220k-300k)
            return 300000 - (position - 6) * 16000
        elif position <= 15:
            # Top 15: Medium-high (150k-220k)
            return 220000 - (position - 11) * 14000
        elif position <= 20:
            # Top 20: Medium (120k-150k)
            return 150000 - (position - 16) * 6000
        elif points > 30:
            # Some points: Lower-medium (100k-120k)
            return 100000
        elif points > 0:
            # Few points: Low (100k)
            return 100000
        else:
            # No points: Default price
            return 100000  # Default for riders without standings

def parse_standings_from_csv(csv_path: str):
    """Parse standings from CSV file"""
    import csv
    
    standings = {
        '450cc': {},
        '250cc': {}
    }
    
    csv_file = pathlib.Path(csv_path)
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return standings
    
    with csv_file.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            class_name = row.get('class', '').strip()
            if class_name not in ['450cc', '250cc']:
                continue
            
            try:
                position = int(row.get('position', 0))
                name = row.get('name', '').strip()
                points = int(row.get('points', 0))
                
                if name:
                    standings[class_name][name] = {
                        'position': position,
                        'points': points
                    }
            except (ValueError, KeyError):
                continue
    
    return standings

def parse_standings_from_txt(txt_path: str = "point standings 2025.txt"):
    """Parse standings from existing text file (fallback)"""
    import re
    
    standings = {
        '450cc': {},
        '250cc': {}
    }
    
    txt_file = pathlib.Path(txt_path)
    if not txt_file.exists():
        print(f"⚠️  Text file not found: {txt_path}")
        return standings
    
    current_class = None
    
    with txt_file.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Check for class header
            if '450' in line.lower() and 'point' in line.lower():
                current_class = '450cc'
                continue
            elif '250' in line.lower():
                current_class = '250cc'
                continue
            
            # Parse rider line
            if current_class:
                # Format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                parts = line.split('\t')
                if len(parts) >= 4:
                    try:
                        position = int(parts[0])
                        name_part = parts[1]
                        points = int(parts[-1]) if parts[-1].isdigit() else 0
                        
                        # Clean up name (remove duplicates)
                        name = name_part
                        if len(name) > 20:  # Likely has duplicate name
                            mid = len(name) // 2
                            for i in range(mid-5, mid+5):
                                if i < len(name) and name[i].isupper():
                                    name = name[:i]
                                    break
                        
                        name = name.strip()
                        if name:
                            standings[current_class][name] = {
                                'position': position,
                                'points': points
                            }
                    except (ValueError, IndexError):
                        continue
    
    return standings

def normalize_name_for_matching(name: str) -> str:
    """Normalize name for matching against database"""
    import re
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove common suffixes
    name = re.sub(r'\s+(Jr\.|Sr\.|III|II|IV)$', '', name, flags=re.IGNORECASE)
    return name

def match_rider_name(db_name: str, standings_name: str) -> bool:
    """Check if two rider names match (fuzzy matching)"""
    db_norm = normalize_name_for_matching(db_name).lower()
    standings_norm = normalize_name_for_matching(standings_name).lower()
    
    # Exact match
    if db_norm == standings_norm:
        return True
    
    # Check if one contains the other (for nicknames or variations)
    if db_norm in standings_norm or standings_norm in db_norm:
        # But make sure it's not too short (avoid false matches)
        if len(db_norm) >= 5 and len(standings_norm) >= 5:
            return True
    
    # Check last name match (for "First Last" vs "Last" cases)
    db_parts = db_norm.split()
    standings_parts = standings_norm.split()
    
    if db_parts and standings_parts:
        if db_parts[-1] == standings_parts[-1]:  # Last name matches
            # Check if first name initial matches
            if len(db_parts) > 1 and len(standings_parts) > 1:
                if db_parts[0][0] == standings_parts[0][0]:
                    return True
    
    return False

def update_rider_prices(standings: dict, default_price: int = 100000):
    """Update rider prices in database based on standings"""
    
    with app.app_context():
        all_riders = Rider.query.all()
        updated_count = 0
        not_found_count = 0
        matched_riders = []
        
        print("\n" + "=" * 60)
        print("UPDATING RIDER PRICES")
        print("=" * 60)
        
        for rider in all_riders:
            class_name = rider.class_name
            if class_name not in standings:
                continue
            
            # Try to find matching rider in standings
            matched = False
            for standings_name, data in standings[class_name].items():
                if match_rider_name(rider.name, standings_name):
                    # Calculate price based on position
                    price = calculate_price_for_budget(
                        data['position'],
                        data['points'],
                        class_name
                    )
                    
                    old_price = rider.price
                    rider.price = price
                    
                    matched_riders.append({
                        'name': rider.name,
                        'class': class_name,
                        'position': data['position'],
                        'points': data['points'],
                        'old_price': old_price,
                        'new_price': price
                    })
                    
                    matched = True
                    updated_count += 1
                    break
            
            if not matched:
                # No match found - set default price
                if rider.price != default_price:
                    old_price = rider.price
                    rider.price = default_price
                    not_found_count += 1
                    print(f"  ⚠️  {rider.name} ({class_name}): No match, set to {default_price:,} kr (was {old_price:,})")
        
        # Commit changes
        try:
            db.session.commit()
            print(f"\n✅ Successfully updated {updated_count} riders with standings data")
            print(f"⚠️  {not_found_count} riders set to default price (no match found)")
            
            # Print summary
            print("\n" + "=" * 60)
            print("PRICE UPDATE SUMMARY")
            print("=" * 60)
            
            # Group by class
            for class_name in ['450cc', '250cc']:
                class_riders = [r for r in matched_riders if r['class'] == class_name]
                if class_riders:
                    print(f"\n{class_name} ({len(class_riders)} riders updated):")
                    for r in sorted(class_riders, key=lambda x: x['position'])[:15]:
                        price_change = r['new_price'] - r['old_price']
                        change_str = f"+{price_change:,}" if price_change > 0 else f"{price_change:,}"
                        print(f"  {r['position']:2d}. {r['name']:25s} - {r['points']:3d} pts - "
                              f"{r['new_price']:,} kr (was {r['old_price']:,}, {change_str})")
            
            # Calculate average prices
            avg_450 = sum(r['new_price'] for r in matched_riders if r['class'] == '450cc') / max(1, len([r for r in matched_riders if r['class'] == '450cc']))
            avg_250 = sum(r['new_price'] for r in matched_riders if r['class'] == '250cc') / max(1, len([r for r in matched_riders if r['class'] == '250cc']))
            
            print(f"\n📊 Average prices:")
            print(f"  450cc: {avg_450:,.0f} kr")
            print(f"  250cc: {avg_250:,.0f} kr")
            print(f"  Combined average: {(avg_450 + avg_250) / 2:,.0f} kr")
            print(f"  Team of 2x450cc + 2x250cc: {avg_450 * 2 + avg_250 * 2:,.0f} kr")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error updating database: {e}")
            raise

def main():
    """Main function"""
    import sys
    sys.stdout.flush()
    
    print("=" * 60)
    print("UPDATE RIDER PRICES FROM STANDINGS")
    print("=" * 60)
    sys.stdout.flush()
    
    # Try to load from CSV first (if scraper was run)
    csv_path = pathlib.Path("data/racerx_standings_2025.csv")
    if csv_path.exists():
        print(f"📄 Loading standings from CSV: {csv_path}")
        standings = parse_standings_from_csv(str(csv_path))
    else:
        # Fallback to text file
        print("📄 Loading standings from text file: point standings 2025.txt")
        standings = parse_standings_from_txt()
    
    if not any(standings.values()):
        print("\n❌ No standings data found!")
        print("Please run: python tools/scrape_racerx_standings.py")
        print("Or ensure 'point standings 2025.txt' exists")
        return
    
    print(f"\n📊 Standings loaded:")
    print(f"  450cc: {len(standings['450cc'])} riders")
    print(f"  250cc: {len(standings['250cc'])} riders")
    
    # Update prices
    update_rider_prices(standings, default_price=100000)
    
    print("\n✅ Done!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        sys.exit(1)

