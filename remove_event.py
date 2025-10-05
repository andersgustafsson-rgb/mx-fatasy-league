from app import app, db, Competition

EVENT_NAME_TO_DELETE = "San Francisco"  # tävlingen som ska bort

with app.app_context():
    comp = Competition.query.filter_by(series="SX", name=EVENT_NAME_TO_DELETE).first()
    if comp:
        db.session.delete(comp)
        db.session.commit()
        print("Borttagen:", EVENT_NAME_TO_DELETE)
    else:
        print("Hittar ej:", EVENT_NAME_TO_DELETE)