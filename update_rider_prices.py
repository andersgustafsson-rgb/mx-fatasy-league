#!/usr/bin/env python3
"""
Update rider prices based on 2025 point standings
Prices should reflect performance from previous year
"""

import re
from collections import defaultdict

def parse_point_standings():
    """Parse the point standings file and return rider data"""
    riders_data = {
        '450cc': {},
        '250cc': {}
    }
    
    print("Reading point standings file...")
    with open('point standings 2025.txt', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"File content length: {len(content)} characters")
    
    # Split by sections
    sections = content.split('\n\n')
    print(f"Found {len(sections)} sections")
    
    current_class = None
    
    for i, section in enumerate(sections):
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        print(f"Section {i}: {lines[0][:50]}...")
            
        # Check if this is a class header
        if lines[0].lower() in ['250 west', '250 east', '450 point standings']:
            if '250' in lines[0].lower():
                current_class = '250cc'
                print(f"  -> Found 250cc section")
            elif '450' in lines[0].lower():
                current_class = '450cc'
                print(f"  -> Found 450cc section")
            continue
        
        # Parse rider data
        if current_class and len(lines) > 1:
            print(f"  -> Parsing {len(lines)-1} riders for {current_class}")
            for line in lines[1:]:  # Skip header line
                if not line.strip():
                    continue
                    
                # Parse format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                parts = line.split('\t')
                if len(parts) >= 4:
                    try:
                        position = int(parts[0])
                        name_part = parts[1]
                        points = int(parts[-1]) if parts[-1].isdigit() else 0
                        
                        # Clean up name (remove duplicates)
                        name = name_part
                        if len(name) > 20:  # Likely has duplicate name
                            # Find the middle point and split
                            mid = len(name) // 2
                            for i in range(mid-5, mid+5):
                                if i < len(name) and name[i].isupper():
                                    name = name[:i]
                                    break
                        
                        riders_data[current_class][name] = {
                            'position': position,
                            'points': points
                        }
                        print(f"    -> {position}. {name} - {points} pts")
                    except (ValueError, IndexError) as e:
                        print(f"    -> Error parsing line: {line[:50]}... - {e}")
                        continue
    
    return riders_data

def calculate_price(position, points, class_name):
    """Calculate price based on position and points"""
    if class_name == '450cc':
        # 450cc pricing - higher base prices
        if position <= 5:
            return 500000  # Top 5 riders
        elif position <= 10:
            return 400000  # Top 10 riders
        elif position <= 15:
            return 300000  # Top 15 riders
        elif position <= 20:
            return 200000  # Top 20 riders
        elif points > 50:
            return 150000  # Some points
        elif points > 0:
            return 100000  # Few points
        else:
            return 50000   # No points
    else:  # 250cc
        # 250cc pricing - lower base prices
        if position <= 5:
            return 300000  # Top 5 riders
        elif position <= 10:
            return 250000  # Top 10 riders
        elif position <= 15:
            return 200000  # Top 15 riders
        elif position <= 20:
            return 150000  # Top 20 riders
        elif points > 30:
            return 100000  # Some points
        elif points > 0:
            return 75000   # Few points
        else:
            return 50000   # No points

def main():
    """Main function to update rider prices"""
    print("Parsing 2025 point standings...")
    standings = parse_point_standings()
    
    print(f"Found {len(standings['450cc'])} 450cc riders")
    print(f"Found {len(standings['250cc'])} 250cc riders")
    
    print("\n450cc Standings:")
    for name, data in standings['450cc'].items():
        price = calculate_price(data['position'], data['points'], '450cc')
        print(f"  {data['position']:2d}. {name:25s} - {data['points']:3d} pts - ${price:,}")
    
    print("\n250cc Standings:")
    for name, data in standings['250cc'].items():
        price = calculate_price(data['position'], data['points'], '250cc')
        print(f"  {data['position']:2d}. {name:25s} - {data['points']:3d} pts - ${price:,}")
    
    # Create SQL update statements
    print("\n" + "="*60)
    print("SQL UPDATE STATEMENTS:")
    print("="*60)
    
    for class_name, riders in standings.items():
        print(f"\n-- {class_name} price updates:")
        for name, data in riders.items():
            price = calculate_price(data['position'], data['points'], class_name)
            # Escape single quotes in names
            escaped_name = name.replace("'", "''")
            print(f"UPDATE riders SET price = {price} WHERE name = '{escaped_name}' AND class = '{class_name}';")

if __name__ == "__main__":
    main()
