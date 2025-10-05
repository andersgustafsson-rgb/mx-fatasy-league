# import_riders_csv.py
import csv
from pathlib import Path
from app import app, db, Rider

CSV_PATH = Path("data/riders_2026.csv")
VALID_BRANDS = {"honda","yamaha","ktm","kawasaki","gasgas","husqvarna","suzuki"}

def normalize_brand(b):
    if not b: return None
    b = b.strip()
    # behåll originalet men kontrollera mot kända
    return b

def normalize_class(c):
    c = (c or "").strip().lower()
    if c in {"450","450cc","sx450","450 sx"}:
        return "450cc"
    if c in {"250","250cc","sx250","250 sx"}:
        return "250cc"
    return c  # lämna oförändrad om den redan är korrekt

def run():
    if not CSV_PATH.exists():
        print("Saknar CSV:", CSV_PATH)
        return
    with app.app_context():
        rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
        created = 0
        for r in rows:
            name = r.get("name","").strip()
            klass = normalize_class(r.get("class",""))
            number = int(r.get("rider_number") or 0)
            brand = normalize_brand(r.get("bike_brand",""))
            price = int(r.get("price") or 0)

            if not name or klass not in {"450cc","250cc"}:
                continue

            # hoppa över dublett (namn+klass)
            exists = Rider.query.filter_by(name=name, class_name=klass).first()
            if exists:
                # uppdatera ev. nummer/brand/price
                exists.rider_number = number
                exists.bike_brand = brand
                exists.price = price
            else:
                db.session.add(Rider(
                    name=name,
                    class_name=klass,
                    rider_number=number,
                    bike_brand=brand,
                    price=price
                ))
                created += 1
        db.session.commit()
        print(f"Klar. Nya förare skapade: {created}. Totalt i DB: {Rider.query.count()}")

if __name__ == "__main__":
    run()