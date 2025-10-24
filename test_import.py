#!/usr/bin/env python3
# Simple test to read entry lists

import csv
from pathlib import Path

def test_read_csv(filename):
    print(f"Testing {filename}...")
    
    if not Path(filename).exists():
        print(f"  ❌ File not found: {filename}")
        return
    
    with open(filename, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        rows = list(reader)
        
        print(f"  📄 Total rows: {len(rows)}")
        
        # Show first few data rows
        data_rows = [row for row in rows if len(row) > 0 and row[0].strip().startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9'))]
        
        print(f"  🏁 Data rows found: {len(data_rows)}")
        
        for i, row in enumerate(data_rows[:5]):
            print(f"    Row {i+1}: {row}")
        
        if len(data_rows) > 5:
            print(f"    ... and {len(data_rows) - 5} more")

def main():
    print("=" * 60)
    print("TESTING ENTRY LIST FILES")
    print("=" * 60)
    
    files = [
        "Entry_List_250_west.csv",
        "Entry_List_250_east.csv", 
        "Entry_List_450.csv"
    ]
    
    for filename in files:
        test_read_csv(filename)
        print()

if __name__ == "__main__":
    main()


