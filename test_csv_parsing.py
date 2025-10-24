import csv
import re

# Test the exact CSV parsing logic
def test_parse_entry_list(csv_path, class_name):
    riders = []
    print(f"DEBUG: Starting to parse {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        for row_num, row in enumerate(reader, 1):
            if row_num <= 7 or not row or len(row) < 4:
                if row_num <= 7:
                    print(f"DEBUG: Skipping header row {row_num}: {row}")
                continue
            
            # Handle CSV format where all data is in one column
            if len(row) >= 1 and row[0].strip():
                try:
                    # All data is in the first column, need to parse it
                    full_text = row[0].strip().strip('"')
                    print(f"DEBUG: Parsing row {row_num}: {full_text}")
                    
                    # Use regex to parse the format
                    match = re.match(r'^(\d+)\s+(.+?)\s+([A-Za-z]+)\s+(.+?)\s+(.+)$', full_text)
                    print(f"DEBUG: Regex match result: {match}")
                    
                    if match:
                        number_str, name, bike, hometown, team = match.groups()
                        print(f"DEBUG: Found rider: {number_str} - {name} - {bike}")
                        riders.append({
                            'number': int(number_str),
                            'name': name.strip(),
                            'bike_brand': bike,
                            'hometown': hometown.strip(),
                            'team': team.strip(),
                            'class': class_name
                        })
                    else:
                        print(f"DEBUG: No match for row {row_num}")
                        
                except Exception as e:
                    print(f"Error parsing row {row_num}: {e}")
                    continue
    
    print(f"DEBUG: Found {len(riders)} riders total")
    return riders

# Test with the actual file
if __name__ == "__main__":
    riders = test_parse_entry_list("data/Entry_List_250_east.csv", "250cc")
    print(f"Total riders found: {len(riders)}")
    if riders:
        print("First few riders:")
        for rider in riders[:3]:
            print(f"  {rider['number']}: {rider['name']} ({rider['bike_brand']})")
