from app import app, db, User, Rider, Competition, RacePick, CompetitionScore, CompetitionResult, SeasonTeam, SeasonTeamRider, League, LeagueMembership, HoleshotPick, HoleshotResult, WildcardPick, SimDate
from werkzeug.security import generate_password_hash
from datetime import datetime

def seed_data():
    # Använd app_context för att kunna interagera med databasen
    with app.app_context():
        # Rensa all data från alla tabeller i rätt ordning (pga Foreign Keys)
        print("🧹 Rensar databasen...")
        db.session.query(RacePick).delete()
        db.session.query(CompetitionScore).delete()
        db.session.query(CompetitionResult).delete()
        db.session.query(SeasonTeamRider).delete()
        db.session.query(LeagueMembership).delete()
        db.session.query(HoleshotPick).delete()
        db.session.query(HoleshotResult).delete()
        db.session.query(WildcardPick).delete()
        db.session.query(League).delete()
        db.session.query(SeasonTeam).delete()
        db.session.query(User).delete()
        db.session.query(Rider).delete()
        db.session.query(Competition).delete()
        db.session.query(SimDate).delete()
        db.session.commit()

        # --- Lägg in ny data ---

        # Användare
        print("👤 Skapar testanvändare…")
        test_user = User(username="test", password_hash=generate_password_hash("password"))
        db.session.add(test_user)
        db.session.commit() # Commit user to get an ID if needed elsewhere, good practice

        # Förare
        print("🏍 Laddar in den kompletta förarlistan...")
        riders_data = [
            # 450cc
            ("Aaron Plessinger", "450cc", 7, "KTM", "", 350000),
            ("Chase Sexton", "450cc", 4, "KTM", "", 420000),
            ("Christian Craig", "450cc", 28, "Husqvarna", "", 250000),
            ("Colt Nichols", "450cc", 45, "Beta", "", 250000),
            ("Cooper Webb", "450cc", 2, "Yamaha", "", 390000),
            ("Dean Wilson", "450cc", 15, "Beta", "", 250000),
            ("Dylan Ferrandis", "450cc", 14, "Honda", "", 300000),
            ("Eli Tomac", "450cc", 3, "Yamaha", "", 400000),
            ("Fredrik Noren", "450cc", 46, "Honda", "", 250000),
            ("Garrett Marchbanks", "450cc", 26, "Yamaha", "", 250000),
            ("Hunter Lawrence", "450cc", 96, "Honda", "", 420000),
            ("Jason Anderson", "450cc", 21, "Kawasaki", "", 350000),
            ("Jett Lawrence", "450cc", 18, "Honda", "", 450000),
            ("Joey Savatgy", "450cc", 17, "Triumph", "", 250000),
            ("Josh Hill", "450cc", 751, "Kawasaki", "", 250000),
            ("Justin Barcia", "450cc", 51, "GasGas", "", 320000),
            ("Justin Cooper", "450cc", 32, "Yamaha", "", 300000),
            ("Justin Hill", "450cc", 44, "KTM", "", 250000),
            ("Ken Roczen", "450cc", 94, "Suzuki", "", 380000),
            ("Kyle Chisholm", "450cc", 11, "Yamaha", "", 250000),
            ("Malcolm Stewart", "450cc", 27, "Husqvarna", "", 300000),

            # 250cc
            ("Cameron McAdoo", "250cc", 29, "Kawasaki", "", 250000),
            ("Chance Hymas", "250cc", 48, "Honda", "", 290000),
            ("Chris Blose", "250cc", 57, "Yamaha", "", 200000),
            ("Cullin Park", "250cc", 53, "Honda", "", 200000),
            ("Derek Kelley", "250cc", 41, "KTM", "", 200000),
            ("Enzo Lopes", "250cc", 50, "Yamaha", "", 200000),
            ("Haiden Deegan", "250cc", 38, "Yamaha", "", 350000),
            ("Hunter Yoder", "250cc", 85, "Suzuki", "", 200000),
            ("Jalek Swoll", "250cc", 33, "Triumph", "", 280000),
            ("Jo Shimoda", "250cc", 30, "Honda", "", 330000),
            ("Jordon Smith", "250cc", 31, "Yamaha", "", 250000),
            ("Julien Beaumer", "250cc", 929, "KTM", "", 200000),
            ("Levi Kitchen", "250cc", 47, "Kawasaki", "", 340000),
            ("Luke Clout", "250cc", 0, "Yamaha", "", 200000),
            ("Max Anstie", "250cc", 37, "Honda", "", 250000),
            ("Max Vohland", "250cc", 20, "Honda", "", 250000),
            ("Michael Mosiman", "250cc", 36, "Yamaha", "", 250000),
            ("Mitchell Oldenburg", "250cc", 40, "Honda", "", 200000),
            ("Nate Thrasher", "250cc", 57, "Yamaha", "", 300000),
            ("Phillip Nicoletti", "250cc", 34, "Yamaha", "", 200000),
            ("Pierce Brown", "250cc", 39, "GasGas", "", 270000),
            ("RJ Hampshire", "250cc", 24, "Husqvarna", "", 310000),
            ("Robbie Wageman", "250cc", 59, "Suzuki", "", 200000),
            ("Ryder DiFrancesco", "250cc", 35, "Kawasaki", "", 260000),
            ("Seth Hammaker", "250cc", 43, "Kawasaki", "", 250000),
            ("Tom Vialle", "250cc", 16, "KTM", "", 320000),
        ]
        rider_objects = [Rider(name=n, class_name=c, rider_number=rn, bike_brand=b, image_url=iu, price=p) for n,c,rn,b,iu,p in riders_data]
        db.session.bulk_save_objects(rider_objects)
        
        # Tävlingar
        print("📅 Skapar 2026 tävlingskalender…")
        competitions_data = [
            ("Anaheim 1","2026-01-03","SX",1.0,0),
            ("San Francisco","2026-01-10","SX",1.0,0),
            ("San Diego","2026-01-17","SX",1.0,0),
            ("Anaheim 2 (Triple Crown)","2026-01-24","SX",1.0,1),
            ("Detroit","2026-01-31","SX",1.0,0),
            ("Glendale (Triple Crown)","2026-02-07","SX",1.0,1),
            ("Arlington (Triple Crown)","2026-02-14","SX",1.0,1),
            ("Birmingham","2026-02-21","SX",1.0,0),
            ("Daytona","2026-02-28","SX",1.0,0),
            ("Indianapolis","2026-03-07","SX",1.0,0),
            ("Seattle","2026-03-14","SX",1.0,0),
            ("St. Louis","2026-03-21","SX",1.0,0),
            ("Foxborough","2026-04-04","SX",1.0,0),
            ("Nashville","2026-04-11","SX",1.0,0),
            ("Philadelphia","2026-04-25","SX",1.0,0),
            ("Denver","2026-05-02","SX",1.0,0),
            ("Salt Lake City","2026-05-09","SX",1.0,0),
            ("Pala (Fox Raceway)","2026-05-23","MX",1.0,0),
            ("Hangtown","2026-05-30","MX",1.0,0),
            ("Thunder Valley","2026-06-06","MX",1.0,0),
            ("High Point","2026-06-13","MX",1.0,0),
            ("Southwick","2026-06-27","MX",1.0,0),
            ("RedBud","2026-07-04","MX",1.0,0),
            ("Millville","2026-07-11","MX",1.0,0),
            ("Washougal","2026-07-25","MX",1.0,0),
            ("Unadilla","2026-08-08","MX",1.0,0),
            ("Budds Creek","2026-08-15","MX",1.0,0),
            ("Ironman","2026-08-22","MX",1.0,0),
            ("SMX Playoff 1","2026-09-05","SMX",1.5,0),
            ("SMX Playoff 2","2026-09-12","SMX",1.5,0),
            ("SMX Final","2026-09-19","SMX",2.0,0),
        ]
        comp_objects = [Competition(name=n, event_date=datetime.strptime(d, "%Y-%m-%d").date(), series=s, point_multiplier=pm, is_triple_crown=tc) for n,d,s,pm,tc in competitions_data]
        db.session.bulk_save_objects(comp_objects)

        db.session.commit()
        print("✅ Databasen har fyllts med startdata.")

if __name__ == '__main__':
    seed_data()