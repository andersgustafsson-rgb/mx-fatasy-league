#!/usr/bin/env python3
# Import all entry lists and replace existing riders

import csv
import re
from pathlib import Path
from datetime import datetime

def clean_rider_name(name):
    """Clean up rider name"""
    name = re.sub(r'\s+', ' ', name.strip())
    return name

def clean_team_name(team):
    """Clean up team name"""
    if not team or team.strip() == '':
        return None
    return team.strip()

def clean_hometown(hometown):
    """Clean up hometown"""
    if not hometown or hometown.strip() == '':
        return None
    return hometown.strip()

def normalize_bike_brand(brand):
    """Normalize bike brand names"""
    brand_map = {
        'Triumph': 'Triumph',
        'KTM': 'KTM', 
        'GasGas': 'GasGas',
        'Honda': 'Honda',
        'Kawasaki': 'Kawasaki',
        'Yamaha': 'Yamaha',
        'Husqvarna': 'Husqvarna',
        'Suzuki': 'Suzuki'
    }
    return brand_map.get(brand, brand)

def parse_entry_list(csv_path, class_name):
    """Parse entry list CSV file"""
    riders = []
    
    print(f"Reading {class_name} entry list: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        for row_num, row in enumerate(reader, 1):
            # Skip header rows and empty rows
            if row_num <= 7 or not row or len(row) < 4:
                continue
                
            # Join all columns into one string and parse
            full_text = ' '.join(row)
            
            # Look for pattern: number, name, bike, hometown, team
            match = re.match(r'^(\d+)\s+(.+?)\s+([A-Za-z]+)\s+(.+?)\s+(.+)$', full_text)
            
            if match:
                number, name, bike, hometown, team = match.groups()
                
                rider = {
                    'number': int(number),
                    'name': clean_rider_name(name),
                    'bike_brand': normalize_bike_brand(bike),
                    'hometown': clean_hometown(hometown),
                    'team': clean_team_name(team),
                    'class': class_name
                }
                riders.append(rider)
    
    print(f"  Found {len(riders)} riders")
    return riders

def main():
    """Import all entry lists and show preview"""
    
    # Define entry list files
    entry_lists = [
        ("Entry_List_250_west.csv", "250cc"),
        ("Entry_List_250_east.csv", "250cc"), 
        ("Entry_List_450.csv", "450cc")
    ]
    
    all_riders = []
    
    print("=" * 80)
    print("ENTRY LIST IMPORT - PREVIEW")
    print("=" * 80)
    
    # Parse all entry lists
    for csv_file, class_name in entry_lists:
        csv_path = Path(csv_file)
        
        if not csv_path.exists():
            print(f"❌ File not found: {csv_file}")
            continue
            
        riders = parse_entry_list(csv_path, class_name)
        all_riders.extend(riders)
    
    print(f"\n📊 SUMMARY:")
    print(f"Total riders to import: {len(all_riders)}")
    
    # Count by class
    class_counts = {}
    for rider in all_riders:
        class_counts[rider['class']] = class_counts.get(rider['class'], 0) + 1
    
    for class_name, count in class_counts.items():
        print(f"  {class_name}: {count} riders")
    
    # Check for duplicates
    print(f"\n🔍 CHECKING FOR DUPLICATES:")
    name_counts = {}
    for rider in all_riders:
        name = rider['name']
        name_counts[name] = name_counts.get(name, 0) + 1
    
    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    if duplicates:
        print("  ⚠️  Found duplicate names:")
        for name, count in duplicates.items():
            print(f"    {name}: {count} times")
    else:
        print("  ✅ No duplicate names found")
    
    # Show sample riders
    print(f"\n📋 SAMPLE RIDERS:")
    print("-" * 80)
    for i, rider in enumerate(all_riders[:10]):
        print(f"#{rider['number']:3d} {rider['name']:25s} {rider['bike_brand']:10s} {rider['class']:5s}")
        if rider['team']:
            print(f"     Team: {rider['team']}")
        print()
    
    if len(all_riders) > 10:
        print(f"... and {len(all_riders) - 10} more riders")
    
    # Save to CSV for review
    output_path = Path("data/all_entry_lists_clean.csv")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['number', 'name', 'bike_brand', 'hometown', 'team', 'class']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        writer.writeheader()
        for rider in all_riders:
            writer.writerow(rider)
    
    print(f"\n💾 Saved clean data to: {output_path}")
    print(f"📝 Ready for database import!")
    
    return all_riders

if __name__ == "__main__":
    riders = main()


