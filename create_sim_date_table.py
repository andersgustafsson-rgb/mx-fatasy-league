# create_sim_date_table.py
from app import app, db

with app.app_context():
    try:
        db.session.execute(db.text(
            "CREATE TABLE IF NOT EXISTS sim_date (id INTEGER PRIMARY KEY, value DATE)"
        ))
        db.session.commit()
        print("KLART: sim_date-tabellen finns nu.")
    except Exception as e:
        db.session.rollback()
        print("FEL:", e)