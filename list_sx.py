from app import app, db, Competition

with app.app_context():
    rows = (Competition.query
            .filter(Competition.series == "SX")
            .order_by(Competition.event_date.asc().nulls_last())
            .all())
    for c in rows:
        print(f"{c.id:>3} | {c.name:30} | {c.event_date}")