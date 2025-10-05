import sqlite3

def debug():
    print("\n--- Startar Felsökning av Poängdata ---")
    conn = sqlite3.connect("fantasy_mx.db")
    conn.row_factory = sqlite3.Row
    
    try:
        # Hämta ID för test-användare och första tävling
        user = conn.execute("SELECT id FROM users WHERE username = 'test'").fetchone()
        if not user:
            print("❌ Hittade inte användaren 'test'.")
            return
        uid = user['id']
        print(f"\n[INFO] Användar-ID för 'test': {uid}")

        comp = conn.execute("SELECT id FROM competitions WHERE name = 'Anaheim 1'").fetchone()
        if not comp:
            print("❌ Hittade inte tävlingen 'Anaheim 1'.")
            return
        comp_id = comp['id']
        print(f"[INFO] Tävlings-ID för 'Anaheim 1': {comp_id}")

        print("\n" + "="*40)
        
        # 1. Hämta ANVÄNDARENS GISSNINGAR (picks)
        print("\n[1] Kontrollerar användarens Race Picks...")
        picks = conn.execute("""
            SELECT rp.rider_id, rp.predicted_position, r.class, r.name as rider_name
            FROM race_picks rp JOIN riders r ON rp.rider_id = r.id
            WHERE rp.user_id=? AND rp.competition_id=?
        """,(uid, comp_id)).fetchall()
        
        if not picks:
            print("  -> ❗ INGA Race Picks hittades för denna användare och tävling.")
        else:
            print(f"  -> ✅ Hittade {len(picks)} Race Picks:")
            for p in picks: print(f"     - {dict(p)}")

        # 2. Hämta FAKTISKA RESULTAT
        print("\n[2] Kontrollerar faktiska Tävlingsresultat...")
        actual = conn.execute("""
            SELECT cr.rider_id, cr.position, r.class, r.name
            FROM competition_results cr JOIN riders r ON cr.rider_id = r.id
            WHERE cr.competition_id=?
        """, (comp_id,)).fetchall()

        if not actual:
            print("  -> ❗ INGA faktiska resultat hittades för denna tävling.")
        else:
            print(f"  -> ✅ Hittade {len(actual)} resultat:")
            for a in actual: print(f"     - {dict(a)}")

        # 3. Hämta ANVÄNDARENS HOLESHOT-GISSNINGAR
        print("\n[3] Kontrollerar användarens Holeshot Picks...")
        holo_picks = conn.execute("""
            SELECT hp.rider_id, hp.class, r.name as rider_name
            FROM holeshot_picks hp JOIN riders r ON hp.rider_id = r.id
            WHERE hp.user_id=? AND hp.competition_id=?
        """,(uid, comp_id)).fetchall()

        if not holo_picks:
            print("  -> ❗ INGA Holeshot Picks hittades för denna användare.")
        else:
            print(f"  -> ✅ Hittade {len(holo_picks)} Holeshot Picks:")
            for hp in holo_picks: print(f"     - {dict(hp)}")
            
        # 4. Hämta FAKTISKA HOLESHOT-VINNARE
        print("\n[4] Kontrollerar faktiska Holeshot-resultat...")
        holos = conn.execute("SELECT * FROM holeshot_results WHERE competition_id=?", (comp_id,)).fetchall()
        if not holos:
            print("  -> ❗ INGA faktiska Holeshot-resultat hittades.")
        else:
            print(f"  -> ✅ Hittade {len(holos)} Holeshot-vinnare:")
            for h in holos: print(f"     - {dict(h)}")

    except Exception as e:
        print(f"\n🚨 ETT FEL INTRÄFFADE: {e}")
    finally:
        conn.close()
        print("\n--- Felsökning KLAR ---")

if __name__ == "__main__":
    debug()