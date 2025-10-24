import re

# Test the exact line from the CSV
test_line = "1      Tom Vialle                   KTM       France                                     Red Bull KTM Factory Racing"
print('Testing line:', test_line)

# Try the current regex
pattern = r'^(\d+)\s+(.+?)\s+([A-Za-z]+)\s+(.+?)\s+(.+)$'
match = re.match(pattern, test_line)
print('Match result:', match)

if match:
    print('Groups:')
    for i, group in enumerate(match.groups()):
        print(f'  {i+1}: "{group}"')
else:
    print('No match - trying different approach')
    
    # Try splitting by multiple spaces
    parts = test_line.split()
    print('Split parts:', parts)
    
    # Try a different regex
    pattern2 = r'^(\d+)\s+(.+?)\s+([A-Za-z]+)\s+(.+?)\s+(.+)$'
    match2 = re.match(pattern2, test_line)
    print('Pattern2 result:', match2)
