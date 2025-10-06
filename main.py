import os
import random
import string
from datetime import date, datetime
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# -------------------------------------------------
# Flask app & config
# -------------------------------------------------
# Flask app & config
# -------------------------------------------------
app = Flask(__name__)

# Configuration from environment variables
app.secret_key = os.getenv('SECRET_KEY', 'din_hemliga_nyckel_har_change_in_production')

# Use in-memory database for Render deployment (filesystem is read-only)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default

# Uploads
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads", "leagues")
# Don't create instance_path on Render to avoid filesystem issues
if not os.getenv('RENDER'):
    os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Database
db = SQLAlchemy(app)

# Debug: Print database configuration
print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
print(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
print(f"Render: {os.getenv('RENDER', 'false')}")
print(f"Current working directory: {os.getcwd()}")
print(f"App instance path: {app.instance_path}")

# -------------------------------------------------
# Modeller
# -------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    season_team = db.relationship(
        "SeasonTeam", backref="user", uselist=False, cascade="all, delete-orphan"
    )


class Competition(db.Model):
    __tablename__ = "competitions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.Date)
    series = db.Column(db.String(10), nullable=False)
    point_multiplier = db.Column(db.Float, default=1.0)
    is_triple_crown = db.Column(db.Integer, default=0)
    coast_250 = db.Column(db.String(10), nullable=True)  # <-- lägg till

class Rider(db.Model):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column("class", db.String(10), nullable=False)
    rider_number = db.Column(db.Integer)
    bike_brand = db.Column(db.String(50))
    image_url = db.Column(db.String(200))
    price = db.Column(db.Integer, nullable=False)
    coast_250 = db.Column(db.String(10), nullable=True)  # <-- lägg till
    


class SeasonTeam(db.Model):
    __tablename__ = "season_teams"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
    team_name = db.Column(db.String(100), nullable=False)
    total_points = db.Column(db.Integer, default=0)
    riders = db.relationship(
        "SeasonTeamRider", backref="team", cascade="all, delete-orphan"
    )


class SeasonTeamRider(db.Model):
    __tablename__ = "season_team_riders"
    entry_id = db.Column(db.Integer, primary_key=True)
    season_team_id = db.Column(db.Integer, db.ForeignKey("season_teams.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))


class League(db.Model):
    __tablename__ = "leagues"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    image_url = db.Column(db.String(200))
    description = db.Column(db.String(255))  # NY: kort beskrivning (nullable)


class LeagueMembership(db.Model):
    __tablename__ = "league_memberships"
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey("leagues.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class RacePick(db.Model):
    __tablename__ = "race_picks"
    pick_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    predicted_position = db.Column(db.Integer)


class CompetitionScore(db.Model):
    __tablename__ = "competition_scores"
    score_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    total_points = db.Column(db.Integer)
class CompetitionRiderStatus(db.Model):
    __tablename__ = "competition_rider_status"
    id = db.Column(db.Integer, primary_key=True)

    # Tävling som statusen gäller
    competition_id = db.Column(
        db.Integer,
        db.ForeignKey("competitions.id"),
        nullable=False,
        index=True,
    )

    # Förare som statusen gäller
    rider_id = db.Column(
        db.Integer,
        db.ForeignKey("riders.id"),
        nullable=False,
        index=True,
    )

    # Status (börja med 'OUT', du kan utöka senare: 'PROB', 'DNS', osv.)
    status = db.Column(db.String(20), nullable=False, default="OUT")

    # Säkra att vi inte sparar dubletter för samma (tävling, förare)
    __table_args__ = (
        db.UniqueConstraint("competition_id", "rider_id", name="uq_comp_rider"),
    )

class CompetitionResult(db.Model):
    __tablename__ = "competition_results"
    result_id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    position = db.Column(db.Integer, nullable=False)


class HoleshotPick(db.Model):
    __tablename__ = "holeshot_picks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    class_name = db.Column("class", db.String(10))


class HoleshotResult(db.Model):
    __tablename__ = "holeshot_results"
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    class_name = db.Column("class", db.String(10))


class WildcardPick(db.Model):
    __tablename__ = "wildcard_picks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    position = db.Column(db.Integer)

class CompetitionImage(db.Model):
    __tablename__ = "competition_images"
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)  # ex: "trackmaps/2026/001_Rd03_Anaheim_Overview03.jpg"
    sort_order = db.Column(db.Integer, default=0)

    competition = db.relationship(
        "Competition",
        backref=db.backref("images", cascade="all, delete-orphan", lazy="dynamic")
    )

class SimDate(db.Model):
    __tablename__ = "sim_date"
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD format    

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_today():
    # Försök läsa simulerat datum från DB om det finns
    try:
        row = db.session.execute(db.text("SELECT value FROM sim_date LIMIT 1")).first()
        if row and row[0]:
            return datetime.strptime(row[0], "%Y-%m-%d").date()
    except Exception:
        pass
    return date.today()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

def generate_invite_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(length))
        if not League.query.filter_by(invite_code=code).first():
            return code

# -------------------------------------------------
# Auth
# -------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        print(f"Login attempt: username='{username}', password='{password}'")
        
        user = User.query.filter_by(username=username).first()
        print(f"User found: {user is not None}")
        
        if user:
            print(f"User ID: {user.id}, Username: {user.username}")
            password_check = check_password_hash(user.password_hash, password)
            print(f"Password check: {password_check}")
            
            if password_check:
                session["user_id"] = user.id
                session["username"] = user.username
                print("Login successful, redirecting...")
                return redirect(url_for("index"))
        
        print("Login failed")
        flash("Felaktigt användarnamn eller lösenord", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        if User.query.filter_by(username=username).first():
            flash("Användarnamnet är redan upptaget", "error")
        else:
            new_user = User(
                username=username,
                password_hash=generate_password_hash(request.form["password"]),
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Konto skapat! Du kan nu logga in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------------------------------
# Pages
# -------------------------------------------------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    uid = session["user_id"]
    today = get_today()

    # Ensure database is initialized
    try:
        # Check if tables exist, if not initialize
        if not db.engine.dialect.has_table(db.engine, 'competitions'):
            print("Tables missing, reinitializing database...")
            init_database()
    except Exception as e:
        print(f"Database check error: {e}")
        init_database()

    # Get competitions with error handling
    try:
        competitions = Competition.query.order_by(Competition.event_date).all()
    except Exception as e:
        print(f"Error getting competitions: {e}")
        competitions = []
    
    upcoming_race = next((c for c in competitions if c.event_date and c.event_date >= today), None)
    
    # Get season team with error handling
    try:
        my_team = SeasonTeam.query.filter_by(user_id=uid).first()
    except Exception as e:
        print(f"Error getting season team: {e}")
        my_team = None

    team_riders = []
    if my_team:
        try:
            rs = (
                db.session.query(Rider)
                .join(SeasonTeamRider, Rider.id == SeasonTeamRider.rider_id)
                .filter(SeasonTeamRider.season_team_id == my_team.id)
                .order_by(Rider.class_name.desc(), Rider.price.desc())
                .all()
            )
            team_riders = [
                {
                    "id": r.id,
                    "name": r.name,
                    "number": r.rider_number,
                    "brand": (r.bike_brand or "").lower(),
                    "class": r.class_name,
                    "image_url": r.image_url or None,   # <-- added
                }
                for r in rs
            ]
        except Exception as e:
            print(f"Error getting team riders: {e}")
            team_riders = []

    return render_template(
        "index.html",
        username=session["username"],
        upcoming_race=upcoming_race,
        upcoming_races=[c for c in competitions if c.event_date and c.event_date >= today],
        my_team=my_team,
        team_riders=team_riders,
    )






@app.route("/leagues")
def leagues_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    uid = session["user_id"]
    
    # Ensure database is initialized
    try:
        # Check if tables exist, if not initialize
        if not db.engine.dialect.has_table(db.engine, 'leagues'):
            print("Tables missing, reinitializing database...")
            init_database()
    except Exception as e:
        print(f"Database check error: {e}")
        init_database()
    
    # Get leagues with error handling
    try:
        my_leagues = League.query.join(LeagueMembership).filter(LeagueMembership.user_id == uid).all()
    except Exception as e:
        print(f"Error getting leagues: {e}")
        my_leagues = []
    
    return render_template("leagues.html", my_leagues=my_leagues, username=session["username"])


@app.route("/leagues/<int:league_id>")
def league_detail_page(league_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    league = League.query.get_or_404(league_id)
    is_member = LeagueMembership.query.filter_by(league_id=league_id, user_id=session["user_id"]).first()
    if not is_member:
        flash("Du är inte medlem i denna liga.", "error")
        return redirect(url_for("leagues_page"))

    members = (
        db.session.query(User.username)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id)
        .all()
    )

    member_user_ids = [m[0] for m in db.session.query(LeagueMembership.user_id).filter_by(league_id=league_id).all()]
    season_leaderboard = []
    if member_user_ids:
        season_leaderboard = (
            db.session.query(User.username, SeasonTeam.team_name, SeasonTeam.total_points)
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .filter(User.id.in_(member_user_ids))
            .order_by(SeasonTeam.total_points.desc().nullslast())
            .all()
        )

    competitions = Competition.query.order_by(Competition.event_date).all()

    return render_template(
        "league_detail.html",
        league=league,
        members=[type("Row", (), {"username": m.username}) for m in members],
        competitions=competitions,
        season_leaderboard=[
            {"username": row.username, "team_name": row.team_name, "total_points": row.total_points or 0}
            for row in season_leaderboard
        ],
    )


@app.route("/season_team")
def season_team_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    team = SeasonTeam.query.filter_by(user_id=session["user_id"]).first()
    riders = []
    if team:
        riders = (
            Rider.query.join(SeasonTeamRider, Rider.id == SeasonTeamRider.rider_id)
            .filter(SeasonTeamRider.season_team_id == team.id)
            .all()
        )
    return render_template("season_team.html", team=team, riders=riders)

@app.route("/season_team_builder")
def season_team_builder():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    try:
        all_riders = Rider.query.all()
        print(f"Found {len(all_riders)} riders for season team builder")
        
        # Convert riders to JSON-serializable format
        riders_data = []
        for rider in all_riders:
            riders_data.append({
                'id': rider.id,
                'name': rider.name,
                'class': rider.class_name,
                'rider_number': rider.rider_number,
                'bike_brand': rider.bike_brand,
                'image_url': rider.image_url,
                'price': rider.price,
                'coast_250': rider.coast_250
            })
        
        return render_template("season_team_builder.html", riders=riders_data)
    except Exception as e:
        print(f"Error in season_team_builder: {e}")
        return f"Error loading riders: {str(e)}", 500

@app.route("/create_season_team", methods=["POST"])
def create_season_team():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    try:
        data = request.get_json()
        team_name = data.get('team_name', 'Mitt Team')
        rider_ids = data.get('rider_ids', [])
        
        # Check if user already has a season team
        existing_team = SeasonTeam.query.filter_by(user_id=user_id).first()
        if existing_team:
            return jsonify({"success": False, "message": "Du har redan ett säsongsteam"})
        
        # Create new season team
        new_team = SeasonTeam(
            user_id=user_id,
            team_name=team_name,
            total_points=0
        )
        db.session.add(new_team)
        db.session.flush()  # Get the team ID
        
        # Add riders to team
        for rider_id in rider_ids:
            team_rider = SeasonTeamRider(
                season_team_id=new_team.id,
                rider_id=rider_id
            )
            db.session.add(team_rider)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Säsongsteam skapat!"})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating season team: {e}")
        return jsonify({"success": False, "message": f"Fel: {str(e)}"}), 500

@app.route("/my_scores")
def my_scores():
    if "user_id" not in session:
        return redirect(url_for("login"))
    uid = session["user_id"]

    rows = (
        db.session.query(
            Competition.id.label("competition_id"),
            Competition.name,
            Competition.series,
            Competition.event_date,
            CompetitionScore.total_points,
        )
        .join(CompetitionScore, Competition.id == CompetitionScore.competition_id)
        .filter(CompetitionScore.user_id == uid)
        .order_by(Competition.event_date.asc().nulls_last())
        .all()
    )

    total_points = sum((r.total_points or 0) for r in rows)
    scores = [
        {
            "competition_id": r.competition_id,
            "name": r.name,
            "series": r.series,
            "event_date": r.event_date.strftime("%Y-%m-%d") if r.event_date else "",
            "total_points": r.total_points or 0,
        }
        for r in rows
    ]

    return render_template("my_scores.html", scores=scores, total_points=total_points)


@app.route("/race_picks/<int:competition_id>")
def race_picks_page(competition_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    comp = Competition.query.get_or_404(competition_id)

    # 1) Hämta OUT-förare för detta race
    out_ids = set(
        rid
        for (rid,) in db.session.query(CompetitionRiderStatus.rider_id)
        .filter(
            CompetitionRiderStatus.competition_id == comp.id,
            CompetitionRiderStatus.status == "OUT",
        )
        .all()
    )

    # 2) Bygg listor (450 + 250 med coast-logik)
    # 450 – ingen coast-filtrering
    riders_450 = (
        Rider.query
        .filter_by(class_name="450cc")
        .order_by(Rider.rider_number)
        .all()
    )

    # 250 – coast-logik
    riders_250_query = Rider.query.filter_by(class_name="250cc")
    if comp.coast_250 == "both":
        # Showdown: tillåt east/west/both
        riders_250_query = riders_250_query.filter(
            (Rider.coast_250 == "east")
            | (Rider.coast_250 == "west")
            | (Rider.coast_250 == "both")
        )
    elif comp.coast_250 in ("east", "west"):
        # Vanligt SX: endast samma coast eller 'both'
        riders_250_query = riders_250_query.filter(
            (Rider.coast_250 == comp.coast_250) | (Rider.coast_250 == "both")
        )
    # Annars (None): visa alla 250
    riders_250 = riders_250_query.order_by(Rider.rider_number).all()

    # 3) Serialisering för JS (inkl is_out + image_url)
    def serialize_rider(r: Rider):
        return {
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand,
            "price": r.price,
            "is_out": (r.id in out_ids),
            "image_url": r.image_url,  # Viktigt för att kunna visa headshots i UI
            "coast_250": r.coast_250,  # För coast-filtrering
        }

    riders_450_json = [serialize_rider(r) for r in riders_450]
    riders_250_json = [serialize_rider(r) for r in riders_250]

    # 4) Placeholder för resultat/holeshot (om ej klart)
    actual_results = []
    holeshot_results = []

    # 5) Skicka out_ids till templaten för (OUT)/disabled
    return render_template(
        "race_picks.html",
        competition=comp,
        riders_450=riders_450,
        riders_250=riders_250,
        riders_450_json=riders_450_json,
        riders_250_json=riders_250_json,
        actual_results=actual_results,
        holeshot_results=holeshot_results,
        out_ids=list(out_ids),
    )










# -------------------------------------------------
# Leagues actions
# -------------------------------------------------
@app.post("/create_league")
def create_league():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        name = (request.form.get("league_name") or "").strip()
        if not name:
            flash("Du måste ange ett liganamn.", "error")
            return redirect(url_for("leagues_page"))

        code = generate_invite_code()
        image_url = None

        file = request.files.get("league_image")
        if file and file.filename and allowed_file(file.filename):
            try:
                fname = secure_filename(f"{code}_{file.filename}")
                path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                file.save(path)
                image_url = url_for("static", filename=f"uploads/leagues/{fname}")
                print(f"League image saved: {path}")
            except Exception as e:
                print(f"Error saving league image: {e}")
                # Continue without image if upload fails

        league = League(name=name, creator_id=session["user_id"], invite_code=code, image_url=image_url)
        db.session.add(league)
        db.session.flush()
        db.session.add(LeagueMembership(league_id=league.id, user_id=session["user_id"]))
        db.session.commit()
        
        print(f"League created successfully: {name} with code {code}")
        flash("Ligan skapades!", "success")
        return redirect(url_for("leagues_page"))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating league: {e}")
        flash(f"Fel vid skapande av liga: {str(e)}", "error")
        return redirect(url_for("leagues_page"))

@app.get("/debug_league")
def debug_league():
    """Debug league creation"""
    try:
        # Test database connection
        league_count = League.query.count()
        user_count = User.query.count()
        
        # Test file upload folder
        upload_folder = app.config["UPLOAD_FOLDER"]
        folder_exists = os.path.exists(upload_folder)
        
        return f"""
        <h1>League Debug Info</h1>
        <p>Leagues in database: {league_count}</p>
        <p>Users in database: {user_count}</p>
        <p>Upload folder: {upload_folder}</p>
        <p>Upload folder exists: {folder_exists}</p>
        <p>Current user: {session.get('username', 'Not logged in')}</p>
        <p>User ID: {session.get('user_id', 'None')}</p>
        """
    except Exception as e:
        return f"<h1>Debug Error</h1><p>{str(e)}</p>"

@app.get("/reset_database")
def reset_database():
    """Reset database - useful when database gets corrupted"""
    try:
        # Drop all tables
        db.drop_all()
        # Recreate all tables
        db.create_all()
        # Create test data
        create_test_data()
        return """
        <h1>Database Reset Successfully!</h1>
        <p>All tables have been recreated and test data has been added.</p>
        <p><a href="/">Go to Home</a></p>
        """
    except Exception as e:
        return f"<h1>Database Reset Error</h1><p>{str(e)}</p>"

@app.post("/join_league")
def join_league():
    if "user_id" not in session:
        return redirect(url_for("login"))
    code = (request.form.get("invite_code") or "").strip().upper()
    league = League.query.filter_by(invite_code=code).first()
    if not league:
        flash("Ogiltig inbjudningskod.", "error")
        return redirect(url_for("leagues_page"))
    exists = LeagueMembership.query.filter_by(league_id=league.id, user_id=session["user_id"]).first()
    if exists:
        flash("Du är redan med i denna liga.", "error")
        return redirect(url_for("leagues_page"))
    db.session.add(LeagueMembership(league_id=league.id, user_id=session["user_id"]))
    db.session.commit()
    flash("Du gick med i ligan!", "success")
    return redirect(url_for("league_detail_page", league_id=league.id))


@app.post("/leagues/<int:league_id>/leave")
def leave_league(league_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    league = League.query.get_or_404(league_id)
    if league.creator_id == session["user_id"]:
        flash("Skaparen kan inte lämna sin egen liga. Du kan radera ligan i stället.", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))
    mem = LeagueMembership.query.filter_by(league_id=league_id, user_id=session["user_id"]).first()
    if mem:
        db.session.delete(mem)
        db.session.commit()
        flash("Du har lämnat ligan.", "success")
    return redirect(url_for("leagues_page"))


@app.post("/leagues/<int:league_id>/delete")
def delete_league(league_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    league = League.query.get_or_404(league_id)
    if league.creator_id != session["user_id"]:
        flash("Endast skaparen kan radera ligan.", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))
    LeagueMembership.query.filter_by(league_id=league_id).delete()
    db.session.delete(league)
    db.session.commit()
    flash("Ligan är raderad.", "success")
    return redirect(url_for("leagues_page"))



@app.post("/save_season_team")
def save_season_team():
    if "user_id" not in session:
        return jsonify({"message": "not_logged_in"}), 401

    data = request.get_json(silent=True) or {}
    team_name = (data.get("team_name") or "").strip()
    team_list = data.get("team") or []

    if not team_name:
        return jsonify({"message": "Du måste ange teamnamn"}), 400
    if not isinstance(team_list, list) or len(team_list) != 4:
        return jsonify({"message": "Du måste välja exakt 4 förare"}), 400

    try:
        rider_ids = [int(x.get("id")) for x in team_list if x.get("id")]
    except Exception:
        return jsonify({"message": "Ogiltiga rider-id:n"}), 400
    if len(set(rider_ids)) != 4:
        return jsonify({"message": "Dubbla förare valda, välj fyra unika"}), 400

    riders = Rider.query.filter(Rider.id.in_(rider_ids)).all()
    if len(riders) != 4:
        return jsonify({"message": "Några förare hittades inte"}), 400

    c450 = sum(1 for r in riders if r.class_name == "450cc")
    c250 = sum(1 for r in riders if r.class_name == "250cc")
    if c450 != 2 or c250 != 2:
        return jsonify({"message": "Regel: 2 x 450cc och 2 x 250cc krävs"}), 400

    uid = session["user_id"]
    team = SeasonTeam.query.filter_by(user_id=uid).first()
    if not team:
        team = SeasonTeam(user_id=uid, team_name=team_name, total_points=0)
        db.session.add(team)
        db.session.flush()
    else:
        team.team_name = team_name
        SeasonTeamRider.query.filter_by(season_team_id=team.id).delete()

    for r in riders:
        db.session.add(SeasonTeamRider(season_team_id=team.id, rider_id=r.id))

    db.session.commit()
    return jsonify({"message": "Team sparat!"}), 200


# -------------------------------------------------
# Admin
# -------------------------------------------------
@app.route("/admin")
def admin_page():
    if session.get("username") != "test":
        return redirect(url_for("index"))
    competitions = Competition.query.order_by(Competition.event_date).all()
    riders_450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.rider_number).all()
    riders_250 = Rider.query.filter_by(class_name="250cc").order_by(Rider.rider_number).all()

    race_scores = []
    last_scored = (
        db.session.query(CompetitionScore.competition_id)
        .join(Competition, Competition.id == CompetitionScore.competition_id)
        .order_by(Competition.event_date.desc())
        .first()
    )
    if last_scored:
        last_comp_id = last_scored[0]
        race_scores = (
            db.session.query(User.username, CompetitionScore.total_points)
            .join(User, User.id == CompetitionScore.user_id)
            .filter(CompetitionScore.competition_id == last_comp_id)
            .order_by(CompetitionScore.total_points.desc())
            .all()
        )

    return render_template(
        "admin.html",
        competitions=competitions,
        riders_450=riders_450,
        riders_250=riders_250,
        race_scores=race_scores,
        today=get_today(),
    )


@app.get("/admin/get_results/<int:competition_id>")
def admin_get_results(competition_id):
    if session.get("username") != "test":
        return jsonify({"error": "unauthorized"}), 403

    results = (
        db.session.query(
            CompetitionResult.rider_id,
            CompetitionResult.position,
            Rider.class_name.label("class_name"),
        )
        .join(Rider, Rider.id == CompetitionResult.rider_id)
        .filter(CompetitionResult.competition_id == competition_id)
        .order_by(CompetitionResult.position.asc())
        .all()
    )

    holos = HoleshotResult.query.filter_by(competition_id=competition_id).all()

    return jsonify(
        {
            "top_results": [
                {"rider_id": r.rider_id, "position": r.position, "class": r.class_name}
                for r in results
            ],
            "holeshot_results": [
                {"rider_id": h.rider_id, "class": h.class_name} for h in holos
            ],
        }
    )


@app.post("/admin/submit_results")
def submit_results():
    if session.get("username") != "test":
        return redirect(url_for("login"))

    comp_id = request.form.get("competition_id", type=int)
    if not comp_id:
        flash("Du måste välja tävling.", "error")
        return redirect(url_for("admin_page"))

    CompetitionResult.query.filter_by(competition_id=comp_id).delete()
    HoleshotResult.query.filter_by(competition_id=comp_id).delete()

    hs_450 = request.form.get("holeshot_450", type=int)
    hs_250 = request.form.get("holeshot_250", type=int)
    if hs_450:
        db.session.add(HoleshotResult(competition_id=comp_id, rider_id=hs_450, class_name="450cc"))
    if hs_250:
        db.session.add(HoleshotResult(competition_id=comp_id, rider_id=hs_250, class_name="250cc"))

    positions_450 = request.form.getlist("positions_450[]", type=int)
    riders_450 = request.form.getlist("riders_450[]", type=int)
    positions_250 = request.form.getlist("positions_250[]", type=int)
    riders_250 = request.form.getlist("riders_250[]", type=int)

    # Validera att inga dubletter finns inom samma klass
    riders_450_filtered = [rid for rid in riders_450 if rid]
    riders_250_filtered = [rid for rid in riders_250 if rid]
    
    if len(riders_450_filtered) != len(set(riders_450_filtered)):
        flash("Du kan inte sätta samma 450cc-förare flera gånger.", "error")
        return redirect(url_for("admin_page"))
    
    if len(riders_250_filtered) != len(set(riders_250_filtered)):
        flash("Du kan inte sätta samma 250cc-förare flera gånger.", "error")
        return redirect(url_for("admin_page"))

    for pos, rid in zip(positions_450, riders_450):
        if rid:
            db.session.add(CompetitionResult(competition_id=comp_id, rider_id=rid, position=pos))
    for pos, rid in zip(positions_250, riders_250):
        if rid:
            db.session.add(CompetitionResult(competition_id=comp_id, rider_id=rid, position=pos))

    db.session.commit()
    calculate_scores(comp_id)

    flash("Resultat sparade och poäng beräknade!", "success")
    return redirect(url_for("admin_page"))


@app.post("/admin/simulate/<int:competition_id>")
def admin_simulate(competition_id):
    if session.get("username") != "test":
        return redirect(url_for("login"))

    comp = Competition.query.get_or_404(competition_id)
    user = User.query.filter_by(username="test").first()
    if not user:
        flash("Användaren 'test' saknas. Skapa den först.", "error")
        return redirect(url_for("admin_page"))

    def find_rider_by_name_or_any(name, cls):
        r = Rider.query.filter_by(name=name, class_name=cls).first()
        if not r:
            r = Rider.query.filter_by(class_name=cls).order_by(Rider.price.desc()).first()
        return r

    jett = find_rider_by_name_or_any("Jett Lawrence", "450cc")
    sexton = find_rider_by_name_or_any("Chase Sexton", "450cc")
    deegan = find_rider_by_name_or_any("Haiden Deegan", "250cc")
    shimoda = find_rider_by_name_or_any("Jo Shimoda", "250cc")

    if not (jett and sexton and deegan and shimoda):
        flash("Hittade inte tillräckligt med förare (450/250). Lägg in riders först.", "error")
        return redirect(url_for("admin_page"))

    CompetitionResult.query.filter_by(competition_id=competition_id).delete()
    HoleshotResult.query.filter_by(competition_id=competition_id).delete()
    RacePick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()
    HoleshotPick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()
    WildcardPick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()

    db.session.add(CompetitionResult(competition_id=competition_id, rider_id=jett.id, position=1))
    db.session.add(CompetitionResult(competition_id=competition_id, rider_id=sexton.id, position=2))
    db.session.add(CompetitionResult(competition_id=competition_id, rider_id=deegan.id, position=1))
    db.session.add(CompetitionResult(competition_id=competition_id, rider_id=shimoda.id, position=2))

    db.session.add(HoleshotResult(competition_id=competition_id, rider_id=jett.id, class_name="450cc"))
    db.session.add(HoleshotResult(competition_id=competition_id, rider_id=deegan.id, class_name="250cc"))

    db.session.add(RacePick(user_id=user.id, competition_id=competition_id, rider_id=jett.id, predicted_position=1))
    db.session.add(RacePick(user_id=user.id, competition_id=competition_id, rider_id=deegan.id, predicted_position=1))
    db.session.add(HoleshotPick(user_id=user.id, competition_id=competition_id, rider_id=jett.id, class_name="450cc"))
    db.session.add(HoleshotPick(user_id=user.id, competition_id=competition_id, rider_id=deegan.id, class_name="250cc"))

    any450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.price.desc()).first()
    if any450:
        db.session.add(WildcardPick(user_id=user.id, competition_id=competition_id, rider_id=any450.id, position=12))
        existing_pos12 = CompetitionResult.query.filter_by(competition_id=competition_id, position=12).first()
        if not existing_pos12:
            db.session.add(CompetitionResult(competition_id=competition_id, rider_id=any450.id, position=12))

    db.session.commit()
    calculate_scores(competition_id)

    flash(f"Simulerade resultat och picks har lagts in för {comp.name}. Poäng uträknade!", "success")
    return redirect(url_for("admin_page"))


@app.post("/admin/set_date")
def admin_set_date():
    if session.get("username") != "test":
        return redirect(url_for("login"))
    flash("Simulerat datum är inte implementerat i denna version.", "error")
    return redirect(url_for("admin_page"))

@app.post("/admin/set_sim_date")
def admin_set_sim_date():
    if session.get("username") != "test":
        return redirect(url_for("index"))
    sim = (request.form.get("sim_date") or "").strip()
    if not sim:
        flash("Du måste ange ett datum (YYYY-MM-DD).", "error")
        return redirect(url_for("admin_page"))
    try:
        # rensa och sätt nytt
        db.session.execute(db.text("DELETE FROM sim_date"))
        db.session.execute(db.text("INSERT INTO sim_date (value) VALUES (:v)"), {"v": sim})
        db.session.commit()
        flash(f"Simulerat datum satt till {sim}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Kunde inte sätta sim datum: {e}", "error")
    return redirect(url_for("admin_page"))


# -------------------------------------------------
# API helpers (för templates JS)
# -------------------------------------------------
@app.get("/get_season_leaderboard")
def get_season_leaderboard():
    # Enkel version: använd SeasonTeam.total_points direkt
    rows = (
        db.session.query(User.username, SeasonTeam.team_name, SeasonTeam.total_points)
        .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
        .order_by(SeasonTeam.total_points.desc().nullslast())
        .all()
    )
    
    # Lägg till rank och delta (enkel version)
    result = []
    for i, (username, team_name, total_points) in enumerate(rows, 1):
        result.append({
            "username": username,
            "team_name": team_name or None,
            "total_points": total_points or 0,
            "rank": i,
            "delta": 0  # TODO: implementera delta senare
        })
    
    return jsonify(result)


@app.get("/user/<string:username>")
def user_stats_page(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    # Lista alla tävlingar och poäng för användaren
    rows = (
        db.session.query(
            Competition.id.label("competition_id"),
            Competition.name,
            Competition.series,
            Competition.event_date,
            CompetitionScore.total_points,
        )
        .outerjoin(CompetitionScore, (Competition.id == CompetitionScore.competition_id) & (CompetitionScore.user_id == user.id))
        .order_by(Competition.event_date.asc().nulls_last())
        .all()
    )

    # Bygg stats
    cum = 0
    history = []
    best = {"name": None, "points": -1}
    for r in rows:
        pts = r.total_points or 0
        cum += pts
        history.append(
            {
                "competition_id": r.competition_id,
                "name": r.name,
                "date": r.event_date.strftime("%Y-%m-%d") if r.event_date else "",
                "points": pts,
                "cumulative": cum,
            }
        )
        if pts > best["points"]:
            best = {"name": r.name, "points": pts}

    avg = round(cum / max(1, sum(1 for h in history if h["points"] > 0)), 2)

    return render_template(
        "user_stats.html",
        username=user.username,
        team=SeasonTeam.query.filter_by(user_id=user.id).first(),
        total=cum,
        avg=avg,
        best=best,
        history=history,
    )

@app.get("/trackmaps")
def trackmaps_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    comps = (
        Competition.query
        .filter(Competition.series == "SX")
        .order_by(Competition.event_date.asc())
        .all()
    )
    return render_template("trackmaps.html", competitions=comps, username=session.get("username"))

@app.get("/trackmaps/<int:competition_id>")
def trackmaps_competition_page(competition_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    comp = Competition.query.get_or_404(competition_id)
    # hämta bilder sorterade
    images = comp.images.order_by(CompetitionImage.sort_order.asc()).all()
    return render_template(
        "trackmaps_single.html",
        competition=comp,
        images=images,
        username=session.get("username"),
    )
@app.get("/admin/get_out_status/<int:competition_id>")
def admin_get_out_status(competition_id):
    if session.get("username") != "test":
        return jsonify({"error": "unauthorized"}), 403

    # all riders
    riders = db.session.query(Rider).order_by(Rider.class_name.desc(), Rider.rider_number.asc()).all()

    # out set for this competition
    out_rows = (
        db.session.query(CompetitionRiderStatus.rider_id)
        .filter(
            CompetitionRiderStatus.competition_id == competition_id,
            CompetitionRiderStatus.status == "OUT",
        )
        .all()
    )
    out_ids = {rid for (rid,) in out_rows}

    result = [
        {
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand,
            "is_out": r.id in out_ids,
        }
        for r in riders
    ]
    return jsonify(result), 200




    # CLEAR (remove or flip to not OUT)
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({"ok": True, "message": "Rider cleared"}), 200

@app.post("/admin/set_out_status")
def admin_set_out_status():
    if session.get("username") != "test":
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json(force=True) or {}
    comp_id = data.get("competition_id")
    rider_id = data.get("rider_id")
    status = (data.get("status") or "").upper()  # "OUT" eller "CLEAR"

    try:
        comp_id = int(comp_id)
        rider_id = int(rider_id)
    except Exception:
        return jsonify({"error": "invalid_payload"}), 400

    # Validera att tävling och förare finns
    if not Competition.query.get(comp_id):
        return jsonify({"error": "competition_not_found"}), 404
    if not Rider.query.get(rider_id):
        return jsonify({"error": "rider_not_found"}), 404

    if status == "OUT":
        row = (
            CompetitionRiderStatus.query.filter_by(
                competition_id=comp_id, rider_id=rider_id
            ).first()
        )
        if not row:
            row = CompetitionRiderStatus(
                competition_id=comp_id, rider_id=rider_id, status="OUT"
            )
            db.session.add(row)
        else:
            row.status = "OUT"
        db.session.commit()
        return jsonify({"ok": True, "message": "Rider set OUT"}), 200

    # CLEAR: rensa alla rader för kombinationen (robust)
    CompetitionRiderStatus.query.filter_by(
        competition_id=comp_id, rider_id=rider_id
    ).delete()
    db.session.commit()
    return jsonify({"ok": True, "message": "Rider cleared"}), 200


@app.get("/season_team_build")
def season_team_build():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Hämta alla riders till buildern
    riders = (
        Rider.query
        .order_by(Rider.class_name.desc(), Rider.price.desc(), Rider.rider_number.asc())
        .all()
    )
    riders_payload = [
        {
            "id": r.id,
            "name": r.name,
            "class": r.class_name,      # buildern förväntar nyckeln "class"
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand,
            "price": r.price,
        }
        for r in riders
    ]

    # VIKTIGT: rendera BUILDERN här:
    return render_template(
        "season_team_builder.html",
        username=session.get("username"),
        riders=riders_payload,
    )




@app.get("/get_my_picks/<int:competition_id>")
def get_my_picks(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]
    picks = (
        RacePick.query.filter_by(user_id=uid, competition_id=competition_id)
        .order_by(RacePick.predicted_position)
        .all()
    )
    holos = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).all()
    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).first()

    return jsonify(
        {
            "top6_picks": [
                {
                    "rider_id": p.rider_id,
                    "predicted_position": p.predicted_position,
                    "class": Rider.query.get(p.rider_id).class_name if p.rider_id else "",
                }
                for p in picks
            ],
            "holeshot_picks": {
                "450cc": next((h.rider_id for h in holos if h.class_name == "450cc"), None),
                "250cc": next((h.rider_id for h in holos if h.class_name == "250cc"), None),
            },
            "wildcard_pick": wc.rider_id if wc else None,
            "wildcard_pos": wc.position if wc else None,
        }
    )


@app.post("/save_picks")
def save_picks():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    uid = session["user_id"]

    # 1) Hämta tävlingen
    try:
        comp_id = int(data.get("competition_id"))
    except Exception:
        return jsonify({"error": "invalid_competition_id"}), 400

    comp = Competition.query.get(comp_id)
    if not comp:
        return jsonify({"error": "competition_not_found"}), 404

    # 2) Hämta OUT‑förare för detta race (viktigt)
    out_ids = set(
    rid
    for (rid,) in db.session.query(CompetitionRiderStatus.rider_id)
    .filter(
        CompetitionRiderStatus.competition_id == comp.id,
        CompetitionRiderStatus.status == "OUT",
    )
    .all()
)

    # 3) Validera att inga dubletter finns i picks
    picks = data.get("picks", [])
    rider_ids = [int(p.get("rider_id")) for p in picks if p.get("rider_id")]
    if len(rider_ids) != len(set(rider_ids)):
        return jsonify({"error": "Du kan inte välja samma förare flera gånger"}), 400

    # 4) Rensa tidigare picks/holeshot för användaren i denna tävling
    RacePick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    HoleshotPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()

    # 5) Spara Top-6 picks
    for p in picks:
        try:
            pos = int(p.get("position"))
            rid = int(p.get("rider_id"))
        except Exception:
            continue

        rider = Rider.query.get(rid)
        if not rider:
            continue

        # 4a) Blockera OUT alltid
        if rider.id in out_ids:
            return jsonify({"error": "Förare är OUT för detta race"}), 400

        # 4b) Coast‑validering för 250cc
        if rider.class_name == "250cc" and comp.coast_250 in ("east","west"):
            # Tillåt endast exakt match eller 'both'
            if rider.coast_250 not in (comp.coast_250, "both"):
                return jsonify({"error":"250-förare matchar inte denna coast"}), 400
        # (för 'both' -> tillåt alla 250)

        db.session.add(
            RacePick(
                user_id=uid,
                competition_id=comp_id,
                rider_id=rid,
                predicted_position=pos
            )
        )

    # 5) Holeshot 450
    hs450 = data.get("holeshot_450")
    if hs450:
        try:
            rid = int(hs450)
            # (om du vill låsa 450-OUT, lägg samma OUT-koll här)
            if rid in out_ids:
                return jsonify({"error": "Förare är OUT för detta race"}), 400
            db.session.add(
                HoleshotPick(
                    user_id=uid,
                    competition_id=comp_id,
                    rider_id=rid,
                    class_name="450cc"
                )
            )
        except Exception:
            pass

    # 6) Holeshot 250
    hs250 = data.get("holeshot_250")
    if hs250:
        try:
            rid = int(hs250)
            rider = Rider.query.get(rid)

            # 6a) Blockera OUT
            if rider and rider.id in out_ids:
                return jsonify({"error": "Förare är OUT för detta race"}), 400

            # 6b) Coast‑validering för 250 holeshot
            if rider and comp.coast_250 in ("east","west"):
                if rider.coast_250 not in (comp.coast_250, "both"):
                    return jsonify({"error":"250-holeshot matchar inte denna coast"}), 400

            db.session.add(
                HoleshotPick(
                    user_id=uid,
                    competition_id=comp_id,
                    rider_id=rid,
                    class_name="250cc"
                )
            )
        except Exception:
            pass

    # 7) Wildcard – oförändrat (450 i ditt UI)
    wc_pick = data.get("wildcard_pick")
    wc_pos = data.get("wildcard_pos")
    existing_wc = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).first()
    if wc_pick and wc_pos:
        try:
            wc_pick_i = int(wc_pick)
            wc_pos_i = int(wc_pos)

            # Blockera OUT även för wildcard om du vill
            # (Wildcard enligt din UI är 450, men vi skyddar ändå)
            if wc_pick_i in out_ids:
                return jsonify({"error": "Förare är OUT för detta race"}), 400

            if not existing_wc:
                existing_wc = WildcardPick(user_id=uid, competition_id=comp_id)
                db.session.add(existing_wc)
            existing_wc.rider_id = wc_pick_i
            existing_wc.position = wc_pos_i
        except Exception:
            pass

    db.session.commit()
    return jsonify({"message":"Picks sparade"}), 200




@app.post("/lock_wildcard_pos")
def lock_wildcard_pos():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    data = request.get_json(force=True)
    comp_id = int(data.get("competition_id"))
    pos = int(data.get("position"))
    uid = session["user_id"]

    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).first()
    if not wc:
        wc = WildcardPick(user_id=uid, competition_id=comp_id, position=pos)
        db.session.add(wc)
    else:
        wc.position = pos
    db.session.commit()
    return jsonify({"status": "locked"}), 200


@app.get("/get_my_race_results/<int:competition_id>")
def get_my_race_results(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    uid = session["user_id"]

    actual = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    actual_by_rider = {r.rider_id: r for r in actual}
    picks = RacePick.query.filter_by(user_id=uid, competition_id=competition_id).all()

    breakdown = []
    total = 0

    for p in picks:
        act = actual_by_rider.get(p.rider_id)
        if not act:
            breakdown.append(f"❌ Pick rider_id={p.rider_id} hittades inte i resultat")
            continue
        if act.position == p.predicted_position:
            breakdown.append(f"✅ Perfekt: rider {p.rider_id} på pos {p.predicted_position} (+25)")
            total += 25
        elif act.position <= 6:
            breakdown.append(f"⚠️ Top6: rider {p.rider_id} var {act.position} (+5)")
            total += 5
        else:
            breakdown.append(f"❌ Miss: rider {p.rider_id} var {act.position}")

    holopicks = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).all()
    holos = HoleshotResult.query.filter_by(competition_id=competition_id).all()
    holo_by_class = {h.class_name: h for h in holos}
    for hp in holopicks:
        act = holo_by_class.get(hp.class_name)
        if act and act.rider_id == hp.rider_id:
            breakdown.append(f"✅ Holeshot {hp.class_name}: rätt (+3)")
            total += 3
        else:
            breakdown.append(f"❌ Holeshot {hp.class_name}: fel")

    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).first()
    if wc:
        target = next((r for r in actual if r.position == wc.position), None)
        if target and target.rider_id == wc.rider_id:
            breakdown.append("✅ Wildcard: rätt (+15)")
            total += 15
        else:
            breakdown.append("❌ Wildcard: fel")

    return jsonify({"breakdown": breakdown, "total": total})

# -------------------------------------------------
# Poängberäkning
# -------------------------------------------------
def calculate_scores(comp_id: int):
    users = User.query.all()
    actual_results = CompetitionResult.query.filter_by(competition_id=comp_id).all()
    actual_holeshots = HoleshotResult.query.filter_by(competition_id=comp_id).all()

    actual_results_dict = {res.rider_id: res for res in actual_results}
    actual_holeshots_dict = {hs.class_name: hs for hs in actual_holeshots}

    for user in users:
        total_points = 0

        picks = RacePick.query.filter_by(user_id=user.id, competition_id=comp_id).all()
        for pick in picks:
            actual_pos_for_pick = (
                actual_results_dict.get(pick.rider_id).position
                if pick.rider_id in actual_results_dict
                else None
            )
            if actual_pos_for_pick == pick.predicted_position:
                total_points += 25
            elif actual_pos_for_pick is not None and actual_pos_for_pick <= 6:
                total_points += 5

        holeshot_picks = HoleshotPick.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).all()
        for hp in holeshot_picks:
            actual_hs = actual_holeshots_dict.get(hp.class_name)
            if actual_hs and actual_hs.rider_id == hp.rider_id:
                total_points += 3

        wc_pick = WildcardPick.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).first()
        if wc_pick:
            actual_wc = next(
                (res for res in actual_results if res.position == wc_pick.position), None
            )
            if actual_wc and actual_wc.rider_id == wc_pick.rider_id:
                total_points += 15

        score_entry = CompetitionScore.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).first()
        if not score_entry:
            score_entry = CompetitionScore(user_id=user.id, competition_id=comp_id)
            db.session.add(score_entry)
        score_entry.total_points = total_points

    db.session.commit()

    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        all_user_scores = CompetitionScore.query.filter_by(user_id=team.user_id).all()
        total_season_points = sum(s.total_points for s in all_user_scores if s.total_points)
        team.total_points = total_season_points

    db.session.commit()
    print(f"✅ Poängberäkning klar för tävling ID: {comp_id}")

# -------------------------------------------------
# Felsökning: lista routes
# -------------------------------------------------
@app.get("/routes")
def list_routes():
    output = []
    for rule in app.url_map.iter_rules():
        methods = ",".join(sorted(rule.methods))
        output.append(f"{rule.endpoint:30s} {methods:20s} {rule.rule}")
    return "<pre>" + "\n".join(sorted(output)) + "</pre>"

@app.get("/create_user_now")
def create_user_now_route():
    """Create user immediately"""
    try:
        # Create test user
        existing_user = User.query.filter_by(username='test').first()
        if existing_user:
            return f"User 'test' already exists with ID {existing_user.id}"
        
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        
        db.session.add(test_user)
        db.session.commit()
        
        return f"""
        <h1>User Created!</h1>
        <p>Username: test</p>
        <p>Password: password</p>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/create_test2_user")
def create_test2_user_route():
    """Create test2 user"""
    try:
        # Create test2 user
        existing_user = User.query.filter_by(username='test2').first()
        if existing_user:
            return f"User 'test2' already exists with ID {existing_user.id}"
        
        test2_user = User(
            username='test2',
            password_hash=generate_password_hash('password')
        )
        
        db.session.add(test2_user)
        db.session.commit()
        
        return f"""
        <h1>User Created!</h1>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/fix_user_roles")
def fix_user_roles_route():
    """Fix user roles - test=admin, test2=normal user"""
    try:
        # Update test user (admin)
        test_user = User.query.filter_by(username='test').first()
        if test_user:
            test_user.password_hash = generate_password_hash('password')
            db.session.commit()
            test_msg = "Updated test user (admin) with password 'password'"
        else:
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            db.session.commit()
            test_msg = "Created test user (admin) with password 'password'"
        
        # Update test2 user (normal)
        test2_user = User.query.filter_by(username='test2').first()
        if test2_user:
            test2_user.password_hash = generate_password_hash('password')
            db.session.commit()
            test2_msg = "Updated test2 user (normal) with password 'password'"
        else:
            test2_user = User(
                username='test2',
                password_hash=generate_password_hash('password'),
                email='test2@example.com'
            )
            db.session.add(test2_user)
            db.session.commit()
            test2_msg = "Created test2 user (normal) with password 'password'"
        
        return f"""
        <h1>User Roles Fixed!</h1>
        <p><strong>Admin User:</strong></p>
        <p>Username: test</p>
        <p>Password: password</p>
        <p>Role: Admin (can access admin page)</p>
        <p>{test_msg}</p>
        <br>
        <p><strong>Normal User:</strong></p>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p>Role: Normal user</p>
        <p>{test2_msg}</p>
        <br>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/debug_users")
def debug_users_route():
    """Debug users - show all users and create missing ones"""
    try:
        # Show all existing users
        all_users = User.query.all()
        user_list = []
        for user in all_users:
            user_list.append(f"ID: {user.id}, Username: '{user.username}'")
        
        # Create test user if missing
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            db.session.commit()
            user_list.append("CREATED: test user")
        else:
            user_list.append("EXISTS: test user")
        
        # Create test2 user if missing
        test2_user = User.query.filter_by(username='test2').first()
        if not test2_user:
            test2_user = User(
                username='test2',
                password_hash=generate_password_hash('password'),
                email='test2@example.com'
            )
            db.session.add(test2_user)
            db.session.commit()
            user_list.append("CREATED: test2 user")
        else:
            user_list.append("EXISTS: test2 user")
        
        return f"""
        <h1>Debug Users</h1>
        <h2>All Users in Database:</h2>
        <ul>
        {''.join([f'<li>{user}</li>' for user in user_list])}
        </ul>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/force_create_users")
def force_create_users_route():
    """Force create users - delete and recreate"""
    try:
        # Delete existing users
        User.query.filter(User.username.in_(['test', 'test2'])).delete()
        db.session.commit()
        
        # Create test user (admin)
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test_user)
        
        # Create test2 user (normal)
        test2_user = User(
            username='test2',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test2_user)
        
        db.session.commit()
        
        # Verify creation
        created_test = User.query.filter_by(username='test').first()
        created_test2 = User.query.filter_by(username='test2').first()
        
        return f"""
        <h1>Users Force Created!</h1>
        <p><strong>Admin User:</strong></p>
        <p>Username: test</p>
        <p>Password: password</p>
        <p>ID: {created_test.id if created_test else 'ERROR'}</p>
        <br>
        <p><strong>Normal User:</strong></p>
        <p>Username: test2</p>
        <p>Password: password</p>
        <p>ID: {created_test2.id if created_test2 else 'ERROR'}</p>
        <br>
        <p><strong>Total users in database:</strong> {User.query.count()}</p>
        <br>
        <p><a href="/login">Go to Login</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/health")
def health_check():
    """Health check endpoint for Render"""
    try:
        # Test database connection
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.get("/fix_database")
def fix_database_route():
    """Fix database by creating all tables and data"""
    try:
        # Create all tables
        db.create_all()
        
        # Create test user
        existing_user = User.query.filter_by(username='test').first()
        if not existing_user:
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            db.session.commit()
        
        # Create competitions
        Competition.query.delete()
        competitions = [
            {'name': 'Anaheim 1', 'event_date': '2026-01-04', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'San Diego', 'event_date': '2026-01-11', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Anaheim 2', 'event_date': '2026-01-18', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Houston', 'event_date': '2026-01-25', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Tampa', 'event_date': '2026-02-01', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False)
            )
            db.session.add(comp)
        
        # Create riders
        Rider.query.delete()
        riders_450 = [
            {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 3},
            {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 2},
            {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 4},
            {'name': 'Aaron Plessinger', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 7},
            {'name': 'Jett Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 18},
            {'name': 'Kyle Chisholm', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 11},
            {'name': 'Shane McElrath', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 12},
            {'name': 'Dylan Ferrandis', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 14},
            {'name': 'Dean Wilson', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 15},
            {'name': 'Tom Vialle', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 16},
            {'name': 'Joey Savatgy', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 17},
            {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 21},
            {'name': 'Malcolm Stewart', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 27},
            {'name': 'Christian Craig', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 28},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Max Anstie', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 37},
            {'name': 'Haiden Deegan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 38},
            {'name': 'Pierce Brown', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 39},
            {'name': 'Dilan Schwartz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 40},
            {'name': 'Derek Kelley', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 41},
            {'name': 'Seth Hammaker', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 43},
            {'name': 'Justin Hill', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 44},
            {'name': 'Colt Nichols', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 45},
            {'name': 'Fredrik Noren', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 46},
            {'name': 'Levi Kitchen', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 47},
            {'name': 'Chance Hymas', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 48},
            {'name': 'Enzo Lopes', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 50},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Cullin Park', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 53},
            {'name': 'Mitchell Oldenburg', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 54},
            {'name': 'Nate Thrasher', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 57},
            {'name': 'Daxton Bennick', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 59},
            {'name': 'Robbie Wageman', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 59},
            {'name': 'Benny Bloss', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 60},
            {'name': 'Justin Starling', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 60},
            {'name': 'Austin Forkner', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 64},
            {'name': 'Vince Friese', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 64},
            {'name': 'Jerry Robin', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Stilez Robertson', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Joshua Cartwright', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 69},
            {'name': 'Hardy Munoz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 72},
            {'name': 'Ryder DiFrancesco', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 75},
            {'name': 'Mitchell Harrison', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 79},
            {'name': 'Cade Clason', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 81},
            {'name': 'Hunter Yoder', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 85},
            {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'rider_number': 94},
            {'name': 'Hunter Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 96},
            {'name': 'Anthony Rodriguez', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 100},
            {'name': 'Grant Harlan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 109},
            {'name': 'Jett Reynolds', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 124},
            {'name': 'Ryan Breece', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 200},
            {'name': 'Nick Romano', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 511},
            {'name': 'Julien Beaumer', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 929}
        ]
        
        riders_250 = [
            # West Coast 250cc riders
            {'name': 'Max Vohland', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 20, 'coast_250': 'west'},
            {'name': 'RJ Hampshire', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'rider_number': 24, 'coast_250': 'west'},
            {'name': 'Garrett Marchbanks', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 26, 'coast_250': 'west'},
            {'name': 'Cameron McAdoo', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 29, 'coast_250': 'west'},
            {'name': 'Jo Shimoda', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 30, 'coast_250': 'west'},
            {'name': 'Justin Cooper', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 32, 'coast_250': 'west'},
            {'name': 'Carson Mumford', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 34, 'coast_250': 'west'},
            {'name': 'Michael Mosiman', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 36, 'coast_250': 'west'},
            {'name': 'Haiden Deegan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 38, 'coast_250': 'west'},
            {'name': 'Pierce Brown', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 39, 'coast_250': 'west'},
            {'name': 'Dilan Schwartz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 40, 'coast_250': 'west'},
            {'name': 'Seth Hammaker', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 43, 'coast_250': 'west'},
            {'name': 'Levi Kitchen', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 47, 'coast_250': 'west'},
            {'name': 'Chance Hymas', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 48, 'coast_250': 'west'},
            {'name': 'Enzo Lopes', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 50, 'coast_250': 'west'},
            {'name': 'Cullin Park', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 53, 'coast_250': 'west'},
            
            # East Coast 250cc riders
            {'name': 'Ty Masterpool', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 29, 'coast_250': 'east'},
            {'name': 'Jordon Smith', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 31, 'coast_250': 'east'},
            {'name': 'Max Anstie', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 37, 'coast_250': 'east'},
            {'name': 'Derek Kelley', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 41, 'coast_250': 'east'},
            {'name': 'Justin Hill', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 44, 'coast_250': 'east'},
            {'name': 'Colt Nichols', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 45, 'coast_250': 'east'},
            {'name': 'Fredrik Noren', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 46, 'coast_250': 'east'},
            {'name': 'Mitchell Oldenburg', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 54, 'coast_250': 'east'},
            {'name': 'Nate Thrasher', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 57, 'coast_250': 'west'},
            {'name': 'Daxton Bennick', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 59, 'coast_250': 'east'},
            {'name': 'Robbie Wageman', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 59, 'coast_250': 'west'},
            {'name': 'Benny Bloss', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 60, 'coast_250': 'east'},
            {'name': 'Justin Starling', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 60, 'coast_250': 'east'},
            {'name': 'Austin Forkner', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 64, 'coast_250': 'west'},
            {'name': 'Vince Friese', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 64, 'coast_250': 'east'},
            {'name': 'Jerry Robin', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'east'},
            {'name': 'Stilez Robertson', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'west'},
            {'name': 'Joshua Cartwright', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 69, 'coast_250': 'east'},
            {'name': 'Hardy Munoz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 72, 'coast_250': 'west'},
            {'name': 'Ryder DiFrancesco', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 75, 'coast_250': 'west'},
            {'name': 'Mitchell Harrison', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 79, 'coast_250': 'east'},
            {'name': 'Cade Clason', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 81, 'coast_250': 'east'},
            {'name': 'Hunter Yoder', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 85, 'coast_250': 'west'},
            {'name': 'Ken Roczen', 'class_name': '250cc', 'bike_brand': 'Suzuki', 'rider_number': 94, 'coast_250': 'east'},
            {'name': 'Hunter Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 96, 'coast_250': 'east'},
            {'name': 'Anthony Rodriguez', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 100, 'coast_250': 'east'},
            {'name': 'Grant Harlan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 109, 'coast_250': 'east'},
            {'name': 'Jett Reynolds', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 124, 'coast_250': 'west'},
            {'name': 'Ryan Breece', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 200, 'coast_250': 'east'},
            {'name': 'Nick Romano', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 511, 'coast_250': 'east'},
            {'name': 'Julien Beaumer', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 929, 'coast_250': 'west'}
        ]
        
        all_riders = riders_450 + riders_250
        for rider_data in all_riders:
            rider = Rider(
                name=rider_data['name'],
                class_name=rider_data['class_name'],
                rider_number=rider_data.get('rider_number'),
                bike_brand=rider_data['bike_brand'],
                price=rider_data.get('price', 50),  # Default price if not specified
                image_url=rider_data.get('image_url', f"riders/{rider_data['rider_number']}_{rider_data['name'].lower().replace(' ', '_')}.png"),
                coast_250=rider_data.get('coast_250')
            )
            db.session.add(rider)
        
        # Create default sim_date
        SimDate.query.delete()
        default_sim_date = SimDate(value='2025-10-06')
        db.session.add(default_sim_date)
        
        db.session.commit()
        
        return f"""
        <h1>Database Fixed!</h1>
        <p>Created all tables and data successfully!</p>
        <p><strong>Competitions:</strong> {len(competitions)}</p>
        <p><strong>Riders:</strong> {len(all_riders)}</p>
        <p><strong>Sim Date:</strong> 2025-10-06</p>
        <p><a href="/admin">Go to Admin</a></p>
        """
    except Exception as e:
        return f"<h1>Error:</h1><p>{str(e)}</p>"

@app.get("/create_test_user")
def create_test_user_route():
    """Create test user and all data via web route"""
    # Create test user
    existing_user = User.query.filter_by(username='test').first()
    if not existing_user:
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test_user)
        db.session.commit()
    
    # Create competitions if they don't exist
    if Competition.query.count() == 0:
        competitions = [
            {'name': 'Anaheim 1', 'event_date': '2026-01-04', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'San Diego', 'event_date': '2026-01-11', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Anaheim 2', 'event_date': '2026-01-18', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Houston', 'event_date': '2026-01-25', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Tampa', 'event_date': '2026-02-01', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False)
            )
            db.session.add(comp)
        db.session.commit()
    
    # Create riders if they don't exist
    if Rider.query.count() == 0:
        riders_450 = [
            {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 3},
            {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 2},
            {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 4},
            {'name': 'Aaron Plessinger', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 7},
            {'name': 'Jett Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 18},
            {'name': 'Kyle Chisholm', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 11},
            {'name': 'Shane McElrath', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 12},
            {'name': 'Dylan Ferrandis', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 14},
            {'name': 'Dean Wilson', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 15},
            {'name': 'Tom Vialle', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 16},
            {'name': 'Joey Savatgy', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 17},
            {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 21},
            {'name': 'Malcolm Stewart', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 27},
            {'name': 'Christian Craig', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 28},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Max Anstie', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 37},
            {'name': 'Haiden Deegan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 38},
            {'name': 'Pierce Brown', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 39},
            {'name': 'Dilan Schwartz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 40},
            {'name': 'Derek Kelley', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 41},
            {'name': 'Seth Hammaker', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 43},
            {'name': 'Justin Hill', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 44},
            {'name': 'Colt Nichols', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 45},
            {'name': 'Fredrik Noren', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 46},
            {'name': 'Levi Kitchen', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 47},
            {'name': 'Chance Hymas', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 48},
            {'name': 'Enzo Lopes', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 50},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
            {'name': 'Cullin Park', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 53},
            {'name': 'Mitchell Oldenburg', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 54},
            {'name': 'Nate Thrasher', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 57},
            {'name': 'Daxton Bennick', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 59},
            {'name': 'Robbie Wageman', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 59},
            {'name': 'Benny Bloss', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 60},
            {'name': 'Justin Starling', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 60},
            {'name': 'Austin Forkner', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 64},
            {'name': 'Vince Friese', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 64},
            {'name': 'Jerry Robin', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Stilez Robertson', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
            {'name': 'Joshua Cartwright', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 69},
            {'name': 'Hardy Munoz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 72},
            {'name': 'Ryder DiFrancesco', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 75},
            {'name': 'Mitchell Harrison', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 79},
            {'name': 'Cade Clason', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 81},
            {'name': 'Hunter Yoder', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 85},
            {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'rider_number': 94},
            {'name': 'Hunter Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 96},
            {'name': 'Anthony Rodriguez', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 100},
            {'name': 'Grant Harlan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 109},
            {'name': 'Jett Reynolds', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 124},
            {'name': 'Ryan Breece', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 200},
            {'name': 'Nick Romano', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 511},
            {'name': 'Julien Beaumer', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 929}
        ]
        
        riders_250 = [
            # West Coast 250cc riders
            {'name': 'Max Vohland', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 20, 'coast_250': 'west'},
            {'name': 'RJ Hampshire', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'rider_number': 24, 'coast_250': 'west'},
            {'name': 'Garrett Marchbanks', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 26, 'coast_250': 'west'},
            {'name': 'Cameron McAdoo', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 29, 'coast_250': 'west'},
            {'name': 'Jo Shimoda', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 30, 'coast_250': 'west'},
            {'name': 'Justin Cooper', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 32, 'coast_250': 'west'},
            {'name': 'Carson Mumford', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 34, 'coast_250': 'west'},
            {'name': 'Michael Mosiman', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 36, 'coast_250': 'west'},
            {'name': 'Haiden Deegan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 38, 'coast_250': 'west'},
            {'name': 'Pierce Brown', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 39, 'coast_250': 'west'},
            {'name': 'Dilan Schwartz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 40, 'coast_250': 'west'},
            {'name': 'Seth Hammaker', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 43, 'coast_250': 'west'},
            {'name': 'Levi Kitchen', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 47, 'coast_250': 'west'},
            {'name': 'Chance Hymas', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 48, 'coast_250': 'west'},
            {'name': 'Enzo Lopes', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 50, 'coast_250': 'west'},
            {'name': 'Cullin Park', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 53, 'coast_250': 'west'},
            
            # East Coast 250cc riders
            {'name': 'Ty Masterpool', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 29, 'coast_250': 'east'},
            {'name': 'Jordon Smith', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 31, 'coast_250': 'east'},
            {'name': 'Max Anstie', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 37, 'coast_250': 'east'},
            {'name': 'Derek Kelley', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 41, 'coast_250': 'east'},
            {'name': 'Justin Hill', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 44, 'coast_250': 'east'},
            {'name': 'Colt Nichols', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 45, 'coast_250': 'east'},
            {'name': 'Fredrik Noren', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 46, 'coast_250': 'east'},
            {'name': 'Mitchell Oldenburg', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 54, 'coast_250': 'east'},
            {'name': 'Nate Thrasher', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 57, 'coast_250': 'west'},
            {'name': 'Daxton Bennick', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 59, 'coast_250': 'east'},
            {'name': 'Robbie Wageman', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 59, 'coast_250': 'west'},
            {'name': 'Benny Bloss', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 60, 'coast_250': 'east'},
            {'name': 'Justin Starling', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 60, 'coast_250': 'east'},
            {'name': 'Austin Forkner', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 64, 'coast_250': 'west'},
            {'name': 'Vince Friese', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 64, 'coast_250': 'east'},
            {'name': 'Jerry Robin', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'east'},
            {'name': 'Stilez Robertson', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'west'},
            {'name': 'Joshua Cartwright', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 69, 'coast_250': 'east'},
            {'name': 'Hardy Munoz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 72, 'coast_250': 'west'},
            {'name': 'Ryder DiFrancesco', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 75, 'coast_250': 'west'},
            {'name': 'Mitchell Harrison', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 79, 'coast_250': 'east'},
            {'name': 'Cade Clason', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 81, 'coast_250': 'east'},
            {'name': 'Hunter Yoder', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 85, 'coast_250': 'west'},
            {'name': 'Ken Roczen', 'class_name': '250cc', 'bike_brand': 'Suzuki', 'rider_number': 94, 'coast_250': 'east'},
            {'name': 'Hunter Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 96, 'coast_250': 'east'},
            {'name': 'Anthony Rodriguez', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 100, 'coast_250': 'east'},
            {'name': 'Grant Harlan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 109, 'coast_250': 'east'},
            {'name': 'Jett Reynolds', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 124, 'coast_250': 'west'},
            {'name': 'Ryan Breece', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 200, 'coast_250': 'east'},
            {'name': 'Nick Romano', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 511, 'coast_250': 'east'},
            {'name': 'Julien Beaumer', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 929, 'coast_250': 'west'}
        ]
        
        all_riders = riders_450 + riders_250
        for rider_data in all_riders:
            rider = Rider(
                name=rider_data['name'],
                class_name=rider_data['class_name'],
                rider_number=rider_data.get('rider_number'),
                bike_brand=rider_data['bike_brand'],
                price=rider_data.get('price', 50),  # Default price if not specified
                image_url=rider_data.get('image_url', f"riders/{rider_data['rider_number']}_{rider_data['name'].lower().replace(' ', '_')}.png"),
                coast_250=rider_data.get('coast_250')
            )
            db.session.add(rider)
        db.session.commit()
    
    # Count what we have
    comp_count = Competition.query.count()
    rider_count = Rider.query.count()
    user_count = User.query.count()
    
    return f"""
    <h1>Data Created!</h1>
    <p><strong>Users:</strong> {user_count}</p>
    <p><strong>Competitions:</strong> {comp_count}</p>
    <p><strong>Riders:</strong> {rider_count}</p>
    <p><a href="/admin">Go to Admin</a></p>
    """

@app.get("/check_data")
def check_data_route():
    """Check what data exists in database"""
    users = User.query.all()
    competitions = Competition.query.all()
    riders = Rider.query.all()
    
    result = f"""
    <h1>Database Status</h1>
    <p><strong>Users:</strong> {len(users)}</p>
    <p><strong>Competitions:</strong> {len(competitions)}</p>
    <p><strong>Riders:</strong> {len(riders)}</p>
    
    <h2>Competitions:</h2>
    <ul>
    """
    
    for comp in competitions:
        result += f"<li>{comp.name} ({comp.event_date})</li>"
    
    result += "</ul>"
    
    riders_450 = [r for r in riders if r.class_name == '450cc']
    riders_250 = [r for r in riders if r.class_name == '250cc']
    
    result += f"""
    <h2>Riders:</h2>
    <p><strong>450cc:</strong> {len(riders_450)}</p>
    <p><strong>250cc:</strong> {len(riders_250)}</p>
    """
    
    return result

@app.get("/reset_database")
def reset_database_route():
    """Reset database - drop all tables and recreate"""
    try:
        with app.app_context():
            print("Dropping all tables...")
            db.drop_all()
            print("All tables dropped")
            
            print("Recreating database...")
            db.create_all()
            print("Database tables recreated")
            
            print("Creating test data...")
            create_test_data()
            print("Test data created")
            
            return f"""
            <h1>Database Reset Complete!</h1>
            <p>All tables have been dropped and recreated with fresh data.</p>
            <p><a href="/">Go to Home</a></p>
            <p><a href="/admin">Go to Admin</a></p>
            """
    except Exception as e:
        return f"""
        <h1>Database Reset Failed!</h1>
        <p>Error: {e}</p>
        <p><a href="/">Go to Home</a></p>
        """

@app.get("/force_create_data")
def force_create_data_route():
    """Force create all data"""
    # Clear existing data
    Competition.query.delete()
    Rider.query.delete()
    db.session.commit()
    
    # Create competitions
    competitions = [
        # Western Regional 250SX Championship
        {'name': 'Anaheim 1', 'event_date': '2026-01-10', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'San Diego', 'event_date': '2026-01-17', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Anaheim 2', 'event_date': '2026-01-24', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Houston', 'event_date': '2026-01-31', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
        {'name': 'Glendale', 'event_date': '2026-02-07', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Seattle', 'event_date': '2026-02-14', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        
        # Eastern Regional 250SX Championship
        {'name': 'Arlington', 'event_date': '2026-02-21', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
        {'name': 'Daytona', 'event_date': '2026-02-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Indianapolis', 'event_date': '2026-03-07', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Birmingham', 'event_date': '2026-03-21', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
        {'name': 'Detroit', 'event_date': '2026-03-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'St. Louis', 'event_date': '2026-04-04', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Nashville', 'event_date': '2026-04-11', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Cleveland', 'event_date': '2026-04-18', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Philadelphia', 'event_date': '2026-04-25', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Denver', 'event_date': '2026-05-02', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
        {'name': 'Salt Lake City', 'event_date': '2026-05-09', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.5}
    ]
    
    for comp_data in competitions:
        comp = Competition(
            name=comp_data['name'],
            event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
            coast_250=comp_data['coast_250'],
            series=comp_data['series'],
            point_multiplier=comp_data['point_multiplier']
        )
        db.session.add(comp)
    
    # Create riders
    riders_450 = [
        {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 3},
        {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 2},
        {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 4},
        {'name': 'Aaron Plessinger', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 7},
        {'name': 'Kyle Chisholm', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 11},
        {'name': 'Shane McElrath', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 12},
        {'name': 'Dylan Ferrandis', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 14},
        {'name': 'Dean Wilson', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 15},
        {'name': 'Tom Vialle', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 16},
        {'name': 'Joey Savatgy', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 17},
        {'name': 'Max Vohland', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 20},
        {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 21},
        {'name': 'RJ Hampshire', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 24},
        {'name': 'Garrett Marchbanks', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 26},
        {'name': 'Malcolm Stewart', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 27},
        {'name': 'Christian Craig', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'rider_number': 28},
        {'name': 'Cameron McAdoo', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 29},
        {'name': 'Ty Masterpool', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 29},
        {'name': 'Jo Shimoda', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 30},
        {'name': 'Jordon Smith', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 31},
        {'name': 'Justin Cooper', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 32},
        {'name': 'Carson Mumford', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 34},
        {'name': 'Michael Mosiman', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 36},
        {'name': 'Max Anstie', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 37},
        {'name': 'Haiden Deegan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 38},
        {'name': 'Pierce Brown', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 39},
        {'name': 'Dilan Schwartz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 40},
        {'name': 'Derek Kelley', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 41},
        {'name': 'Seth Hammaker', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 43},
        {'name': 'Justin Hill', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 44},
        {'name': 'Colt Nichols', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 45},
        {'name': 'Fredrik Noren', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 46},
        {'name': 'Levi Kitchen', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 47},
        {'name': 'Chance Hymas', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 48},
        {'name': 'Enzo Lopes', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 50},
        {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 51},
        {'name': 'Cullin Park', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 53},
        {'name': 'Mitchell Oldenburg', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 54},
        {'name': 'Nate Thrasher', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 57},
        {'name': 'Daxton Bennick', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 59},
        {'name': 'Robbie Wageman', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 59},
        {'name': 'Benny Bloss', 'class_name': '450cc', 'bike_brand': 'Beta', 'rider_number': 60},
        {'name': 'Justin Starling', 'class_name': '450cc', 'bike_brand': 'GasGas', 'rider_number': 60},
        {'name': 'Austin Forkner', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 64},
        {'name': 'Vince Friese', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 64},
        {'name': 'Jerry Robin', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
        {'name': 'Stilez Robertson', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 67},
        {'name': 'Joshua Cartwright', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 69},
        {'name': 'Hardy Munoz', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 72},
        {'name': 'Ryder DiFrancesco', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'rider_number': 75},
        {'name': 'Mitchell Harrison', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 79},
        {'name': 'Cade Clason', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 81},
        {'name': 'Hunter Yoder', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 85},
        {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'rider_number': 94},
        {'name': 'Hunter Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 96},
        {'name': 'Anthony Rodriguez', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 100},
        {'name': 'Grant Harlan', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 109},
        {'name': 'Jett Reynolds', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 124},
        {'name': 'Ryan Breece', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 200},
        {'name': 'Nick Romano', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 511},
        {'name': 'Julien Beaumer', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 929}
    ]
    
    riders_250 = [
        # West Coast 250cc riders
        {'name': 'Max Vohland', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 20, 'coast_250': 'west'},
        {'name': 'RJ Hampshire', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'rider_number': 24, 'coast_250': 'west'},
        {'name': 'Garrett Marchbanks', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 26, 'coast_250': 'west'},
        {'name': 'Cameron McAdoo', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 29, 'coast_250': 'west'},
        {'name': 'Jo Shimoda', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 30, 'coast_250': 'west'},
        {'name': 'Justin Cooper', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 32, 'coast_250': 'west'},
        {'name': 'Carson Mumford', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 34, 'coast_250': 'west'},
        {'name': 'Michael Mosiman', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 36, 'coast_250': 'west'},
        {'name': 'Haiden Deegan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 38, 'coast_250': 'west'},
        {'name': 'Pierce Brown', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 39, 'coast_250': 'west'},
        {'name': 'Dilan Schwartz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 40, 'coast_250': 'west'},
        {'name': 'Seth Hammaker', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 43, 'coast_250': 'west'},
        {'name': 'Levi Kitchen', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 47, 'coast_250': 'west'},
        {'name': 'Chance Hymas', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 48, 'coast_250': 'west'},
        {'name': 'Enzo Lopes', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 50, 'coast_250': 'west'},
        {'name': 'Cullin Park', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 53, 'coast_250': 'west'},
        
        # East Coast 250cc riders
        {'name': 'Ty Masterpool', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 29, 'coast_250': 'east'},
        {'name': 'Jordon Smith', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 31, 'coast_250': 'east'},
        {'name': 'Max Anstie', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 37, 'coast_250': 'east'},
        {'name': 'Derek Kelley', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 41, 'coast_250': 'east'},
        {'name': 'Justin Hill', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 44, 'coast_250': 'east'},
        {'name': 'Colt Nichols', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 45, 'coast_250': 'east'},
        {'name': 'Fredrik Noren', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 46, 'coast_250': 'east'},
        {'name': 'Mitchell Oldenburg', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 54, 'coast_250': 'east'},
        {'name': 'Nate Thrasher', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 57, 'coast_250': 'west'},
        {'name': 'Daxton Bennick', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 59, 'coast_250': 'east'},
        {'name': 'Robbie Wageman', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 59, 'coast_250': 'west'},
        {'name': 'Benny Bloss', 'class_name': '250cc', 'bike_brand': 'Beta', 'rider_number': 60, 'coast_250': 'east'},
        {'name': 'Justin Starling', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 60, 'coast_250': 'east'},
        {'name': 'Austin Forkner', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 64, 'coast_250': 'east'},
        {'name': 'Vince Friese', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 64, 'coast_250': 'east'},
        {'name': 'Jerry Robin', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'east'},
        {'name': 'Stilez Robertson', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 67, 'coast_250': 'west'},
        {'name': 'Joshua Cartwright', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 69, 'coast_250': 'east'},
        {'name': 'Hardy Munoz', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 72, 'coast_250': 'west'},
        {'name': 'Ryder DiFrancesco', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 75, 'coast_250': 'west'},
        {'name': 'Mitchell Harrison', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 79, 'coast_250': 'east'},
        {'name': 'Cade Clason', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 81, 'coast_250': 'east'},
        {'name': 'Hunter Yoder', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 85, 'coast_250': 'east'},
        {'name': 'Ken Roczen', 'class_name': '250cc', 'bike_brand': 'Suzuki', 'rider_number': 94, 'coast_250': 'east'},
        {'name': 'Hunter Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 96, 'coast_250': 'east'},
        {'name': 'Anthony Rodriguez', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 100, 'coast_250': 'east'},
        {'name': 'Grant Harlan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 109, 'coast_250': 'east'},
        {'name': 'Jett Reynolds', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 124, 'coast_250': 'west'},
        {'name': 'Ryan Breece', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 200, 'coast_250': 'east'},
        {'name': 'Nick Romano', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 511, 'coast_250': 'west'},
        {'name': 'Julien Beaumer', 'class_name': '250cc', 'bike_brand': 'KTM', 'rider_number': 929, 'coast_250': 'west'}
    ]
    
    all_riders = riders_450 + riders_250
    for rider_data in all_riders:
        rider = Rider(
            name=rider_data['name'],
            class_name=rider_data['class_name'],
            rider_number=rider_data.get('rider_number'),
            bike_brand=rider_data['bike_brand'],
            price=rider_data.get('price', 50),  # Default price if not specified
            image_url=rider_data.get('image_url', f"riders/{rider_data['rider_number']}_{rider_data['name'].lower().replace(' ', '_')}.png"),
            coast_250=rider_data.get('coast_250')
        )
        db.session.add(rider)
    
    db.session.commit()
    
    return f"""
    <h1>Data Created!</h1>
    <p>Created {len(competitions)} competitions and {len(all_riders)} riders</p>
    <p><a href="/admin">Go to Admin</a></p>
    <p><a href="/check_data">Check Data</a></p>
    """

# -------------------------------------------------
# Main
# -------------------------------------------------
def load_smx_2026_riders():
    """Load rider data from SMX 2026 CSV file"""
    try:
        import csv
        riders = []
        
        print("DEBUG: Starting to load SMX 2026 riders...")
        
        # Check if file exists
        import os
        file_path = 'data/smx_2026_riders_numbers_best_effort.csv'
        if not os.path.exists(file_path):
            print(f"DEBUG: File not found at {file_path}")
            return []
        
        print(f"DEBUG: File exists at {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as file:
            # Read all lines first to debug
            lines = file.readlines()
            print(f"DEBUG: File has {len(lines)} lines")
            
            # Reset file pointer
            file.seek(0)
            
            reader = csv.DictReader(file, delimiter='|')
            total_rows = 0
            skipped_rows = 0
            
            # Debug: Print column names
            print(f"DEBUG: Column names: {reader.fieldnames}")
            
            for row in reader:
                total_rows += 1
                
                # Debug first few rows
                if total_rows <= 5:
                    print(f"DEBUG: Row {total_rows}: Förare='{row.get('Förare')}', Klass='{row.get('Klass (best-effort)')}'")
                    print(f"DEBUG: Full row keys: {list(row.keys())}")
                    print(f"DEBUG: Full row values: {list(row.values())}")
                
                # Skip empty rows or rows with missing essential data
                if not row.get('Förare') or not row.get('Klass (best-effort)') or row.get('Förare').strip() == '' or row.get('Klass (best-effort)').strip() == '':
                    skipped_rows += 1
                    if total_rows <= 10:  # Only print first 10 skipped rows for debugging
                        print(f"DEBUG: Skipped row {total_rows}: Förare='{row.get('Förare')}', Klass='{row.get('Klass (best-effort)')}'")
                    continue
                    
                # Convert class format (450 -> 450cc, 250 -> 250cc)
                class_name = row['Klass (best-effort)'] + 'cc'
                
                # Get rider number
                rider_number = None
                if row.get('Nummer (career)'):
                    try:
                        rider_number = int(row['Nummer (career)'])
                    except ValueError:
                        pass
                
                # Get coast for 250cc riders
                coast_250 = None
                if class_name == '250cc' and row.get('Coast (250 East/West)'):
                    coast = row['Coast (250 East/West)'].lower()
                    if coast in ['east', 'west']:
                        coast_250 = coast
                
                # Extract bike brand from team/bike info
                bike_brand = 'Unknown'
                if row.get('Team/Bike (if known)'):
                    team_bike = row['Team/Bike (if known)']
                    # Try to extract brand from team/bike string
                    if 'Honda' in team_bike:
                        bike_brand = 'Honda'
                    elif 'Yamaha' in team_bike:
                        bike_brand = 'Yamaha'
                    elif 'KTM' in team_bike:
                        bike_brand = 'KTM'
                    elif 'Kawasaki' in team_bike:
                        bike_brand = 'Kawasaki'
                    elif 'Suzuki' in team_bike:
                        bike_brand = 'Suzuki'
                    elif 'Husqvarna' in team_bike:
                        bike_brand = 'Husqvarna'
                    elif 'GasGas' in team_bike:
                        bike_brand = 'GasGas'
                    elif 'Beta' in team_bike:
                        bike_brand = 'Beta'
                
                # Set default price based on class
                price = 450000 if class_name == '450cc' else 50000
                
                # Create rider data
                rider_data = {
                    'name': row['Förare'],
                    'class_name': class_name,
                    'rider_number': rider_number,
                    'bike_brand': bike_brand,
                    'price': price,
                    'coast_250': coast_250,
                    'image_url': f'riders/{row["Förare"].lower().replace(" ", "_")}.jpg'
                }
                
                riders.append(rider_data)
        
        print(f"DEBUG: Loaded {len(riders)} riders from CSV (total rows: {total_rows}, skipped: {skipped_rows})")
        
        # Count by class
        riders_450 = [r for r in riders if r['class_name'] == '450cc']
        riders_250 = [r for r in riders if r['class_name'] == '250cc']
        print(f"DEBUG: 450cc riders: {len(riders_450)}, 250cc riders: {len(riders_250)}")
        
        return riders
    except Exception as e:
        print(f"Error loading SMX 2026 riders: {e}")
        import traceback
        traceback.print_exc()
        return []

def create_test_data():
    """Create test data if it doesn't exist"""
    # Create test user
    existing_user = User.query.filter_by(username='test').first()
    if not existing_user:
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password')
        )
        db.session.add(test_user)
        print("Created test user: test/password")
    
    # Create all Supercross 2025 competitions
    if Competition.query.count() == 0:
        competitions = [
            # Western Regional 250SX Championship
            {'name': 'Anaheim 1', 'event_date': '2026-01-10', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'San Diego', 'event_date': '2026-01-17', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Anaheim 2', 'event_date': '2026-01-24', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Houston', 'event_date': '2026-01-31', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
            {'name': 'Glendale', 'event_date': '2026-02-07', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Seattle', 'event_date': '2026-02-14', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            
            # Eastern Regional 250SX Championship
            {'name': 'Arlington', 'event_date': '2026-02-21', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
            {'name': 'Daytona', 'event_date': '2026-02-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Indianapolis', 'event_date': '2026-03-07', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Birmingham', 'event_date': '2026-03-21', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True},
            {'name': 'Detroit', 'event_date': '2026-03-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'St. Louis', 'event_date': '2026-04-04', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Nashville', 'event_date': '2026-04-11', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Cleveland', 'event_date': '2026-04-18', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Philadelphia', 'event_date': '2026-04-25', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Denver', 'event_date': '2026-05-02', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
            {'name': 'Salt Lake City', 'event_date': '2026-05-09', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.5}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False)
            )
            db.session.add(comp)
        print("Created 17 Supercross 2026 competitions")
    
    # Create all Supercross 2026 riders from SMX data
    if Rider.query.count() == 0:
        # Load riders from SMX 2026 CSV file
        all_riders = load_smx_2026_riders()
        
        if not all_riders:
            print("Warning: Could not load SMX 2026 riders, using fallback data")
            # Fallback to some basic riders if CSV loading fails
            all_riders = [
                {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'rider_number': 3, 'price': 450000, 'coast_250': None, 'image_url': 'riders/3_eli_tomac.jpg'},
                {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'rider_number': 2, 'price': 450000, 'coast_250': None, 'image_url': 'riders/2_cooper_webb.jpg'},
                {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 4, 'price': 450000, 'coast_250': None, 'image_url': 'riders/4_chase_sexton.jpg'},
                {'name': 'Jett Lawrence', 'class_name': '450cc', 'bike_brand': 'Honda', 'rider_number': 18, 'price': 450000, 'coast_250': None, 'image_url': 'riders/18_jett_lawrence.jpg'},
                {'name': 'Haiden Deegan', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 38, 'price': 50000, 'coast_250': 'west', 'image_url': 'riders/38_haiden_deegan.jpg'},
                {'name': 'Levi Kitchen', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'rider_number': 47, 'price': 50000, 'coast_250': 'west', 'image_url': 'riders/47_levi_kitchen.jpg'},
                {'name': 'Jordon Smith', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 22, 'price': 50000, 'coast_250': 'east', 'image_url': 'riders/22_jordon_smith.jpg'},
                {'name': 'Max Anstie', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 62, 'price': 50000, 'coast_250': 'east', 'image_url': 'riders/62_max_anstie.jpg'}
            ]
        
        for rider_data in all_riders:
            rider = Rider(
                name=rider_data['name'],
                class_name=rider_data['class_name'],
                rider_number=rider_data.get('rider_number'),
                bike_brand=rider_data['bike_brand'],
                price=rider_data.get('price', 50),  # Default price if not specified
                image_url=rider_data.get('image_url', f"riders/{rider_data.get('rider_number', 'unknown')}_{rider_data['name'].lower().replace(' ', '_')}.jpg"),
                coast_250=rider_data.get('coast_250')
            )
            db.session.add(rider)
        
        # Count riders by class
        riders_450_count = len([r for r in all_riders if r['class_name'] == '450cc'])
        riders_250_count = len([r for r in all_riders if r['class_name'] == '250cc'])
        print(f"Created {len(all_riders)} Supercross 2026 riders ({riders_450_count}x 450cc, {riders_250_count}x 250cc)")
    
    db.session.commit()

# Initialize database function
def init_database():
    """Initialize database with tables and test data"""
    try:
        with app.app_context():
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully")
            
            print("Creating test data...")
            create_test_data()
            print("Test data created successfully")
            
            print("Database initialized successfully")
            return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Initialize database for Render
print("Starting database initialization...")
init_success = init_database()
if init_success:
    print("✅ Database initialization completed successfully")
else:
    print("❌ Database initialization failed")

if __name__ == "__main__":
    # Production vs Development configuration
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    app.run(host=host, port=port, debug=debug_mode)