from app import app, db, User, Competition, Rider, RacePick, CompetitionResult, SeasonTeam, SeasonTeamRider, HoleshotPick, HoleshotResult, WildcardPick, CompetitionScore
from scoring import calculate_scores
from sqlalchemy import text

def run_simulation():
    # Använd app_context för att kunna interagera med databasen
    with app.app_context():
        # Rensa bara transaktionsdata, inte grunddata som förare/tävlingar
        print("🧹 Rensar gamla resultat och picks...")
        db.session.query(RacePick).delete()
        db.session.query(HoleshotPick).delete()
        db.session.query(CompetitionResult).delete()
        db.session.query(HoleshotResult).delete()
        db.session.query(CompetitionScore).delete()
        db.session.query(WildcardPick).delete()
        db.session.query(SeasonTeamRider).delete()
        db.session.query(SeasonTeam).delete()
        db.session.commit()

        # --- Hämta grunddata med SQLAlchemy ---
        print("👤 Hämtar testanvändare och tävling...")
        test_user = User.query.filter_by(username="test").first()
        a1 = Competition.query.filter_by(name="Anaheim 1").first()

        if not test_user or not a1:
            print("❌ Testanvändare eller Anaheim 1 saknas. Kör seed_db_2026.py först.")
            return

        print("🏍 Hämtar förare...")
        riders_to_find = ["Jett Lawrence", "Chase Sexton", "Haiden Deegan", "Jo Shimoda", "Ken Roczen", "Aaron Plessinger"]
        rider_objects = Rider.query.filter(Rider.name.in_(riders_to_find)).all()
        # Skapa en uppslagstabell från namn -> id
        rider_ids = {r.name: r.id for r in rider_objects}
        
        if len(rider_ids) != len(riders_to_find):
            print("❌ Alla förare för simuleringen kunde inte hittas i databasen.")
            return

        # --- Lägg in simulerad data ---
        print("🏆 Skapar ett simulerat säsongsteam...")
        new_team = SeasonTeam(user_id=test_user.id, team_name='Simulated Team', total_points=0)
        db.session.add(new_team)
        # Vi måste köra flush() för att få ett ID på new_team innan vi kan använda det
        db.session.flush()

        team_riders_to_add = [
            SeasonTeamRider(season_team_id=new_team.id, rider_id=rider_ids["Jett Lawrence"]),
            SeasonTeamRider(season_team_id=new_team.id, rider_id=rider_ids["Chase Sexton"]),
            SeasonTeamRider(season_team_id=new_team.id, rider_id=rider_ids["Haiden Deegan"]),
            SeasonTeamRider(season_team_id=new_team.id, rider_id=rider_ids["Jo Shimoda"])
        ]
        db.session.add_all(team_riders_to_add)

        print("📝 Lägger in simulerade picks för Anaheim 1...")
        picks_to_add = [
            RacePick(user_id=test_user.id, competition_id=a1.id, rider_id=rider_ids["Jett Lawrence"], predicted_position=1),
            RacePick(user_id=test_user.id, competition_id=a1.id, rider_id=rider_ids["Haiden Deegan"], predicted_position=1),
            HoleshotPick(user_id=test_user.id, competition_id=a1.id, rider_id=rider_ids["Chase Sexton"], class_name='450cc'),
            HoleshotPick(user_id=test_user.id, competition_id=a1.id, rider_id=rider_ids["Haiden Deegan"], class_name='250cc'),
            WildcardPick(user_id=test_user.id, competition_id=a1.id, rider_id=rider_ids["Aaron Plessinger"], position=12)
        ]
        db.session.add_all(picks_to_add)
        
        print("🏁 Lägger in simulerade resultat för Anaheim 1...")
        results_to_add = [
            CompetitionResult(competition_id=a1.id, rider_id=rider_ids["Jett Lawrence"], position=1),
            CompetitionResult(competition_id=a1.id, rider_id=rider_ids["Chase Sexton"], position=2),
            CompetitionResult(competition_id=a1.id, rider_id=rider_ids["Haiden Deegan"], position=1),
            CompetitionResult(competition_id=a1.id, rider_id=rider_ids["Jo Shimoda"], position=2),
            CompetitionResult(competition_id=a1.id, rider_id=rider_ids["Ken Roczen"], position=12),
            HoleshotResult(competition_id=a1.id, rider_id=rider_ids["Jett Lawrence"], class_name='450cc'),
            HoleshotResult(competition_id=a1.id, rider_id=rider_ids["Haiden Deegan"], class_name='250cc')
        ]
        db.session.add_all(results_to_add)
        
        # Spara all data vi lagt till hittills
        db.session.commit()

        # --- Kör poängberäkning ---
        print("⚙️ Beräknar poäng...")
        calculate_scores(a1.id)
        
        print(f"✅ Komplett simulering klar!")

if __name__ == "__main__":
    run_simulation()