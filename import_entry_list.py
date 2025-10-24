#!/usr/bin/env python3
# Import rider data from Entry_List_250_west.csv

import csv
import re
from pathlib import Path

def clean_rider_name(name):
    """Clean up rider name"""
    # Remove extra spaces and normalize
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

def parse_entry_list(csv_path):
    """Parse the entry list CSV file"""
    riders = []
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        for row_num, row in enumerate(reader, 1):
            # Skip header rows and empty rows
            if row_num <= 7 or not row or len(row) < 4:
                continue
                
            # Join all columns into one string and parse
            full_text = ' '.join(row)
            
            # Look for pattern: number, name, bike, hometown, team
            # Example: "19    Jordon Smith                Triumph     Belmont, NC                               Triumph Racing Factory Team"
            match = re.match(r'^(\d+)\s+(.+?)\s+([A-Za-z]+)\s+(.+?)\s+(.+)$', full_text)
            
            if match:
                number, name, bike, hometown, team = match.groups()
                
                rider = {
                    'number': int(number),
                    'name': clean_rider_name(name),
                    'bike_brand': normalize_bike_brand(bike),
                    'hometown': clean_hometown(hometown),
                    'team': clean_team_name(team),
                    'class': '250cc'  # This is 250 West entry list
                }
                riders.append(rider)
    
    return riders

def main():
    csv_path = Path("Entry_List_250_west.csv")
    
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        return
    
    print(f"Reading entry list: {csv_path}")
    riders = parse_entry_list(csv_path)
    
    print(f"\nFound {len(riders)} riders:")
    print("=" * 80)
    
    for rider in riders:
        print(f"#{rider['number']:3d} {rider['name']:25s} {rider['bike_brand']:10s} {rider['hometown']:20s}")
        if rider['team']:
            print(f"     Team: {rider['team']}")
        print()
    
    # Save to new CSV for import
    output_path = Path("data/entry_list_250_west_clean.csv")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['number', 'name', 'bike_brand', 'hometown', 'team', 'class']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        writer.writeheader()
        for rider in riders:
            writer.writerow(rider)
    
    print(f"Saved clean data to: {output_path}")
    print(f"Ready for import into database!")

if __name__ == "__main__":
    main()


