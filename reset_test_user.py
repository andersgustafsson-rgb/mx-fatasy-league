# reset_test_user.py
from app import app, db, User
from werkzeug.security import generate_password_hash

USERNAME = "test"
PLAINTEXT = "password"  # ditt önskade lösenord

with app.app_context():
    u = User.query.filter_by(username=USERNAME).first()
    if not u:
        u = User(username=USERNAME, password_hash=generate_password_hash(PLAINTEXT))
        db.session.add(u)
        db.session.commit()
        print(f"Skapade användare '{USERNAME}' med lösenord '{PLAINTEXT}'.")
    else:
        u.password_hash = generate_password_hash(PLAINTEXT)
        db.session.commit()
        print(f"Uppdaterade lösenord för '{USERNAME}' till '{PLAINTEXT}'.")