import os
import random
import string
from datetime import date, datetime, timedelta
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
from sqlalchemy import text
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

# Database configuration
# For Render deployment, use PostgreSQL if available, otherwise in-memory SQLite
if os.getenv('DATABASE_URL') and 'postgresql' in os.getenv('DATABASE_URL', ''):
    # Use PostgreSQL on Render (persistent)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    print("✅ Using PostgreSQL database from DATABASE_URL - DATA WILL PERSIST!")
elif os.getenv('RENDER'):
    # On Render without PostgreSQL, use in-memory SQLite (temporary)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    print("⚠️  WARNING: Using in-memory SQLite on Render - DATA WILL BE LOST ON RESTART!")
    print("🔧 TO FIX: Add a PostgreSQL database on Render and set DATABASE_URL environment variable")
    print("📋 Steps:")
    print("   1. Go to Render Dashboard")
    print("   2. Click 'New +' → 'PostgreSQL'")
    print("   3. Choose 'PostgreSQL Free' plan")
    print("   4. Copy the DATABASE_URL from database settings")
    print("   5. Add DATABASE_URL environment variable to your web service")
else:
    # For local development, use a local file
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fantasy_mx.db'
    print("Using local SQLite database file")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database engine options - different for different database types
if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
    # PostgreSQL options
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }
else:
    # SQLite options
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {'check_same_thread': False}  # Allow multiple threads
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
    display_name = db.Column(db.String(100), nullable=True)  # Användarens riktiga namn
    profile_picture_url = db.Column(db.Text, nullable=True)  # Profilbild (base64 data)
    bio = db.Column(db.Text, nullable=True)  # Kort beskrivning om sig själv
    favorite_rider = db.Column(db.String(100), nullable=True)  # Favoritförare
    favorite_team = db.Column(db.String(100), nullable=True)  # Favoritlag
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # När kontot skapades
    season_team = db.relationship(
        "SeasonTeam", backref="user", uselist=False, cascade="all, delete-orphan"
    )


class GlobalSimulation(db.Model):
    __tablename__ = "global_simulation"
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=False)
    simulated_time = db.Column(db.String(50), nullable=True)
    start_time = db.Column(db.String(50), nullable=True)
    scenario = db.Column(db.String(50), nullable=True)

class Series(db.Model):
    __tablename__ = "series"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 'Supercross', 'Motocross', 'SMX Finals'
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    points_system = db.Column(db.String(20), default='standard')  # 'standard', 'double', 'triple'

class Competition(db.Model):
    __tablename__ = "competitions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.Date)
    series = db.Column(db.String(10), nullable=False)
    point_multiplier = db.Column(db.Float, default=1.0)
    is_triple_crown = db.Column(db.Integer, default=0)
    coast_250 = db.Column(db.String(10), nullable=True)  # <-- lägg till
    timezone = db.Column(db.String(50), nullable=True)  # <-- tidszon för banan
    
    # New SMX fields
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    phase = db.Column(db.String(20), nullable=True)  # 'regular', 'playoff1', 'playoff2', 'final'
    is_qualifying = db.Column(db.Boolean, default=False)  # For SMX Finals qualification
    
    # Relationship
    series_ref = db.relationship('Series', backref='competitions', lazy=True)

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
    
    # New SMX fields
    series_participation = db.Column(db.String(50), default='all')  # 'supercross', 'motocross', 'all'
    smx_qualified = db.Column(db.Boolean, default=False)  # Qualified for SMX Finals
    smx_seed_points = db.Column(db.Integer, default=0)  # Starting points for SMX Finals
    


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

class BulletinPost(db.Model):
    __tablename__ = "bulletin_posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), default="general")  # general, tips, question, discussion
    parent_id = db.Column(db.Integer, db.ForeignKey("bulletin_posts.id"), nullable=True)  # For replies
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship("User", backref="bulletin_posts")
    parent = db.relationship("BulletinPost", remote_side=[id], backref="replies")
    reactions = db.relationship("BulletinReaction", backref="post", cascade="all, delete-orphan")

class BulletinReaction(db.Model):
    __tablename__ = "bulletin_reactions"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("bulletin_posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)  # 🚀, 😂, 👍, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship("User", backref="bulletin_reactions")
    
    # Unique constraint - one reaction per user per post per emoji
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', 'emoji', name='unique_user_post_emoji'),)


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

class CrossDinoHighScore(db.Model):
    __tablename__ = 'cross_dino_highscores'
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.player_name,
            'score': self.score,
            'created_at': self.created_at.isoformat()
        }    

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_today():
    # Försök läsa simulerat datum från DB om det finns
    try:
        row = db.session.execute(db.text("SELECT value FROM sim_date LIMIT 1")).first()
        if row and row[0]:
            sim_date = datetime.strptime(row[0], "%Y-%m-%d").date()
            print(f"DEBUG: get_today() returning simulated date: {sim_date}")
            return sim_date
    except Exception as e:
        print(f"DEBUG: get_today() error reading sim_date: {e}")
        pass
    
    today = date.today()
    print(f"DEBUG: get_today() returning real date: {today}")
    return today


def get_track_timezone(track_name):
    """Get timezone for a track based on its name"""
    timezone_map = {
        # Pacific Time (UTC-8/-7) - California, Washington
        'Anaheim 1': 'America/Los_Angeles',      # Anaheim, CA
        'Anaheim 2': 'America/Los_Angeles',      # Anaheim, CA
        'San Diego': 'America/Los_Angeles',      # San Diego, CA
        'Seattle': 'America/Los_Angeles',        # Seattle, WA
        
        # Mountain Time (UTC-7/-6) - Colorado, Utah, Arizona
        'Denver': 'America/Denver',              # Denver, CO
        'Salt Lake City': 'America/Denver',      # Salt Lake City, UT
        'Glendale': 'America/Phoenix',           # Glendale, AZ (no DST)
        
        # Central Time (UTC-6/-5) - Texas, Missouri, Tennessee, Alabama
        'Houston': 'America/Chicago',            # Houston, TX
        'Arlington': 'America/Chicago',          # Arlington, TX
        'St. Louis': 'America/Chicago',          # St. Louis, MO
        'Nashville': 'America/Chicago',          # Nashville, TN
        'Birmingham': 'America/Chicago',         # Birmingham, AL
        
        # Eastern Time (UTC-5/-4) - Florida, Indiana, Michigan, Ohio, Pennsylvania
        'Daytona': 'America/New_York',           # Daytona Beach, FL
        'Indianapolis': 'America/New_York',      # Indianapolis, IN
        'Detroit': 'America/New_York',           # Detroit, MI
        'Cleveland': 'America/New_York',         # Cleveland, OH
        'Philadelphia': 'America/New_York',      # Philadelphia, PA
    }
    return timezone_map.get(track_name, 'America/New_York')  # Default to Eastern

def create_trackmap_images():
    """Create CompetitionImage records for compressed track maps"""
    print("Creating CompetitionImage records for compressed track maps...")
    
    # Map competition names to image files
    COMP_TO_IMAGE = {
        "Anaheim 1": "anaheim1.jpg",
        "San Diego": "sandiego.jpg", 
        "Anaheim 2": "anaheim2.jpg",
        "Houston": "houston.jpg",
        "Glendale": "glendale.jpg",
        "Seattle": "seattle.jpg",
        "Arlington": "arlington.jpg",
        "Daytona": "daytona.jpg",
        "Indianapolis": "indianapolis.jpg",
        "Birmingham": "birmingham.jpg",
        "Detroit": "detroit.jpg",
        "St. Louis": "stlouis.jpg",
        "Nashville": "nashville.jpg",
        "Cleveland": "cleveland.jpg",
        "Philadelphia": "philadelphia.jpg",
        "Denver": "denver.jpg",
        "Salt Lake City": "saltlakecity.jpg"
    }
    
    # Get all competitions
    competitions = Competition.query.all()
    print(f"Found {len(competitions)} competitions")
    
    total_created = 0
    
    for comp in competitions:
        if comp.name in COMP_TO_IMAGE:
            # Clear existing images for this competition
            CompetitionImage.query.filter_by(competition_id=comp.id).delete()
            
            # Create new image record
            image_url = f"trackmaps/compressed/{COMP_TO_IMAGE[comp.name]}"
            ci = CompetitionImage(
                competition_id=comp.id,
                image_url=image_url,
                sort_order=0
            )
            db.session.add(ci)
            total_created += 1
            print(f"Created image for {comp.name}: {image_url}")
            
            # Check if image file exists
            from pathlib import Path
            image_path = Path(f"static/{image_url}")
            if image_path.exists():
                print(f"  ✅ Image file exists: {image_path}")
            else:
                print(f"  ❌ Image file missing: {image_path}")
    
    db.session.commit()
    print(f"Total CompetitionImage records created: {total_created}")


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
@app.route("/api/series_status")
def series_status():
    """Get status of all series for user interface"""
    try:
        series = Series.query.filter_by(year=2026, is_active=True).all()
        
        # Use simulated date if available, otherwise use real date
        current_date = get_today()
        
        series_data = []
        for s in series:
            # Check if series is active based on dates
            is_currently_active = False
            if s.start_date and s.end_date:
                is_currently_active = s.start_date <= current_date <= s.end_date
            elif s.start_date:
                is_currently_active = current_date >= s.start_date
            
            # Get next race in this series
            next_race = Competition.query.filter_by(series_id=s.id).filter(
                Competition.event_date >= current_date
            ).order_by(Competition.event_date).first()
            
            series_data.append({
                'id': s.id,
                'name': s.name,
                'is_active': is_currently_active,
                'start_date': s.start_date.isoformat() if s.start_date else None,
                'end_date': s.end_date.isoformat() if s.end_date else None,
                'next_race': {
                    'name': next_race.name,
                    'date': next_race.event_date.isoformat()
                } if next_race else None
            })
        
        return jsonify(series_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

    # Get user profile picture
    user_profile_picture = None
    try:
        user = User.query.get(uid)
        if user and hasattr(user, 'profile_picture_url') and user.profile_picture_url:
            user_profile_picture = user.profile_picture_url
    except Exception as e:
        print(f"Error getting user profile picture: {e}")
        user_profile_picture = None

    # Get user's picks for upcoming race
    current_picks_450 = []
    current_picks_250 = []
    picks_status = "no_picks"
    picks_locked = False
    
    if upcoming_race:
        try:
            # Use the unified picks lock check function
            picks_locked = is_picks_locked(upcoming_race)
            
            # Use the correct competition_id for picks lookup
            competition_id_for_picks = upcoming_race.id
            
            print(f"DEBUG: Looking for picks for user {uid}, competition {competition_id_for_picks}")
            print(f"DEBUG: Picks locked: {picks_locked}")
            
            # Get race picks for both classes
            race_picks = RacePick.query.filter_by(
                user_id=uid, 
                competition_id=competition_id_for_picks
            ).order_by(RacePick.predicted_position).all()
            
            # Get holeshot picks
            holeshot_picks = HoleshotPick.query.filter_by(
                user_id=uid,
                competition_id=competition_id_for_picks
            ).all()
            
            # Get wildcard pick
            wildcard_pick = WildcardPick.query.filter_by(
                user_id=uid,
                competition_id=competition_id_for_picks
            ).first()
            
            print(f"DEBUG: Found {len(race_picks)} race picks, {len(holeshot_picks)} holeshot picks, wildcard: {wildcard_pick is not None}")
            
            if race_picks or holeshot_picks or wildcard_pick:
                picks_status = "has_picks"
                
                # Always show user's own picks (they can see their own choices)
                for pick in race_picks:
                    rider = Rider.query.get(pick.rider_id)
                    if rider:
                        pick_data = {
                            "position": pick.predicted_position,
                            "rider_name": rider.name,
                            "rider_number": rider.rider_number,
                            "class": rider.class_name
                        }
                        
                        # Separate by class
                        if rider.class_name == "450cc":
                            current_picks_450.append(pick_data)
                        elif rider.class_name == "250cc":
                            current_picks_250.append(pick_data)
                        
                        print(f"DEBUG: Added pick - position {pick.predicted_position}, rider {rider.name} ({rider.class_name})")
                
                # Process holeshot picks
                current_holeshot_450 = None
                current_holeshot_250 = None
                for holeshot in holeshot_picks:
                    rider = Rider.query.get(holeshot.rider_id)
                    if rider:
                        if rider.class_name == "450cc":
                            current_holeshot_450 = {
                                "rider_name": rider.name,
                                "rider_number": rider.rider_number,
                                "class": rider.class_name
                            }
                        elif rider.class_name == "250cc":
                            current_holeshot_250 = {
                                "rider_name": rider.name,
                                "rider_number": rider.rider_number,
                                "class": rider.class_name
                            }
                
                # Process wildcard pick
                current_wildcard = None
                if wildcard_pick:
                    rider = Rider.query.get(wildcard_pick.rider_id)
                    if rider:
                        current_wildcard = {
                            "rider_name": rider.name,
                            "rider_number": rider.rider_number,
                            "class": rider.class_name,
                            "position": wildcard_pick.position
                        }
        except Exception as e:
            print(f"Error getting current picks: {e}")
            current_picks_450 = []
            current_picks_250 = []

    return render_template(
        "index.html",
        username=session["username"],
        user_profile_picture=user_profile_picture,
        upcoming_race=upcoming_race,
        upcoming_races=[c for c in competitions if c.event_date and c.event_date >= today],
        my_team=my_team,
        team_riders=team_riders,
        current_picks_450=current_picks_450,
        current_picks_250=current_picks_250,
        current_holeshot_450=current_holeshot_450 if 'current_holeshot_450' in locals() else None,
        current_holeshot_250=current_holeshot_250 if 'current_holeshot_250' in locals() else None,
        current_wildcard=current_wildcard if 'current_wildcard' in locals() else None,
        picks_status=picks_status,
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
        db.session.query(User.id, User.username)
        .join(LeagueMembership, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.league_id == league_id)
        .all()
    )

    member_user_ids = [m[0] for m in db.session.query(LeagueMembership.user_id).filter_by(league_id=league_id).all()]
    season_leaderboard = []
    if member_user_ids:
        season_leaderboard = (
            db.session.query(User.id, User.username, SeasonTeam.team_name, SeasonTeam.total_points)
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .filter(User.id.in_(member_user_ids))
            .order_by(SeasonTeam.total_points.desc().nullslast())
            .all()
        )

    competitions = Competition.query.order_by(Competition.event_date).all()

    return render_template(
        "league_detail.html",
        league=league,
        members=[type("Row", (), {"id": m.id, "username": m.username}) for m in members],
        competitions=competitions,
        season_leaderboard=[
            {"user_id": row.id, "username": row.username, "team_name": row.team_name, "total_points": row.total_points or 0}
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

@app.route("/profile")
def profile_page():
    print(f"DEBUG: profile_page called, session: {dict(session)}")
    if "user_id" not in session:
        print("DEBUG: No user_id in session, redirecting to login")
        return redirect(url_for("login"))
    
    print(f"DEBUG: User ID in session: {session['user_id']}")
    try:
        # Try to get user with new columns first
        user = User.query.get(session["user_id"])
        print(f"DEBUG: User query result: {user}")
        if not user:
            print("DEBUG: User not found, redirecting to index")
            flash("Användare hittades inte.", "error")
            return redirect(url_for("index"))
    except Exception as e:
        print(f"DEBUG: Error loading user profile (likely missing columns): {e}")
        # Rollback any failed transaction
        try:
            db.session.rollback()
        except:
            pass
        
        # Try to add missing columns automatically
        try:
            print("DEBUG: Attempting to add missing profile columns...")
            columns_to_add = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_rider VARCHAR(100);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(100);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
            ]
            
            for sql in columns_to_add:
                db.session.execute(db.text(sql))
            
            # Also try to fix existing profile_picture_url column if it's VARCHAR(300)
            try:
                if 'postgresql' in str(db.engine.url):
                    db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
                    print("DEBUG: Fixed existing profile_picture_url column to TEXT")
            except Exception as alter_error:
                print(f"DEBUG: Could not alter column (may already be TEXT): {alter_error}")
            
            db.session.commit()
            print("DEBUG: Successfully added/fixed profile columns")
            
            # Now try to get user again
            user = User.query.get(session["user_id"])
            if not user:
                flash("Användare hittades inte.", "error")
                return redirect(url_for("index"))
        except Exception as e2:
            print(f"DEBUG: Error adding columns or loading user: {e2}")
            # Rollback any failed transaction
            try:
                db.session.rollback()
            except:
                pass
            
            # If error, try to get user with basic query
            try:
                user = db.session.execute(
                    db.text("SELECT id, username, password_hash FROM users WHERE id = :user_id"),
                    {"user_id": session["user_id"]}
                ).fetchone()
                if not user:
                    flash("Användare hittades inte.", "error")
                    return redirect(url_for("index"))
                # Create a simple user object
                class SimpleUser:
                    def __init__(self, id, username, password_hash):
                        self.id = id
                        self.username = username
                        self.password_hash = password_hash
                        self.display_name = None
                        self.profile_picture_url = None
                        self.bio = None
                        self.favorite_rider = None
                        self.favorite_team = None
                        self.created_at = None
                user = SimpleUser(user.id, user.username, user.password_hash)
            except Exception as e3:
                print(f"DEBUG: Error with basic user query: {e3}")
                # Rollback any failed transaction
                try:
                    db.session.rollback()
                except:
                    pass
                flash("Databasen behöver uppdateras. Kontakta admin.", "error")
                return redirect(url_for("index"))
    
    # Hämta säsongsteam
    season_team = SeasonTeam.query.filter_by(user_id=user.id).first()
    
    # Beräkna statistik
    competitions_played = CompetitionScore.query.filter_by(user_id=user.id).count()
    
    # Hitta bästa placering (lägsta position i leaderboard)
    best_position = None
    if competitions_played > 0:
        # Hämta alla tävlingar där användaren har poäng
        user_scores = CompetitionScore.query.filter_by(user_id=user.id).all()
        best_positions = []
        
        for score in user_scores:
            # Hitta användarens placering i denna tävling
            all_scores_for_comp = CompetitionScore.query.filter_by(competition_id=score.competition_id).order_by(CompetitionScore.total_points.desc()).all()
            position = 1
            for i, s in enumerate(all_scores_for_comp):
                if s.user_id == user.id:
                    position = i + 1
                    break
            best_positions.append(position)
        
        if best_positions:
            best_position = min(best_positions)
    
    print(f"DEBUG: Rendering profile template with user: {user.username}")
    return render_template(
        "profile.html",
        user=user,
        season_team=season_team,
        competitions_played=competitions_played,
        best_position=best_position
    )

@app.post("/update_profile")
def update_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        user = User.query.get(session["user_id"])
        if not user:
            flash("Användare hittades inte.", "error")
            return redirect(url_for("profile_page"))
    except Exception as e:
        print(f"DEBUG: Error loading user for update: {e}")
        # Try to fix the column issue automatically
        try:
            if 'postgresql' in str(db.engine.url):
                db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
                db.session.commit()
                print("DEBUG: Fixed profile_picture_url column to TEXT in update_profile")
                # Try to get user again
                user = User.query.get(session["user_id"])
                if not user:
                    flash("Användare hittades inte.", "error")
                    return redirect(url_for("profile_page"))
            else:
                flash("Databasen behöver uppdateras. Kontakta admin.", "error")
                return redirect(url_for("profile_page"))
        except Exception as fix_error:
            print(f"DEBUG: Could not fix column: {fix_error}")
            flash("Databasen behöver uppdateras. Kontakta admin.", "error")
            return redirect(url_for("profile_page"))
    
    try:
        # Uppdatera grundläggande information (only if columns exist)
        display_name = request.form.get("display_name", "").strip() or None
        bio = request.form.get("bio", "").strip() or None
        favorite_rider = request.form.get("favorite_rider", "").strip() or None
        favorite_team = request.form.get("favorite_team", "").strip() or None
        
        # Try to update profile fields
        try:
            user.display_name = display_name
            user.bio = bio
            user.favorite_rider = favorite_rider
            user.favorite_team = favorite_team
        except AttributeError:
            # Columns don't exist yet, skip profile updates
            print("DEBUG: Profile columns don't exist yet, skipping profile updates")
            flash("Profilfunktioner kommer att fungera efter databas-uppdatering.", "info")
        
        # Hantera profilbild - försök base64 först, fallback till fil
        file = request.files.get("profile_picture")
        if file and file.filename and allowed_file(file.filename):
            try:
                import base64
                from PIL import Image
                import io
                
                # Läs och optimera bilden
                file_data = file.read()
                file.seek(0)
                
                # Öppna och optimera bilden
                img = Image.open(io.BytesIO(file_data))
                
                # Konvertera till RGB om nödvändigt
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize till lämplig storlek för profilbilder
                max_size = (150, 150)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Spara som JPEG med bra kvalitet
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=80, optimize=True)
                optimized_data = output.getvalue()
                
                # Konvertera till base64
                base64_data = base64.b64encode(optimized_data).decode('utf-8')
                data_url = f"data:image/jpeg;base64,{base64_data}"
                
                try:
                    # Försök spara som base64 först (permanent lösning)
                    user.profile_picture_url = data_url
                    print(f"Profile picture saved as base64 (size: {len(base64_data)} chars)")
                    flash("Profilbild uppladdad och sparad permanent! 🎉", "success")
                except Exception as base64_error:
                    print(f"DEBUG: Base64 save failed, trying file fallback: {base64_error}")
                    # Fallback: spara som fil
                    fname = secure_filename(f"profile_{user.id}_{file.filename}")
                    path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                    file.save(path)
                    user.profile_picture_url = f"uploads/leagues/{fname}"
                    print(f"Profile picture saved as file: {path}")
                    flash("Profilbild sparad (kommer att försvinna vid deployment). Fixa kolumnen för permanent lagring!", "warning")
                except AttributeError:
                    print("DEBUG: profile_picture_url column doesn't exist yet")
                    flash("Profilbild sparad, men kommer att visas efter databas-uppdatering.", "info")
            except Exception as e:
                print(f"Error saving profile picture: {e}")
                flash("Kunde inte spara profilbilden.", "error")
        
        db.session.commit()
        flash("Profil uppdaterad!", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating profile: {e}")
        flash(f"Fel vid uppdatering av profil: {str(e)}", "error")
    
    return redirect(url_for("profile_page"))

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
    print(f"DEBUG: my_scores called for user ID {uid}")

    rows = (
        db.session.query(
            Competition.id.label("competition_id"),
            Competition.name,
            Competition.series,
            Competition.event_date,
            CompetitionScore.total_points,
        )
        .outerjoin(CompetitionScore, (Competition.id == CompetitionScore.competition_id) & (CompetitionScore.user_id == uid))
        .order_by(Competition.event_date.asc().nulls_last())
        .all()
    )

    print(f"DEBUG: Found {len(rows)} score entries for user {uid}")
    for r in rows:
        print(f"DEBUG: Competition {r.name}: {r.total_points} points")

    total_points = sum((r.total_points or 0) for r in rows)
    print(f"DEBUG: Total points for user {uid}: {total_points}")
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


@app.route("/series/<int:series_id>")
def series_page(series_id):
    """Dedicated page for a specific series (SX/MX/SMX)"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        print(f"DEBUG: series_page called with series_id: {series_id}")
        
        # Get series info
        series = Series.query.get_or_404(series_id)
        print(f"DEBUG: Found series: {series.name} (ID: {series.id})")
        
        # Get all competitions in this series
        competitions = Competition.query.filter_by(series_id=series_id).order_by(Competition.event_date).all()
        print(f"DEBUG: Found {len(competitions)} competitions for series {series.name}")
        
        # Get current date (use simulated date if available)
        current_date = get_today()
        
        # Check if we're in test simulation mode
        simulation_active = False
        test_race = None
        try:
            global_sim = GlobalSimulation.query.first()
            if global_sim and global_sim.active:
                simulation_active = True
                
                # Check if there's a selected competition in admin
                selected_comp_id = global_sim.simulated_time  # This stores the selected competition ID
                if selected_comp_id and selected_comp_id.isdigit():
                    # Use the selected competition from admin
                    selected_comp = Competition.query.get(int(selected_comp_id))
                    if selected_comp and selected_comp.series_id == series_id:
                        test_race = selected_comp
                    else:
                        # Fallback to scenario-based test race
                        scenario = global_sim.scenario or 'race_in_3h'
                        from datetime import datetime, timedelta
                        fake_race_base_time = datetime.now()
                        
                        if scenario == "race_in_3h":
                            fake_race_datetime_utc = fake_race_base_time + timedelta(hours=3)
                        elif scenario == "race_in_1h":
                            fake_race_datetime_utc = fake_race_base_time + timedelta(hours=1)
                        elif scenario == "race_in_30m":
                            fake_race_datetime_utc = fake_race_base_time + timedelta(minutes=30)
                        elif scenario == "race_tomorrow":
                            fake_race_datetime_utc = fake_race_base_time + timedelta(days=1)
                        else:
                            fake_race_datetime_utc = fake_race_base_time + timedelta(hours=3)
                        
                        # Create a fake test race object
                        class FakeRace:
                            def __init__(self):
                                self.id = 9999
                                self.name = f"Test Race ({scenario})"
                                self.event_date = fake_race_datetime_utc.date()
                                self.series_id = series_id
                                self.timezone = "UTC"
                        
                        test_race = FakeRace()
                else:
                    # No selected competition, use scenario-based test race
                    scenario = global_sim.scenario or 'race_in_3h'
                    from datetime import datetime, timedelta
                    fake_race_base_time = datetime.now()
                    
                    if scenario == "race_in_3h":
                        fake_race_datetime_utc = fake_race_base_time + timedelta(hours=3)
                    elif scenario == "race_in_1h":
                        fake_race_datetime_utc = fake_race_base_time + timedelta(hours=1)
                    elif scenario == "race_in_30m":
                        fake_race_datetime_utc = fake_race_base_time + timedelta(minutes=30)
                    elif scenario == "race_tomorrow":
                        fake_race_datetime_utc = fake_race_base_time + timedelta(days=1)
                    else:
                        fake_race_datetime_utc = fake_race_base_time + timedelta(hours=3)
                    
                    # Create a fake test race object
                    class FakeRace:
                        def __init__(self):
                            self.id = 9999
                            self.name = f"Test Race ({scenario})"
                            self.event_date = fake_race_datetime_utc.date()
                            self.series_id = series_id
                            self.timezone = "UTC"
                    
                    test_race = FakeRace()
        except:
            pass
        
        # Find next race (use test race if in simulation mode)
        next_race = test_race if simulation_active else None
        if not next_race:
            # Find the first competition that doesn't have results yet (hasn't been run)
            for comp in competitions:
                # Check if this competition has results
                has_results = (
                    CompetitionResult.query.filter_by(competition_id=comp.id).first() is not None
                )
                
                # If no results, this is the next race to run
                if not has_results:
                    next_race = comp
                    break
        
        # Check if picks should be open
        picks_open = False
        if simulation_active:
            # In test mode, picks are always open
            picks_open = True
        elif series.start_date:
            # Check if we're within 1 week of season start
            days_until_start = (series.start_date - current_date).days
            picks_open = days_until_start <= 7  # Open 1 week before season start
            
            # If picks are open and we have a next race, check if it's locked
            if picks_open and next_race:
                picks_locked = is_picks_locked(next_race.id)
                picks_open = not picks_locked
        elif next_race:
            # For races after season has started, picks are open if:
            # 1. The next race doesn't have results yet (hasn't been run)
            # 2. The race is not locked (not within 2 hours of start)
            
            # Check if next race has results
            has_results = (
                CompetitionResult.query.filter_by(competition_id=next_race.id).first() is not None
            )
            
            if not has_results:
                # Race hasn't been run yet, check if picks are locked
                picks_locked = is_picks_locked(next_race.id)
                picks_open = not picks_locked
            else:
                # Race has been run, picks should be closed
                picks_open = False
        
        # Get results for each competition to show status
        competition_results = {}
        user_picks_status = {}
        for comp in competitions:
            results = CompetitionResult.query.filter_by(competition_id=comp.id).all()
            competition_results[comp.id] = results
            
            # Check if current user has made picks for this competition
            if "user_id" in session:
                user_id = session["user_id"]
                race_picks = RacePick.query.filter_by(user_id=user_id, competition_id=comp.id).count()
                holeshot_picks = HoleshotPick.query.filter_by(user_id=user_id, competition_id=comp.id).count()
                wildcard_pick = WildcardPick.query.filter_by(user_id=user_id, competition_id=comp.id).first()
                
                has_picks = race_picks > 0 or holeshot_picks > 0 or wildcard_pick is not None
                user_picks_status[comp.id] = {
                    'has_picks': has_picks,
                    'race_picks_count': race_picks,
                    'holeshot_picks_count': holeshot_picks,
                    'has_wildcard': wildcard_pick is not None
                }
            else:
                user_picks_status[comp.id] = {'has_picks': False}
        
        print(f"DEBUG: Rendering series_page.html for {series.name}")
        return render_template('series_page.html',
                             series=series,
                             competitions=competitions,
                             competition_results=competition_results,
                             user_picks_status=user_picks_status,
                             next_race=next_race,
                             picks_open=picks_open,
                             current_date=current_date)
        
    except Exception as e:
        print(f"ERROR in series_page: {e}")
        import traceback
        print(f"ERROR traceback: {traceback.format_exc()}")
        return redirect(url_for("index"))

@app.route("/race_picks/<int:competition_id>")
def race_picks_page(competition_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    comp = Competition.query.get_or_404(competition_id)
    
    # Use the unified picks lock check function
    picks_locked = is_picks_locked(comp)
    
    # If picks are locked, show locked page instead of redirect
    if picks_locked:
        return render_template(
            "race_picks_locked.html",
            competition=comp,
            picks_locked=True
        )

    # 1) Hämta OUT-förare för detta race
    out_rows = db.session.query(CompetitionRiderStatus.rider_id).filter(
        CompetitionRiderStatus.competition_id == comp.id,
        CompetitionRiderStatus.status == "OUT",
    ).all()
    out_ids = set(rid for (rid,) in out_rows)
    
    print(f"DEBUG: race_picks_page for {comp.name} (id: {comp.id})")
    print(f"DEBUG: Found {len(out_ids)} OUT riders: {list(out_ids)}")

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
    
    # Debug: Show which riders are marked as OUT
    out_450 = [r for r in riders_450_json if r['is_out']]
    out_250 = [r for r in riders_250_json if r['is_out']]
    print(f"DEBUG: 450cc OUT riders: {[r['name'] for r in out_450]}")
    print(f"DEBUG: 250cc OUT riders: {[r['name'] for r in out_250]}")

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
    
    try:
        # Get the same data as the old admin page
        competitions = Competition.query.order_by(Competition.event_date).all()
        riders_450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.rider_number).all()
        riders_250 = Rider.query.filter_by(class_name="250cc").order_by(Rider.rider_number).all()
    except Exception as e:
        print(f"DEBUG: Error in admin_page: {e}")
        return f'''
        <html>
        <head><title>Database Error</title></head>
        <body style="font-family: Arial; margin: 50px; background: #1a1a1a; color: white;">
            <h1>🔧 Database Error</h1>
            <p>Admin page requires database fixes. Please fix the database first:</p>
            <a href="/fix_database" style="background: #22d3ee; color: black; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0;">
                Fix Database
            </a>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        '''
    
    # Get current simulated date
    try:
        result = db.session.execute(db.text("SELECT value FROM sim_date LIMIT 1")).fetchone()
        today = result[0] if result else None
    except:
        today = None
    
    # Serialize data for JavaScript
    def serialize_competition(comp):
        return {
            "id": comp.id,
            "name": comp.name,
            "event_date": comp.event_date.isoformat(),
            "coast_250": comp.coast_250
        }
    
    def serialize_rider(rider):
        return {
            "id": rider.id,
            "name": rider.name,
            "class_name": rider.class_name,
            "rider_number": rider.rider_number,
            "bike_brand": rider.bike_brand,
            "coast_250": rider.coast_250
        }
    
    competitions_data = [serialize_competition(comp) for comp in competitions]
    riders_450_data = [serialize_rider(rider) for rider in riders_450]
    riders_250_data = [serialize_rider(rider) for rider in riders_250]
    
    # Create competition coast map for JavaScript
    comp_coast_map = {}
    for comp in competitions:
        comp_coast_map[comp.id] = comp.coast_250
    
    return render_template("admin_new.html", 
                         competitions=competitions_data,
                         riders_450=riders_450_data,
                         riders_250=riders_250_data,
                         comp_coast_map=comp_coast_map,
                         today=today)

@app.route('/rider_management')
def rider_management():
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        # Get riders by class and coast
        riders_450 = Rider.query.filter_by(class_name='450cc').order_by(Rider.rider_number).all()
        riders_250_east = Rider.query.filter_by(class_name='250cc', coast_250='east').order_by(Rider.rider_number).all()
        riders_250_west = Rider.query.filter_by(class_name='250cc', coast_250='west').order_by(Rider.rider_number).all()
        
        return render_template('rider_management.html',
                             riders_450=riders_450,
                             riders_250_east=riders_250_east,
                             riders_250_west=riders_250_west)
    except Exception as e:
        print(f"DEBUG: Error in rider_management: {e}")
        return f'''
        <html>
        <head><title>Database Error</title></head>
        <body style="font-family: Arial; margin: 50px; background: #1a1a1a; color: white;">
            <h1>🔧 Database Error</h1>
            <p>Rider management requires database fixes. Please fix the database first:</p>
            <a href="/fix_database" style="background: #22d3ee; color: black; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0;">
                Fix Database
            </a>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        '''

# API endpoints for rider management
@app.route('/api/riders', methods=['POST'])
def add_rider():
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    # Set default price based on class
    price = 450000 if data['class_name'] == '450cc' else 50000
    
    rider = Rider(
        name=data['name'],
        class_name=data['class_name'],
        rider_number=data['rider_number'],
        bike_brand=data['bike_brand'],
        coast_250=data.get('coast_250'),
        price=price
    )
    
    db.session.add(rider)
    db.session.commit()
    
    return jsonify({'success': True, 'id': rider.id})

@app.route('/api/riders/<int:rider_id>', methods=['PUT'])
def update_rider(rider_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    rider = Rider.query.get_or_404(rider_id)
    data = request.get_json()
    
    rider.name = data['name']
    rider.rider_number = data['rider_number']
    rider.bike_brand = data['bike_brand']
    
    # Update coast_250 if provided (for 250cc riders)
    if 'coast_250' in data:
        rider.coast_250 = data['coast_250']
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/riders/<int:rider_id>', methods=['DELETE'])
def delete_rider(rider_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    rider = Rider.query.get_or_404(rider_id)
    db.session.delete(rider)
    db.session.commit()
    
    return jsonify({'success': True})

# API endpoints for series management
@app.route('/api/series', methods=['GET'])
def get_series():
    """Get all series"""
    series = Series.query.order_by(Series.year.desc(), Series.start_date.asc()).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'year': s.year,
        'start_date': s.start_date.isoformat() if s.start_date else None,
        'end_date': s.end_date.isoformat() if s.end_date else None,
        'is_active': s.is_active,
        'points_system': s.points_system
    } for s in series])

@app.route('/api/series', methods=['POST'])
def create_series():
    """Create a new series"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    series = Series(
        name=data['name'],
        year=data['year'],
        start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None,
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
        is_active=data.get('is_active', True),
        points_system=data.get('points_system', 'standard')
    )
    
    db.session.add(series)
    db.session.commit()
    
    return jsonify({'success': True, 'id': series.id})

@app.route('/api/series/<int:series_id>', methods=['PUT'])
def update_series(series_id):
    """Update a series"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    series = Series.query.get_or_404(series_id)
    data = request.get_json()
    
    series.name = data['name']
    series.year = data['year']
    series.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None
    series.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
    series.is_active = data.get('is_active', True)
    series.points_system = data.get('points_system', 'standard')
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/series/<int:series_id>', methods=['DELETE'])
def delete_series(series_id):
    """Delete a series"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    series = Series.query.get_or_404(series_id)
    db.session.delete(series)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/series/create_default_2025', methods=['POST'])
def create_default_series_2025():
    """Create default SMX series for 2026"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    # First, delete any old 2025 series
    old_2025_series = Series.query.filter_by(year=2025).all()
    if old_2025_series:
        print(f"Deleting {len(old_2025_series)} old 2025 series")
        for series in old_2025_series:
            db.session.delete(series)
        db.session.commit()
        print("Deleted old 2025 series")
    
    # Check if series already exist and update them
    existing = Series.query.filter_by(year=2026).first()
    if existing:
        # Update existing series with correct dates
        supercross = Series.query.filter_by(name='Supercross', year=2026).first()
        if supercross:
            supercross.start_date = date(2026, 1, 4)
            supercross.end_date = date(2026, 5, 10)
            supercross.is_active = True
        
        motocross = Series.query.filter_by(name='Motocross', year=2026).first()
        if motocross:
            motocross.start_date = date(2026, 5, 24)
            motocross.end_date = date(2026, 8, 23)
            motocross.is_active = True
        
        smx_finals = Series.query.filter_by(name='SMX Finals', year=2026).first()
        if smx_finals:
            smx_finals.start_date = date(2026, 9, 6)
            smx_finals.end_date = date(2026, 9, 20)
            smx_finals.is_active = True
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Updated existing series with correct dates',
            'series_updated': [
                {'name': 'Supercross', 'start': '2026-01-04', 'end': '2026-05-10'},
                {'name': 'Motocross', 'start': '2026-05-24', 'end': '2026-08-23'},
                {'name': 'SMX Finals', 'start': '2026-09-06', 'end': '2026-09-20'}
            ]
        })
    
    # Create Supercross series (should be active now)
    supercross = Series(
        name='Supercross',
        year=2026,
        start_date=date(2026, 1, 4),  # Anaheim 1
        end_date=date(2026, 5, 10),   # Salt Lake City
        is_active=True,
        points_system='standard'
    )
    
    # Create Motocross series (starts in May 2026)
    motocross = Series(
        name='Motocross',
        year=2026,
        start_date=date(2026, 5, 24),  # Pala
        end_date=date(2026, 8, 23),    # Ironman
        is_active=True,
        points_system='standard'
    )
    
    # Create SMX Finals series (starts in September 2026)
    smx_finals = Series(
        name='SMX Finals',
        year=2026,
        start_date=date(2026, 9, 6),   # Playoff 1
        end_date=date(2026, 9, 20),    # Final
        is_active=True,
        points_system='playoff'
    )
    
    db.session.add_all([supercross, motocross, smx_finals])
    db.session.commit()
    
    # Automatically create all competitions for each series
    create_supercross_competitions(supercross.id)
    create_motocross_competitions(motocross.id)
    create_smx_finals_competitions(smx_finals.id)
    
    return jsonify({
        'success': True,
        'series_created': [
            {'id': supercross.id, 'name': 'Supercross'},
            {'id': motocross.id, 'name': 'Motocross'},
            {'id': smx_finals.id, 'name': 'SMX Finals'}
        ],
        'message': 'All series and competitions created successfully!'
    })

def create_supercross_competitions(supercross_series_id):
    """Create all Supercross competitions for 2026"""
    # Supercross races 2026 (existing ones)
    supercross_races = [
        {"name": "Anaheim 1", "date": "2026-01-04", "coast_250": "west"},
        {"name": "San Francisco", "date": "2026-01-11", "coast_250": "west"},
        {"name": "San Diego", "date": "2026-01-18", "coast_250": "west"},
        {"name": "Anaheim 2", "date": "2026-01-25", "coast_250": "west"},
        {"name": "Detroit", "date": "2026-02-01", "coast_250": "east"},
        {"name": "Glendale", "date": "2026-02-08", "coast_250": "west"},
        {"name": "Arlington", "date": "2026-02-15", "coast_250": "east"},
        {"name": "Daytona", "date": "2026-03-01", "coast_250": "east"},
        {"name": "Birmingham", "date": "2026-03-08", "coast_250": "east"},
        {"name": "Indianapolis", "date": "2026-03-15", "coast_250": "east"},
        {"name": "Seattle", "date": "2026-03-22", "coast_250": "west"},
        {"name": "St. Louis", "date": "2026-03-29", "coast_250": "east"},
        {"name": "Foxborough", "date": "2026-04-05", "coast_250": "east"},
        {"name": "Nashville", "date": "2026-04-12", "coast_250": "east"},
        {"name": "Philadelphia", "date": "2026-04-19", "coast_250": "east"},
        {"name": "Denver", "date": "2026-04-26", "coast_250": "west"},
        {"name": "Salt Lake City", "date": "2026-05-03", "coast_250": "west"}
    ]
    
    for race in supercross_races:
        # Check if competition already exists
        existing = Competition.query.filter_by(name=race["name"]).first()
        if existing:
            # Update existing competition with series_id and new date
            existing.series_id = supercross_series_id
            existing.phase = "regular"
            existing.event_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
            continue
            
        competition = Competition(
            name=race["name"],
            event_date=datetime.strptime(race["date"], "%Y-%m-%d").date(),
            series="450cc",
            point_multiplier=1.0,
            is_triple_crown=0,
            coast_250=race["coast_250"],
            timezone="America/Los_Angeles",
            series_id=supercross_series_id,
            phase="regular",
            is_qualifying=False
        )
        db.session.add(competition)
    
    db.session.commit()

def create_motocross_competitions(motocross_series_id):
    """Create all Motocross competitions for 2026"""
    motocross_races = [
        {"name": "Fox Raceway National", "date": "2026-05-24", "location": "Pala, CA"},
        {"name": "Hangtown Classic", "date": "2026-05-31", "location": "Rancho Cordova, CA"},
        {"name": "Thunder Valley National", "date": "2026-06-07", "location": "Lakewood, CO"},
        {"name": "High Point National", "date": "2026-06-14", "location": "Mt. Morris, PA"},
        {"name": "Southwick National", "date": "2026-06-28", "location": "Southwick, MA"},
        {"name": "RedBud National", "date": "2026-07-05", "location": "Buchanan, MI"},
        {"name": "Spring Creek National", "date": "2026-07-12", "location": "Millville, MN"},
        {"name": "Washougal National", "date": "2026-07-19", "location": "Washougal, WA"},
        {"name": "Unadilla National", "date": "2026-08-16", "location": "New Berlin, NY"},
        {"name": "Budds Creek National", "date": "2026-08-23", "location": "Mechanicsville, MD"},
        {"name": "Ironman National", "date": "2026-08-09", "location": "Crawfordsville, IN"}
    ]
    
    for race in motocross_races:
        # Check if competition already exists
        existing = Competition.query.filter_by(name=race["name"]).first()
        if existing:
            # Update existing competition with series_id and new date
            existing.series_id = motocross_series_id
            existing.phase = "regular"
            existing.event_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
            continue
            
        competition = Competition(
            name=race["name"],
            event_date=datetime.strptime(race["date"], "%Y-%m-%d").date(),
            series="450cc",  # Motocross is 450cc only
            point_multiplier=1.0,
            is_triple_crown=0,
            coast_250=None,
            timezone="America/Los_Angeles",
            series_id=motocross_series_id,
            phase="regular",
            is_qualifying=False
        )
        db.session.add(competition)
    
    db.session.commit()

def create_smx_finals_competitions(smx_series_id):
    """Create all SMX Finals competitions for 2026"""
    smx_races = [
        {"name": "SMX Playoff 1", "date": "2026-09-06", "phase": "playoff1"},
        {"name": "SMX Playoff 2", "date": "2026-09-13", "phase": "playoff2"},
        {"name": "SMX Final", "date": "2026-09-20", "phase": "final"}
    ]
    
    for race in smx_races:
        # Check if competition already exists
        existing = Competition.query.filter_by(name=race["name"]).first()
        if existing:
            # Update existing competition with series_id and new date
            existing.series_id = smx_series_id
            existing.phase = race["phase"]
            existing.event_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
            continue
            
        competition = Competition(
            name=race["name"],
            event_date=datetime.strptime(race["date"], "%Y-%m-%d").date(),
            series="450cc",  # SMX Finals is 450cc only
            point_multiplier=3.0,  # Triple points for SMX Finals
            is_triple_crown=0,
            coast_250=None,
            timezone="America/Los_Angeles",
            series_id=smx_series_id,
            phase=race["phase"],
            is_qualifying=False
        )
        db.session.add(competition)
    
    db.session.commit()

@app.route('/api/competitions/create_motocross_2025', methods=['POST'])
def create_motocross_competitions_2025():
    """Create all Motocross competitions for 2026"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get Motocross series
        motocross_series = Series.query.filter_by(name="Motocross", year=2026).first()
        if not motocross_series:
            return jsonify({'error': 'Motocross series not found. Create series first.'}), 400
        
        # Motocross races 2026
        motocross_races = [
            {"name": "Fox Raceway National", "date": "2026-05-24", "location": "Pala, CA"},
            {"name": "Hangtown Classic", "date": "2026-05-31", "location": "Rancho Cordova, CA"},
            {"name": "Thunder Valley National", "date": "2026-06-07", "location": "Lakewood, CO"},
            {"name": "High Point National", "date": "2026-06-14", "location": "Mt. Morris, PA"},
            {"name": "Southwick National", "date": "2026-06-28", "location": "Southwick, MA"},
            {"name": "RedBud National", "date": "2026-07-05", "location": "Buchanan, MI"},
            {"name": "Spring Creek National", "date": "2026-07-12", "location": "Millville, MN"},
            {"name": "Washougal National", "date": "2026-07-19", "location": "Washougal, WA"},
            {"name": "Unadilla National", "date": "2026-08-16", "location": "New Berlin, NY"},
            {"name": "Budds Creek National", "date": "2026-08-23", "location": "Mechanicsville, MD"},
            {"name": "Ironman National", "date": "2026-08-09", "location": "Crawfordsville, IN"}
        ]
        
        created_competitions = []
        
        for race in motocross_races:
            # Check if competition already exists
            existing = Competition.query.filter_by(name=race["name"]).first()
            if existing:
                # Update existing competition with series_id and new date
                existing.series_id = motocross_series.id
                existing.phase = "regular"
                existing.event_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
                continue
                
            competition = Competition(
                name=race["name"],
                event_date=datetime.strptime(race["date"], "%Y-%m-%d").date(),
                series="450cc",  # Motocross is 450cc only
                point_multiplier=1.0,
                is_triple_crown=0,
                coast_250=None,
                timezone="America/Los_Angeles",
                series_id=motocross_series.id,
                phase="regular",
                is_qualifying=False
            )
            
            db.session.add(competition)
            created_competitions.append(race["name"])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'competitions_created': created_competitions,
            'message': f'Created {len(created_competitions)} Motocross competitions'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitions/create_smx_finals_2025', methods=['POST'])
def create_smx_finals_competitions_2025():
    """Create SMX Finals competitions for 2026"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get SMX Finals series
        smx_series = Series.query.filter_by(name="SMX Finals", year=2026).first()
        if not smx_series:
            return jsonify({'error': 'SMX Finals series not found. Create series first.'}), 400
        
        # SMX Finals races 2026
        smx_races = [
            {"name": "SMX Playoff 1", "date": "2026-09-06", "phase": "playoff1"},
            {"name": "SMX Playoff 2", "date": "2026-09-13", "phase": "playoff2"},
            {"name": "SMX Final", "date": "2026-09-20", "phase": "final"}
        ]
        
        created_competitions = []
        
        for race in smx_races:
            # Check if competition already exists
            existing = Competition.query.filter_by(name=race["name"]).first()
            if existing:
                # Update existing competition with series_id and new date
                existing.series_id = smx_series.id
                existing.phase = race["phase"]
                existing.event_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
                continue
                
            competition = Competition(
                name=race["name"],
                event_date=datetime.strptime(race["date"], "%Y-%m-%d").date(),
                series="450cc",  # SMX Finals is 450cc only
                point_multiplier=3.0,  # Triple points for SMX Finals
                is_triple_crown=0,
                coast_250=None,
                timezone="America/Los_Angeles",
                series_id=smx_series.id,
                phase=race["phase"],
                is_qualifying=False
            )
            
            db.session.add(competition)
            created_competitions.append(race["name"])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'competitions_created': created_competitions,
            'message': f'Created {len(created_competitions)} SMX Finals competitions'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/fix_database_tables', methods=['POST'])
def fix_database_tables():
    """Fix missing database tables and columns"""
    print("DEBUG: fix_database_tables() called")
    
    if session.get("username") != "test":
        print("DEBUG: Unauthorized access attempt")
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print("DEBUG: Starting database fix process")
        
        # Create all tables
        print("DEBUG: Creating all tables with db.create_all()")
        db.create_all()
        print("DEBUG: db.create_all() completed")
        
        # Manually add missing columns to competitions table
        print("DEBUG: Starting manual column addition")
        try:
            # Check if series_id column exists
            print("DEBUG: Checking if series_id column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='series_id'"))
            series_id_exists = result.fetchone()
            print(f"DEBUG: series_id column exists: {series_id_exists is not None}")
            
            if not series_id_exists:
                print("DEBUG: Adding series_id column")
                db.session.execute(text("ALTER TABLE competitions ADD COLUMN series_id INTEGER"))
                print("DEBUG: Added series_id column to competitions")
            else:
                print("DEBUG: series_id column already exists")
            
            # Check if phase column exists
            print("DEBUG: Checking if phase column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='phase'"))
            phase_exists = result.fetchone()
            print(f"DEBUG: phase column exists: {phase_exists is not None}")
            
            if not phase_exists:
                print("DEBUG: Adding phase column")
                db.session.execute(text("ALTER TABLE competitions ADD COLUMN phase VARCHAR(20)"))
                print("DEBUG: Added phase column to competitions")
            else:
                print("DEBUG: phase column already exists")
            
            # Check if is_qualifying column exists
            print("DEBUG: Checking if is_qualifying column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='is_qualifying'"))
            is_qualifying_exists = result.fetchone()
            print(f"DEBUG: is_qualifying column exists: {is_qualifying_exists is not None}")
            
            if not is_qualifying_exists:
                print("DEBUG: Adding is_qualifying column")
                db.session.execute(text("ALTER TABLE competitions ADD COLUMN is_qualifying BOOLEAN DEFAULT FALSE"))
                print("DEBUG: Added is_qualifying column to competitions")
            else:
                print("DEBUG: is_qualifying column already exists")
            
            print("DEBUG: Committing column changes")
            db.session.commit()
            print("DEBUG: Column changes committed successfully")
            
        except Exception as col_error:
            print(f"DEBUG: Column addition error: {col_error}")
            print(f"DEBUG: Error type: {type(col_error)}")
            db.session.rollback()
            print("DEBUG: Rolled back column changes")
        
        # Check and add missing columns to riders table
        print("DEBUG: Checking for missing columns in riders table")
        try:
            # Check if series_participation column exists
            print("DEBUG: Checking if series_participation column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='series_participation'"))
            series_participation_exists = result.fetchone()
            print(f"DEBUG: series_participation column exists: {series_participation_exists is not None}")
            
            if not series_participation_exists:
                print("DEBUG: Adding series_participation column")
                db.session.execute(text("ALTER TABLE riders ADD COLUMN series_participation VARCHAR(50) DEFAULT 'all'"))
                print("DEBUG: Added series_participation column to riders")
            else:
                print("DEBUG: series_participation column already exists")
            
            # Check if smx_qualified column exists
            print("DEBUG: Checking if smx_qualified column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_qualified'"))
            smx_qualified_exists = result.fetchone()
            print(f"DEBUG: smx_qualified column exists: {smx_qualified_exists is not None}")
            
            if not smx_qualified_exists:
                print("DEBUG: Adding smx_qualified column")
                db.session.execute(text("ALTER TABLE riders ADD COLUMN smx_qualified BOOLEAN DEFAULT FALSE"))
                print("DEBUG: Added smx_qualified column to riders")
            else:
                print("DEBUG: smx_qualified column already exists")
            
            # Check if smx_seed_points column exists
            print("DEBUG: Checking if smx_seed_points column exists")
            result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_seed_points'"))
            smx_seed_points_exists = result.fetchone()
            print(f"DEBUG: smx_seed_points column exists: {smx_seed_points_exists is not None}")
            
            if not smx_seed_points_exists:
                print("DEBUG: Adding smx_seed_points column")
                db.session.execute(text("ALTER TABLE riders ADD COLUMN smx_seed_points INTEGER DEFAULT 0"))
                print("DEBUG: Added smx_seed_points column to riders")
            else:
                print("DEBUG: smx_seed_points column already exists")
            
            print("DEBUG: Committing riders column changes")
            db.session.commit()
            print("DEBUG: Riders column changes committed successfully")
            
        except Exception as riders_error:
            print(f"DEBUG: Riders column addition error: {riders_error}")
            print(f"DEBUG: Error type: {type(riders_error)}")
            db.session.rollback()
            print("DEBUG: Rolled back riders column changes")
        
        # Check if global_simulation exists and create default entry
        print("DEBUG: Checking global_simulation table")
        try:
            global_sim_exists = GlobalSimulation.query.first()
            print(f"DEBUG: global_simulation entry exists: {global_sim_exists is not None}")
            
            if not global_sim_exists:
                print("DEBUG: Creating default global_simulation entry")
                global_sim = GlobalSimulation(
                    active=False,
                    simulated_time=None,
                    start_time=None,
                    scenario=None
                )
                db.session.add(global_sim)
                db.session.commit()
                print("DEBUG: Created default global_simulation entry")
            else:
                print("DEBUG: global_simulation entry already exists")
                
        except Exception as global_error:
            print(f"DEBUG: Global simulation error: {global_error}")
            print(f"DEBUG: Error type: {type(global_error)}")
        
        # Fix all 2025 competitions to 2026
        print("DEBUG: Fixing 2025 competitions to 2026...")
        try:
            competitions_2025 = Competition.query.filter(Competition.event_date.like('2025-%')).all()
            print(f"DEBUG: Found {len(competitions_2025)} competitions with 2025 dates")
            
            for comp in competitions_2025:
                old_date = comp.event_date
                # Convert 2025 to 2026
                new_date = comp.event_date.replace(year=2026)
                comp.event_date = new_date
                print(f"DEBUG: Updated {comp.name}: {old_date} -> {new_date}")
            
            db.session.commit()
            print(f"DEBUG: Updated {len(competitions_2025)} competitions from 2025 to 2026")
        except Exception as date_error:
            print(f"DEBUG: Date fix error: {date_error}")
            db.session.rollback()
        
        print("DEBUG: Database fix completed successfully")
        return jsonify({'success': True, 'message': f'Database tables and columns fixed. Updated {len(competitions_2025) if "competitions_2025" in locals() else 0} competitions from 2025 to 2026'})
        
    except Exception as e:
        print(f"DEBUG: Main error in fix_database_tables: {e}")
        print(f"DEBUG: Error type: {type(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/fix_database')
def fix_database_page():
    """Simple page to fix database issues"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fix Database</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 50px; background: #1a1a1a; color: white; }
            .container { max-width: 600px; margin: 0 auto; }
            button { 
                background: #22d3ee; 
                color: black; 
                border: none; 
                padding: 15px 30px; 
                font-size: 16px; 
                border-radius: 5px; 
                cursor: pointer; 
                margin: 10px;
            }
            button:hover { background: #0891b2; }
            .result { margin: 20px 0; padding: 15px; border-radius: 5px; }
            .success { background: #065f46; border: 1px solid #10b981; }
            .error { background: #7f1d1d; border: 1px solid #ef4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Database Fix Tool</h1>
            <p>This tool will fix missing database tables and columns.</p>
            
            <button onclick="fixDatabase()">Fix Database</button>
            <button onclick="window.location.href='/'">Back to Home</button>
            
            <div id="result"></div>
        </div>
        
        <script>
            async function fixDatabase() {
                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = '<p>Fixing database...</p>';
                
                try {
                    const response = await fetch('/api/fix_database_tables', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <h3>✅ Success!</h3>
                                <p>${result.message}</p>
                                <p>You can now go back to the admin page.</p>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <h3>❌ Error</h3>
                                <p>${result.error}</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <h3>❌ Network Error</h3>
                            <p>${error.message}</p>
                        </div>
                    `;
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route("/admin_old")
def admin_page_old():
    if session.get("username") != "test":
        return redirect(url_for("index"))
    competitions = Competition.query.order_by(Competition.event_date).all()
    riders_450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.rider_number).all()
    
    # For admin page, we need ALL 250cc riders (not filtered by coast)
    # Coast filtering will be handled by JavaScript based on selected competition
    riders_250 = Rider.query.filter_by(class_name="250cc").order_by(Rider.rider_number).all()

    # Serialize riders data for JavaScript
    def serialize_rider(r: Rider):
        return {
            "id": r.id,
            "name": r.name,
            "class_name": r.class_name,
            "rider_number": r.rider_number,
            "bike_brand": r.bike_brand,
            "coast_250": r.coast_250,
        }

    riders_250_json = [serialize_rider(r) for r in riders_250]

    # Create competition coast map for JavaScript
    comp_coast_map = {}
    for comp in competitions:
        comp_coast_map[comp.id] = comp.coast_250

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
        riders_250_json=riders_250_json,
        comp_coast_map=comp_coast_map,
        race_scores=race_scores,
        today=get_today(),
    )


@app.get("/admin/get_results/<int:competition_id>")
def admin_get_results(competition_id):
    if session.get("username") != "test":
        return jsonify({"error": "unauthorized"}), 403

    try:
        print(f"DEBUG: admin_get_results called for competition {competition_id}")

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

        print(f"DEBUG: Found {len(results)} results and {len(holos)} holeshot results")

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
    except Exception as e:
        print(f"DEBUG: Error in admin_get_results: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "internal_error"}), 500


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
    print(f"DEBUG: Results saved for competition {comp_id}")
    print(f"DEBUG: 450cc results: {len(riders_450_filtered)} riders")
    print(f"DEBUG: 250cc results: {len(riders_250_filtered)} riders")
    print(f"DEBUG: Holeshot 450: {hs_450}, Holeshot 250: {hs_250}")
    
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
    print(f"DEBUG: admin_set_sim_date called with date: {sim}")
    if not sim:
        flash("Du måste ange ett datum (YYYY-MM-DD).", "error")
        return redirect(url_for("admin_page"))
    try:
        # rensa och sätt nytt
        db.session.execute(db.text("DELETE FROM sim_date"))
        db.session.execute(db.text("INSERT INTO sim_date (value) VALUES (:v)"), {"v": sim})
        db.session.commit()
        print(f"DEBUG: Successfully saved sim_date: {sim}")
        flash(f"Simulerat datum satt till {sim}.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error saving sim_date: {e}")
        flash(f"Kunde inte sätta sim datum: {e}", "error")
    return redirect(url_for("admin_page"))


# -------------------------------------------------
# API helpers (för templates JS)
# -------------------------------------------------
@app.get("/get_season_leaderboard")
def get_season_leaderboard():
    # Använd CompetitionScore direkt för att få korrekta poäng
    from sqlalchemy import func
    
    # Hämta alla användare med deras totala poäng från CompetitionScore
    user_scores = (
        db.session.query(
            User.id,
            User.username,
            SeasonTeam.team_name,
            func.coalesce(func.sum(CompetitionScore.total_points), 0).label('total_points')
        )
        .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
        .outerjoin(CompetitionScore, CompetitionScore.user_id == User.id)
        .group_by(User.id, User.username, SeasonTeam.team_name)
        .order_by(func.coalesce(func.sum(CompetitionScore.total_points), 0).desc())
        .all()
    )
    
    # Lägg till rank och delta (enkel version)
    result = []
    for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
        result.append({
            "user_id": user_id,
            "username": username,
            "team_name": team_name or None,
            "total_points": int(total_points),
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

@app.get("/race_results")
def race_results_page():
    """Show actual race results for all competitions"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    competitions = (
        Competition.query
        .filter(Competition.series == "SX")
        .order_by(Competition.event_date.asc())
        .all()
    )
    
    # Get results for each competition
    competition_results = {}
    for comp in competitions:
        results = (
            db.session.query(
                CompetitionResult.rider_id,
                CompetitionResult.position,
                Rider.name,
                Rider.class_name,
                Rider.rider_number,
                Rider.image_url,
                Rider.bike_brand
            )
            .join(Rider, Rider.id == CompetitionResult.rider_id)
            .filter(CompetitionResult.competition_id == comp.id)
            .order_by(CompetitionResult.position.asc())
            .all()
        )
        
        holeshots = (
            db.session.query(
                HoleshotResult.rider_id,
                Rider.name,
                HoleshotResult.class_name,
                Rider.rider_number,
                Rider.image_url,
                Rider.bike_brand
            )
            .join(Rider, Rider.id == HoleshotResult.rider_id)
            .filter(HoleshotResult.competition_id == comp.id)
            .all()
        )
        
        competition_results[comp.id] = {
            'results': results,
            'holeshots': holeshots
        }
    
    # Determine status for each competition and find the latest one
    today = get_today()
    latest_competition_id = None
    
    for comp in competitions:
        # Check if competition has results
        has_results = len(competition_results[comp.id]['results']) > 0 or len(competition_results[comp.id]['holeshots']) > 0
        
        print(f"DEBUG: Competition {comp.name} (ID: {comp.id}) - Results: {len(competition_results[comp.id]['results'])}, Holeshots: {len(competition_results[comp.id]['holeshots'])}, Has Results: {has_results}")
        
        # Determine status
        if has_results:
            comp.status = "completed"
            comp.status_text = "Körda race"
            comp.status_color = "text-green-600"
            comp.status_bg = "bg-green-100"
        elif comp.event_date and comp.event_date < today:
            comp.status = "missed"
            comp.status_text = "Missade race"
            comp.status_color = "text-red-600"
            comp.status_bg = "bg-red-100"
        else:
            comp.status = "upcoming"
            comp.status_text = "Uppkommande"
            comp.status_color = "text-blue-600"
            comp.status_bg = "bg-blue-100"
        
        # Find the latest competition (most recent with results, or most recent upcoming)
        if has_results and (latest_competition_id is None or comp.event_date > competitions[latest_competition_id].event_date):
            latest_competition_id = comp.id
        elif not latest_competition_id and comp.event_date and comp.event_date >= today:
            latest_competition_id = comp.id
    
    return render_template(
        "race_results.html", 
        competitions=competitions, 
        competition_results=competition_results,
        latest_competition_id=latest_competition_id,
        username=session.get("username")
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
    
    # Debug: Print competition and image information
    print(f"DEBUG: Found {len(comps)} competitions for trackmaps")
    for comp in comps:
        images = comp.images.order_by('sort_order').all()
        print(f"DEBUG: {comp.name} (ID: {comp.id}) has {len(images)} images")
        for img in images:
            print(f"  - Image: {img.image_url} (sort_order: {img.sort_order})")
            # Check if image file exists
            from pathlib import Path
            image_path = Path(f"static/{img.image_url}")
            print(f"    File exists: {image_path.exists()}")
            if not image_path.exists():
                print(f"    ERROR: Image file missing: static/{img.image_url}")
    
    # Auto-create track map images if none exist
    total_images = CompetitionImage.query.count()
    print(f"DEBUG: Total CompetitionImage records: {total_images}")
    if total_images == 0:
        print("DEBUG: No CompetitionImage records found, creating them...")
        create_trackmap_images()
    else:
        print("DEBUG: CompetitionImage records already exist, skipping creation")
    
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

@app.get("/create_trackmaps")
def create_trackmaps_route():
    """Manual route to create track map images"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    print("DEBUG: Manual track map creation triggered")
    create_trackmap_images()
    return redirect(url_for("trackmaps_page"))

@app.get("/reset_trackmaps")
def reset_trackmaps_route():
    """Reset and recreate all track map images"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    print("DEBUG: Resetting all track map images")
    # Clear all existing CompetitionImage records
    CompetitionImage.query.delete()
    db.session.commit()
    print("DEBUG: Cleared all CompetitionImage records")
    
    # Recreate them
    create_trackmap_images()
    return redirect(url_for("trackmaps_page"))

@app.get("/list_trackmap_files")
def list_trackmap_files():
    """List all files in compressed trackmaps folder"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    from pathlib import Path
    compressed_dir = Path("static/trackmaps/compressed")
    print(f"DEBUG: Checking compressed directory: {compressed_dir}")
    print(f"DEBUG: Directory exists: {compressed_dir.exists()}")
    
    if compressed_dir.exists():
        files = list(compressed_dir.glob("*.jpg"))
        print(f"DEBUG: Found {len(files)} .jpg files:")
        for file in files:
            print(f"  - {file.name}")
    else:
        print("DEBUG: Compressed directory does not exist!")
    
    return redirect(url_for("trackmaps_page"))
@app.get("/admin/get_out_status/<int:competition_id>")
def admin_get_out_status(competition_id):
    if session.get("username") != "test":
        return jsonify({"error": "unauthorized"}), 403

    try:
        print(f"DEBUG: admin_get_out_status called for competition {competition_id}")

        # all riders
        riders = db.session.query(Rider).order_by(Rider.class_name.desc(), Rider.rider_number.asc()).all()
        print(f"DEBUG: Found {len(riders)} riders")

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
        print(f"DEBUG: Found {len(out_ids)} OUT riders for competition {competition_id}")

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
        print(f"DEBUG: Returning {len(result)} riders with OUT status")
        return jsonify(result), 200
    except Exception as e:
        print(f"DEBUG: Error in admin_get_out_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "internal_error"}), 500




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

    print(f"DEBUG: admin_set_out_status called - comp_id: {comp_id}, rider_id: {rider_id}, status: {status}")

    try:
        comp_id = int(comp_id)
        rider_id = int(rider_id)
    except Exception as e:
        print(f"DEBUG: Error parsing IDs: {e}")
        return jsonify({"error": "invalid_payload"}), 400

    # Validera att tävling och förare finns
    comp = Competition.query.get(comp_id)
    rider = Rider.query.get(rider_id)
    if not comp:
        print(f"DEBUG: Competition {comp_id} not found")
        return jsonify({"error": "competition_not_found"}), 404
    if not rider:
        print(f"DEBUG: Rider {rider_id} not found")
        return jsonify({"error": "rider_not_found"}), 404

    print(f"DEBUG: Found competition: {comp.name}, rider: {rider.name}")

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
            print(f"DEBUG: Created new OUT status for {rider.name}")
        else:
            row.status = "OUT"
            print(f"DEBUG: Updated existing OUT status for {rider.name}")
        db.session.commit()
        print(f"DEBUG: Committed OUT status for {rider.name}")
        return jsonify({"ok": True, "message": "Rider set OUT"}), 200

    # CLEAR: rensa alla rader för kombinationen (robust)
    deleted_count = CompetitionRiderStatus.query.filter_by(
        competition_id=comp_id, rider_id=rider_id
    ).delete()
    db.session.commit()
    print(f"DEBUG: Cleared OUT status for {rider.name} (deleted {deleted_count} rows)")
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
    print(f"DEBUG: get_my_picks called for user {uid}, competition {competition_id}")
    
    picks = (
        RacePick.query.filter_by(user_id=uid, competition_id=competition_id)
        .order_by(RacePick.predicted_position)
        .all()
    )
    holos = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).all()
    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).first()

    print(f"DEBUG: Found {len(picks)} picks, {len(holos)} holeshots, wildcard: {wc is not None}")
    for p in picks:
        rider = Rider.query.get(p.rider_id)
        print(f"DEBUG: Pick - position {p.predicted_position}: {rider.name if rider else 'Unknown'} (ID: {p.rider_id})")

    result = {
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
    
    print(f"DEBUG: Returning picks data: {result}")
    return jsonify(result)


@app.post("/save_picks")
def save_picks():
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    uid = session["user_id"]
    print(f"DEBUG: save_picks called for user {uid}")
    print(f"DEBUG: Received data: {data}")

    # 1) Hämta tävlingen
    try:
        comp_id = int(data.get("competition_id"))
    except Exception:
        return jsonify({"error": "invalid_competition_id"}), 400

    comp = Competition.query.get(comp_id)
    if not comp:
        return jsonify({"error": "competition_not_found"}), 404
    
    print(f"DEBUG: Competition: {comp.name} (ID: {comp_id})")
    
    # Use the unified picks lock check function
    picks_locked = is_picks_locked(comp)
    
    # If picks are locked, reject the save
    if picks_locked:
        return jsonify({"error": "Picks är låsta! Du kan inte längre ändra dina val."}), 403

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
    print(f"DEBUG: Received {len(picks)} picks: {picks}")
    
    rider_ids = [int(p.get("rider_id")) for p in picks if p.get("rider_id")]
    if len(rider_ids) != len(set(rider_ids)):
        return jsonify({"error": "Du kan inte välja samma förare flera gånger"}), 400

    # 4) Rensa tidigare picks/holeshot för användaren i denna tävling
    # VIKTIGT: Rensa INTE resultat när picks sparas - bara picks
    deleted_picks = RacePick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    print(f"DEBUG: Deleted {deleted_picks} old picks, {deleted_holeshots} old holeshots, {deleted_wildcards} old wildcards")

    # 5) Spara Top-6 picks
    saved_picks = 0
    for p in picks:
        try:
            pos = int(p.get("position"))
            rid = int(p.get("rider_id"))
            print(f"DEBUG: Processing pick - position: {pos}, rider_id: {rid}")
        except Exception as e:
            print(f"DEBUG: Error parsing pick {p}: {e}")
            continue

        rider = Rider.query.get(rid)
        if not rider:
            print(f"DEBUG: Rider {rid} not found")
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
        saved_picks += 1
        print(f"DEBUG: Added pick - {rider.name} at position {pos}")
    
    print(f"DEBUG: Saved {saved_picks} picks total")

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
    print(f"DEBUG: calculate_scores called for competition {comp_id}")
    users = User.query.all()
    actual_results = CompetitionResult.query.filter_by(competition_id=comp_id).all()
    actual_holeshots = HoleshotResult.query.filter_by(competition_id=comp_id).all()

    print(f"DEBUG: Found {len(users)} users, {len(actual_results)} results, {len(actual_holeshots)} holeshots")
    
    actual_results_dict = {res.rider_id: res for res in actual_results}
    actual_holeshots_dict = {hs.class_name: hs for hs in actual_holeshots}

    for user in users:
        total_points = 0
        print(f"DEBUG: Calculating points for user {user.username} (ID: {user.id})")

        picks = RacePick.query.filter_by(user_id=user.id, competition_id=comp_id).all()
        print(f"DEBUG: User {user.username} has {len(picks)} race picks")
        
        for pick in picks:
            actual_pos_for_pick = (
                actual_results_dict.get(pick.rider_id).position
                if pick.rider_id in actual_results_dict
                else None
            )
            if actual_pos_for_pick == pick.predicted_position:
                total_points += 25
                print(f"DEBUG: Perfect match! +25 points for {user.username}")
            elif actual_pos_for_pick is not None and actual_pos_for_pick <= 6:
                total_points += 5
                print(f"DEBUG: Top 6 finish! +5 points for {user.username}")

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
            print(f"DEBUG: Created new score entry for {user.username}")
        else:
            print(f"DEBUG: Updated existing score entry for {user.username}")
        score_entry.total_points = total_points
        print(f"DEBUG: {user.username} total points: {total_points}")
        
        # Debug: Check if user has any picks at all
        all_user_picks = RacePick.query.filter_by(user_id=user.id).all()
        print(f"DEBUG: {user.username} has {len(all_user_picks)} total picks across all competitions")

    db.session.commit()

    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        all_user_scores = CompetitionScore.query.filter_by(user_id=team.user_id).all()
        total_season_points = sum(s.total_points for s in all_user_scores)
        team.total_points = total_season_points
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) to {total_season_points} points")

    db.session.commit()
    print(f"✅ Poängberäkning klar för tävling ID: {comp_id}")

# -------------------------------------------------
# Felsökning: lista routes
# -------------------------------------------------
@app.get("/clear_my_picks")
def clear_my_picks():
    """Clear all picks for the current user - for debugging"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    uid = session["user_id"]
    print(f"DEBUG: clear_my_picks called for user {uid}")
    
    # Delete all picks for this user
    deleted_picks = RacePick.query.filter_by(user_id=uid).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid).delete()
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards")
    
    return jsonify({
        "message": f"Cleared {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards",
        "deleted_picks": deleted_picks,
        "deleted_holeshots": deleted_holeshots,
        "deleted_wildcards": deleted_wildcards
    })

@app.post("/clear_my_picks_for_competition/<int:competition_id>")
def clear_my_picks_for_competition(competition_id):
    """Clear picks for current user and specific competition - called automatically when loading race picks"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    uid = session["user_id"]
    print(f"DEBUG: clear_my_picks_for_competition called for user {uid}, competition {competition_id}")
    
    # Delete picks for this user and competition
    deleted_picks = RacePick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).delete()
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards for competition {competition_id}")
    
    return jsonify({
        "message": f"Cleared {deleted_picks} picks, {deleted_holeshots} holeshots, {deleted_wildcards} wildcards for competition {competition_id}",
        "deleted_picks": deleted_picks,
        "deleted_holeshots": deleted_holeshots,
        "deleted_wildcards": deleted_wildcards
    })

@app.get("/clear_admin_results")
def clear_admin_results():
    """Clear all admin results and scores - for debugging"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print(f"DEBUG: clear_admin_results called")
    
    # Delete all admin results
    deleted_results = CompetitionResult.query.delete()
    deleted_holeshot_results = HoleshotResult.query.delete()
    deleted_scores = CompetitionScore.query.delete()
    deleted_out_status = CompetitionRiderStatus.query.delete()
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_out_status} out statuses")
    
    return jsonify({
        "message": f"Cleared {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_out_status} out statuses",
        "deleted_results": deleted_results,
        "deleted_holeshot_results": deleted_holeshot_results,
        "deleted_scores": deleted_scores,
        "deleted_out_status": deleted_out_status
    })

@app.post("/clear_competition_results/<int:competition_id>")
def clear_competition_results(competition_id):
    """Clear results for a specific competition - called automatically when switching competitions"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print(f"DEBUG: clear_competition_results called for competition {competition_id}")
    
    # Get competition name for debugging
    comp = Competition.query.get(competition_id)
    comp_name = comp.name if comp else f"Unknown (ID: {competition_id})"
    print(f"DEBUG: Clearing results for competition: {comp_name}")
    
    # Check what exists before deletion
    existing_results = CompetitionResult.query.filter_by(competition_id=competition_id).count()
    existing_holeshots = HoleshotResult.query.filter_by(competition_id=competition_id).count()
    existing_scores = CompetitionScore.query.filter_by(competition_id=competition_id).count()
    existing_out_status = CompetitionRiderStatus.query.filter_by(competition_id=competition_id).count()
    print(f"DEBUG: Before deletion - Results: {existing_results}, Holeshots: {existing_holeshots}, Scores: {existing_scores}, Out Status: {existing_out_status}")
    
    # Delete results for this specific competition
    deleted_results = CompetitionResult.query.filter_by(competition_id=competition_id).delete()
    deleted_holeshot_results = HoleshotResult.query.filter_by(competition_id=competition_id).delete()
    deleted_scores = CompetitionScore.query.filter_by(competition_id=competition_id).delete()
    deleted_out_status = CompetitionRiderStatus.query.filter_by(competition_id=competition_id).delete()
    
    # ALSO delete user picks for this competition
    deleted_race_picks = RacePick.query.filter_by(competition_id=competition_id).delete()
    deleted_holeshot_picks = HoleshotPick.query.filter_by(competition_id=competition_id).delete()
    deleted_wildcard_picks = WildcardPick.query.filter_by(competition_id=competition_id).delete()
    
    db.session.commit()
    
    # Update season team points after clearing competition scores
    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        all_user_scores = CompetitionScore.query.filter_by(user_id=team.user_id).all()
        total_season_points = sum(s.total_points for s in all_user_scores)
        team.total_points = total_season_points
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) to {total_season_points} points")
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_out_status} out statuses, {deleted_race_picks} race picks, {deleted_holeshot_picks} holeshot picks, {deleted_wildcard_picks} wildcard picks for competition {competition_id}")
    
    return jsonify({
        "message": f"Cleared {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_out_status} out statuses, {deleted_race_picks} race picks, {deleted_holeshot_picks} holeshot picks, {deleted_wildcard_picks} wildcard picks for competition {competition_id}",
        "deleted_results": deleted_results,
        "deleted_holeshot_results": deleted_holeshot_results,
        "deleted_scores": deleted_scores,
        "deleted_out_status": deleted_out_status,
        "deleted_race_picks": deleted_race_picks,
        "deleted_holeshot_picks": deleted_holeshot_picks,
        "deleted_wildcard_picks": deleted_wildcard_picks
    })

@app.get("/update_season_team_points")
def update_season_team_points():
    """Update all season team points based on current competition scores"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: update_season_team_points called")
    
    all_season_teams = SeasonTeam.query.all()
    updated_teams = []
    
    for team in all_season_teams:
        all_user_scores = CompetitionScore.query.filter_by(user_id=team.user_id).all()
        total_season_points = sum(s.total_points for s in all_user_scores)
        old_points = team.total_points
        team.total_points = total_season_points
        updated_teams.append({
            "team_name": team.team_name,
            "user_id": team.user_id,
            "old_points": old_points,
            "new_points": total_season_points
        })
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) from {old_points} to {total_season_points} points")
    
    db.session.commit()
    
    return jsonify({
        "message": f"Updated {len(updated_teams)} season teams",
        "updated_teams": updated_teams
    })

@app.get("/check_season_teams")
def check_season_teams():
    """Check if users have season teams and create them if missing"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: check_season_teams called")
    
    all_users = User.query.all()
    missing_teams = []
    existing_teams = []
    
    for user in all_users:
        team = SeasonTeam.query.filter_by(user_id=user.id).first()
        if not team:
            missing_teams.append({
                "user_id": user.id,
                "username": user.username
            })
        else:
            existing_teams.append({
                "user_id": user.id,
                "username": user.username,
                "team_name": team.team_name,
                "total_points": team.total_points
            })
    
    return jsonify({
        "message": f"Found {len(existing_teams)} existing teams, {len(missing_teams)} missing teams",
        "existing_teams": existing_teams,
        "missing_teams": missing_teams
    })


@app.get("/fix_league_images")
def fix_league_images():
    """Fix league images by setting them to None if files don't exist (for Render compatibility)"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: fix_league_images called")
    
    all_leagues = League.query.all()
    fixed_count = 0
    
    for league in all_leagues:
        if league.image_url:
            # Extract filename from URL
            filename = league.image_url.split('/')[-1]
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            
            # If image file doesn't exist, clear the image_url
            if not os.path.exists(image_path):
                print(f"DEBUG: Image file missing for league {league.name}, clearing image_url")
                league.image_url = None
                fixed_count += 1
    
    db.session.commit()
    
    return jsonify({
        "message": f"Fixed {fixed_count} leagues with missing images",
        "fixed_count": fixed_count
    })

@app.get("/add_profile_columns")
def add_profile_columns():
    """Add missing profile columns to users table"""
    # Allow any logged-in user to add columns (needed for profile page)
    if "user_id" not in session:
        return jsonify({"error": "login_required"}), 401
    
    print("DEBUG: add_profile_columns called")

@app.get("/fix_profile_columns")
def fix_profile_columns():
    """Fix profile columns - no login required for debugging"""
    print("DEBUG: fix_profile_columns called")
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Add missing columns to users table
        columns_to_add = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_rider VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
        ]
        
        for sql in columns_to_add:
            try:
                db.session.execute(db.text(sql))
                print(f"DEBUG: Executed: {sql}")
            except Exception as e:
                print(f"DEBUG: Error executing {sql}: {e}")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile columns added successfully",
            "columns_added": len(columns_to_add)
        })
    except Exception as e:
        print(f"DEBUG: Error adding profile columns: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.get("/backup_profiles")
def backup_profiles():
    """Backup all user profile data to JSON"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        users = User.query.all()
        profile_backups = []
        for user in users:
            profile_pic = getattr(user, 'profile_picture_url', None)
            # Truncate base64 data for backup display (first 100 chars)
            profile_pic_display = profile_pic[:100] + "..." if profile_pic and len(profile_pic) > 100 else profile_pic
            
            backup = {
                'id': user.id,
                'username': user.username,
                'password_hash': user.password_hash,
                'display_name': getattr(user, 'display_name', None),
                'profile_picture_url': profile_pic,
                'profile_picture_display': profile_pic_display,  # For display purposes
                'bio': getattr(user, 'bio', None),
                'favorite_rider': getattr(user, 'favorite_rider', None),
                'favorite_team': getattr(user, 'favorite_team', None),
                'created_at': getattr(user, 'created_at', None).isoformat() if getattr(user, 'created_at', None) else None
            }
            profile_backups.append(backup)
        
        return jsonify({
            "message": f"Backed up {len(profile_backups)} user profiles",
            "profiles": profile_backups,
            "backup_date": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/restore_profiles")
def restore_profiles():
    """Restore user profile data from backup"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        data = request.get_json()
        if not data or 'profiles' not in data:
            return jsonify({"error": "No profile data provided"}), 400
        
        restored_count = 0
        for backup in data['profiles']:
            user = User.query.filter_by(username=backup['username']).first()
            if user:
                # Update existing user with backup data
                if backup.get('display_name'):
                    user.display_name = backup['display_name']
                if backup.get('profile_picture_url'):
                    user.profile_picture_url = backup['profile_picture_url']
                if backup.get('bio'):
                    user.bio = backup['bio']
                if backup.get('favorite_rider'):
                    user.favorite_rider = backup['favorite_rider']
                if backup.get('favorite_team'):
                    user.favorite_team = backup['favorite_team']
                if backup.get('created_at'):
                    user.created_at = datetime.fromisoformat(backup['created_at'])
                restored_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Restored {restored_count} user profiles",
            "restored_count": restored_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/fix_profile_picture_column")
def fix_profile_picture_column():
    """Fix profile_picture_url column to support base64 data"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403

@app.get("/fix_column_public")
def fix_column_public():
    """Fix profile_picture_url column - no login required for emergency fix"""
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Check if we need to alter the column type
        if 'postgresql' in str(db.engine.url):
            # PostgreSQL syntax - alter column type
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
            print("DEBUG: Changed profile_picture_url column to TEXT")
        else:
            # SQLite doesn't support ALTER COLUMN, but TEXT is default anyway
            print("DEBUG: SQLite detected - TEXT is default for profile_picture_url")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile picture column updated to support base64 data",
            "column_type": "TEXT",
            "status": "success"
        })
    except Exception as e:
        print(f"DEBUG: Error updating column: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e), "status": "failed"}), 500

@app.get("/update_rider_prices")
def update_rider_prices():
    """Update rider prices based on 2025 point standings"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Read point standings file
        with open('point standings 2025.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the data
        riders_data = {
            '450cc': {},
            '250cc': {}
        }
        
        sections = content.split('\n\n')
        current_class = None
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            # Check if this is a class header
            if lines[0].lower() in ['250 west', '250 east', '450 point standings']:
                if '250' in lines[0].lower():
                    current_class = '250cc'
                elif '450' in lines[0].lower():
                    current_class = '450cc'
                continue
            
            # Parse rider data
            if current_class and len(lines) > 1:
                for line in lines[1:]:  # Skip header line
                    if not line.strip():
                        continue
                        
                    # Parse format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        try:
                            position = int(parts[0])
                            name_part = parts[1]
                            points = int(parts[-1]) if parts[-1].isdigit() else 0
                            
                            # Clean up name (remove duplicates)
                            name = name_part
                            if len(name) > 20:  # Likely has duplicate name
                                # Find the middle point and split
                                mid = len(name) // 2
                                for i in range(mid-5, mid+5):
                                    if i < len(name) and name[i].isupper():
                                        name = name[:i]
                                        break
                            
                            riders_data[current_class][name] = {
                                'position': position,
                                'points': points
                            }
                        except (ValueError, IndexError):
                            continue
        
        # Calculate prices and update database
        updated_riders = []
        
        for class_name, riders in riders_data.items():
            for name, data in riders.items():
                position = data['position']
                points = data['points']
                
                # Calculate price based on position and points
                if class_name == '450cc':
                    if position <= 5:
                        price = 500000  # Top 5 riders
                    elif position <= 10:
                        price = 400000  # Top 10 riders
                    elif position <= 15:
                        price = 300000  # Top 15 riders
                    elif position <= 20:
                        price = 200000  # Top 20 riders
                    elif points > 50:
                        price = 150000  # Some points
                    elif points > 0:
                        price = 100000  # Few points
                    else:
                        price = 50000   # No points
                else:  # 250cc
                    if position <= 5:
                        price = 300000  # Top 5 riders
                    elif position <= 10:
                        price = 250000  # Top 10 riders
                    elif position <= 15:
                        price = 200000  # Top 15 riders
                    elif position <= 20:
                        price = 150000  # Top 20 riders
                    elif points > 30:
                        price = 100000  # Some points
                    elif points > 0:
                        price = 75000   # Few points
                    else:
                        price = 50000   # No points
                
                # Update rider in database
                rider = Rider.query.filter_by(name=name, class_name=class_name).first()
                if rider:
                    old_price = rider.price
                    rider.price = price
                    updated_riders.append({
                        'name': name,
                        'class': class_name,
                        'position': position,
                        'points': points,
                        'old_price': old_price,
                        'new_price': price
                    })
        
        db.session.commit()
        
        return jsonify({
            "message": f"Updated prices for {len(updated_riders)} riders based on 2025 standings",
            "updated_riders": updated_riders
        })
        
    except Exception as e:
        print(f"Error updating rider prices: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/import_all_2025_riders_fixed")
def import_all_2025_riders_fixed():
    """Import all riders from 2025 point standings with proper data"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Read point standings file
        with open('point standings 2025.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the data
        riders_data = {
            '450cc': {},
            '250cc': {}
        }
        
        sections = content.split('\n\n')
        current_class = None
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            # Check if this is a class header
            if lines[0].lower() in ['250 west', '250 east', '450 point standings']:
                if '250' in lines[0].lower():
                    current_class = '250cc'
                elif '450' in lines[0].lower():
                    current_class = '450cc'
                continue
            
            # Parse rider data
            if current_class and len(lines) > 1:
                for line in lines[1:]:  # Skip header line
                    if not line.strip():
                        continue
                        
                    # Parse format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        try:
                            position = int(parts[0])
                            name_part = parts[1]
                            points = int(parts[-1]) if parts[-1].isdigit() else 0
                            
                            # Clean up name (remove duplicates) - SUPER IMPROVED VERSION
                            name = name_part.strip()
                            
                            # Method 1: Check for exact duplicate patterns like "Drew AdamsDrew Adams"
                            if len(name) > 15:  # Likely has duplicate name
                                # Find the middle point and look for capital letters
                                mid = len(name) // 2
                                for i in range(mid-3, mid+3):
                                    if i < len(name) and name[i].isupper() and i > 0:
                                        # Check if this looks like a duplicate
                                        first_part = name[:i]
                                        second_part = name[i:]
                                        if first_part == second_part:
                                            name = first_part
                                            break
                                        # Also check if second part starts with first part
                                        elif second_part.startswith(first_part):
                                            name = first_part
                                            break
                            
                            # Method 2: Check for word-level duplicates
                            words = name.split()
                            if len(words) >= 4:  # At least 4 words suggests duplication
                                mid = len(words) // 2
                                first_half = words[:mid]
                                second_half = words[mid:]
                                if first_half == second_half:
                                    name = ' '.join(first_half)
                            
                            # Method 3: Remove any remaining obvious duplicates
                            if ' ' in name:
                                parts = name.split(' ')
                                if len(parts) >= 2:
                                    # Check if first two words repeat
                                    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
                                        name = f"{parts[0]} {parts[1]}"
                                    # Check if the name is just repeated
                                    elif len(parts) == 2 and parts[0] == parts[1]:
                                        name = parts[0]
                            
                            riders_data[current_class][name] = {
                                'position': position,
                                'points': points
                            }
                        except (ValueError, IndexError):
                            continue
        
        # Import riders into database with PROPER DATA
        imported_riders = []
        updated_riders = []
        
        for class_name, riders in riders_data.items():
            for name, data in riders.items():
                position = data['position']
                points = data['points']
                
                # Calculate price based on position and points
                if class_name == '450cc':
                    # 450cc riders: $50k base + $10k per point + position bonus
                    price = 50000 + (points * 1000) + max(0, (50 - position) * 5000)
                else:
                    # 250cc riders: $10k base + $500 per point + position bonus
                    price = 10000 + (points * 500) + max(0, (30 - position) * 2000)
                
                # Check if rider already exists
                existing_rider = Rider.query.filter_by(name=name, class_name=class_name).first()
                
                if existing_rider:
                    # Update existing rider with better data
                    old_price = existing_rider.price
                    existing_rider.price = price
                    
                    # Update rider number and bike brand if they're still default values
                    if existing_rider.rider_number is None or existing_rider.rider_number == 0:
                        existing_rider.rider_number = min(position * 10, 999) if position <= 50 else 100 + position
                    
                    if existing_rider.bike_brand == 'Unknown':
                        bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
                        existing_rider.bike_brand = bike_brands[position % len(bike_brands)]
                    
                    # Update coast for 250cc riders
                    if class_name == '250cc':
                        existing_rider.coast_250 = 'east' if position % 2 == 0 else 'west'
                    
                    updated_riders.append({
                        'name': name,
                        'class': class_name,
                        'position': position,
                        'points': points,
                        'old_price': old_price,
                        'new_price': price,
                        'rider_number': existing_rider.rider_number,
                        'bike_brand': existing_rider.bike_brand
                    })
                else:
                    # Create new rider with realistic data
                    # Generate rider number based on position (1-999)
                    rider_number = min(position * 10, 999) if position <= 50 else 100 + position
                    
                    # Assign bike brand based on position (realistic distribution)
                    bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
                    bike_brand = bike_brands[position % len(bike_brands)]
                    
                    # Set coast for 250cc riders
                    coast_250 = 'east' if class_name == '250cc' and position % 2 == 0 else 'west' if class_name == '250cc' else None
                    
                    new_rider = Rider(
                        name=name,
                        class_name=class_name,
                        price=price,
                        rider_number=rider_number,
                        bike_brand=bike_brand,
                        coast_250=coast_250
                    )
                    db.session.add(new_rider)
                    imported_riders.append({
                        'name': name,
                        'class': class_name,
                        'position': position,
                        'points': points,
                        'price': price,
                        'rider_number': rider_number,
                        'bike_brand': bike_brand
                    })
        
        db.session.commit()
        
        return jsonify({
            "message": f"FIXED: Imported {len(imported_riders)} new riders and updated {len(updated_riders)} existing riders with proper data",
            "imported_riders": imported_riders[:10],  # Show first 10
            "updated_riders": updated_riders[:10],    # Show first 10
            "total_450cc": len(riders_data['450cc']),
            "total_250cc": len(riders_data['250cc'])
        })
        
    except Exception as e:
        print(f"Error importing 2025 riders: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/fix_existing_riders")
def fix_existing_riders():
    """Fix existing riders in database - update names, numbers, and bike brands"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all riders from database
        all_riders = Rider.query.all()
        fixed_count = 0
        
        for rider in all_riders:
            original_name = rider.name
            fixed_name = original_name
            
            # Fix name duplicates using the same logic as import function
            if len(fixed_name) > 15:  # Likely has duplicate name
                # Find the middle point and look for capital letters
                mid = len(fixed_name) // 2
                for i in range(mid-3, mid+3):
                    if i < len(fixed_name) and fixed_name[i].isupper() and i > 0:
                        # Check if this looks like a duplicate
                        first_part = fixed_name[:i]
                        second_part = fixed_name[i:]
                        if first_part == second_part:
                            fixed_name = first_part
                            break
                        # Also check if second part starts with first part
                        elif second_part.startswith(first_part):
                            fixed_name = first_part
                            break
            
            # Fix word-level duplicates
            words = fixed_name.split()
            if len(words) >= 4:  # At least 4 words suggests duplication
                mid = len(words) // 2
                first_half = words[:mid]
                second_half = words[mid:]
                if first_half == second_half:
                    fixed_name = ' '.join(first_half)
            
            # Remove any remaining obvious duplicates
            if ' ' in fixed_name:
                parts = fixed_name.split(' ')
                if len(parts) >= 2:
                    # Check if first two words repeat
                    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
                        fixed_name = f"{parts[0]} {parts[1]}"
                    # Check if the name is just repeated
                    elif len(parts) == 2 and parts[0] == parts[1]:
                        fixed_name = parts[0]
            
            # Update rider if name was fixed
            if fixed_name != original_name:
                rider.name = fixed_name
                fixed_count += 1
            
            # Fix rider number if it's None or 0
            if rider.rider_number is None or rider.rider_number == 0:
                # Generate a reasonable number based on name hash
                import hashlib
                hash_val = int(hashlib.md5(fixed_name.encode()).hexdigest()[:8], 16)
                rider.rider_number = (hash_val % 999) + 1
            
            # Fix bike brand if it's Unknown
            if rider.bike_brand == 'Unknown':
                bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
                import hashlib
                hash_val = int(hashlib.md5(fixed_name.encode()).hexdigest()[:8], 16)
                rider.bike_brand = bike_brands[hash_val % len(bike_brands)]
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with duplicate names and updated all riders with proper numbers and bike brands",
            "total_riders": len(all_riders),
            "fixed_names": fixed_count
        })
        
    except Exception as e:
        print(f"Error fixing existing riders: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/fix_rider_coasts")
def fix_rider_coasts():
    """Fix coast assignments for 250cc riders based on point standings 2025.txt"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Read point standings file to get correct coast assignments
        with open('point standings 2025.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the data to extract east/west riders
        sections = content.split('\n\n')
        east_riders = []
        west_riders = []
        current_coast = None
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            # Check if this is a coast header
            if lines[0].lower() in ['250 west', '250 east']:
                current_coast = lines[0].lower().replace('250 ', '')
                continue
            
            # Parse rider data
            if current_coast and len(lines) > 1:
                for line in lines[1:]:  # Skip header line
                    if not line.strip():
                        continue
                        
                    # Parse format: "1	Haiden DeeganHaiden Deegan	Temecula, CAUnited States	221"
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        try:
                            name_part = parts[1]
                            
                            # Clean up name (remove duplicates) - same logic as import
                            name = name_part.strip()
                            if len(name) > 15:  # Likely has duplicate name
                                mid = len(name) // 2
                                for i in range(mid-3, mid+3):
                                    if i < len(name) and name[i].isupper() and i > 0:
                                        first_part = name[:i]
                                        second_part = name[i:]
                                        if first_part == second_part:
                                            name = first_part
                                            break
                                        elif second_part.startswith(first_part):
                                            name = first_part
                                            break
                            
                            # Additional cleanup
                            if name.endswith(name[:len(name)//2]):
                                name = name[:len(name)//2]
                            
                            words = name.split()
                            if len(words) >= 4:
                                mid = len(words) // 2
                                first_half = words[:mid]
                                second_half = words[mid:]
                                if first_half == second_half:
                                    name = ' '.join(first_half)
                            
                            if ' ' in name:
                                parts = name.split(' ')
                                if len(parts) >= 2:
                                    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
                                        name = f"{parts[0]} {parts[1]}"
                                    elif len(parts) == 2 and parts[0] == parts[1]:
                                        name = parts[0]
                            
                            # Add to appropriate coast list
                            if current_coast == 'east':
                                east_riders.append(name)
                            elif current_coast == 'west':
                                west_riders.append(name)
                                
                        except (ValueError, IndexError):
                            continue
        
        # Fix East riders
        east_fixed = 0
        for name in east_riders:
            rider = Rider.query.filter_by(name=name, class_name="250cc").first()
            if rider:
                if rider.coast_250 != "east":
                    rider.coast_250 = "east"
                    east_fixed += 1
        
        # Fix West riders  
        west_fixed = 0
        for name in west_riders:
            rider = Rider.query.filter_by(name=name, class_name="250cc").first()
            if rider:
                if rider.coast_250 != "west":
                    rider.coast_250 = "west"
                    west_fixed += 1
        
        # Set remaining 250cc riders to "both" if they don't have coast set
        remaining_fixed = 0
        all_250_riders = Rider.query.filter_by(class_name="250cc").all()
        for rider in all_250_riders:
            if not rider.coast_250:
                rider.coast_250 = "both"
                remaining_fixed += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed coast assignments from point standings: {east_fixed} East riders, {west_fixed} West riders, {remaining_fixed} set to 'both'",
            "east_riders_found": len(east_riders),
            "west_riders_found": len(west_riders),
            "east_fixed": east_fixed,
            "west_fixed": west_fixed,
            "remaining_fixed": remaining_fixed,
            "total_250cc": len(all_250_riders)
        })
        
    except Exception as e:
        print(f"Error fixing rider coasts: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/debug_rider_coasts")
def debug_rider_coasts():
    """Debug coast assignments for 250cc riders"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all 250cc riders
        riders_250 = Rider.query.filter_by(class_name="250cc").all()
        
        # Group by coast
        coast_groups = {}
        for rider in riders_250:
            coast = rider.coast_250 or "None"
            if coast not in coast_groups:
                coast_groups[coast] = []
            coast_groups[coast].append(f"{rider.name} (#{rider.rider_number})")
        
        # Check specific riders
        tom_vialle = Rider.query.filter_by(name="Tom Vialle", class_name="250cc").first()
        haiden_deegan = Rider.query.filter_by(name="Haiden Deegan", class_name="250cc").first()
        
        result = f"""
        <h1>250cc Rider Coast Debug</h1>
        <p><strong>Total 250cc riders:</strong> {len(riders_250)}</p>
        
        <h2>Coast Distribution:</h2>
        """
        
        for coast, riders in coast_groups.items():
            result += f"<h3>{coast}: {len(riders)} riders</h3><ul>"
            for rider in riders[:10]:  # Show first 10
                result += f"<li>{rider}</li>"
            if len(riders) > 10:
                result += f"<li>... and {len(riders) - 10} more</li>"
            result += "</ul>"
        
        result += f"""
        <h2>Specific Riders:</h2>
        <p><strong>Tom Vialle:</strong> {tom_vialle.coast_250 if tom_vialle else 'Not found'}</p>
        <p><strong>Haiden Deegan:</strong> {haiden_deegan.coast_250 if haiden_deegan else 'Not found'}</p>
        """
        
        return result
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/profile/<int:user_id>")
def view_user_profile(user_id):
    """View another user's profile"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        # Get the user to view
        target_user = User.query.get(user_id)
        if not target_user:
            flash("Användaren hittades inte.", "error")
            return redirect(url_for("index"))
        
        # Don't allow viewing your own profile through this route
        if target_user.id == session["user_id"]:
            return redirect(url_for("profile_page"))
        
        # Get user's season team
        season_team = SeasonTeam.query.filter_by(user_id=user_id).first()
        team_riders = []
        if season_team:
            try:
                rs = (
                    db.session.query(Rider)
                    .join(SeasonTeamRider, Rider.id == SeasonTeamRider.rider_id)
                    .filter(SeasonTeamRider.season_team_id == season_team.id)
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
                        "image_url": r.image_url or None,
                    }
                    for r in rs
                ]
            except Exception as e:
                print(f"Error getting team riders: {e}")
                team_riders = []
        
        # Get user's recent picks for current race
        current_picks_450 = []
        current_picks_250 = []
        upcoming_race = None
        picks_locked = False
        
        try:
            today = get_today()
            upcoming_race = Competition.query.filter(
                Competition.event_date >= today
            ).order_by(Competition.event_date).first()
            
            if upcoming_race:
                # Check if picks are locked (2 hours before race)
                race_time_str = "20:00"  # 8pm local time
                race_hour, race_minute = map(int, race_time_str.split(':'))
                race_date = upcoming_race.event_date
                race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=race_hour, minute=race_minute))
                
                # Convert to UTC for countdown calculation
                timezone_offsets = {
                    'America/Los_Angeles': -8,  # PST
                    'America/Denver': -7,       # MST  
                    'America/Phoenix': -7,      # MST (no DST)
                    'America/Chicago': -6,      # CST
                    'America/New_York': -5      # EST
                }
                
                timezone = getattr(upcoming_race, 'timezone', 'America/Los_Angeles')
                utc_offset = timezone_offsets.get(timezone, -8)
                race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
                
                # Check if picks are locked (2 hours before race)
                current_time = get_current_time()
                time_to_deadline = race_datetime_utc - timedelta(hours=2) - current_time
                picks_locked = time_to_deadline.total_seconds() <= 0
                
                race_picks = RacePick.query.filter_by(
                    user_id=user_id, 
                    competition_id=upcoming_race.id
                ).order_by(RacePick.predicted_position).all()
                
                # Only show picks if they are locked (after deadline)
                if picks_locked:
                    for pick in race_picks:
                        rider = Rider.query.get(pick.rider_id)
                        if rider:
                            pick_data = {
                                "position": pick.predicted_position,
                                "rider_name": rider.name,
                                "rider_number": rider.rider_number,
                                "class": rider.class_name
                            }
                            
                            if rider.class_name == "450cc":
                                current_picks_450.append(pick_data)
                            elif rider.class_name == "250cc":
                                current_picks_250.append(pick_data)
                else:
                    print(f"DEBUG: Picks not locked yet, hiding other user's picks for security")
        except Exception as e:
            print(f"Error getting user picks: {e}")
        
        return render_template(
            "user_profile.html",
            target_user=target_user,
            season_team=season_team,
            team_riders=team_riders,
            current_picks_450=current_picks_450,
            current_picks_250=current_picks_250,
            upcoming_race=upcoming_race,
            picks_locked=picks_locked,
            current_user_id=session["user_id"]
        )
        
    except Exception as e:
        print(f"Error viewing user profile: {e}")
        flash("Ett fel uppstod vid visning av profilen.", "error")
        return redirect(url_for("index"))

@app.get("/fix_column_now")
def fix_column_now():
    """Emergency fix for profile picture column - no login required"""
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        # Check if we need to alter the column type
        if 'postgresql' in str(db.engine.url):
            # PostgreSQL syntax - alter column type
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN profile_picture_url TYPE TEXT;"))
            print("DEBUG: Changed profile_picture_url column to TEXT")
            db.session.commit()
            return jsonify({
                "message": "Profile picture column updated to TEXT - base64 images will now work!",
                "status": "success"
            })
        else:
            return jsonify({
                "message": "SQLite detected - TEXT is default, column should already support base64",
                "status": "info"
            })
    except Exception as e:
        print(f"DEBUG: Error updating column: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"error": str(e), "status": "failed"}), 500
        
        # Add missing columns to users table
        columns_to_add = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_rider VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
        ]
        
        for sql in columns_to_add:
            try:
                db.session.execute(db.text(sql))
                print(f"DEBUG: Executed: {sql}")
            except Exception as e:
                print(f"DEBUG: Error executing {sql}: {e}")
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile columns added successfully",
            "columns_added": len(columns_to_add)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error adding profile columns: {e}")
        return jsonify({
            "error": f"Failed to add profile columns: {str(e)}"
        }), 500

@app.get("/fix_missing_images")
def fix_missing_images():
    """Fix missing rider images by clearing invalid image_urls"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: fix_missing_images called")
    
    try:
        riders = Rider.query.all()
        fixed_count = 0
        
        for rider in riders:
            if rider.image_url:
                # Check if image file exists
                image_path = os.path.join(app.static_folder, rider.image_url)
                if not os.path.exists(image_path):
                    print(f"DEBUG: Image file missing for {rider.name}: {rider.image_url}")
                    rider.image_url = None
                    fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with missing images",
            "fixed_count": fixed_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error fixing missing images: {e}")
        return jsonify({
            "error": f"Failed to fix missing images: {str(e)}"
        }), 500

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
        default_sim_date = SimDate(value='2026-10-06')
        db.session.add(default_sim_date)
        
        db.session.commit()
        
        return f"""
        <h1>Database Fixed!</h1>
        <p>Created all tables and data successfully!</p>
        <p><strong>Competitions:</strong> {len(competitions)}</p>
        <p><strong>Riders:</strong> {len(all_riders)}</p>
        <p><strong>Sim Date:</strong> 2026-10-06</p>
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
        {'name': 'Anaheim 1', 'event_date': '2026-01-10', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
        {'name': 'San Diego', 'event_date': '2026-01-17', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
        {'name': 'Anaheim 2', 'event_date': '2026-01-24', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
        {'name': 'Houston', 'event_date': '2026-01-31', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
        {'name': 'Glendale', 'event_date': '2026-02-07', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Phoenix'},
        {'name': 'Seattle', 'event_date': '2026-02-14', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
        
        # Eastern Regional 250SX Championship
        {'name': 'Arlington', 'event_date': '2026-02-21', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
        {'name': 'Daytona', 'event_date': '2026-02-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
        {'name': 'Indianapolis', 'event_date': '2026-03-07', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
        {'name': 'Birmingham', 'event_date': '2026-03-21', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
        {'name': 'Detroit', 'event_date': '2026-03-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
        {'name': 'St. Louis', 'event_date': '2026-04-04', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Chicago'},
        {'name': 'Nashville', 'event_date': '2026-04-11', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Chicago'},
        {'name': 'Cleveland', 'event_date': '2026-04-18', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
        {'name': 'Philadelphia', 'event_date': '2026-04-25', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
        {'name': 'Denver', 'event_date': '2026-05-02', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Denver'},
        {'name': 'Salt Lake City', 'event_date': '2026-05-09', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.5, 'timezone': 'America/Denver'}
    ]
    
    for comp_data in competitions:
        comp = Competition(
            name=comp_data['name'],
            event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
            coast_250=comp_data['coast_250'],
            series=comp_data['series'],
            point_multiplier=comp_data['point_multiplier'],
            is_triple_crown=comp_data.get('is_triple_crown', False),
            timezone=comp_data.get('timezone', 'America/New_York')
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
        
        with open('data/smx_2026_riders_numbers_best_effort.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=',')
            
            for row in reader:
                # Skip empty rows or rows with missing essential data
                if not row.get('Förare') or not row.get('Klass (best-effort)') or row.get('Förare').strip() == '' or row.get('Klass (best-effort)').strip() == '':
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
                if class_name == '250cc':
                    if row.get('Coast (250 East/West)'):
                        coast = row['Coast (250 East/West)'].lower()
                        if coast in ['east', 'west']:
                            coast_250 = coast
                    else:
                        # Default coast assignment for 250cc riders without explicit coast
                        # This is a temporary solution - in reality, you'd need proper coast data
                        # For now, assign alternating east/west based on rider number
                        if rider_number:
                            coast_250 = 'east' if rider_number % 2 == 0 else 'west'
                        else:
                            coast_250 = 'east'  # Default fallback
                
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
                
                # Build image URL: riders/{number}_{name}.png (or .jpg fallback)
                image_url = None
                if rider_number:
                    name_slug = row['Förare'].lower().replace(" ", "_")
                    # Try PNG first, then JPG
                    potential_urls = [
                        f'riders/{rider_number}_{name_slug}.png',
                        f'riders/{rider_number}_{name_slug}.jpg'
                    ]
                    # We'll use the first format (PNG) as default, backend will serve what exists
                    image_url = potential_urls[0]
                
                # Create rider data
                rider_data = {
                    'name': row['Förare'],
                    'class_name': class_name,
                    'rider_number': rider_number,
                    'bike_brand': bike_brand,
                    'price': price,
                    'coast_250': coast_250,
                    'image_url': image_url
                }
                
                riders.append(rider_data)
        
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
    
    # Create all Supercross 2026 competitions
    if Competition.query.count() == 0:
        competitions = [
            # Western Regional 250SX Championship
            {'name': 'Anaheim 1', 'event_date': '2026-01-10', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
            {'name': 'San Diego', 'event_date': '2026-01-17', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
            {'name': 'Anaheim 2', 'event_date': '2026-01-24', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
            {'name': 'Houston', 'event_date': '2026-01-31', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
            {'name': 'Glendale', 'event_date': '2026-02-07', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Phoenix'},
            {'name': 'Seattle', 'event_date': '2026-02-14', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Los_Angeles'},
            
            # Eastern Regional 250SX Championship
            {'name': 'Arlington', 'event_date': '2026-02-21', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
            {'name': 'Daytona', 'event_date': '2026-02-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
            {'name': 'Indianapolis', 'event_date': '2026-03-07', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
            {'name': 'Birmingham', 'event_date': '2026-03-21', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'is_triple_crown': True, 'timezone': 'America/Chicago'},
            {'name': 'Detroit', 'event_date': '2026-03-28', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
            {'name': 'St. Louis', 'event_date': '2026-04-04', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Chicago'},
            {'name': 'Nashville', 'event_date': '2026-04-11', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Chicago'},
            {'name': 'Cleveland', 'event_date': '2026-04-18', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
            {'name': 'Philadelphia', 'event_date': '2026-04-25', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/New_York'},
            {'name': 'Denver', 'event_date': '2026-05-02', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0, 'timezone': 'America/Denver'},
            {'name': 'Salt Lake City', 'event_date': '2026-05-09', 'coast_250': 'both', 'series': 'SX', 'point_multiplier': 1.5, 'timezone': 'America/Denver'}
        ]
        
        for comp_data in competitions:
            comp = Competition(
                name=comp_data['name'],
                event_date=datetime.strptime(comp_data['event_date'], '%Y-%m-%d').date(),
                coast_250=comp_data['coast_250'],
                series=comp_data['series'],
                point_multiplier=comp_data['point_multiplier'],
                is_triple_crown=comp_data.get('is_triple_crown', False),
                timezone=comp_data.get('timezone', 'America/New_York')
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
        
        for i, rider_data in enumerate(all_riders):
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
            print("Starting database initialization...")
            
            # Create tables only if they don't exist
            try:
                db.create_all()
                print("Database tables created successfully")
            except Exception as e:
                print(f"Warning: Could not create tables (they may already exist): {e}")
            
            # Handle timezone column migration for existing competitions
            try:
                # Check if timezone column exists, if not add it (PostgreSQL compatible)
                if 'postgresql' in str(db.engine.url):
                    # PostgreSQL syntax
                    result = db.session.execute(db.text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'competitions' AND column_name = 'timezone'
                    """))
                    columns = [row[0] for row in result.fetchall()]
                    
                    if not columns:  # timezone column doesn't exist
                        print("Adding timezone column to competitions table...")
                        db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN timezone VARCHAR(50)"))
                        db.session.commit()
                        print("Timezone column added successfully")
                else:
                    # SQLite syntax (fallback)
                    result = db.session.execute(db.text("PRAGMA table_info(competitions)"))
                    columns = [row[1] for row in result.fetchall()]
                    
                    if 'timezone' not in columns:
                        print("Adding timezone column to competitions table...")
                        db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN timezone VARCHAR(50)"))
                        db.session.commit()
                        print("Timezone column added successfully")
                    
                    # Update existing competitions with timezone data
                    competitions = Competition.query.all()
                    for comp in competitions:
                        comp.timezone = get_track_timezone(comp.name)
                    db.session.commit()
                    print(f"Updated {len(competitions)} competitions with timezone data")
            except Exception as e:
                print(f"Warning: Could not migrate timezone column: {e}")
                # Continue anyway, the column will be added when creating new competitions
            
            # Only create test data if database is completely empty AND we're in development
            try:
                user_count = User.query.count()
                competition_count = Competition.query.count()
                
                # Only create test data if both users and competitions are empty
                if user_count == 0 and competition_count == 0:
                    print("Database is empty, creating test data...")
                    create_test_data()
                    print("Test data created successfully")
                else:
                    print(f"Database has {user_count} users and {competition_count} competitions, skipping test data creation")
            except Exception as e:
                print(f"Warning: Could not create test data: {e}")
                # Don't try to create test data if there's an error
                pass
            
            print("Database initialized successfully")
            return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Initialize database for Render
# NOTE: Set FLASK_ENV=production in Render environment variables to prevent test data creation
print("Starting database initialization...")
init_success = init_database()
if init_success:
    print("✅ Database initialization completed successfully - pipeline minutes test")
    
    # Auto-create track map images only if none exist
    print("🖼️ Checking track map images...")
    try:
        with app.app_context():
            # Only create track map images if none exist
            existing_images = CompetitionImage.query.count()
            if existing_images == 0:
                print("No track map images found, creating them...")
                
                COMP_TO_IMAGE = {
                    "Anaheim 1": "anaheim1.jpg",
                    "San Diego": "sandiego.jpg", 
                    "Anaheim 2": "anaheim2.jpg",
                    "Houston": "houston.jpg",
                    "Glendale": "glendale.jpg",
                    "Seattle": "seattle.jpg",
                    "Arlington": "arlington.jpg",
                    "Daytona": "daytona.jpg",
                    "Indianapolis": "indianapolis.jpg",
                    "Birmingham": "birmingham.jpg",
                    "Detroit": "detroit.jpg",
                    "St. Louis": "stlouis.jpg",
                    "Nashville": "nashville.jpg",
                    "Cleveland": "cleveland.jpg",
                    "Philadelphia": "philadelphia.jpg",
                    "Denver": "denver.jpg",
                    "Salt Lake City": "saltlakecity.jpg"
                }
                
                competitions = Competition.query.all()
                created = 0
                for comp in competitions:
                    if comp.name in COMP_TO_IMAGE:
                        image_url = f"trackmaps/compressed/{COMP_TO_IMAGE[comp.name]}"
                        ci = CompetitionImage(competition_id=comp.id, image_url=image_url, sort_order=0)
                        db.session.add(ci)
                        created += 1
                
                db.session.commit()
                print(f"✅ Auto-created {created} track map records on startup")
            else:
                print(f"Found {existing_images} existing track map images, skipping creation")
    except Exception as e:
        print(f"❌ Error auto-creating track maps on startup: {e}")
else:
    print("❌ Database initialization failed")

@app.get("/create_test_data")
def create_test_data_route():
    """Manually create test data - useful for development"""
    if session.get("username") != "test":
        return redirect(url_for("login"))
    
    try:
        with app.app_context():
            # Check if data already exists
            user_count = User.query.count()
            competition_count = Competition.query.count()
            rider_count = Rider.query.count()
            
            if user_count > 0 or competition_count > 0 or rider_count > 0:
                return f"""
                <h1>Data Already Exists</h1>
                <p>Database has {user_count} users, {competition_count} competitions, and {rider_count} riders.</p>
                <p><a href="/admin">Go to Admin</a></p>
                <p><a href="/force_recreate_data">Force Recreate All Data</a></p>
                """
            
            # Create test data
            create_test_data()
            return """
            <h1>Test Data Created Successfully!</h1>
            <p>Test user, competitions, and riders have been created.</p>
            <p><a href="/admin">Go to Admin</a></p>
            """
    except Exception as e:
        return f"""
        <h1>Error Creating Test Data</h1>
        <p>Error: {e}</p>
        <p><a href="/admin">Go to Admin</a></p>
        """

@app.get("/force_recreate_data")
def force_recreate_data():
    """Force recreate all data - clears everything and recreates"""
    if session.get("username") != "test":
        return redirect(url_for("login"))
    
    try:
        with app.app_context():
            # BACKUP USER PROFILE DATA BEFORE DELETION
            print("Backing up user profile data...")
            users = User.query.all()
            profile_backups = []
            for user in users:
                backup = {
                    'username': user.username,
                    'password_hash': user.password_hash,
                    'display_name': getattr(user, 'display_name', None),
                    'profile_picture_url': getattr(user, 'profile_picture_url', None),
                    'bio': getattr(user, 'bio', None),
                    'favorite_rider': getattr(user, 'favorite_rider', None),
                    'favorite_team': getattr(user, 'favorite_team', None),
                    'created_at': getattr(user, 'created_at', None)
                }
                profile_backups.append(backup)
            
            print(f"Backed up {len(profile_backups)} user profiles")
            
            # Clear all data
            print("Clearing all existing data...")
            db.session.query(CompetitionImage).delete()
            db.session.query(CompetitionRiderStatus).delete()
            db.session.query(CompetitionScore).delete()
            db.session.query(HoleshotPick).delete()
            db.session.query(WildcardPick).delete()
            db.session.query(RacePick).delete()
            db.session.query(SeasonTeamRider).delete()
            db.session.query(SeasonTeam).delete()
            db.session.query(Rider).delete()
            db.session.query(Competition).delete()
            db.session.query(User).delete()
            db.session.commit()
            
            # RESTORE USER PROFILE DATA
            print("Restoring user profile data...")
            for backup in profile_backups:
                user = User(
                    username=backup['username'],
                    password_hash=backup['password_hash']
                )
                db.session.add(user)
                db.session.flush()  # Get the user ID
                
                # Restore profile data if columns exist
                if backup['display_name']:
                    user.display_name = backup['display_name']
                if backup['profile_picture_url']:
                    user.profile_picture_url = backup['profile_picture_url']
                if backup['bio']:
                    user.bio = backup['bio']
                if backup['favorite_rider']:
                    user.favorite_rider = backup['favorite_rider']
                if backup['favorite_team']:
                    user.favorite_team = backup['favorite_team']
                if backup['created_at']:
                    user.created_at = backup['created_at']
            
            db.session.commit()
            print(f"Restored {len(profile_backups)} user profiles with their data")
            
            # Create fresh data
            print("Creating fresh data...")
            create_test_data()
            
            return """
            <h1>All Data Recreated Successfully!</h1>
            <p>All data has been cleared and recreated with fresh test data.</p>
            <p><a href="/admin">Go to Admin</a></p>
            <p><a href="/trackmaps">Go to Track Maps</a></p>
            """
    except Exception as e:
        return f"""
        <h1>Error Recreating Data</h1>
        <p>Error: {e}</p>
        <p><a href="/admin">Go to Admin</a></p>
        """

@app.get("/debug_riders")
def debug_riders():
    """Debug riders in database"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        all_riders = Rider.query.all()
        riders_450 = [r for r in all_riders if r.class_name == '450cc']
        riders_250 = [r for r in all_riders if r.class_name == '250cc']
        
        result = f"""
        <h1>Riders Debug</h1>
        <p><strong>Total riders:</strong> {len(all_riders)}</p>
        <p><strong>450cc riders:</strong> {len(riders_450)}</p>
        <p><strong>250cc riders:</strong> {len(riders_250)}</p>
        
        <h2>450cc Riders (first 10):</h2>
        <ul>
        """
        
        for rider in riders_450[:10]:
            result += f"<li>{rider.name} (#{rider.rider_number}) - {rider.bike_brand} - ${rider.price}</li>"
        
        result += "</ul>"
        
        result += """
        <h2>250cc Riders (first 10):</h2>
        <ul>
        """
        
        for rider in riders_250[:10]:
            result += f"<li>{rider.name} (#{rider.rider_number}) - {rider.bike_brand} - ${rider.price} - {rider.coast_250}</li>"
        
        result += "</ul>"
        
        return result
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.get("/debug_database")
def debug_database():
    """Debug database configuration and status"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        with app.app_context():
            # Database info
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            db_type = "PostgreSQL" if "postgresql" in db_uri else "SQLite"
            is_memory = ":memory:" in db_uri
            is_render = bool(os.getenv('RENDER'))
            has_database_url = bool(os.getenv('DATABASE_URL'))
            
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Count records in each table
            table_counts = {}
            for table in tables:
                try:
                    result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    table_counts[table] = count
                except Exception as e:
                    table_counts[table] = f"Error: {e}"
            
            # Check specific data for Anaheim 1 (competition_id = 1)
            anaheim1_results = CompetitionResult.query.filter_by(competition_id=1).all()
            anaheim1_holeshots = HoleshotResult.query.filter_by(competition_id=1).all()
            anaheim1_scores = CompetitionScore.query.filter_by(competition_id=1).all()
            anaheim1_picks = RacePick.query.filter_by(competition_id=1).all()
            anaheim1_holeshot_picks = HoleshotPick.query.filter_by(competition_id=1).all()
            anaheim1_wildcard_picks = WildcardPick.query.filter_by(competition_id=1).all()
            
            return f"""
            <h1>Database Debug Information</h1>
            <h2>Configuration:</h2>
            <p><strong>Database Type:</strong> {db_type}</p>
            <p><strong>Database URI:</strong> {db_uri}</p>
            <p><strong>Is Memory Database:</strong> {is_memory}</p>
            <p><strong>Running on Render:</strong> {is_render}</p>
            <p><strong>Has DATABASE_URL:</strong> {has_database_url}</p>
            
            <h2>Tables ({len(tables)}):</h2>
            <ul>
            {''.join([f'<li><strong>{table}:</strong> {table_counts.get(table, "Unknown")} records</li>' for table in tables])}
            </ul>
            
            <h2>Anaheim 1 (Competition ID 1) Data:</h2>
            <ul>
            <li><strong>Results:</strong> {len(anaheim1_results)} records</li>
            <li><strong>Holeshot Results:</strong> {len(anaheim1_holeshots)} records</li>
            <li><strong>Scores:</strong> {len(anaheim1_scores)} records</li>
            <li><strong>Race Picks:</strong> {len(anaheim1_picks)} records</li>
            <li><strong>Holeshot Picks:</strong> {len(anaheim1_holeshot_picks)} records</li>
            <li><strong>Wildcard Picks:</strong> {len(anaheim1_wildcard_picks)} records</li>
            </ul>
            
            <h2>Environment Variables:</h2>
            <p><strong>RENDER:</strong> {os.getenv('RENDER', 'Not set')}</p>
            <p><strong>DATABASE_URL:</strong> {'Set' if os.getenv('DATABASE_URL') else 'Not set'}</p>
            <p><strong>FLASK_ENV:</strong> {os.getenv('FLASK_ENV', 'Not set')}</p>
            
            <hr>
            <p><a href="/admin">Go to Admin</a></p>
            <p><a href="/">Go to Home</a></p>
            <p><a href="/force_recreate_data">Force Recreate All Data</a></p>
            """
    except Exception as e:
        return f"<h1>Error</h1><p>{e}</p>"

@app.get("/clear_anaheim1")
def clear_anaheim1():
    """Clear all data for Anaheim 1 specifically - for debugging"""
    if session.get("username") != "test":
        return redirect(url_for("login"))
    
    try:
        with app.app_context():
            comp_id = 1  # Anaheim 1
            
            # Delete all data for Anaheim 1
            deleted_results = CompetitionResult.query.filter_by(competition_id=comp_id).delete()
            deleted_holeshot_results = HoleshotResult.query.filter_by(competition_id=comp_id).delete()
            deleted_scores = CompetitionScore.query.filter_by(competition_id=comp_id).delete()
            deleted_out_status = CompetitionRiderStatus.query.filter_by(competition_id=comp_id).delete()
            deleted_race_picks = RacePick.query.filter_by(competition_id=comp_id).delete()
            deleted_holeshot_picks = HoleshotPick.query.filter_by(competition_id=comp_id).delete()
            deleted_wildcard_picks = WildcardPick.query.filter_by(competition_id=comp_id).delete()
            
            db.session.commit()
            
            return f"""
            <h1>Anaheim 1 Cleared Successfully!</h1>
            <p>Deleted:</p>
            <ul>
            <li>{deleted_results} race results</li>
            <li>{deleted_holeshot_results} holeshot results</li>
            <li>{deleted_scores} scores</li>
            <li>{deleted_out_status} out statuses</li>
            <li>{deleted_race_picks} race picks</li>
            <li>{deleted_holeshot_picks} holeshot picks</li>
            <li>{deleted_wildcard_picks} wildcard picks</li>
            </ul>
            <p><a href="/admin">Go to Admin</a></p>
            <p><a href="/debug_database">Check Database</a></p>
            """
    except Exception as e:
        return f"<h1>Error</h1><p>{e}</p>"



@app.get("/trackmap_status")
def trackmap_status():
    """Show track map status for debugging"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        with app.app_context():
            competitions = Competition.query.all()
            total_images = CompetitionImage.query.count()
            
            status = f"""
            <h1>Track Map Status</h1>
            <p><strong>Total competitions:</strong> {len(competitions)}</p>
            <p><strong>Total CompetitionImage records:</strong> {total_images}</p>
            <hr>
            <h2>Competitions:</h2>
            """
            
            for comp in competitions:
                images = comp.images.all()
                status += f"<p><strong>{comp.name}</strong> (ID: {comp.id}): {len(images)} images</p>"
                for img in images:
                    status += f"<p>&nbsp;&nbsp;- {img.image_url}</p>"
            
            status += """
            <hr>
            <p><a href="/trackmaps">Go to Track Maps</a></p>
            <p><a href="/force_create_all_trackmaps">Force Create All Track Maps</a></p>
            """
            
            return status
    except Exception as e:
        return f"<h1>Error</h1><p>{e}</p>"

@app.get("/force_create_all_trackmaps")
def force_create_all_trackmaps():
    """Force create all track map images - bypasses existing check"""
    print("FORCE CREATING ALL TRACKMAPS...")
    
    # Clear all existing
    CompetitionImage.query.delete()
    db.session.commit()
    print("Cleared all existing CompetitionImage records")
    
    # Create all 16 manually
    COMP_TO_IMAGE = {
        "Anaheim 1": "anaheim1.jpg",
        "San Diego": "sandiego.jpg", 
        "Anaheim 2": "anaheim2.jpg",
        "Houston": "houston.jpg",
        "Glendale": "glendale.jpg",
        "Seattle": "seattle.jpg",
        "Arlington": "arlington.jpg",
        "Daytona": "daytona.jpg",
        "Indianapolis": "indianapolis.jpg",
        "Birmingham": "birmingham.jpg",
        "Detroit": "detroit.jpg",
        "St. Louis": "stlouis.jpg",
        "Nashville": "nashville.jpg",
        "Cleveland": "cleveland.jpg",
        "Philadelphia": "philadelphia.jpg",
        "Denver": "denver.jpg",
        "Salt Lake City": "saltlakecity.jpg"
    }
    
    competitions = Competition.query.all()
    created = 0
    for comp in competitions:
        if comp.name in COMP_TO_IMAGE:
            image_url = f"trackmaps/compressed/{COMP_TO_IMAGE[comp.name]}"
            ci = CompetitionImage(competition_id=comp.id, image_url=image_url, sort_order=0)
            db.session.add(ci)
            created += 1
            print(f"Created: {comp.name} -> {image_url}")
    
    db.session.commit()
    print(f"FORCE CREATED {created} track map records")
    
    return f"Created {created} track map records. <a href='/trackmaps'>Go to Track Maps</a>"

@app.route("/bulletin")
def bulletin_board():
    """Anslagstavla - visa alla posts"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        # Hämta alla posts (ej borttagna, ej replies) sorterade efter datum (nyaste först)
        try:
            posts = (
                BulletinPost.query
                .filter_by(is_deleted=False, parent_id=None)
                .order_by(BulletinPost.created_at.desc())
                .limit(50)  # Visa max 50 senaste posts
                .all()
            )
        except Exception as e:
            # Fallback if new columns don't exist yet
            posts = (
                BulletinPost.query
                .filter_by(is_deleted=False)
                .order_by(BulletinPost.created_at.desc())
                .limit(50)
                .all()
            )
        
        # Formatera posts för template
        formatted_posts = []
        for post in posts:
            # Hämta reactions för denna post
            reactions = {}
            for reaction in post.reactions:
                if reaction.emoji not in reactions:
                    reactions[reaction.emoji] = []
                reactions[reaction.emoji].append({
                    'user_id': reaction.user_id,
                    'username': reaction.user.username if reaction.user else 'Okänd'
                })
            
            # Hämta replies
            replies = []
            for reply in post.replies:
                if not reply.is_deleted:
                    replies.append({
                        'id': reply.id,
                        'content': reply.content,
                        'author': reply.user.username if reply.user else 'Okänd',
                        'author_display_name': getattr(reply.user, 'display_name', None) or reply.user.username if reply.user else 'Okänd',
                        'created_at': reply.created_at,
                        'is_own_post': reply.user_id == session.get('user_id')
                    })
            
            formatted_posts.append({
                'id': post.id,
                'content': post.content,
                'category': getattr(post, 'category', 'general'),  # Fallback if column doesn't exist
                'author': post.user.username if post.user else 'Okänd',
                'author_display_name': getattr(post.user, 'display_name', None) or post.user.username if post.user else 'Okänd',
                'created_at': post.created_at,
                'is_own_post': post.user_id == session.get('user_id'),
                'is_admin': session.get('username') == 'test',
                'reactions': reactions,
                'replies': replies
            })
        
        return render_template("bulletin.html", posts=formatted_posts)
        
    except Exception as e:
        print(f"Error loading bulletin board: {e}")
        return f"Error loading bulletin board: {str(e)}", 500

@app.post("/bulletin/post")
def create_bulletin_post():
    """Skapa ny post på anslagstavlan"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        category = data.get('category', 'general')
        parent_id = data.get('parent_id')  # For replies
        
        # Validering
        if not content:
            return jsonify({"error": "Innehåll kan inte vara tomt"}), 400
        
        if len(content) > 500:
            return jsonify({"error": "Innehåll kan inte vara längre än 500 tecken"}), 400
        
        # Validera kategori
        valid_categories = ['general', 'tips', 'question', 'discussion']
        if category not in valid_categories:
            category = 'general'
        
        # Skapa ny post
        post = BulletinPost(
            user_id=session['user_id'],
            content=content,
            category=category,
            parent_id=parent_id
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            "message": "Post skapad!" if not parent_id else "Svar skickat!",
            "post": {
                'id': post.id,
                'content': post.content,
                'category': post.category,
                'author': post.user.username if post.user else 'Okänd',
                'author_display_name': getattr(post.user, 'display_name', None) or post.user.username if post.user else 'Okänd',
                'created_at': post.created_at.isoformat(),
                'is_own_post': True,
                'parent_id': post.parent_id
            }
        })
        
    except Exception as e:
        print(f"Error creating bulletin post: {e}")
        return jsonify({"error": str(e)}), 500

@app.delete("/bulletin/post/<int:post_id>")
def delete_bulletin_post(post_id):
    """Ta bort post från anslagstavlan"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        post = BulletinPost.query.get_or_404(post_id)
        
        # Kontrollera att användaren äger posten eller är admin
        if post.user_id != session['user_id'] and session.get('username') != 'test':
            return jsonify({"error": "Du kan bara ta bort dina egna posts"}), 403
        
        # Markera som borttagen istället för att ta bort
        post.is_deleted = True
        db.session.commit()
        
        return jsonify({"message": "Post borttagen!"})
        
    except Exception as e:
        print(f"Error deleting bulletin post: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/bulletin/post/<int:post_id>/reaction")
def add_bulletin_reaction(post_id):
    """Lägg till eller ta bort reaction på post"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        data = request.get_json()
        emoji = data.get('emoji', '').strip()
        
        if not emoji:
            return jsonify({"error": "Emoji krävs"}), 400
        
        # Kontrollera om posten finns
        post = BulletinPost.query.get_or_404(post_id)
        
        # Kontrollera om användaren redan har reagerat med denna emoji
        existing_reaction = BulletinReaction.query.filter_by(
            post_id=post_id,
            user_id=session['user_id'],
            emoji=emoji
        ).first()
        
        if existing_reaction:
            # Ta bort befintlig reaction
            db.session.delete(existing_reaction)
            action = "removed"
        else:
            # Lägg till ny reaction
            reaction = BulletinReaction(
                post_id=post_id,
                user_id=session['user_id'],
                emoji=emoji
            )
            db.session.add(reaction)
            action = "added"
        
        db.session.commit()
        
        # Hämta uppdaterade reactions
        reactions = {}
        for reaction in post.reactions:
            if reaction.emoji not in reactions:
                reactions[reaction.emoji] = []
            reactions[reaction.emoji].append({
                'user_id': reaction.user_id,
                'username': reaction.user.username if reaction.user else 'Okänd'
            })
        
        return jsonify({
            "message": f"Reaction {action}!",
            "reactions": reactions,
            "action": action
        })
        
    except Exception as e:
        print(f"Error handling bulletin reaction: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/fix_bulletin_columns")
def fix_bulletin_columns():
    """Fix missing columns in bulletin_posts table"""
    if session.get('username') != 'test':
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Add missing columns to bulletin_posts table
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE bulletin_posts ADD COLUMN IF NOT EXISTS category VARCHAR(20) DEFAULT 'general'"))
            conn.execute(db.text("ALTER TABLE bulletin_posts ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES bulletin_posts(id)"))
            
            # Create bulletin_reactions table if it doesn't exist
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS bulletin_reactions (
                    id SERIAL PRIMARY KEY,
                    post_id INTEGER NOT NULL REFERENCES bulletin_posts(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    emoji VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(post_id, user_id, emoji)
                )
            """))
            conn.commit()
        
        return jsonify({
            "message": "Bulletin board columns fixed!",
            "added_columns": ["category", "parent_id"],
            "created_table": "bulletin_reactions"
        })
        
    except Exception as e:
        print(f"Error fixing bulletin columns: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/create_global_simulation_table")
def create_global_simulation_table():
    """Create global simulation table for cross-device sync"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Create global_simulation table
        with db.engine.connect() as conn:
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS global_simulation (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    active BOOLEAN DEFAULT FALSE,
                    simulated_time TEXT,
                    start_time TEXT,
                    initial_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        return jsonify({"message": "Global simulation table created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/create_admin")
def create_admin():
    """Create admin user - emergency route"""
    try:
        # Check if test user exists
        existing_user = User.query.filter_by(username='test').first()
        
        if existing_user:
            return jsonify({
                "message": "Admin user 'test' already exists",
                "user_id": existing_user.id,
                "username": existing_user.username
            })
        
        # Create admin user
        admin_user = User(
            username='test',
            password_hash=generate_password_hash('test123'),
            display_name='Admin'
        )
        
        db.session.add(admin_user)
        db.session.commit()
        
        return jsonify({
            "message": "Admin user created successfully!",
            "username": "test",
            "password": "test123",
            "user_id": admin_user.id
        })
        
    except Exception as e:
        print(f"Error creating admin: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/users")
def admin_users():
    """Admin page to manage users"""
    if session.get('username') != 'test':
        return jsonify({"error": "admin_only"}), 403
    
    try:
        users = User.query.all()
        user_list = []
        
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'display_name': getattr(user, 'display_name', None),
                'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None,
                'is_admin': user.username == 'test'
            })
        
        return render_template("admin_users.html", users=user_list)
        
    except Exception as e:
        print(f"Error loading users: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/delete_user/<int:user_id>", methods=['DELETE'])
def delete_user(user_id):
    """Delete a user - admin only"""
    if session.get('username') != 'test':
        return jsonify({"error": "admin_only"}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Don't allow deleting admin user
        if user.username == 'test':
            return jsonify({"error": "Cannot delete admin user"}), 400
        
        # Delete user and all related data
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            "message": f"User '{username}' deleted successfully"
        })
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/cleanup_duplicate_users")
def cleanup_duplicate_users():
    """Remove duplicate test users - keep only the first one"""
    if session.get('username') != 'test':
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find all test users
        test_users = User.query.filter_by(username='test').all()
        
        if len(test_users) <= 1:
            return jsonify({
                "message": "No duplicate test users found",
                "count": len(test_users)
            })
        
        # Keep the first one (oldest), delete the rest
        first_user = test_users[0]
        duplicates = test_users[1:]
        
        deleted_count = 0
        for user in duplicates:
            db.session.delete(user)
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Cleaned up {deleted_count} duplicate test users",
            "kept_user_id": first_user.id,
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        print(f"Error cleaning up duplicate users: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/debug_session")
def debug_session():
    """Debug session data"""
    return jsonify({
        "user_id": session.get("user_id"),
        "username": session.get("username"),
        "is_admin": session.get("username") == "test",
        "all_session": dict(session)
    })

@app.route("/race_countdown")
def race_countdown():
    """Get countdown data for next race"""
    try:
        # Get mode parameter (real or test)
        mode = request.args.get('mode', 'real')
        print(f"DEBUG: race_countdown() called with mode: {mode}")
        
        # Get current time (or simulated time for testing)
        current_time = get_current_time()
        print(f"DEBUG: race_countdown using time: {current_time}")
        
        # Check if we're in simulation mode (use only global database state for consistency)
        simulation_active = False
        print(f"DEBUG: race_countdown - checking global database simulation only")
        
        try:
            # Rollback any existing transaction first
            db.session.rollback()
            
            result = db.session.execute(text("SELECT active FROM global_simulation WHERE id = 1")).fetchone()
            simulation_active = result and result[0] if result else False
            print(f"DEBUG: race_countdown - database simulation_active: {simulation_active}")
        except Exception as e:
            print(f"DEBUG: Error checking global simulation: {e}")
            # Rollback and fallback to app globals if database table doesn't exist
            db.session.rollback()
            simulation_active = hasattr(app, 'global_simulation_active') and app.global_simulation_active
            print(f"DEBUG: race_countdown - app global simulation_active: {simulation_active}")
        
        print(f"DEBUG: race_countdown - final simulation_active: {simulation_active}")
        
        # For real mode, always use real race data
        if mode == 'real':
            simulation_active = False
            print(f"DEBUG: race_countdown - forcing real mode, simulation_active: {simulation_active}")
        # For test mode, always use simulation
        elif mode == 'test':
            simulation_active = True
            print(f"DEBUG: race_countdown - forcing test mode, simulation_active: {simulation_active}")
        
        if simulation_active:
            print(f"DEBUG: race_countdown - ENTERING SIMULATION MODE")
            # Use the same logic as test_countdown for consistency
            # Get the scenario from global database state or use default
            try:
                result = db.session.execute(text("SELECT scenario FROM global_simulation WHERE id = 1")).fetchone()
                scenario = result[0] if result and result[0] else 'race_in_3h'
                print(f"DEBUG: race_countdown - using scenario from database: {scenario}")
            except Exception as e:
                print(f"DEBUG: Error getting scenario from database: {e}")
                scenario = session.get('test_scenario', 'race_in_3h')
                print(f"DEBUG: race_countdown - using scenario from session: {scenario}")
            
            # Create fake race based on scenario - use a fixed future time for the race
            # This ensures the countdown actually counts down
            # Use a fixed base time that doesn't change between calls
            fake_race_base_time = current_time + timedelta(hours=3)  # 3 hours from current simulated time
            fake_race_base_time = fake_race_base_time.replace(minute=0, second=0, microsecond=0)
            print(f"DEBUG: race_countdown - fake_race_base_time: {fake_race_base_time}")
            
            # Adjust fake race time based on scenario
            if scenario == "race_in_3h":
                fake_race_datetime_utc = fake_race_base_time
            elif scenario == "race_in_1h":
                fake_race_datetime_utc = fake_race_base_time - timedelta(hours=2)  # Race in 1h, deadline in -1h
            elif scenario == "race_in_30m":
                fake_race_datetime_utc = fake_race_base_time - timedelta(hours=2, minutes=30)  # Race in 30m, deadline in -1.5h
            elif scenario == "race_tomorrow":
                fake_race_datetime_utc = fake_race_base_time + timedelta(days=1)  # Race tomorrow
            else:
                fake_race_datetime_utc = fake_race_base_time
            
            # Create a fake race object for testing
            class FakeRace:
                def __init__(self):
                    self.name = f"Test Race ({scenario})"
                    self.event_date = fake_race_datetime_utc.date()
                    self.timezone = "UTC"
            
            next_race = FakeRace()
            print(f"DEBUG: Using fake race for simulation: {next_race.name} on {next_race.event_date} at {fake_race_datetime_utc}")
        else:
            # Get next upcoming race
            print(f"DEBUG: race_countdown - ENTERING REAL RACE MODE")
            print(f"DEBUG: race_countdown - getting real race, current_time.date(): {current_time.date()}")
            next_race = (
                Competition.query
                .filter(Competition.event_date >= current_time.date())
                .order_by(Competition.event_date)
                .first()
            )
            
            print(f"DEBUG: Found next race: {next_race.name if next_race else 'None'} on {next_race.event_date if next_race else 'None'}")
            print(f"DEBUG: Current time date: {current_time.date()}")
            
            if not next_race:
                print(f"DEBUG: No upcoming races found, returning error")
                return jsonify({
                    "error": "No upcoming races found",
                    "current_time": current_time.isoformat()
                })
        
        # Race time mapping (8pm local time for each race)
        race_times = {
            'Anaheim 1': '20:00',
            'San Diego': '20:00', 
            'Anaheim 2': '20:00',
            'Houston': '20:00',
            'Tampa': '20:00',
            'Glendale': '20:00',
            'Arlington': '20:00',
            'Daytona': '20:00',
            'Indianapolis': '20:00',
            'Detroit': '20:00',
            'Nashville': '20:00',
            'Denver': '20:00',
            'Salt Lake City': '20:00'
        }
        
        # Get race time (8pm local)
        race_time_str = race_times.get(next_race.name, '20:00')
        race_hour, race_minute = map(int, race_time_str.split(':'))
        
        # Create race datetime in local timezone
        race_date = next_race.event_date
        race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=race_hour, minute=race_minute))
        
        # Convert to UTC for countdown calculation
        if simulation_active:
            # For fake race, use the calculated fake_race_datetime_utc
            race_datetime_utc = fake_race_datetime_utc
            timezone = "UTC"
            print(f"DEBUG: Fake race datetime UTC: {race_datetime_utc}")
        else:
            # For real races, use timezone offsets
            timezone_offsets = {
                'America/Los_Angeles': -8,  # PST
                'America/Denver': -7,       # MST  
                'America/Phoenix': -7,      # MST (no DST)
                'America/Chicago': -6,      # CST
                'America/New_York': -5      # EST
            }
            
            timezone = getattr(next_race, 'timezone', 'America/Los_Angeles')
            utc_offset = timezone_offsets.get(timezone, -8)
            
            # Convert local time to UTC
            race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
            print(f"DEBUG: Real race datetime UTC: {race_datetime_utc}")
        
        # Calculate time differences
        time_to_race = race_datetime_utc - current_time
        time_to_deadline = race_datetime_utc - timedelta(hours=2) - current_time
        
        # Check if picks are locked (2 hours before race)
        picks_locked = time_to_deadline.total_seconds() <= 0
        
        print(f"DEBUG: Time to race: {time_to_race}")
        print(f"DEBUG: Time to deadline: {time_to_deadline}")
        print(f"DEBUG: Picks locked: {picks_locked}")
        
        return jsonify({
            "next_race": {
                "name": next_race.name,
                "date": next_race.event_date.isoformat(),
                "timezone": timezone,
                "local_time": race_time_str,
                "utc_time": race_datetime_utc.isoformat()
            },
            "countdown": {
                "race_start": {
                    "total_seconds": max(0, int(time_to_race.total_seconds())),
                    "days": max(0, time_to_race.days),
                    "hours": max(0, time_to_race.seconds // 3600),
                    "minutes": max(0, (time_to_race.seconds % 3600) // 60),
                    "seconds": max(0, time_to_race.seconds % 60)
                },
                "pick_deadline": {
                    "total_seconds": max(0, int(time_to_deadline.total_seconds())),
                    "days": max(0, time_to_deadline.days),
                    "hours": max(0, time_to_deadline.seconds // 3600),
                    "minutes": max(0, (time_to_deadline.seconds % 3600) // 60),
                    "seconds": max(0, time_to_deadline.seconds % 60)
                }
            },
            "picks_locked": picks_locked,
            "current_time": current_time.isoformat()
        })
        
    except Exception as e:
        print(f"Error getting race countdown: {e}")
        return jsonify({"error": str(e)}), 500

# API routes for admin panel
@app.route("/api/races")
def api_races():
    """Get all races for admin panel"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    races = Competition.query.order_by(Competition.event_date).all()
    return jsonify([{
        "id": race.id,
        "name": race.name,
        "date": race.event_date.isoformat()
    } for race in races])

@app.route("/api/riders")
def api_riders():
    """Get all riders for admin panel"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    riders = Rider.query.order_by(Rider.class_name, Rider.rider_number).all()
    return jsonify([{
        "id": rider.id,
        "name": rider.name,
        "class": rider.class_name.replace("cc", ""),
        "number": rider.rider_number,
        "bike_brand": rider.bike_brand
    } for rider in riders])

@app.route("/simulate_race/<int:race_id>", methods=['POST'])
def simulate_race(race_id):
    """Simulate a race - placeholder for now"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    # TODO: Implement actual race simulation
    return jsonify({"message": f"Race {race_id} simulation not yet implemented"})

@app.route("/reset_simulation", methods=['POST'])
def reset_simulation():
    """Reset simulation to real time"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    # Clear session-based simulation (for backward compatibility, but we'll use global database state)
    session.pop('simulation_active', None)
    session.pop('simulation_start_time', None)
    session.pop('initial_simulated_time', None)
    session.pop('simulated_time', None)
    session.pop('test_scenario', None)
    
    # Clear global simulation state from database
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        db.session.execute(text("UPDATE global_simulation SET active = FALSE WHERE id = 1"))
        db.session.commit()
    except Exception as e:
        print(f"DEBUG: Error clearing global simulation: {e}")
        # Rollback and fallback to app globals if database table doesn't exist
        db.session.rollback()
        if hasattr(app, 'global_simulation_active'):
            app.global_simulation_active = False
        if hasattr(app, 'global_simulation_start_time'):
            delattr(app, 'global_simulation_start_time')
        if hasattr(app, 'global_initial_simulated_time'):
            delattr(app, 'global_initial_simulated_time')
        if hasattr(app, 'global_simulated_time'):
            delattr(app, 'global_simulated_time')
    
    return jsonify({"message": "Simulation reset to real time"})

@app.route("/dino_game")
def dino_game():
    """Cross Dino game - Chrome Dino clone with motocross theme"""
    return render_template("dino_game.html")

@app.route("/dino_game_dev")
def dino_game_dev():
    """Cross Dino game development version - Excitebike style"""
    return render_template("dino_game_dev.html")

@app.route("/excitebike_clone")
def excitebike_clone():
    """Excitebike Clone game - Based on AlamantusGameDev repository"""
    return render_template("excitebike_clone.html")

@app.route("/api/cross_dino/highscores", methods=["GET"])
def get_cross_dino_highscores():
    """Get top 5 Cross Dino highscores"""
    try:
        highscores = CrossDinoHighScore.query.order_by(CrossDinoHighScore.score.desc()).limit(5).all()
        return jsonify([score.to_dict() for score in highscores])
    except Exception as e:
        print(f"Error getting highscores: {e}")
        return jsonify([])

@app.route("/api/cross_dino/highscores", methods=["POST"])
def submit_cross_dino_highscore():
    """Submit a new Cross Dino highscore"""
    try:
        data = request.get_json()
        player_name = data.get('player_name', 'Anonym')
        score = int(data.get('score', 0))
        
        if score <= 0:
            return jsonify({"error": "Invalid score"}), 400
        
        # Create new highscore
        highscore = CrossDinoHighScore(
            player_name=player_name,
            score=score
        )
        
        db.session.add(highscore)
        db.session.commit()
        
        # Return top 5 highscores
        highscores = CrossDinoHighScore.query.order_by(CrossDinoHighScore.score.desc()).limit(5).all()
        return jsonify([score.to_dict() for score in highscores])
        
    except Exception as e:
        print(f"Error submitting highscore: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to submit highscore"}), 500

@app.route("/api/cross_dino/reset_highscores", methods=["POST"])
def reset_cross_dino_highscores():
    """Reset all Cross Dino highscores (admin only)"""
    try:
        # Check if user is admin (you might want to add proper admin authentication here)
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Delete all highscores
        CrossDinoHighScore.query.delete()
        db.session.commit()
        
        return jsonify({"success": True, "message": "All highscores have been reset"})
        
    except Exception as e:
        print(f"Error resetting highscores: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to reset highscores"}), 500

@app.route("/api/smx_qualification")
def get_smx_qualification():
    """Get current SMX qualification standings"""
    try:
        top_20 = calculate_smx_qualification_points()
        
        qualification_data = []
        for i, (rider_id, data) in enumerate(top_20, 1):
            rider = data['rider']
            qualification_data.append({
                'position': i,
                'rider_id': rider.id,
                'rider_name': rider.name,
                'rider_number': rider.rider_number,
                'bike_brand': rider.bike_brand,
                'rider_class': rider.class_name,
                'coast_250': rider.coast_250 if rider.class_name == '250cc' else None,
                'total_points': data['total_points'],
                'sx_points': data['sx_points'],
                'mx_points': data['mx_points'],
                'qualified': i <= 20
            })
        
        return jsonify({
            'success': True,
            'qualification': qualification_data,
            'total_qualified': len(qualification_data)
        })
        
    except Exception as e:
        print(f"ERROR in get_smx_qualification: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/series_leaders")
def get_series_leaders():
    """Get current leaders for each series and SMX overview"""
    try:
        leaders = get_series_leaders()
        smx_qualification = calculate_smx_qualification_points()
        
        # Format leaders data
        leaders_data = {}
        for series, data in leaders.items():
            if data['leader']:
                rider = data['leader']
                leaders_data[series] = {
                    'leader': {
                        'rider_name': rider.name,
                        'rider_number': rider.rider_number,
                        'bike_brand': rider.bike_brand,
                        'points': data['points']
                    },
                    'top_5': [
                        {
                            'rider_name': item['rider'].name,
                            'rider_number': item['rider'].rider_number,
                            'bike_brand': item['rider'].bike_brand,
                            'points': item['points']
                        } for item in data['top_5']
                    ]
                }
            else:
                leaders_data[series] = None
        
        # Format SMX qualification overview
        smx_overview = {
            'total_qualified': len(smx_qualification),
            'top_5': []
        }
        
        for i, (rider_id, data) in enumerate(smx_qualification[:5], 1):
            rider = data['rider']
            smx_overview['top_5'].append({
                'position': i,
                'rider_name': rider.name,
                'rider_number': rider.rider_number,
                'rider_class': rider.class_name,
                'coast_250': rider.coast_250 if rider.class_name == '250cc' else None,
                'total_points': data['total_points']
            })
        
        return jsonify({
            'success': True,
            'leaders': leaders_data,
            'smx_overview': smx_overview
        })
        
    except Exception as e:
        print(f"ERROR in get_series_leaders: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/test_countdown")
def test_countdown():
    """Test countdown with simulated time - for development only"""
    try:
        # Get the next race first to base our test scenarios on
        next_race_date = (
            Competition.query
            .filter(Competition.event_date >= datetime.utcnow().date())
            .order_by(Competition.event_date)
            .first()
        )
        
        if not next_race_date:
            return jsonify({"error": "No upcoming races found for testing"})
        
        # Create race datetime for testing (8pm local time)
        race_date = next_race_date.event_date
        race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=20, minute=0))
        
        # Convert to UTC for testing
        timezone_offsets = {
            'America/Los_Angeles': -8,  # PST
            'America/Denver': -7,       # MST  
            'America/Phoenix': -7,      # MST (no DST)
            'America/Chicago': -6,      # CST
            'America/New_York': -5      # EST
        }
        
        timezone = getattr(next_race_date, 'timezone', 'America/Los_Angeles')
        utc_offset = timezone_offsets.get(timezone, -8)
        race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
        
        # Simulate different times for testing - create a fake race that's closer
        # Use a fake race date that's closer to now for testing
        fake_race_date = datetime.utcnow() + timedelta(days=1)  # Tomorrow
        fake_race_datetime_utc = fake_race_date.replace(hour=20, minute=0, second=0, microsecond=0)
        
        test_scenarios = {
            "race_in_3h": fake_race_datetime_utc - timedelta(hours=3),  # 3 hours before fake race
            "race_in_1h": fake_race_datetime_utc - timedelta(hours=1),  # 1 hour before fake race (picks locked)
            "race_in_30m": fake_race_datetime_utc - timedelta(minutes=30),  # 30 minutes before fake race
            "race_tomorrow": fake_race_datetime_utc - timedelta(days=1),  # 1 day before fake race
        }
        
        # Get the scenario from query parameter
        scenario = request.args.get('scenario', 'race_in_3h')
        simulated_time = test_scenarios.get(scenario, datetime.utcnow() + timedelta(hours=3))
        
        # Set the simulated time in session for global use (for backward compatibility, but we'll use global database state)
        session['simulation_active'] = True
        session['simulated_time'] = simulated_time.isoformat()
        session['simulation_start_time'] = datetime.utcnow().isoformat()
        session['initial_simulated_time'] = simulated_time.isoformat()
        session['test_scenario'] = scenario  # Store the scenario for race_countdown to use
        
        # Also set global simulation state for cross-device sync using database
        # Create or update global simulation record
        try:
            from sqlalchemy import text
            # Rollback any existing transaction first
            db.session.rollback()
            
            db.session.execute(text("""
                INSERT INTO global_simulation (id, active, simulated_time, start_time, initial_time, scenario) 
                VALUES (1, :active, :simulated_time, :start_time, :initial_time, :scenario)
                ON CONFLICT (id) DO UPDATE SET 
                    active = :active,
                    simulated_time = :simulated_time,
                    start_time = :start_time,
                    initial_time = :initial_time,
                    scenario = :scenario
            """), {
                'active': True,
                'simulated_time': simulated_time.isoformat(),
                'start_time': datetime.utcnow().isoformat(),
                'initial_time': simulated_time.isoformat(),
                'scenario': scenario
            })
            db.session.commit()
        except Exception as e:
            print(f"DEBUG: Error setting global simulation (table might not exist): {e}")
            # Rollback and fallback to app globals if database table doesn't exist yet
            db.session.rollback()
            app.global_simulation_active = True
            app.global_simulated_time = simulated_time.isoformat()
            app.global_simulation_start_time = datetime.utcnow().isoformat()
            app.global_initial_simulated_time = simulated_time.isoformat()
        
        # Get next upcoming race (use simulated time for testing)
        next_race = (
            Competition.query
            .filter(Competition.event_date >= simulated_time.date())
            .order_by(Competition.event_date)
            .first()
        )
        
        if not next_race:
            return jsonify({
                "error": "No upcoming races found",
                "simulated_time": simulated_time.isoformat(),
                "scenario": scenario
            })
        
        # Race time mapping (8pm local time for each race)
        race_times = {
            'Anaheim 1': '20:00',
            'San Diego': '20:00', 
            'Anaheim 2': '20:00',
            'Houston': '20:00',
            'Tampa': '20:00',
            'Glendale': '20:00',
            'Arlington': '20:00',
            'Daytona': '20:00',
            'Indianapolis': '20:00',
            'Detroit': '20:00',
            'Nashville': '20:00',
            'Denver': '20:00',
            'Salt Lake City': '20:00'
        }
        
        # Get race time (8pm local)
        race_time_str = race_times.get(next_race.name, '20:00')
        race_hour, race_minute = map(int, race_time_str.split(':'))
        
        # Create race datetime in local timezone
        race_date = next_race.event_date
        race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=race_hour, minute=race_minute))
        
        # Convert to UTC for countdown calculation
        timezone_offsets = {
            'America/Los_Angeles': -8,  # PST
            'America/Denver': -7,       # MST  
            'America/Phoenix': -7,      # MST (no DST)
            'America/Chicago': -6,      # CST
            'America/New_York': -5      # EST
        }
        
        timezone = getattr(next_race, 'timezone', 'America/Los_Angeles')
        utc_offset = timezone_offsets.get(timezone, -8)
        
        # Convert local time to UTC
        race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
        
        # Calculate time differences using simulated time
        # For countdown, we need to use the current simulated time, not the fixed simulated time
        current_simulated_time = get_current_time()
        time_to_race = fake_race_datetime_utc - current_simulated_time
        time_to_deadline = fake_race_datetime_utc - timedelta(hours=2) - current_simulated_time
        
        # Check if picks are locked (2 hours before race)
        picks_locked = time_to_deadline.total_seconds() <= 0
        
        return jsonify({
            "success": True,
            "next_race": {
                "name": f"Test Race ({scenario})",
                "date": fake_race_date.date().isoformat(),
                "timezone": "UTC",
                "local_time": "20:00",
                "utc_time": fake_race_datetime_utc.isoformat()
            },
            "countdown": {
                "race_start": {
                    "total_seconds": max(0, int(time_to_race.total_seconds())),
                    "days": max(0, time_to_race.days),
                    "hours": max(0, time_to_race.seconds // 3600),
                    "minutes": max(0, (time_to_race.seconds % 3600) // 60),
                    "seconds": max(0, time_to_race.seconds % 60)
                },
                "pick_deadline": {
                    "total_seconds": max(0, int(time_to_deadline.total_seconds())),
                    "days": max(0, time_to_deadline.days),
                    "hours": max(0, time_to_deadline.seconds // 3600),
                    "minutes": max(0, (time_to_deadline.seconds % 3600) // 60),
                    "seconds": max(0, time_to_deadline.seconds % 60)
                }
            },
            "picks_locked": picks_locked,
            "simulated_time": simulated_time.isoformat(),
            "scenario": scenario,
            "available_scenarios": list(test_scenarios.keys())
        })
        
    except Exception as e:
        print(f"Error in test countdown: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/test_countdown_page")
def test_countdown_page():
    """Test countdown page with scenario buttons"""
    return render_template('test_countdown.html')

@app.route("/set_simulated_time")
def set_simulated_time():
    """Set simulated time for testing - affects entire application"""
    try:
        scenario = request.args.get('scenario', 'race_in_3h')
        
        # Store simulated time in session
        if scenario == 'reset':
            session.pop('simulated_time', None)
            session.pop('simulation_active', None)
            session.pop('simulation_start_time', None)
            session.pop('simulation_scenario', None)
            return jsonify({"message": "Simulated time reset to real time", "scenario": "reset"})
        
        # Create fake race date for testing
        fake_race_date = datetime.utcnow() + timedelta(days=1)  # Tomorrow
        fake_race_datetime_utc = fake_race_date.replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Calculate simulated time based on scenario
        if scenario == 'race_in_3h':
            simulated_time = fake_race_datetime_utc - timedelta(hours=3)
        elif scenario == 'race_in_1h':
            simulated_time = fake_race_datetime_utc - timedelta(hours=1)
        elif scenario == 'race_in_30m':
            simulated_time = fake_race_datetime_utc - timedelta(minutes=30)
        elif scenario == 'race_tomorrow':
            simulated_time = fake_race_datetime_utc - timedelta(days=1)
        else:
            return jsonify({"error": "Invalid scenario"}), 400
        
        # Store in session with start time for countdown
        session['simulated_time'] = simulated_time.isoformat()
        session['simulation_active'] = True
        session['simulation_start_time'] = datetime.utcnow().isoformat()  # When simulation started
        session['simulation_scenario'] = scenario
        
        return jsonify({
            "message": f"Simulated time set for scenario: {scenario}",
            "simulated_time": simulated_time.isoformat(),
            "scenario": scenario
        })
        
    except Exception as e:
        print(f"Error setting simulated time: {e}")
        return jsonify({"error": str(e)}), 500

def get_current_time():
    """Get current time - either real or simulated"""
    print(f"DEBUG: get_current_time() called - session simulation_active: {session.get('simulation_active')}")
    
    # Skip session-based simulation - use only global database simulation for consistency
    print(f"DEBUG: Skipping session simulation, using only global database simulation")
    
    # Check global simulation state for cross-device sync using database
    print(f"DEBUG: Checking database global simulation state...")
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        result = db.session.execute(text("SELECT active, simulated_time, start_time FROM global_simulation WHERE id = 1")).fetchone()
        print(f"DEBUG: Database query result: {result}")
        if result and result[0]:  # active is True
            initial_simulated_time = datetime.fromisoformat(result[1])  # simulated_time
            simulation_start_time = datetime.fromisoformat(result[2])   # start_time
            
            # Calculate how much real time has passed since simulation started
            real_time_elapsed = datetime.utcnow() - simulation_start_time
            
            # Add the elapsed time to the initial simulated time
            current_simulated_time = initial_simulated_time + real_time_elapsed
            
            print(f"DEBUG: Using database global simulated time: {current_simulated_time} (elapsed: {real_time_elapsed})")
            print(f"DEBUG: Database data - active: {result[0]}, time: {result[1]}, start: {result[2]}")
            return current_simulated_time
        else:
            print(f"DEBUG: Database simulation not active or no result")
    except Exception as e:
        print(f"DEBUG: Error parsing database global simulated time: {e}")
        # Rollback and fallback to app globals if database table doesn't exist
        db.session.rollback()
        print(f"DEBUG: Checking app global simulation state...")
        if hasattr(app, 'global_simulation_active') and app.global_simulation_active and hasattr(app, 'global_simulated_time') and hasattr(app, 'global_simulation_start_time'):
            try:
                # Get the initial simulated time
                initial_simulated_time = datetime.fromisoformat(app.global_simulated_time)
                simulation_start_time = datetime.fromisoformat(app.global_simulation_start_time)
                
                # Calculate how much real time has passed since simulation started
                real_time_elapsed = datetime.utcnow() - simulation_start_time
                
                # Add the elapsed time to the initial simulated time
                current_simulated_time = initial_simulated_time + real_time_elapsed
                
                print(f"DEBUG: Using app global simulated time: {current_simulated_time} (elapsed: {real_time_elapsed})")
                print(f"DEBUG: App global data - active: {app.global_simulation_active}, time: {app.global_simulated_time}, start: {app.global_simulation_start_time}")
                return current_simulated_time
            except Exception as e2:
                print(f"DEBUG: Error parsing app global simulated time: {e2}")
                pass
        else:
            print(f"DEBUG: App global simulation not active or missing data")
    
    print(f"DEBUG: Using real time: {datetime.utcnow()}")
    return datetime.utcnow()

def calculate_smx_qualification_points():
    """Calculate SMX qualification points for all riders based on Supercross and Motocross results"""
    print("DEBUG: Calculating SMX qualification points...")
    
    # Get all riders
    riders = Rider.query.all()
    smx_points = {}
    
    for rider in riders:
        total_points = 0
        
        # Get Supercross results for this rider (considering coast for 250cc)
        sx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
            CompetitionResult.rider_id == rider.id,
            Series.name.ilike('%supercross%')
        ).all()
        
        # Filter 250cc results by coast if applicable
        if rider.class_name == '250cc':
            sx_results = [r for r in sx_results if hasattr(r, 'competition') and r.competition.coast_250 == rider.coast_250]
        
        # Get Motocross results for this rider (considering coast for 250cc)
        mx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
            CompetitionResult.rider_id == rider.id,
            Series.name.ilike('%motocross%')
        ).all()
        
        # Filter 250cc results by coast if applicable
        if rider.class_name == '250cc':
            mx_results = [r for r in mx_results if hasattr(r, 'competition') and r.competition.coast_250 == rider.coast_250]
        
        # Calculate points from Supercross (top 17 rounds)
        sx_points = []
        for result in sx_results:
            if result.position and result.position <= 20:  # Only top 20 get points
                points = get_smx_qualification_points(result.position)
                sx_points.append(points)
        
        # Take best 17 rounds from Supercross
        sx_points.sort(reverse=True)
        total_points += sum(sx_points[:17])
        
        # Calculate points from Motocross (top 11 rounds)
        mx_points = []
        for result in mx_results:
            if result.position and result.position <= 20:  # Only top 20 get points
                points = get_smx_qualification_points(result.position)
                mx_points.append(points)
        
        # Take best 11 rounds from Motocross
        mx_points.sort(reverse=True)
        total_points += sum(mx_points[:11])
        
        smx_points[rider.id] = {
            'rider': rider,
            'total_points': total_points,
            'sx_points': sum(sx_points[:17]),
            'mx_points': sum(mx_points[:11])
        }
    
    # Sort by total points and get top 20
    sorted_riders = sorted(smx_points.items(), key=lambda x: x[1]['total_points'], reverse=True)
    top_20 = sorted_riders[:20]
    
    print(f"DEBUG: SMX qualification calculated. Top 20 riders:")
    for i, (rider_id, data) in enumerate(top_20, 1):
        print(f"  {i}. {data['rider'].name} - {data['total_points']} points (SX: {data['sx_points']}, MX: {data['mx_points']})")
    
    return top_20

def get_series_leaders():
    """Get current leaders for each series (450cc, 250cc East, 250cc West)"""
    print("DEBUG: Getting series leaders...")
    
    leaders = {
        '450cc': {'leader': None, 'points': 0, 'top_5': []},
        '250cc_east': {'leader': None, 'points': 0, 'top_5': []},
        '250cc_west': {'leader': None, 'points': 0, 'top_5': []}
    }
    
    # Get all riders
    riders = Rider.query.all()
    
    # Calculate points for all riders
    rider_points = {}
    for rider in riders:
        total_points = 0
        
        # Get results for this rider based on their class and coast
        if rider.class_name == '450cc':
            # 450cc riders compete in all series
            results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
                CompetitionResult.rider_id == rider.id
            ).all()
        else:
            # 250cc riders only compete in their coast
            results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
                CompetitionResult.rider_id == rider.id,
                Competition.coast_250 == rider.coast_250
            ).all()
        
        # Calculate total points
        for result in results:
            if result.position and result.position <= 20:
                points = get_smx_qualification_points(result.position)
                total_points += points
        
        rider_points[rider.id] = {
            'rider': rider,
            'points': total_points
        }
    
    # Sort riders by class and coast, get top 5 for each
    for rider_id, data in rider_points.items():
        rider = data['rider']
        points = data['points']
        
        if rider.class_name == '450cc':
            leaders['450cc']['top_5'].append({'rider': rider, 'points': points})
            if points > leaders['450cc']['points']:
                leaders['450cc']['leader'] = rider
                leaders['450cc']['points'] = points
        elif rider.class_name == '250cc':
            if rider.coast_250 == 'east':
                leaders['250cc_east']['top_5'].append({'rider': rider, 'points': points})
                if points > leaders['250cc_east']['points']:
                    leaders['250cc_east']['leader'] = rider
                    leaders['250cc_east']['points'] = points
            elif rider.coast_250 == 'west':
                leaders['250cc_west']['top_5'].append({'rider': rider, 'points': points})
                if points > leaders['250cc_west']['points']:
                    leaders['250cc_west']['leader'] = rider
                    leaders['250cc_west']['points'] = points
    
    # Sort top 5 for each series
    for series in leaders:
        leaders[series]['top_5'].sort(key=lambda x: x['points'], reverse=True)
        leaders[series]['top_5'] = leaders[series]['top_5'][:5]
    
    print(f"DEBUG: Series leaders calculated:")
    for series, data in leaders.items():
        if data['leader']:
            print(f"  {series}: {data['leader'].name} - {data['points']} points")
        else:
            print(f"  {series}: No leader yet")
    
    return leaders

def get_smx_qualification_points(position):
    """Get SMX qualification points based on position (1st = 25 points, 2nd = 22, etc.)"""
    points_map = {
        1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
        11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1
    }
    return points_map.get(position, 0)

def is_picks_locked(competition):
    """Check if picks are locked for a specific competition"""
    # Handle both Competition objects and competition IDs
    if isinstance(competition, int):
        # If it's an ID, fetch the competition object
        competition_obj = Competition.query.get(competition)
        if not competition_obj:
            print(f"DEBUG: is_picks_locked() called with invalid competition ID: {competition}")
            return False
        competition_name = f"ID {competition}"
    else:
        # If it's a Competition object
        competition_obj = competition
        competition_name = competition.name if hasattr(competition, 'name') else f"ID {competition.id}"
    
    print(f"DEBUG: is_picks_locked() called for competition: {competition_name}")
    
    # Check if we're in simulation mode (use only global database state for consistency)
    simulation_active = False
    print(f"DEBUG: is_picks_locked - checking global database simulation only")
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        result = db.session.execute(text("SELECT active FROM global_simulation WHERE id = 1")).fetchone()
        simulation_active = result and result[0] if result else False
        print(f"DEBUG: is_picks_locked - database simulation_active: {simulation_active}")
    except Exception as e:
        print(f"DEBUG: Error checking global simulation in is_picks_locked: {e}")
        # Rollback and fallback to app globals if database table doesn't exist
        db.session.rollback()
        simulation_active = hasattr(app, 'global_simulation_active') and app.global_simulation_active
        print(f"DEBUG: is_picks_locked - app global simulation_active: {simulation_active}")
    
    if simulation_active:
        # Use the same logic as test_countdown for consistency
        # Get the scenario from global database state or use default
        try:
            result = db.session.execute(text("SELECT scenario FROM global_simulation WHERE id = 1")).fetchone()
            scenario = result[0] if result and result[0] else 'race_in_3h'
            print(f"DEBUG: is_picks_locked - using scenario from database: {scenario}")
        except Exception as e:
            print(f"DEBUG: Error getting scenario from database: {e}")
            scenario = session.get('test_scenario', 'race_in_3h')
            print(f"DEBUG: is_picks_locked - using scenario from session: {scenario}")
        
        # Get current time first
        current_time = get_current_time()
        
        # Use the same fake race logic as test_countdown
        # Create a fake race date that's closer to now for testing
        fake_race_date = datetime.utcnow() + timedelta(days=1)  # Tomorrow
        fake_race_datetime_utc = fake_race_date.replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Calculate time differences using simulated time
        # For countdown, we need to use the current simulated time, not the fixed simulated time
        time_to_race = fake_race_datetime_utc - current_time
        time_to_deadline = fake_race_datetime_utc - timedelta(hours=2) - current_time
        
        # Check if picks are locked (2 hours before fake race)
        picks_locked = time_to_deadline.total_seconds() <= 0
        
        print(f"DEBUG: is_picks_locked - Using fake race for picks_locked calculation: {fake_race_datetime_utc}")
        print(f"DEBUG: is_picks_locked - Current simulated time: {current_time}")
        print(f"DEBUG: is_picks_locked - Time to race: {time_to_race}")
        print(f"DEBUG: is_picks_locked - Time to deadline: {time_to_deadline}")
    else:
        # Check if picks are locked (2 hours before race)
        race_time_str = "20:00"  # 8pm local time
        race_hour, race_minute = map(int, race_time_str.split(':'))
        race_date = competition_obj.event_date
        race_datetime_local = datetime.combine(race_date, datetime.min.time().replace(hour=race_hour, minute=race_minute))
        
        # Convert to UTC for countdown calculation
        timezone_offsets = {
            'America/Los_Angeles': -8,  # PST
            'America/Denver': -7,       # MST  
            'America/Phoenix': -7,      # MST (no DST)
            'America/Chicago': -6,      # CST
            'America/New_York': -5      # EST
        }
        
        timezone = getattr(competition_obj, 'timezone', 'America/Los_Angeles')
        utc_offset = timezone_offsets.get(timezone, -8)
        race_datetime_utc = race_datetime_local - timedelta(hours=utc_offset)
        
        # Check if picks are locked (2 hours before race)
        current_time = get_current_time()
        time_to_deadline = race_datetime_utc - timedelta(hours=2) - current_time
        picks_locked = time_to_deadline.total_seconds() <= 0
    
    print(f"DEBUG: is_picks_locked - Picks locked: {picks_locked}")
    print(f"DEBUG: is_picks_locked - Current time: {current_time}")
    if simulation_active:
        print(f"DEBUG: is_picks_locked - Fake race datetime UTC: {fake_race_datetime_utc}")
        print(f"DEBUG: is_picks_locked - Time to race: {time_to_race}")
    else:
        print(f"DEBUG: is_picks_locked - Race datetime UTC: {race_datetime_utc}")
    print(f"DEBUG: is_picks_locked - Time to deadline: {time_to_deadline}")
    print(f"DEBUG: is_picks_locked - Time to deadline seconds: {time_to_deadline.total_seconds()}")
    
    return picks_locked

if __name__ == "__main__":
    # Production vs Development configuration
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    app.run(host=host, port=port, debug=debug_mode)