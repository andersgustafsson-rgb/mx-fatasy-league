import sqlite3

print("--- Startar Databas-inspektion (Utökad) ---")

try:
    connection = sqlite3.connect('fantasy_mx.db')
    # Använd Row-factory för att kunna komma åt kolumner med namn
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # 1. Lista alla tabeller som finns
    print("\n[1] HITTADE TABELLER:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    if not tables:
        print("  -> Inga tabeller hittades!")
    for table_name in tables:
        print(f"  -> {table_name[0]}")

    # ==========================================================
    # NYTT: Inspektera Competition Scores
    # ==========================================================
    print("\n[2] INNEHÅLL I 'competition_scores':")
    try:
        cursor.execute("SELECT * FROM competition_scores")
        scores = cursor.fetchall()
        if not scores:
            print("  -> Tabellen är TOM.")
        else:
            print(f"  -> Hittade {len(scores)} rad(er):")
            for row in scores:
                # Konvertera raden till en vanlig dictionary för utskrift
                print(f"  -> {dict(row)}")
    except sqlite3.OperationalError:
        print("  -> Tabellen 'competition_scores' finns inte.")

    # ==========================================================
    # FÖRBÄTTRAD: Inspektera Season Teams (korrekt tabellnamn och visar poäng)
    # ==========================================================
    print("\n[3] INNEHÅLL I 'season_teams':")
    try:
        # Notera: Korrigerat från 'user_teams' till 'season_teams'
        cursor.execute("SELECT * FROM season_teams")
        teams = cursor.fetchall()
        if not teams:
            print("  -> Tabellen är TOM.")
        else:
            print(f"  -> Hittade {len(teams)} rad(er):")
            for row in teams:
                print(f"  -> {dict(row)}")
    except sqlite3.OperationalError:
        print("  -> Tabellen 'season_teams' finns inte.")


    connection.close()

except Exception as e:
    print(f"\nEtt allvarligt fel inträffade: {e}")

print("\n--- Inspektion Avslutad ---")