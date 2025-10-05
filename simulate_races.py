import sqlite3

conn = sqlite3.connect("fantasy_mx.db")
cur = conn.cursor()

# töm tidigare picks/resultat för enkelhet
cur.executescript("""
DELETE FROM competition_results;
DELETE FROM holeshot_results;
DELETE FROM race_picks;
DELETE FROM holeshot_picks;
DELETE FROM competition_scores;
UPDATE season_teams SET total_points=0;
""")

# -------------------------------
# Användar-ID
test_id = 1
test2_id = 2

# -------------------------------
# Race 1 (Anaheim 1)
# test gissar Jett (450, id=1), Deegan (250, id=6)
# test2 gissar Sexton (450, id=3), Hampshire (250, id=10)

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,1,1))   # Jett pos 1
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,1,6))   # Deegan pos 1
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,1,1,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,1,6,"250cc"))

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,1,2)) # Sexton
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,1,10)) # Hampshire
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,1,2,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,1,10,"250cc"))

# Resultat race 1
cur.execute("INSERT INTO competition_results VALUES (NULL,1,1,1)")   # Jett 1a
cur.execute("INSERT INTO competition_results VALUES (NULL,1,6,1)")   # Deegan 1a
cur.execute("INSERT INTO competition_results VALUES (NULL,1,2,2)")   # Sexton 2a
cur.execute("INSERT INTO competition_results VALUES (NULL,1,10,2)")  # Hampshire 2a
cur.execute("INSERT INTO holeshot_results VALUES (NULL,1,1,'450cc')")
cur.execute("INSERT INTO holeshot_results VALUES (NULL,1,6,'250cc')")

# -------------------------------
# Race 2 (San Francisco)
# test: Jett/Deegan
# test2: Sexton/Hampshire

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,2,1))
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,2,6))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,2,1,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,2,6,"250cc"))

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,2,2))
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,2,10))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,2,2,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,2,10,"250cc"))

# Resultat race 2
cur.execute("INSERT INTO competition_results VALUES (NULL,2,2,1)")   # Sexton 1
cur.execute("INSERT INTO competition_results VALUES (NULL,2,10,1)")  # Hampshire 1
cur.execute("INSERT INTO competition_results VALUES (NULL,2,1,2)")   # Jett 2
cur.execute("INSERT INTO competition_results VALUES (NULL,2,6,2)")   # Deegan 2
cur.execute("INSERT INTO holeshot_results VALUES (NULL,2,2,'450cc')")
cur.execute("INSERT INTO holeshot_results VALUES (NULL,2,10,'250cc')")

# -------------------------------
# Race 3 (San Diego)
# test: Jett/Deegan
# test2: Sexton/Hampshire

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,3,1))
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test_id,3,6))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,3,1,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test_id,3,6,"250cc"))

cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,3,2))
cur.execute("INSERT INTO race_picks VALUES (NULL,?,?,?,1)", (test2_id,3,10))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,3,2,"450cc"))
cur.execute("INSERT INTO holeshot_picks VALUES (NULL,?,?,?,?)",(test2_id,3,10,"250cc"))

# Resultat race 3
cur.execute("INSERT INTO competition_results VALUES (NULL,3,1,1)")   # Jett 1
cur.execute("INSERT INTO competition_results VALUES (NULL,3,6,1)")   # Deegan 1
cur.execute("INSERT INTO competition_results VALUES (NULL,3,2,7)")   # Sexton långt bak
cur.execute("INSERT INTO competition_results VALUES (NULL,3,10,5)")  # Hampshire topp 6
cur.execute("INSERT INTO holeshot_results VALUES (NULL,3,17,'450cc')") # Roczen
cur.execute("INSERT INTO holeshot_results VALUES (NULL,3,19,'250cc')") # Thrasher

conn.commit()
conn.close()

print("Simulering klar: Race 1-3 inlagda med picks & resultat")