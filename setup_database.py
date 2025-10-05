import sqlite3
import random
import string
from werkzeug.security import generate_password_hash

connection = sqlite3.connect('fantasy_mx.db')
cursor = connection.cursor()

# -- Radera alla tabeller för en ren start --
print("Raderar gamla tabeller...")
cursor.execute('DROP TABLE IF EXISTS league_memberships'); cursor.execute('DROP TABLE IF EXISTS leagues')
cursor.execute('DROP TABLE IF EXISTS season_team_riders'); cursor.execute('DROP TABLE IF EXISTS season_teams')
cursor.execute('DROP TABLE IF EXISTS competition_results'); cursor.execute('DROP TABLE IF EXISTS race_picks')
cursor.execute('DROP TABLE IF EXISTS competition_scores'); cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('DROP TABLE IF EXISTS competitions'); cursor.execute('DROP TABLE IF EXISTS riders')
cursor.execute('DROP TABLE IF EXISTS holeshot_picks'); cursor.execute('DROP TABLE IF EXISTS holeshot_results')

# -- Skapa alla tabeller från grunden --
print("Skapar ny databasstruktur...")
cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)')
cursor.execute('CREATE TABLE competitions (id INTEGER PRIMARY KEY, name TEXT NOT NULL, event_date DATE)')
cursor.execute('CREATE TABLE riders (id INTEGER PRIMARY KEY, name TEXT NOT NULL, class TEXT NOT NULL, rider_number INTEGER, bike_brand TEXT, image_url TEXT, price INTEGER NOT NULL)')
cursor.execute('CREATE TABLE race_picks (pick_id INTEGER PRIMARY KEY, user_id INTEGER, competition_id INTEGER, rider_id INTEGER, predicted_position INTEGER)')
cursor.execute('CREATE TABLE competition_scores (score_id INTEGER PRIMARY KEY, user_id INTEGER, competition_id INTEGER, total_points INTEGER)')
cursor.execute('CREATE TABLE competition_results (result_id INTEGER PRIMARY KEY, competition_id INTEGER, rider_id INTEGER, position INTEGER NOT NULL)')
cursor.execute('CREATE TABLE season_teams (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, team_name TEXT NOT NULL, total_points INTEGER DEFAULT 0)')
cursor.execute('CREATE TABLE season_team_riders (entry_id INTEGER PRIMARY KEY, season_team_id INTEGER, rider_id INTEGER)')
cursor.execute('CREATE TABLE leagues (id INTEGER PRIMARY KEY, name TEXT NOT NULL, creator_id INTEGER NOT NULL, invite_code TEXT UNIQUE NOT NULL)')
cursor.execute('CREATE TABLE league_memberships (id INTEGER PRIMARY KEY, league_id INTEGER NOT NULL, user_id INTEGER NOT NULL, UNIQUE(league_id, user_id))')
cursor.execute('CREATE TABLE holeshot_picks (id INTEGER PRIMARY KEY, user_id INTEGER, competition_id INTEGER, rider_id INTEGER, class TEXT)')
cursor.execute('CREATE TABLE holeshot_results (id INTEGER PRIMARY KEY, competition_id INTEGER, rider_id INTEGER, class TEXT)')
print("Alla tabeller har skapats.")

# -- Fyll på med exempeldata --
hashed_password = generate_password_hash('password')
cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('test', hashed_password))
riders_to_add = [ (1, "Jett Lawrence", "450cc", 18, "Honda", "https://placehold.co/100x100/E12828/FFF?text=%2318", 450000), (2, "Chase Sexton", "450cc", 1, "KTM", "https://placehold.co/100x100/FF6600/FFF?text=%231", 420000), (3, "Eli Tomac", "450cc", 3, "Yamaha", "https://placehold.co/100x100/0033A0/FFF?text=%233", 400000), (4, "Cooper Webb", "450cc", 2, "Yamaha", "https://placehold.co/100x100/0033A0/FFF?text=%232", 390000), (5, "Jason Anderson", "450cc", 21, "Kawasaki", "https://placehold.co/100x100/00A651/FFF?text=%2321", 350000), (11, "Malcolm Stewart", "450cc", 27, "Husqvarna", "https://placehold.co/100x100/FFFFFF/000?text=%2327", 250000), (13, "Hunter Lawrence", "450cc", 96, "Honda", "https://placehold.co/100x100/E12828/FFF?text=%2396", 360000), (14, "Justin Barcia", "450cc", 51, "GasGas", "https://placehold.co/100x100/D90000/FFF?text=%2351", 320000), (17, "Ken Roczen", "450cc", 94, "Suzuki", "https://placehold.co/100x100/FFD700/000?text=%2394", 380000), (18, "Aaron Plessinger", "450cc", 7, "KTM", "https://placehold.co/100x100/FF6600/FFF?text=%237", 300000), (6, "Haiden Deegan", "250cc", 38, "Yamaha", "https://placehold.co/100x100/0033A0/FFF?text=%2338", 350000), (7, "Jo Shimoda", "250cc", 30, "Honda", "https://placehold.co/100x100/E12828/FFF?text=%2330", 320000), (8, "Levi Kitchen", "250cc", 47, "Kawasaki", "https://placehold.co/100x100/00A651/FFF?text=%2347", 310000), (9, "Tom Vialle", "250cc", 16, "KTM", "https://placehold.co/100x100/FF6600/FFF?text=%2316", 300000), (10, "RJ Hampshire", "250cc", 24, "Husqvarna", "https://placehold.co/100x100/FFFFFF/000?text=%2324", 290000), (12, "Chance Hymas", "250cc", 48, "Honda", "https://placehold.co/100x100/E12828/FFF?text=%2348", 260000), (15, "Jalek Swoll", "250cc", 33, "Triumph", "https://placehold.co/100x100/000000/FFF?text=%2333", 250000), (16, "Pierce Brown", "250cc", 39, "GasGas", "https://placehold.co/100x100/D90000/FFF?text=%2339", 240000), (19, "Nate Thrasher", "250cc", 57, "Yamaha", "https://placehold.co/100x100/0033A0/FFF?text=%2357", 230000), (20, "Ryder DiFrancesco", "250cc", 75, "GasGas", "https://placehold.co/100x100/D90000/FFF?text=%2375", 220000) ]
cursor.executemany('INSERT INTO riders (id, name, class, rider_number, bike_brand, image_url, price) VALUES (?,?,?,?,?,?,?)', riders_to_add)
competitions_to_add = [ ('Anaheim 1', '2026-01-04'), ('San Francisco', '2026-01-11'), ('San Diego', '2026-01-18') ]
cursor.executemany('INSERT INTO competitions (name, event_date) VALUES (?, ?)', competitions_to_add)
connection.commit()
connection.close()

print("Databasen har nollställts med den senaste korrekta datan.")

