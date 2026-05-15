# assign_mx_trackmaps.py
# Kör: python assign_mx_trackmaps.py
# Läser bilder från static/trackmaps/pro motocross och skapar CompetitionImage per MX-tävling.

from trackmap_utils import find_mx_trackmap_dir, resolve_mx_trackmap_urls

from app import app, db
from models import Competition, CompetitionImage


def main():
    track_dir = find_mx_trackmap_dir()
    if not track_dir:
        print("Saknar mapp. Skapa t.ex.: static/trackmaps/pro motocross/")
        return

    with app.app_context():
        comps = Competition.query.filter_by(series="MX").order_by(Competition.event_date).all()
        if not comps:
            print("Inga MX-tävlingar i databasen.")
            return

        created = 0
        for comp in comps:
            urls = resolve_mx_trackmap_urls(comp.name)
            if not urls:
                print(f"  ⚠ Ingen bild: {comp.name}")
                continue

            CompetitionImage.query.filter_by(competition_id=comp.id).delete()
            for i, url in enumerate(urls):
                db.session.add(
                    CompetitionImage(
                        competition_id=comp.id,
                        image_url=url,
                        sort_order=i,
                    )
                )
            created += 1
            print(f"  ✓ {comp.name} -> {urls[0]}")

        db.session.commit()
        print(f"Klart: {created}/{len(comps)} tävlingar fick track map.")


if __name__ == "__main__":
    main()
