#!/usr/bin/env python3

import sqlite3
import os

def check_trackmaps():
    # Check database
    conn = sqlite3.connect('instance/app.db')
    cursor = conn.cursor()
    
    # Get competitions
    cursor.execute('SELECT id, name FROM competition ORDER BY id')
    competitions = cursor.fetchall()
    print("Competitions in database:")
    for comp_id, name in competitions:
        print(f"  {comp_id}: {name}")
    
    # Get existing images
    cursor.execute('SELECT competition_id, image_url FROM competition_image ORDER BY competition_id')
    existing_images = cursor.fetchall()
    print(f"\nExisting CompetitionImage records: {len(existing_images)}")
    for comp_id, image_url in existing_images:
        print(f"  Comp {comp_id}: {image_url}")
    
    # Check which image files exist
    print("\nChecking image files:")
    image_dir = "static/trackmaps/compressed"
    if os.path.exists(image_dir):
        files = os.listdir(image_dir)
        print(f"  Found {len(files)} files in {image_dir}:")
        for f in sorted(files):
            print(f"    {f}")
    else:
        print(f"  Directory {image_dir} does not exist!")
    
    conn.close()

if __name__ == "__main__":
    check_trackmaps()
