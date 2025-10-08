import sqlite3

# Connect to database
conn = sqlite3.connect('instance/app.db')
cursor = conn.cursor()

# Clear existing competition images
cursor.execute('DELETE FROM competition_image')
print("Cleared existing competition images")

# Get all competitions
cursor.execute('SELECT id, name FROM competition ORDER BY id')
competitions = cursor.fetchall()

# Map competition names to image files
COMP_TO_IMAGE = {
    "Anaheim 1": "anaheim1.jpg",
    "San Diego": "sandiego.jpg", 
    "Anaheim 2 (Triple Crown)": "anaheim2.jpg",
    "Houston": "houston.jpg",
    "Glendale": "glendale.jpg",
    "Seattle": "seattle.jpg",
    "Arlington": "arlington.jpg",
    "Daytona": "daytona.jpg",
    "Indianapolis": "indianapolis.jpg",
    "Birmingham": "birmingham.jpg",
    "Detroit": "detroit.jpg",
    "St. Louis": "stlouis.jpg",
    "Nashville": "nashville.jpg",
    "Cleveland": "cleveland.jpg",
    "Philadelphia": "philadelphia.jpg",
    "Denver": "denver.jpg",
    "Salt Lake City": "saltlakecity.jpg"
}

# Create competition image records
created = 0
for comp_id, comp_name in competitions:
    if comp_name in COMP_TO_IMAGE:
        image_url = f"trackmaps/compressed/{COMP_TO_IMAGE[comp_name]}"
        cursor.execute('INSERT INTO competition_image (competition_id, image_url, sort_order) VALUES (?, ?, ?)', 
                      (comp_id, image_url, 0))
        created += 1
        print(f"Created: {comp_name} -> {image_url}")

# Commit changes
conn.commit()
print(f"Created {created} competition image records")

# Verify
cursor.execute('SELECT COUNT(*) FROM competition_image')
count = cursor.fetchone()[0]
print(f"Total competition images in database: {count}")

conn.close()
print("Done!")
