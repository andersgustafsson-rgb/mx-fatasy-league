# run_simulation.py
import sys
from datetime import date
from app import app, db, User, Competition, Rider, RacePick, HoleshotPick, WildcardPick, CompetitionResult, HoleshotResult, CompetitionScore, SeasonTeam, SeasonTeamRider
from app import calculate_scores

def ensure_minimal_data():
    created = []
    # Minsta möjliga data: test-user, 1-3 tävlingar, några riders 450/250
    with app.app_context():
        user = User.query.filter_by(username="test").first()
        if not user:
            user = User(username="test", password_hash="$pbkdf2-sha256$29000$dummy$dummy")  # funkar ej att logga in, men behövs ej i script
            db.session.add(user)
            db.session.commit()
            created.append("User 'test'")

        if Competition.query.count() == 0:
            comps = [
                Competition(name="Anaheim 1", event_date=date(2026,1,3), series="SX", point_multiplier=1.0, is_triple_crown=0),
                Competition(name="San Francisco", event_date=date(2026,1,10), series="SX", point_multiplier=1.0, is_triple_crown=0),
                Competition(name="San Diego", event_date=date(2026,1,17), series="SX", point_multiplier=1.0, is_triple_crown=0),
            ]
            db.session.add_all(comps)
            db.session.commit()
            created.append("Competitions x3")

        if Rider.query.filter_by(class_name="450cc").count() == 0:
            db.session.add(Rider(name="Jett Lawrence", class_name="450cc", rider_number=18, bike_brand="Honda", price=450000))
            db.session.add(Rider(name="Chase Sexton", class_name="450cc", rider_number=4, bike_brand="KTM", price=420000))
            db.session.commit()
            created.append("Riders 450")

        if Rider.query.filter_by(class_name="250cc").count() == 0:
            db.session.add(Rider(name="Haiden Deegan", class_name="250cc", rider_number=38, bike_brand="Yamaha", price=350000))
            db.session.add(Rider(name="Jo Shimoda", class_name="250cc", rider_number=30, bike_brand="Honda", price=330000))
            db.session.commit()
            created.append("Riders 250")

        # Skapa ett tomt SeasonTeam om saknas
        user = User.query.filter_by(username="test").first()
        if user and not SeasonTeam.query.filter_by(user_id=user.id).first():
            team = SeasonTeam(user_id=user.id, team_name="Team Test", total_points=0)
            db.session.add(team)
            db.session.flush()
            # lägg in 2+2 riders om finns
            r450 = Rider.query.filter_by(class_name="450cc").limit(2).all()
            r250 = Rider.query.filter_by(class_name="250cc").limit(2).all()
            for r in r450 + r250:
                db.session.add(SeasonTeamRider(season_team_id=team.id, rider_id=r.id))
            db.session.commit()
            created.append("SeasonTeam for test")

    if created:
        print("Seeded:", ", ".join(created))
    else:
        print("Minimal data already present.")

def simulate_for_comp(comp_name="Anaheim 1"):
    with app.app_context():
        user = User.query.filter_by(username="test").first()
        comp = Competition.query.filter_by(name=comp_name).first()
        if not (user and comp):
            print("Missing user 'test' or competition", comp_name)
            return

        # Hämta riders
        jett = Rider.query.filter_by(name="Jett Lawrence", class_name="450cc").first() or Rider.query.filter_by(class_name="450cc").first()
        sexton = Rider.query.filter_by(name="Chase Sexton", class_name="450cc").first() or Rider.query.filter_by(class_name="450cc").offset(1).first()
        deegan = Rider.query.filter_by(name="Haiden Deegan", class_name="250cc").first() or Rider.query.filter_by(class_name="250cc").first()
        shimoda = Rider.query.filter_by(name="Jo Shimoda", class_name="250cc").first() or Rider.query.filter_by(class_name="250cc").offset(1).first()

        if not all([jett, sexton, deegan, shimoda]):
            print("Not enough riders to simulate.")
            return

        # Rensa för tävlingen och användaren
        CompetitionResult.query.filter_by(competition_id=comp.id).delete()
        HoleshotResult.query.filter_by(competition_id=comp.id).delete()
        RacePick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        HoleshotPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        WildcardPick.query.filter_by(user_id=user.id, competition_id=comp.id).delete()
        CompetitionScore.query.filter_by(competition_id=comp.id).delete()
        db.session.commit()

        # Resultat
        db.session.add(CompetitionResult(competition_id=comp.id, rider_id=jett.id, position=1))
        db.session.add(CompetitionResult(competition_id=comp.id, rider_id=sexton.id, position=2))
        db.session.add(CompetitionResult(competition_id=comp.id, rider_id=deegan.id, position=1))
        db.session.add(CompetitionResult(competition_id=comp.id, rider_id=shimoda.id, position=2))
        db.session.add(HoleshotResult(competition_id=comp.id, rider_id=jett.id, class_name="450cc"))
        db.session.add(HoleshotResult(competition_id=comp.id, rider_id=deegan.id, class_name="250cc"))

        # Picks
        db.session.add(RacePick(user_id=user.id, competition_id=comp.id, rider_id=jett.id, predicted_position=1))
        db.session.add(RacePick(user_id=user.id, competition_id=comp.id, rider_id=deegan.id, predicted_position=1))
        db.session.add(HoleshotPick(user_id=user.id, competition_id=comp.id, rider_id=jett.id, class_name="450cc"))
        db.session.add(HoleshotPick(user_id=user.id, competition_id=comp.id, rider_id=deegan.id, class_name="250cc"))
        # Wildcard
        any450 = Rider.query.filter_by(class_name="450cc").first()
        if any450:
            db.session.add(WildcardPick(user_id=user.id, competition_id=comp.id, rider_id=any450.id, position=12))
            # se till att någon blev 12:a
            if not CompetitionResult.query.filter_by(competition_id=comp.id, position=12).first():
                db.session.add(CompetitionResult(competition_id=comp.id, rider_id=any450.id, position=12))

        db.session.commit()

        # Poäng
        calculate_scores(comp.id)
        print(f"Simulated and scored for competition '{comp.name}' (id {comp.id}).")

if __name__ == "__main__":
    ensure_minimal_data()
    # Standard: simulera för "Anaheim 1". Du kan skicka namn som argv:
    comp_name = sys.argv[1] if len(sys.argv) > 1 else "Anaheim 1"
    simulate_for_comp(comp_name)