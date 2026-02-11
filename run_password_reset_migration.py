"""
Kör denna fil EN GANG för att lägga till kolumnerna för "glömt lösenord".

  Lokalt (din dator):
    python run_password_reset_migration.py

  På Render (efter deploy):
    1. Gå till https://dashboard.render.com
    2. Välj din webbtjänst (MX Fantasy League)
    3. Klicka på "Shell" i vänstermenyn
    4. I Shell-fönstret, skriv:  python run_password_reset_migration.py
    5. Tryck Enter. När du ser "Klar. Glömt-lösenord-funktionen är redo." är det klart.

Använder samma databas som appen (DATABASE_URL eller sqlite:///fantasy_mx.db).
"""
import os
import sys

# Ladda .env om den finns (lokalt)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Importera app och db från main
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import app, db
from sqlalchemy import text

def column_exists(conn, table, column):
    """Kolla om en kolumn finns (fungerar för SQLite och PostgreSQL)."""
    if "sqlite" in str(conn.engine.url):
        r = conn.execute(text(f"PRAGMA table_info({table})"))
        for row in r:
            if row[1] == column:
                return True
        return False
    else:
        q = """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
        """
        r = conn.execute(text(q), {"t": table, "c": column})
        return r.scalar() is not None

def run_migration():
    with app.app_context():
        uri = app.config["SQLALCHEMY_DATABASE_URI"] or ""
        print("Databas:", "PostgreSQL" if "postgresql" in uri else "SQLite")
        conn = db.engine.connect()
        try:
            if column_exists(conn, "users", "password_reset_token"):
                print("Kolumnen password_reset_token finns redan. Inget att göra.")
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(64)"))
                conn.commit()
                print("Lade till kolumn: password_reset_token")
            if column_exists(conn, "users", "password_reset_expires"):
                print("Kolumnen password_reset_expires finns redan. Inget att göra.")
            else:
                if "postgresql" in uri:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_expires TIMESTAMP"))
                else:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_expires DATETIME"))
                conn.commit()
                print("Lade till kolumn: password_reset_expires")
        except Exception as e:
            print("Fel:", e)
            raise
        finally:
            conn.close()
    print("Klar. Glömt-lösenord-funktionen är redo.")

if __name__ == "__main__":
    run_migration()
