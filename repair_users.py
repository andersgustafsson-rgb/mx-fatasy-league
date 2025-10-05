import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("fantasy_mx.db")
cur = conn.cursor()

# Rensa gamla "test" om något spökinlägg fanns
cur.execute("DELETE FROM users WHERE username=?", ("test",))

# Lägg till användaren test/password
cur.execute(
    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
    ("test", generate_password_hash("password"))
)

# Lägg till en extra användare om du vill
cur.execute(
    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
    ("test2", generate_password_hash("password"))
)

conn.commit()
conn.close()
print("✅ Användarna 'test' och 'test2' har återställts. Login = password")