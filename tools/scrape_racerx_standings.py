#!/usr/bin/env python3
"""
Scrape point standings from RacerX online for previous year
Used to set rider prices for season teams based on performance
"""

import re
import csv
import time
import pathlib
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://racerxonline.com"
VAULT_BASE = "https://vault.racerxonline.com"
OUT_DIR = pathlib.Path("data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def normalize_name(name: str) -> str:
    """Normalize rider name for matching"""
    # Remove extra spaces, convert to title case
    name = clean_ws(name)
    # Remove common suffixes like "Jr.", "Sr.", "III", etc.
    name = re.sub(r'\s+(Jr\.|Sr\.|III|II|IV)$', '', name, flags=re.IGNORECASE)
    return name.strip()

def fetch(url: str) -> BeautifulSoup:
    """Fetch and parse HTML from URL"""
    print(f"Fetching: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def scrape_standings_from_vault(year: int = 2025):
    """
    Scrape point standings from RacerX Vault
    Returns dict with '450cc' and '250cc' (west/east combined) standings
    """
    standings = {
        '450cc': {},
        '250cc': {}
    }
    
    # Try to find point standings page
    # Common URLs: vault.racerxonline.com/2025/sx/points
    points_url = f"{VAULT_BASE}/{year}/sx/points"
    
    try:
        soup = fetch(points_url)
        
        # Look for tables with standings
        # Try different selectors that might contain standings
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            
            # Check header to determine class
            header = rows[0].get_text().lower()
            class_name = None
            if '450' in header or '450sx' in header:
                class_name = '450cc'
            elif '250' in header or '250sx' in header:
                class_name = '250cc'
            
            if not class_name:
                continue
            
            print(f"Found {class_name} standings table")
            
            # Parse rows (skip header)
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                try:
                    # Try to extract position and name
                    position_text = cells[0].get_text().strip()
                    position = int(re.search(r'\d+', position_text).group())
                    
                    name_text = cells[1].get_text().strip()
                    name = normalize_name(name_text)
                    
                    # Try to extract points (usually in last column or column with numbers)
                    points = 0
                    for cell in cells[2:]:
                        cell_text = cell.get_text().strip()
                        if cell_text.isdigit():
                            points = int(cell_text)
                            break
                    
                    if name:
                        standings[class_name][name] = {
                            'position': position,
                            'points': points
                        }
                        print(f"  {position}. {name} - {points} pts")
                        
                except (ValueError, AttributeError, IndexError) as e:
                    continue
        
        # If no tables found, try alternative parsing
        if not any(standings.values()):
            print("No tables found, trying alternative parsing...")
            # Look for divs or other structures with standings
            # This would need to be customized based on actual page structure
            
    except Exception as e:
        print(f"Error fetching from vault: {e}")
        print(f"Trying alternative method...")
    
    # Alternative: Try scraping individual race results and aggregate
    # Or use the existing point standings file if available
    
    return standings

def scrape_standings_alternative(year: int = 2025):
    """
    Alternative method: Try to find standings from main RacerX site
    or parse from known structure
    """
    standings = {
        '450cc': {},
        '250cc': {}
    }
    
    # Try main site standings page
    standings_urls = [
        f"{BASE}/sx/standings",
        f"{BASE}/sx/{year}/standings",
        f"{BASE}/results/{year}/supercross/standings"
    ]
    
    for url in standings_urls:
        try:
            soup = fetch(url)
            # Parse based on actual page structure
            # This would need to be customized
            break
        except:
            continue
    
    return standings

def save_standings_to_csv(standings: dict, filename: str = "racerx_standings_2025.csv"):
    """Save standings to CSV file"""
    csv_path = OUT_DIR / filename
    
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['class', 'position', 'name', 'points'])
        
        for class_name in ['450cc', '250cc']:
            for name, data in sorted(standings[class_name].items(), 
                                     key=lambda x: x[1]['position']):
                writer.writerow([
                    class_name,
                    data['position'],
                    name,
                    data['points']
                ])
    
    print(f"\n✅ Saved standings to {csv_path}")
    return csv_path

def main():
    """Main function to scrape standings"""
    print("=" * 60)
    print("Scraping RacerX Point Standings for 2025")
    print("=" * 60)
    
    # Try vault first
    standings = scrape_standings_from_vault(2025)
    
    # If vault didn't work, try alternative
    if not any(standings.values()):
        print("\nTrying alternative method...")
        standings = scrape_standings_alternative(2025)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"450cc riders found: {len(standings['450cc'])}")
    print(f"250cc riders found: {len(standings['250cc'])}")
    
    if standings['450cc']:
        print("\nTop 10 450cc:")
        for name, data in sorted(standings['450cc'].items(), 
                                key=lambda x: x[1]['position'])[:10]:
            print(f"  {data['position']:2d}. {name:25s} - {data['points']:3d} pts")
    
    if standings['250cc']:
        print("\nTop 10 250cc:")
        for name, data in sorted(standings['250cc'].items(), 
                                key=lambda x: x[1]['position'])[:10]:
            print(f"  {data['position']:2d}. {name:25s} - {data['points']:3d} pts")
    
    # Save to CSV
    if any(standings.values()):
        save_standings_to_csv(standings)
        print("\n✅ Standings scraped successfully!")
        print("Next step: Run update_rider_prices_from_standings.py to update database")
    else:
        print("\n⚠️  No standings found. You may need to:")
        print("  1. Check if the URL structure has changed")
        print("  2. Use the existing 'point standings 2025.txt' file")
        print("  3. Manually update the scraper for the current page structure")

if __name__ == "__main__":
    main()

