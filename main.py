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
    make_response,
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

# Security settings
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24 hour session timeout
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

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
# Database configuration loaded

# -------------------------------------------------
# Modeller
# -------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)  # E-post för lösenordsåterställning
    display_name = db.Column(db.String(100), nullable=True)  # Användarens riktiga namn
    profile_picture_url = db.Column(db.Text, nullable=True)  # Profilbild (base64 data)
    bio = db.Column(db.Text, nullable=True)  # Kort beskrivning om sig själv
    favorite_rider = db.Column(db.String(100), nullable=True)  # Favoritförare
    favorite_team = db.Column(db.String(100), nullable=True)  # Favoritlag
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # När kontot skapades
    is_admin = db.Column(db.Boolean, default=False)  # Admin-flagga
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
    active_race_id = db.Column(db.Integer, nullable=True)  # Which race is currently active for picks

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
    
    # Check if start_time column exists in database (cached)
    _start_time_column_exists = None
    
    @classmethod
    def has_start_time_column(cls):
        if cls._start_time_column_exists is None:
            try:
                db.session.execute(db.text("SELECT start_time FROM competitions LIMIT 1"))
                cls._start_time_column_exists = True
            except Exception:
                cls._start_time_column_exists = False
        return cls._start_time_column_exists
    
    # Dynamic property for start_time to handle missing column gracefully
    @property
    def start_time(self):
        if not self.has_start_time_column():
            return None
        try:
            # Use raw SQL to get start_time if column exists
            result = db.session.execute(
                db.text("SELECT start_time FROM competitions WHERE id = :id"), 
                {'id': self.id}
            ).fetchone()
            if result and result[0]:
                from datetime import time
                return result[0] if isinstance(result[0], time) else None
            return None
        except Exception:
            return None
    
    @start_time.setter
    def start_time(self, value):
        if not self.has_start_time_column():
            return
        try:
            # Use raw SQL to set start_time if column exists
            db.session.execute(
                db.text("UPDATE competitions SET start_time = :start_time WHERE id = :id"),
                {'start_time': value, 'id': self.id}
            )
        except Exception:
            pass

class Rider(db.Model):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column("class", db.String(10), nullable=False)  # Keep for backward compatibility
    classes = db.Column(db.String(50), nullable=True)  # New: comma-separated classes like "250cc,450cc"
    rider_number = db.Column(db.Integer)
    bike_brand = db.Column(db.String(50))
    image_url = db.Column(db.String(200))
    price = db.Column(db.Integer, nullable=False)
    coast_250 = db.Column(db.String(10), nullable=True)  # <-- lägg till
    
    # New SMX fields
    series_participation = db.Column(db.String(50), default='all')  # 'supercross', 'motocross', 'all'
    smx_qualified = db.Column(db.Boolean, default=False)  # Qualified for SMX Finals
    smx_seed_points = db.Column(db.Integer, default=0)  # Starting points for SMX Finals
    
    # Bio fields (nullable)
    nickname = db.Column(db.String(100))
    hometown = db.Column(db.String(100))
    residence = db.Column(db.String(100))
    birthdate = db.Column(db.Date)
    height_cm = db.Column(db.Integer)
    weight_kg = db.Column(db.Integer)
    team = db.Column(db.String(150))
    manufacturer = db.Column(db.String(100))
    team_manager = db.Column(db.String(100))
    mechanic = db.Column(db.String(100))
    turned_pro = db.Column(db.Integer)
    instagram = db.Column(db.String(100))
    twitter = db.Column(db.String(100))
    facebook = db.Column(db.String(100))
    website = db.Column(db.String(200))
    bio = db.Column(db.Text)
    achievements = db.Column(db.Text)
    


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
    image_url = db.Column(db.String(200))  # Legacy: file path (deprecated)
    image_data = db.Column(db.Text)  # NEW: base64 encoded image data
    image_mime_type = db.Column(db.String(50))  # NEW: image MIME type (e.g., 'image/png')
    description = db.Column(db.String(255))  # NY: kort beskrivning (nullable)
    is_public = db.Column(db.Boolean, default=True)  # NEW: public/private league
    total_points = db.Column(db.Integer, default=0)  # NEW: league competition points
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # NEW: creation date


class LeagueMembership(db.Model):
    __tablename__ = "league_memberships"
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey("leagues.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('league_id', 'user_id', name='uq_league_user'),)


class LeagueRequest(db.Model):
    __tablename__ = "league_requests"
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey("leagues.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500))  # Optional message from requester
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('league_id', 'user_id', name='uq_league_request'),)

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
    race_points = db.Column(db.Integer, default=0)
    holeshot_points = db.Column(db.Integer, default=0)
    wildcard_points = db.Column(db.Integer, default=0)
class LeaderboardHistory(db.Model):
    __tablename__ = "leaderboard_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ranking = db.Column(db.Integer, nullable=False)
    total_points = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index för snabbare queries
    __table_args__ = (
        db.Index('idx_leaderboard_history_user_created', 'user_id', 'created_at'),
    )

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
    
    # Relationships
    competition = db.relationship('Competition', backref='results', lazy=True)
    rider = db.relationship('Rider', backref='results', lazy=True)
    
    # Unique constraint to prevent duplicate results for same rider in same competition
    __table_args__ = (
        db.UniqueConstraint('competition_id', 'rider_id', name='uq_comp_rider_result'),
    )


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
    """Get today's date - simplified without old simulation"""
    today = date.today()
    return today

def is_admin_user():
    """Check if current user is admin"""
    username = session.get("username")
    if not username:
        return False
    
    # Check if user has is_admin flag
    try:
        user = User.query.filter_by(username=username).first()
        if user and hasattr(user, 'is_admin') and user.is_admin:
            return True
    except Exception as e:
        # If is_admin column doesn't exist, fall back to old method
        print(f"Error checking is_admin flag: {e}")
        pass
    
    # Fallback to old method for backward compatibility
    return username == "test"

def check_session_timeout():
    """Check if session has expired and logout if needed"""
    if "login_time" in session:
        login_time = datetime.fromisoformat(session["login_time"])
        if datetime.utcnow() - login_time > timedelta(hours=24):
            session.clear()
            return False
    return True

def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if "user_id" not in session:
            flash("Du måste logga in för att komma åt denna sida", "error")
            return redirect(url_for("login"))
        
        # Check session timeout
        if not check_session_timeout():
            flash("Din session har gått ut. Logga in igen.", "error")
            return redirect(url_for("login"))
        
        return f(*args, **kwargs)
    return decorated_function


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
    # Creating CompetitionImage records for compressed track maps
    
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
    # Found competitions
    
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
            # Created image for competition
            
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

def require_login(f):
    """Decorator to require login for routes"""
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or "username" not in session:
            return redirect(url_for("login"))
        
        # Verify user still exists in database
        user = User.query.get(session["user_id"])
        if not user or user.username != session["username"]:
            session.clear()
            return redirect(url_for("login"))
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        modal = request.form.get('modal')
        
        if not username or not password:
            if modal:
                return jsonify({"success": False, "error": "Användarnamn och lösenord krävs"})
            else:
                flash("Användarnamn och lösenord krävs", "error")
                return render_template("login.html")
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            # Complete session reset - nuclear approach
            session.clear()
            
            # Set new session with minimal data
            session["user_id"] = user.id
            session["username"] = user.username
            session["login_time"] = datetime.utcnow().isoformat()
            session.permanent = True
            
            # Force session to be saved
            session.modified = True
            
            # Check if this is an AJAX request (from popup)
            if modal:
                return jsonify({"success": True, "redirect": url_for("index")})
            else:
                return redirect(url_for("index"))
        
        # Login failed
        if modal:
            return jsonify({"success": False, "error": "Felaktigt användarnamn eller lösenord"})
        else:
            flash("Felaktigt användarnamn eller lösenord", "error")
            return render_template("login.html")
    
    # Handle GET request (show login page)
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        email = request.form.get("email", "").strip()
        
        # Check if username is already taken
        if User.query.filter_by(username=username).first():
            flash("Användarnamnet är redan upptaget", "error")
        # Check if email is already taken (if provided)
        elif email and User.query.filter_by(email=email).first():
            flash("E-postadressen är redan registrerad", "error")
        else:
            new_user = User(
                username=username,
                password_hash=generate_password_hash(request.form["password"]),
                email=email if email else None,
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Konto skapat! Du kan nu logga in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    # Complete session destruction
    session.clear()
    session.permanent = False
    session.modified = True
    
    # Create response and clear cookies
    response = make_response(redirect(url_for("index")))
    response.set_cookie('session', '', expires=0, path='/', domain=None)
    return response


# -------------------------------------------------
# Pages
# -------------------------------------------------
@app.route("/api/series_status")
def series_status():
    """Get status of all series for user interface"""
    try:
        # Always show all series for 2026, not just active ones
        # Sort by custom order: Supercross, Motocross, SMX Finals
        series = Series.query.filter_by(year=2026).all()
        # Custom sort order
        series_order = {'Supercross': 1, 'Motocross': 2, 'SMX Finals': 3}
        series.sort(key=lambda s: series_order.get(s.name, 999))
        
        # Use simulated date if available, otherwise use real date
        current_date = get_today()
        
        series_data = []
        for s in series:
            # Use is_active from database (set by simulation) or fallback to date-based logic
            is_currently_active = s.is_active
            
            # If not explicitly set by simulation, use date-based logic as fallback
            # Check if any series is currently being simulated
            simulation = GlobalSimulation.query.filter_by(id=1, active=True).first()
            if not simulation:
                # No active simulation, use date-based logic
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
    # Validate session and check if user is logged in
    if "user_id" in session and "username" in session:
        # Verify user still exists in database
        user = User.query.get(session["user_id"])
        if user and user.username == session["username"]:
            uid = session["user_id"]
            is_logged_in = True
        else:
            # User no longer exists or username mismatch - clear session
            session.clear()
            uid = None
            is_logged_in = False
    else:
        uid = None
        is_logged_in = False
    today = get_today()

    # Ensure database is initialized
    try:
        # Check if tables exist, if not initialize
        from sqlalchemy import inspect
        if not inspect(db.engine).has_table('competitions'):
            print("Tables missing, reinitializing database...")
            init_database()
        
        # Add classes column if missing
        try:
            exists = db.session.execute(db.text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='riders' AND column_name='classes'
            """)).fetchone()
            if not exists:
                print("Adding classes column to riders table...")
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN classes VARCHAR(50)"))
                db.session.commit()
                print("Classes column added successfully")
        except Exception as e:
            print(f"Error adding classes column: {e}")
            db.session.rollback()
            pass
        
        # Skip rider bio column migrations for now
        pass

        # Skip league_memberships column migrations for now
        pass
        
        
        # Skip league image column migrations for now
        pass
        
        # Skip league additional column migrations for now
        pass
        
        # Check if league_requests table exists
        if not inspect(db.engine).has_table('league_requests'):
            print("Creating league_requests table...")
            try:
                db.session.rollback()
                db.session.execute(db.text("""
                    CREATE TABLE league_requests (
                        id SERIAL PRIMARY KEY,
                        league_id INTEGER NOT NULL REFERENCES leagues(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        message VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP,
                        UNIQUE(league_id, user_id)
                    )
                """))
                db.session.commit()
                print("league_requests table created successfully")
            except Exception as e:
                print(f"Error creating league_requests table: {e}")
                db.session.rollback()
        
    except Exception as e:
        print(f"Database check error: {e}")
        init_database()

    # Get competitions with error handling
    try:
        competitions = Competition.query.order_by(Competition.event_date).all()
    except Exception as e:
        print(f"Error getting competitions: {e}")
        competitions = []
    
    # Check if there's an active race set in admin panel
    upcoming_race = None
    try:
        global_sim = GlobalSimulation.query.first()
        if global_sim and global_sim.active and global_sim.active_race_id:
            # Use the active race from admin panel
            upcoming_race = Competition.query.get(global_sim.active_race_id)
            pass
    except Exception as e:
        pass
    
    # Fallback to next race by date if no active race is set
    if not upcoming_race:
        upcoming_race = next((c for c in competitions if c.event_date and c.event_date >= today), None)
    
    # Get user-specific data only if logged in
    my_team = None
    team_riders = []
    user_profile_picture = None
    current_picks_450 = []
    current_picks_250 = []
    current_holeshot_450 = None
    current_holeshot_250 = None
    current_wildcard = None
    picks_status = "no_picks"
    picks_locked = True
    league_requests_count = 0
    
    if is_logged_in:
        # Get season team with error handling
        try:
            my_team = SeasonTeam.query.filter_by(user_id=uid).first()
        except Exception as e:
            print(f"Error getting season team: {e}")
            my_team = None

        # Get team riders
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
        try:
            user = User.query.get(uid)
            if user and hasattr(user, 'profile_picture_url') and user.profile_picture_url:
                user_profile_picture = user.profile_picture_url
        except Exception as e:
            print(f"Error getting user profile picture: {e}")
            user_profile_picture = None

        # Get user's picks for upcoming race
        picks_status = "no_picks"
        picks_locked = False
        
        if upcoming_race:
            try:
                # Use the unified picks lock check function
                picks_locked = is_picks_locked(upcoming_race)
                
                # Use the correct competition_id for picks lookup
                competition_id_for_picks = upcoming_race.id
                
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
                    if wildcard_pick and wildcard_pick.rider_id:
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

    # Check for new bulletin posts (last 24 hours)
    new_bulletin_posts = 0
    latest_post_author = None
    try:
        from datetime import timedelta
        yesterday = today - timedelta(days=1)
        new_posts = BulletinPost.query.filter(
            BulletinPost.created_at >= yesterday,
            BulletinPost.is_deleted == False,
            BulletinPost.parent_id == None  # Only count main posts, not replies
        ).order_by(BulletinPost.created_at.desc()).all()
        
        new_bulletin_posts = len(new_posts)
        if new_posts:
            # Get the latest post author
            latest_post = new_posts[0]
            if latest_post.user:
                # Use display_name if available, otherwise fallback to username
                # Handle case where is_admin column might not exist yet
                try:
                    latest_post_author = getattr(latest_post.user, 'display_name', None) or latest_post.user.username
                except Exception:
                    latest_post_author = latest_post.user.username
            else:
                latest_post_author = "Okänd"
    except Exception as e:
        print(f"Error checking bulletin posts: {e}")
        new_bulletin_posts = 0
        latest_post_author = None

    # Check for league join requests (for league creators)
    try:
        # Get all leagues where current user is creator
        user_leagues = League.query.filter_by(creator_id=uid).all()
        league_ids = [league.id for league in user_leagues]
        
        if league_ids:
            # Count pending requests for user's leagues
            league_requests_count = LeagueRequest.query.filter(
                LeagueRequest.league_id.in_(league_ids),
                LeagueRequest.status == 'pending'
            ).count()
        else:
            league_requests_count = 0
    except Exception as e:
        print(f"Error checking league requests: {e}")
        league_requests_count = 0

    return render_template(
        "index.html",
        username=session.get("username", "Gäst"),
        user_profile_picture=user_profile_picture if is_logged_in else None,
        upcoming_race=upcoming_race,
        upcoming_races=[c for c in competitions if c.event_date and c.event_date >= today],
        my_team=my_team if is_logged_in else None,
        team_riders=team_riders if is_logged_in else [],
        current_picks_450=current_picks_450 if is_logged_in else None,
        current_picks_250=current_picks_250 if is_logged_in else None,
        current_holeshot_450=current_holeshot_450 if is_logged_in and 'current_holeshot_450' in locals() else None,
        current_holeshot_250=current_holeshot_250 if is_logged_in and 'current_holeshot_250' in locals() else None,
        current_wildcard=current_wildcard if is_logged_in and 'current_wildcard' in locals() else None,
        new_bulletin_posts=new_bulletin_posts,
        latest_post_author=latest_post_author,
        league_requests_count=league_requests_count if is_logged_in else 0,
        picks_status=picks_status,
        picks_locked=picks_locked,
        is_admin=is_admin_user() if is_logged_in else False,
        is_logged_in=is_logged_in,
    )






@app.route("/leagues")
def leagues_page():
    # Check if user is logged in
    if "user_id" in session:
        uid = session["user_id"]
        is_logged_in = True
    else:
        uid = None
        is_logged_in = False
    
    # Ensure database is initialized
    try:
        # Check if tables exist, if not initialize
        from sqlalchemy import inspect
        if not inspect(db.engine).has_table('leagues'):
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
    
    return render_template("leagues.html", 
                         my_leagues=my_leagues if is_logged_in else [], 
                         username=session.get("username", "Gäst"),
                         is_logged_in=is_logged_in)


@app.get("/leagues/browse")
def browse_leagues():
    """Browse all public leagues"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    # Get all public leagues with member count and points
    public_leagues = db.session.query(
        League,
        db.func.count(LeagueMembership.user_id).label('member_count')
    ).outerjoin(LeagueMembership).filter(
        League.is_public == True
    ).group_by(League.id).order_by(
        League.total_points.desc(),
        League.created_at.desc()
    ).all()
    
    # Get user's current leagues to show which ones they're already in
    user_league_ids = db.session.query(LeagueMembership.league_id).filter(
        LeagueMembership.user_id == session["user_id"]
    ).all()
    user_league_ids = [lid[0] for lid in user_league_ids]
    
    # Get pending requests
    pending_requests = db.session.query(LeagueRequest.league_id).filter(
        LeagueRequest.user_id == session["user_id"],
        LeagueRequest.status == 'pending'
    ).all()
    pending_league_ids = [rid[0] for rid in pending_requests]
    
    return render_template("browse_leagues.html", 
                         public_leagues=public_leagues,
                         user_league_ids=user_league_ids,
                         pending_league_ids=pending_league_ids,
                         username=session.get("username"))


@app.get("/leagues/leaderboard")
def leagues_leaderboard():
    """Public league leaderboard sorted by league points."""
    # Allow viewing without login (readonly UX handled in template/header if needed)
    is_logged_in = "user_id" in session
    try:
        leagues_with_members = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).group_by(League.id).order_by(
            League.total_points.desc(),
            League.created_at.desc()
        ).all()

        leaderboard = []
        for row in leagues_with_members:
            league = row[0]
            member_count = row[1]
            leaderboard.append({
                'id': league.id,
                'name': league.name,
                'member_count': member_count,
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True)
            })
    except Exception as e:
        print(f"Error loading league leaderboard: {e}")
        leaderboard = []

    return render_template(
        "league_leaderboard.html",
        leaderboard=leaderboard,
        username=session.get("username", "Gäst"),
        is_logged_in=is_logged_in,
    )


@app.get("/api/leagues/leaderboard")
def api_leagues_leaderboard():
    """API endpoint for league leaderboard data (JSON)."""
    try:
        leagues_with_members = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).group_by(League.id).order_by(
            League.total_points.desc(),
            League.created_at.desc()
        ).all()

        leaderboard = []
        for row in leagues_with_members:
            league = row[0]
            member_count = row[1]
            leaderboard.append({
                'id': league.id,
                'name': league.name,
                'member_count': member_count,
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True)
            })
    except Exception as e:
        print(f"Error loading league leaderboard: {e}")
        leaderboard = []

    return jsonify(leaderboard)




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
    
    # Get pending requests if user is league creator
    pending_requests = []
    is_creator = league.creator_id == session["user_id"]
    if is_creator:
        pending_requests = db.session.query(
            LeagueRequest.id,
            LeagueRequest.message,
            LeagueRequest.created_at,
            User.username,
            User.display_name
        ).join(User, LeagueRequest.user_id == User.id).filter(
            LeagueRequest.league_id == league_id,
            LeagueRequest.status == 'pending'
        ).order_by(LeagueRequest.created_at.desc()).all()

    return render_template(
        "league_detail.html",
        league=league,
        members=[type("Row", (), {"id": m.id, "username": m.username}) for m in members],
        competitions=competitions,
        season_leaderboard=[
            {"user_id": row.id, "username": row.username, "team_name": row.team_name, "total_points": row.total_points or 0}
            for row in season_leaderboard
        ],
        pending_requests=pending_requests,
        is_creator=is_creator,
    )


@app.route("/season_team")
def season_team_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    team = SeasonTeam.query.filter_by(user_id=user_id).first()
    riders = []
    
    # Calculate user's total points (same as leaderboard)
    user_scores = CompetitionScore.query.filter_by(user_id=user_id).all()
    user_total_points = sum(score.total_points or 0 for score in user_scores)
    
    if team:
        riders = (
            Rider.query.join(SeasonTeamRider, Rider.id == SeasonTeamRider.rider_id)
            .filter(SeasonTeamRider.season_team_id == team.id)
            .all()
        )
    
    return render_template("season_team.html", team=team, riders=riders, user_total_points=user_total_points)

@app.route("/profile")
def profile_page():
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
    
    # Beräkna separata poängsummor
    user_scores = CompetitionScore.query.filter_by(user_id=user.id).all()
    total_race_points = sum(score.race_points or 0 for score in user_scores)
    total_holeshot_points = sum(score.holeshot_points or 0 for score in user_scores)
    total_wildcard_points = sum(score.wildcard_points or 0 for score in user_scores)
    
    # Hitta bästa placering (lägsta position i leaderboard)
    best_position = None
    if competitions_played > 0:
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
    print(f"DEBUG: Total points breakdown - Race: {total_race_points}, Holeshot: {total_holeshot_points}, Wildcard: {total_wildcard_points}")
    return render_template(
        "profile.html",
        user=user,
        season_team=season_team,
        competitions_played=competitions_played,
        best_position=best_position,
        total_race_points=total_race_points,
        total_holeshot_points=total_holeshot_points,
        total_wildcard_points=total_wildcard_points
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
        all_riders = Rider.query.order_by(Rider.rider_number).all()
        print(f"Found {len(all_riders)} riders for season team builder")
        
        # Check if user already has a team
        existing_team = SeasonTeam.query.filter_by(user_id=user_id).first()
        has_existing_team = existing_team is not None
        
        # Get existing team riders for frontend calculation
        existing_team_riders = []
        if existing_team:
            existing_team_riders = SeasonTeamRider.query.filter_by(season_team_id=existing_team.id).all()
            existing_team_riders = [str(tr.rider_id) for tr in existing_team_riders]
        
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
        
        return render_template("season_team_builder.html", 
                             riders=riders_data, 
                             has_existing_team=has_existing_team,
                             existing_team=existing_team,
                             existing_team_riders=existing_team_riders)
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
    
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()
    
    uid = session["user_id"]
    # Getting user scores

    rows = (
        db.session.query(
            Competition.id.label("competition_id"),
            Competition.name,
            Competition.series,
            Competition.event_date,
            CompetitionScore.total_points,
            CompetitionScore.race_points,
            CompetitionScore.holeshot_points,
            CompetitionScore.wildcard_points,
        )
        .outerjoin(CompetitionScore, (Competition.id == CompetitionScore.competition_id) & (CompetitionScore.user_id == uid))
        .order_by(Competition.event_date.asc().nulls_last())
        .all()
    )

    # Calculate total points
    total_points = sum((r.total_points or 0) for r in rows)
    
    # Check which competitions have results (are completed)
    scores = []
    for r in rows:
        # Check if this competition has any results
        has_results = db.session.query(CompetitionResult).filter_by(competition_id=r.competition_id).first() is not None
        
        scores.append({
            "competition_id": r.competition_id,
            "name": r.name,
            "series": r.series,
            "event_date": r.event_date.strftime("%Y-%m-%d") if r.event_date else "",
            "total_points": r.total_points or 0,
            "race_points": r.race_points or 0,
            "holeshot_points": r.holeshot_points or 0,
            "wildcard_points": r.wildcard_points or 0,
            "has_results": has_results,  # New field to indicate if race is completed
        })

    return render_template("my_scores.html", scores=scores, total_points=total_points)


@app.route("/series/<int:series_id>")
def series_page(series_id):
    """Simple series page that actually works"""
    print(f"DEBUG: series_page called with series_id={series_id}")
    try:
        # Always rollback first
        db.session.rollback()
        print(f"DEBUG: Database rollback completed")
        
        # Get series info
        series = Series.query.get(series_id)
        print(f"DEBUG: Series query result: {series}")
        if not series:
            print(f"DEBUG: No series found, redirecting to index")
            return redirect(url_for("index"))
        
        # Get competitions for this series
        db.session.rollback()
        competitions = Competition.query.filter_by(series_id=series_id).order_by(Competition.event_date).all()
        print(f"DEBUG: Found {len(competitions)} competitions for series {series_id}")
        
        # Check if there's an active race set in admin panel
        active_race_id = None
        try:
            global_sim = GlobalSimulation.query.first()
            if global_sim and global_sim.active and global_sim.active_race_id:
                active_race_id = global_sim.active_race_id
        except Exception as e:
            pass
        
        # Get competition results for template - OPTIMIZED
        competition_results = {}
        user_picks_status = {}
        picks_locked_status = {}
        
        # Get all competition IDs
        comp_ids = [comp.id for comp in competitions]
        
        # Batch load all results for all competitions
        if comp_ids:
            all_results = CompetitionResult.query.filter(CompetitionResult.competition_id.in_(comp_ids)).all()
            for result in all_results:
                if result.competition_id not in competition_results:
                    competition_results[result.competition_id] = []
                competition_results[result.competition_id].append(result)
        
        # Batch load user picks if logged in
        if "user_id" in session and comp_ids:
            user_id = session["user_id"]
            
            # Get all race picks for user in this series
            race_picks = RacePick.query.filter(
                RacePick.user_id == user_id,
                RacePick.competition_id.in_(comp_ids)
            ).all()
            
            # Get all holeshot picks for user in this series
            holeshot_picks = HoleshotPick.query.filter(
                HoleshotPick.user_id == user_id,
                HoleshotPick.competition_id.in_(comp_ids)
            ).all()
            
            # Get all wildcard picks for user in this series
            wildcard_picks = WildcardPick.query.filter(
                WildcardPick.user_id == user_id,
                WildcardPick.competition_id.in_(comp_ids)
            ).all()
            
            # Group picks by competition_id
            race_picks_by_comp = {}
            for pick in race_picks:
                if pick.competition_id not in race_picks_by_comp:
                    race_picks_by_comp[pick.competition_id] = []
                race_picks_by_comp[pick.competition_id].append(pick)
            
            holeshot_picks_by_comp = {}
            for pick in holeshot_picks:
                if pick.competition_id not in holeshot_picks_by_comp:
                    holeshot_picks_by_comp[pick.competition_id] = []
                holeshot_picks_by_comp[pick.competition_id].append(pick)
            
            wildcard_picks_by_comp = {}
            for pick in wildcard_picks:
                wildcard_picks_by_comp[pick.competition_id] = pick
        
        # Process each competition - OPTIMIZED
        current_time = get_current_time()  # Get once, use many times
        
        for comp in competitions:
            # Initialize empty results if none found
            if comp.id not in competition_results:
                competition_results[comp.id] = []
            
            # Check if picks are locked for this competition - OPTIMIZED
            # Use simple date comparison instead of complex is_picks_locked function
            if comp.event_date and comp.event_date <= current_time.date():
                picks_locked = True
            else:
                picks_locked = False
            picks_locked_status[comp.id] = picks_locked
            
            # Check if current user has made picks for this competition
            if "user_id" in session:
                race_count = len(race_picks_by_comp.get(comp.id, []))
                holeshot_count = len(holeshot_picks_by_comp.get(comp.id, []))
                has_wildcard = comp.id in wildcard_picks_by_comp
                
                has_picks = race_count > 0 or holeshot_count > 0 or has_wildcard
                user_picks_status[comp.id] = {
                    'has_picks': has_picks,
                    'race_picks_count': race_count,
                    'holeshot_picks_count': holeshot_count,
                    'has_wildcard': has_wildcard
                }
            else:
                user_picks_status[comp.id] = {'has_picks': False}
        
        # Find next race (either active race or next upcoming race)
        next_race = None
        if active_race_id:
            # If there's an active race, check if it belongs to this series
            potential_race = Competition.query.get(active_race_id)
            if potential_race and potential_race.series_id == series_id:
                next_race = potential_race
                # Found active race in this series
            else:
                # Active race is not in this series
                pass
        
        if not next_race:
            # Otherwise find the next upcoming race in this series
            current_date = get_today()
            next_race = Competition.query.filter_by(series_id=series_id).filter(
                Competition.event_date >= current_date
            ).order_by(Competition.event_date).first()
            # Found next upcoming race
        
        # Determine if picks are open - OPTIMIZED
        picks_open = False
        if next_race:
            # Use simple date comparison instead of complex is_picks_locked function
            picks_open = next_race.event_date and next_race.event_date > current_time.date()
        
        # Simple template render with all required variables
        print(f"DEBUG: About to render series_page.html for series {series_id}")
        return render_template("series_page.html", 
                             series=series, 
                             competitions=competitions,
                             competition_results=competition_results,
                             user_picks_status=user_picks_status,
                             picks_locked_status=picks_locked_status,
                             next_race=next_race,
                             picks_open=picks_open,
                             current_date=get_today(),
                             active_race_id=active_race_id,
                             user_logged_in="user_id" in session)
        
    except Exception as e:
        print(f"DEBUG: Exception in series_page: {e}")
        db.session.rollback()
        return redirect(url_for("index"))

@app.route("/race_picks/<int:competition_id>")
@login_required
def race_picks_page(competition_id):
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
    # Filtered out riders

    # 4) Placeholder för resultat/holeshot (om ej klart)
    actual_results = []
    holeshot_results = []

    # 5) Get trackmap images for this competition
    trackmap_images = []
    try:
        trackmap_images = CompetitionImage.query.filter_by(competition_id=comp.id).order_by(CompetitionImage.sort_order).all()
        # Found trackmap images
    except Exception as e:
        # Error getting trackmap images
        pass
    
    # 6) Skicka out_ids till templaten för (OUT)/disabled
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
        trackmap_images=trackmap_images,
        picks_locked=picks_locked,
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
        image_data = None
        image_mime_type = None
        image_url = None  # Legacy support
        
        if file and file.filename and allowed_file(file.filename):
            try:
                # Read file data and convert to base64
                file_data = file.read()
                import base64
                image_data = base64.b64encode(file_data).decode('utf-8')
                image_mime_type = file.content_type or 'image/jpeg'
                
                # Also save to file system for legacy support (optional)
                try:
                    fname = secure_filename(f"{code}_{file.filename}")
                    path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                    file.seek(0)  # Reset file pointer
                    file.save(path)
                    image_url = url_for("static", filename=f"uploads/leagues/{fname}")
                    print(f"League image saved to file: {path}")
                except Exception as e:
                    print(f"Error saving league image to file: {e}")
                    # Continue without file, we have base64 data
                
                print(f"League image saved to database as base64: {len(image_data)} chars")
            except Exception as e:
                print(f"Error processing league image: {e}")
                # Continue without image if processing fails

        league = League(
            name=name, 
            creator_id=session["user_id"], 
            invite_code=code, 
            image_url=image_url,
            image_data=image_data,
            image_mime_type=image_mime_type
        )
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


@app.post("/leagues/<int:league_id>/edit")
def edit_league(league_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    league = League.query.get_or_404(league_id)
    if league.creator_id != session["user_id"]:
        flash("Endast skaparen kan redigera ligan.", "error")
        return redirect(url_for("league_detail_page", league_id=league_id))
    
    try:
        # Update league name if provided
        new_name = (request.form.get("league_name") or "").strip()
        if new_name and new_name != league.name:
            league.name = new_name
        
        # Handle new image upload
        file = request.files.get("league_image")
        if file and file.filename and allowed_file(file.filename):
            try:
                # Delete old image file if it exists (legacy)
                if league.image_url:
                    try:
                        old_filename = league.image_url.split('/')[-1]
                        old_image_path = os.path.join(app.config["UPLOAD_FOLDER"], old_filename)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            print(f"Deleted old league image file: {old_image_path}")
                    except Exception as e:
                        print(f"Error deleting old league image file: {e}")
                
                # Read file data and convert to base64
                file_data = file.read()
                import base64
                league.image_data = base64.b64encode(file_data).decode('utf-8')
                league.image_mime_type = file.content_type or 'image/jpeg'
                
                # Also save to file system for legacy support (optional)
                try:
                    fname = secure_filename(f"{league.invite_code}_{file.filename}")
                    path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                    file.seek(0)  # Reset file pointer
                    file.save(path)
                    league.image_url = url_for("static", filename=f"uploads/leagues/{fname}")
                    print(f"New league image saved to file: {path}")
                except Exception as e:
                    print(f"Error saving new league image to file: {e}")
                    # Continue without file, we have base64 data
                
                print(f"New league image saved to database as base64: {len(league.image_data)} chars")
            except Exception as e:
                print(f"Error processing new league image: {e}")
                flash("Fel vid uppladdning av bild. Ligan uppdaterades utan bild.", "warning")
        
        db.session.commit()
        flash("Ligan uppdaterades!", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error editing league: {e}")
        flash(f"Fel vid redigering av liga: {str(e)}", "error")
    
    return redirect(url_for("league_detail_page", league_id=league_id))

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
    try:
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
        is_team_change = False
        riders_changed = 0
        penalty_points = 0
        
        if not team:
            # First time creating team - no penalty
            team = SeasonTeam(user_id=uid, team_name=team_name, total_points=0)
            db.session.add(team)
            db.session.flush()
        else:
            # Team already exists - calculate how many riders changed
            is_team_change = True
            team.team_name = team_name
            
            # Get current team riders
            current_riders = SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
            current_rider_ids = set(tr.rider_id for tr in current_riders)
            new_rider_ids = set(rider_ids)
            
            # Calculate how many riders changed
            riders_changed = len(current_rider_ids - new_rider_ids)
            penalty_points = riders_changed * 50  # 50 points per changed rider
            
            # Check if user has enough points for the penalty
            if penalty_points > 0:
                user_scores = CompetitionScore.query.filter_by(user_id=uid).all()
                total_race_points = sum(score.race_points or 0 for score in user_scores)
                total_holeshot_points = sum(score.holeshot_points or 0 for score in user_scores)
                total_wildcard_points = sum(score.wildcard_points or 0 for score in user_scores)
                user_total_points = total_race_points + total_holeshot_points + total_wildcard_points
                
                if user_total_points < penalty_points:
                    return jsonify({
                        "message": f"Du har inte tillräckligt med poäng! Du har {user_total_points} poäng men behöver {penalty_points} poäng för att byta {riders_changed} förare."
                    }), 400
            
            # Delete old riders and apply penalty
            SeasonTeamRider.query.filter_by(season_team_id=team.id).delete()
            
            # Apply penalty to user's total points
            if penalty_points > 0:
                user = User.query.get(uid)
                if user:
                    # Create a penalty score entry - put penalty in race_points since that's what gets summed
                    penalty_score = CompetitionScore(
                        user_id=uid,
                        competition_id=None,  # Penalty not tied to a specific competition
                        total_points=-penalty_points,
                        race_points=-penalty_points,  # Put penalty here so it gets summed in profile
                        holeshot_points=0,
                        wildcard_points=0,
                    )
                    db.session.add(penalty_score)
                    print(f"DEBUG: Applied -{penalty_points} point penalty for {riders_changed} rider changes to user {uid}")
                    print(f"DEBUG: Created CompetitionScore with race_points={-penalty_points}, total_points={-penalty_points}")

        for r in riders:
            db.session.add(SeasonTeamRider(season_team_id=team.id, rider_id=r.id))

        db.session.commit()
        
        if is_team_change:
            if penalty_points > 0:
                return jsonify({"message": f"Team uppdaterat! -{penalty_points} poäng för {riders_changed} bytade förare."}), 200
            else:
                return jsonify({"message": "Team uppdaterat! Inga poängstraff (inga förare byttes)."}), 200
        else:
            return jsonify({"message": "Team sparat!"}), 200
            
    except Exception as e:
        print(f"ERROR in save_season_team: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"message": f"Ett fel uppstod: {str(e)}"}), 500


# -------------------------------------------------
# Admin
# -------------------------------------------------
@app.route("/save_leaderboard_snapshot")
def save_leaderboard_snapshot():
    """Manually save current leaderboard as a snapshot"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Get current leaderboard
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
        
        # Save current ranking
        result = "Saved leaderboard snapshot:\n\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nSnapshot saved successfully! Timestamp: {datetime.utcnow()}"
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error saving snapshot: {str(e)}"

@app.route("/create_initial_snapshot")
def create_initial_snapshot():
    """Create initial leaderboard snapshot for comparison"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        # Clear existing history first
        LeaderboardHistory.query.delete()
        db.session.commit()
        
        from sqlalchemy import func
        
        # Get current leaderboard
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
        
        # Save current ranking as initial snapshot
        result = "Created initial leaderboard snapshot:\n\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nInitial snapshot created! Timestamp: {datetime.utcnow()}"
        result += f"\n\nNow when you run quick simulation, you should see ranking changes!"
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error creating initial snapshot: {str(e)}"

@app.route("/force_snapshot")
def force_snapshot():
    """Force create a snapshot even if no changes detected"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Get current leaderboard
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
        
        # Force save current ranking
        result = "Forced leaderboard snapshot:\n\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nForced snapshot created! Timestamp: {datetime.utcnow()}"
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error creating forced snapshot: {str(e)}"

@app.route("/test_delta")
def test_delta():
    """Test delta calculation by creating two snapshots"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Clear existing history
        LeaderboardHistory.query.delete()
        db.session.commit()
        
        # Get current leaderboard
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
        
        # Create first snapshot
        result = "Creating test snapshots:\n\n"
        result += "FIRST SNAPSHOT:\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nFirst snapshot created at: {datetime.utcnow()}\n\n"
        
        # Wait a moment and create second snapshot with different order
        import time
        time.sleep(1)
        
        # Shuffle the order for testing
        shuffled_scores = list(user_scores)
        import random
        random.shuffle(shuffled_scores)
        
        result += "SECOND SNAPSHOT (shuffled order):\n"
        for i, (user_id, username, team_name, total_points) in enumerate(shuffled_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nSecond snapshot created at: {datetime.utcnow()}\n\n"
        result += "Now refresh the main page to see delta calculations!"
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error creating test snapshots: {str(e)}"

@app.route("/create_baseline")
def create_baseline():
    """Create a baseline snapshot and disable auto-saving"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Clear existing history
        LeaderboardHistory.query.delete()
        db.session.commit()
        
        # Get current leaderboard
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
        
        # Create baseline snapshot
        result = "Creating baseline snapshot:\n\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            result += f"{i}. {username}: {total_points} points\n"
        
        db.session.commit()
        result += f"\nBaseline snapshot created at: {datetime.utcnow()}\n\n"
        result += "Now run quick simulation and you should see ranking arrows!\n"
        result += "The system will compare new rankings against this baseline."
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        db.session.rollback()
        return f"Error creating baseline snapshot: {str(e)}"

@app.route("/debug_leaderboard")
def debug_leaderboard():
    """Debug route to check leaderboard history"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        # Check leaderboard history
        history_entries = db.session.query(LeaderboardHistory).order_by(LeaderboardHistory.created_at.desc()).limit(20).all()
        
        result = "Leaderboard History Debug:\n\n"
        result += f"Total history entries: {len(history_entries)}\n\n"
        
        for entry in history_entries:
            user = User.query.get(entry.user_id)
            result += f"User: {user.username if user else 'Unknown'}, Rank: {entry.ranking}, Points: {entry.total_points}, Time: {entry.created_at}\n"
        
        # Check current leaderboard
        from sqlalchemy import func
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
        
        result += "\n\nCurrent Leaderboard:\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            result += f"{i}. {username}: {total_points} points\n"
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        return f"Debug error: {str(e)}"

@app.route("/clear_history")
def clear_history():
    """Clear all leaderboard history"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        count = LeaderboardHistory.query.count()
        LeaderboardHistory.query.delete()
        db.session.commit()
        return f"<pre>Cleared {count} leaderboard history entries.</pre>"
    except Exception as e:
        db.session.rollback()
        return f"Error clearing history: {str(e)}"

@app.route("/set_baseline")
def set_baseline():
    """Set baseline ranking in session - SIMPLE VERSION"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        from sqlalchemy import func
        
        # Get current leaderboard
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
        
        # Set baseline in session
        baseline = {}
        result = "Setting baseline ranking in session:\n\n"
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            baseline[str(user_id)] = i
            result += f"{i}. {username}: {total_points} points\n"
        
        session['previous_leaderboard_ranking'] = baseline
        result += f"\nBaseline set! Now run quick simulation and you should see arrows!"
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        return f"Error setting baseline: {str(e)}"

@app.route("/test_session")
def test_session():
    """Test what's in session"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    result = "Session contents:\n\n"
    result += f"Username: {session.get('username')}\n"
    result += f"Previous ranking: {session.get('previous_leaderboard_ranking')}\n"
    result += f"All session keys: {list(session.keys())}\n"
    
    return f"<pre>{result}</pre>"

@app.route("/run_migration")
def run_migration():
    """Run database migration - temporary route"""
    if session.get("username") != "test":
        return redirect(url_for("index"))
    
    try:
        # Add the missing column directly with SQL
        db.session.execute(db.text("ALTER TABLE global_simulation ADD COLUMN IF NOT EXISTS active_race_id INTEGER"))
        
        # Add detailed points columns to competition_scores table
        db.session.execute(db.text("ALTER TABLE competition_scores ADD COLUMN IF NOT EXISTS race_points INTEGER DEFAULT 0"))
        db.session.execute(db.text("ALTER TABLE competition_scores ADD COLUMN IF NOT EXISTS holeshot_points INTEGER DEFAULT 0"))
        db.session.execute(db.text("ALTER TABLE competition_scores ADD COLUMN IF NOT EXISTS wildcard_points INTEGER DEFAULT 0"))
        
        # Create leaderboard_history table
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS leaderboard_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                ranking INTEGER NOT NULL,
                total_points INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create index for better performance
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS idx_leaderboard_history_user_created 
            ON leaderboard_history (user_id, created_at)
        """))
        
        # Update existing CompetitionScore records to have proper detailed points
        # This will recalculate all existing scores with the new detailed breakdown
        print("Updating existing competition scores with detailed points...")
        competitions_with_scores = db.session.query(CompetitionScore.competition_id).distinct().all()
        for (comp_id,) in competitions_with_scores:
            print(f"Recalculating scores for competition {comp_id}")
            # This will use the updated calculate_scores function
            calculate_scores(comp_id)
        
        # Create initial leaderboard history entry so we have something to compare with
        print("Creating initial leaderboard history...")
        from sqlalchemy import func
        
        # Get current leaderboard
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
        
        # Save initial ranking
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            history_entry = LeaderboardHistory(
                user_id=user_id,
                ranking=i,
                total_points=int(total_points)
            )
            db.session.add(history_entry)
            print(f"Saved initial ranking: {username} at position {i} with {total_points} points")
        
        db.session.commit()
        return "Migration completed successfully! Added active_race_id, detailed points columns, leaderboard history table, recalculated existing scores, and created initial leaderboard history."
    except Exception as e:
        db.session.rollback()
        return f"Migration failed: {str(e)}"

@app.route("/admin")
@login_required
def admin_page():
    if not is_admin_user():
        return redirect(url_for("index"))
    
    # Skip rider bio column migrations for now
    pass

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
    
    # Use real date
    today = get_today()
    
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
    
    return render_template("admin_organized.html")

@app.route('/competition_management')
def competition_management():
    if not is_admin_user():
        return redirect(url_for("index"))
    
    return render_template("competition_management.html")

@app.route('/rider_management')
def rider_management():
    if not is_admin_user():
        return redirect(url_for("index"))
    
    try:
        # Ensure new bio columns exist (auto-migration)
        try:
            db.session.rollback()
            columns = [
                ('nickname', 'VARCHAR(100)'), ('hometown', 'VARCHAR(100)'), ('residence', 'VARCHAR(100)'),
                ('birthdate', 'DATE'), ('height_cm', 'INTEGER'), ('weight_kg', 'INTEGER'),
                ('team', 'VARCHAR(150)'), ('manufacturer', 'VARCHAR(100)'), ('team_manager', 'VARCHAR(100)'),
                ('mechanic', 'VARCHAR(100)'), ('turned_pro', 'INTEGER'), ('instagram', 'VARCHAR(100)'),
                ('twitter', 'VARCHAR(100)'), ('facebook', 'VARCHAR(100)'), ('website', 'VARCHAR(200)'),
                ('bio', 'TEXT'), ('achievements', 'TEXT'), ('classes', 'VARCHAR(50)')
            ]
            
            # Special handling for classes column - add it first
            try:
                exists = db.session.execute(db.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='riders' AND column_name='classes'
                """)).fetchone()
                if not exists:
                    print("Adding classes column to riders table...")
                    db.session.execute(db.text("ALTER TABLE riders ADD COLUMN classes VARCHAR(50)"))
                    print("Classes column added successfully")
            except Exception as e:
                print(f"Error adding classes column: {e}")
                pass
            for col, typ in columns:
                exists = db.session.execute(db.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='riders' AND column_name=:col
                """), {'col': col}).fetchone()
                if not exists:
                    db.session.execute(db.text(f"ALTER TABLE riders ADD COLUMN {col} {typ}"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            # soft-fail, UI will still work without new columns
            pass
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
    
    # Check if season is active - show warning but allow addition
    season_warning = None
    if is_season_active():
        season_warning = "⚠️ VARNING: Säsong är igång. Nya förare kan påverka befintliga picks och säsongsteam."
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    # Handle image upload
    image_url = None
    if 'rider_image' in request.files:
        file = request.files['rider_image']
        if file and file.filename:
            try:
                # Save image to static/riders/ directory
                import os
                from werkzeug.utils import secure_filename
                
                # Create riders directory if it doesn't exist
                riders_dir = os.path.join(app.static_folder, 'riders')
                os.makedirs(riders_dir, exist_ok=True)
                
                # Generate unique filename - keep original extension
                original_ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
                filename = secure_filename(f"{data['name'].replace(' ', '_')}_{data['rider_number']}{original_ext}")
                file_path = os.path.join(riders_dir, filename)
                file.save(file_path)
                image_url = f"riders/{filename}"
                print(f"Rider image saved: {file_path}")
            except Exception as e:
                print(f"Error saving rider image: {e}")
    
    # Check for number conflict
    existing_rider = Rider.query.filter_by(
        rider_number=data['rider_number'],
        class_name=data['class_name']
    ).first()
    
    if existing_rider:
        return jsonify({
            'error': 'conflict',
            'message': f'Nummer {data["rider_number"]} finns redan för {existing_rider.name} ({existing_rider.class_name})',
            'existing_rider': {
                'id': existing_rider.id,
                'name': existing_rider.name,
                'class_name': existing_rider.class_name,
                'rider_number': existing_rider.rider_number,
                'bike_brand': existing_rider.bike_brand
            }
        }), 409
    
    # Use price from form, or set default based on class
    price = data.get('price')
    if not price:
        price = 450000 if data['class_name'] == '450cc' else 50000
    
    # Handle classes - if not provided, use class_name for backward compatibility
    classes = data.get('classes', data.get('class_name', '250cc'))
    
    rider = Rider(
        name=data['name'],
        class_name=data.get('class_name', classes.split(',')[0].strip() if classes else '250cc'),
        classes=classes,
        rider_number=data['rider_number'],
        bike_brand=data['bike_brand'],
        coast_250=data.get('coast_250'),
        price=price,
        image_url=image_url
    )
    
    db.session.add(rider)
    db.session.commit()
    
    response = {'success': True, 'id': rider.id}
    if season_warning:
        response['warning'] = season_warning
    
    return jsonify(response)

@app.route('/api/riders/<int:rider_id>', methods=['PUT'])
def update_rider(rider_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    rider = Rider.query.get_or_404(rider_id)
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    # Check if season is active - show warning but allow changes
    season_warning = None
    if is_season_active():
        season_warning = "⚠️ VARNING: Säsong är igång. Ändringar kan påverka befintliga picks och säsongsteam."
    
    # Handle image upload
    if 'rider_image' in request.files:
        file = request.files['rider_image']
        if file and file.filename:
            try:
                # Save image to static/riders/ directory
                import os
                from werkzeug.utils import secure_filename
                
                # Create riders directory if it doesn't exist
                riders_dir = os.path.join(app.static_folder, 'riders')
                os.makedirs(riders_dir, exist_ok=True)
                
                # Generate unique filename - keep original extension
                original_ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
                filename = secure_filename(f"{data['name'].replace(' ', '_')}_{data['rider_number']}{original_ext}")
                file_path = os.path.join(riders_dir, filename)
                file.save(file_path)
                rider.image_url = f"riders/{filename}"
                print(f"Rider image updated: {file_path}")
            except Exception as e:
                print(f"Error saving rider image: {e}")
    
    # Check for number conflict (excluding current rider)
    # Use new class_name from classes field if provided, otherwise use current class
    new_class_name = rider.class_name
    if 'classes' in data and data['classes']:
        new_class_name = data['classes'].split(',')[0].strip()
    elif 'class_name' in data:
        new_class_name = data['class_name']
    
    if data['rider_number'] != rider.rider_number or new_class_name != rider.class_name:
        existing_rider = Rider.query.filter_by(
            rider_number=data['rider_number'],
            class_name=new_class_name
        ).filter(Rider.id != rider_id).first()
        
        if existing_rider:
            return jsonify({
                'error': 'conflict',
                'message': f'Nummer {data["rider_number"]} finns redan för {existing_rider.name} ({existing_rider.class_name}). Du måste ändra nummer på den andra föraren först.',
                'existing_rider': {
                    'id': existing_rider.id,
                    'name': existing_rider.name,
                    'class_name': existing_rider.class_name,
                    'rider_number': existing_rider.rider_number,
                    'bike_brand': existing_rider.bike_brand
                }
            }), 409
    
    print(f"DEBUG: Updating rider {rider.name} (ID: {rider.id})")
    print(f"DEBUG: New name: {data['name']}, number: {data['rider_number']}, brand: {data['bike_brand']}")
    
    rider.name = data['name']
    rider.rider_number = data['rider_number']
    rider.bike_brand = data['bike_brand']
    
    # Update classes if provided
    if 'classes' in data:
        rider.classes = data['classes']
        # Update class_name for backward compatibility (use first class)
        if data['classes']:
            rider.class_name = data['classes'].split(',')[0].strip()
        else:
            rider.class_name = '250cc'  # Default fallback
        
        # If no 250cc class, clear coast_250
        if '250cc' not in data['classes']:
            rider.coast_250 = None
    
    # Update price if provided
    if 'price' in data:
        rider.price = data['price']
    
    # Update coast_250 if provided (for 250cc riders)
    if 'coast_250' in data:
        rider.coast_250 = data['coast_250']
    
    # Optional bio fields
    for field in [
        'nickname','hometown','residence','team','manufacturer','team_manager','mechanic',
        'instagram','twitter','facebook','website','bio','achievements'
    ]:
        if field in data:
            setattr(rider, field, data[field])
    
    if 'birthdate' in data:
        try:
            from datetime import datetime
            rider.birthdate = datetime.strptime(data['birthdate'], '%Y-%m-%d').date() if data['birthdate'] else None
        except Exception:
            pass
    if 'height_cm' in data:
        try:
            rider.height_cm = int(data['height_cm']) if data['height_cm'] else None
        except Exception:
            pass
    if 'weight_kg' in data:
        try:
            rider.weight_kg = int(data['weight_kg']) if data['weight_kg'] else None
        except Exception:
            pass
    if 'turned_pro' in data:
        try:
            rider.turned_pro = int(data['turned_pro']) if data['turned_pro'] else None
        except Exception:
            pass
    
    print(f"DEBUG: About to commit rider update for {rider.name} (ID: {rider.id})")
    db.session.commit()
    print(f"DEBUG: Successfully updated rider {rider.name} (ID: {rider.id})")
    
    response = {'success': True}
    if season_warning:
        response['warning'] = season_warning
    
    return jsonify(response)

@app.route('/api/riders/<int:rider_id>', methods=['DELETE'])
def delete_rider(rider_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Check if season is active - show warning but allow deletion
        season_warning = None
        if is_season_active():
            season_warning = "⚠️ VARNING: Säsong är igång. Borttagning kan påverka befintliga picks och säsongsteam."
        
        rider = Rider.query.get_or_404(rider_id)
        
        # Delete associated data first
        from sqlalchemy import text
        try:
            # Delete from all tables that reference riders
            db.session.execute(text("DELETE FROM competition_results WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM holeshot_results WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM season_team_riders WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM race_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM holeshot_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM wildcard_picks WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            db.session.execute(text("DELETE FROM competition_rider_status WHERE rider_id = :rider_id"), {'rider_id': rider_id})
            
            # Commit the deletions
            db.session.commit()
            print(f"Successfully deleted associated data for rider {rider_id}")
            
        except Exception as e:
            print(f"Error deleting associated data for rider {rider_id}: {e}")
            db.session.rollback()
            raise
        
        # Delete the rider
        db.session.delete(rider)
        db.session.commit()
        
        response = {'success': True}
        if season_warning:
            response['warning'] = season_warning
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error deleting rider {rider_id}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Error deleting rider: {str(e)}'}), 500

# Public rider profile
@app.get('/rider/<int:rider_id>')
def rider_profile(rider_id: int):
    rider = Rider.query.get_or_404(rider_id)
    return render_template('rider_detail.html', rider=rider, username=session.get('username'))

# Public rider list
@app.get('/riders')
def riders_directory():
    # Simple searchable list grouped by class
    riders_450 = Rider.query.filter_by(class_name='450cc').order_by(Rider.rider_number.asc()).all()
    riders_250_east = Rider.query.filter_by(class_name='250cc', coast_250='east').order_by(Rider.rider_number.asc()).all()
    riders_250_west = Rider.query.filter_by(class_name='250cc', coast_250='west').order_by(Rider.rider_number.asc()).all()
    return render_template('riders.html',
                           riders_450=riders_450,
                           riders_250_east=riders_250_east,
                           riders_250_west=riders_250_west,
                           username=session.get('username'))

# API endpoints for competition management
@app.route('/api/competitions/list', methods=['GET'])
def list_competitions():
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # First check if start_time column exists
        try:
            db.session.execute(db.text("SELECT start_time FROM competitions LIMIT 1"))
            has_start_time = True
        except Exception:
            has_start_time = False
        
        competitions = Competition.query.order_by(Competition.event_date).all()
        result = []
        
        for comp in competitions:
            comp_data = {
                'id': comp.id,
                'name': comp.name,
                'event_date': comp.event_date.isoformat() if comp.event_date else None,
                'series': comp.series,
                'coast_250': comp.coast_250,
                'point_multiplier': comp.point_multiplier,
                'is_triple_crown': comp.is_triple_crown,
                'timezone': comp.timezone
            }
            
            # Only add start_time if column exists
            if has_start_time and hasattr(comp, 'start_time'):
                comp_data['start_time'] = comp.start_time.isoformat() if comp.start_time else None
            else:
                comp_data['start_time'] = None
                
            result.append(comp_data)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in list_competitions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitions/create', methods=['POST'])
def create_competition():
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    try:
        competition_data = {
            'name': data['name'],
            'event_date': datetime.strptime(data['event_date'], '%Y-%m-%d').date() if data['event_date'] else None,
            'series': data['series'],
            'coast_250': data.get('coast_250'),
            'point_multiplier': data.get('point_multiplier', 1.0),
            'is_triple_crown': data.get('is_triple_crown', False),
            'timezone': data.get('timezone')
        }
        
        # Only add start_time if it exists in the model
        if hasattr(Competition, 'start_time') and data.get('start_time'):
            try:
                # Handle both HH:MM and HH:MM:SS formats
                time_str = data['start_time']
                if len(time_str.split(':')) == 2:
                    competition_data['start_time'] = datetime.strptime(time_str, '%H:%M').time()
                else:
                    competition_data['start_time'] = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError as e:
                print(f"Error parsing start_time '{data['start_time']}': {e}")
                competition_data['start_time'] = None
        
        competition = Competition(**competition_data)
        db.session.add(competition)
        db.session.commit()
        
        return jsonify({'success': True, 'id': competition.id, 'message': 'Tävling skapad!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/competitions/update/<int:competition_id>', methods=['PUT'])
def update_competition(competition_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    competition = Competition.query.get_or_404(competition_id)
    data = request.get_json()
    
    try:
        competition.name = data['name']
        competition.event_date = datetime.strptime(data['event_date'], '%Y-%m-%d').date() if data['event_date'] else None
        competition.series = data['series']
        competition.coast_250 = data.get('coast_250')
        competition.point_multiplier = data.get('point_multiplier', 1.0)
        competition.is_triple_crown = data.get('is_triple_crown', False)
        competition.timezone = data.get('timezone')
        
        # Only update start_time if it exists in the model
        if hasattr(competition, 'start_time') and data.get('start_time'):
            try:
                # Handle both HH:MM and HH:MM:SS formats
                time_str = data['start_time']
                if len(time_str.split(':')) == 2:
                    competition.start_time = datetime.strptime(time_str, '%H:%M').time()
                else:
                    competition.start_time = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError as e:
                print(f"Error parsing start_time '{data['start_time']}': {e}")
                competition.start_time = None
        elif hasattr(competition, 'start_time'):
            competition.start_time = None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Tävling uppdaterad!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/competitions/delete/<int:competition_id>', methods=['DELETE'])
def delete_competition(competition_id):
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    competition = Competition.query.get_or_404(competition_id)
    force = request.args.get('force', 'false').lower() == 'true'
    
    try:
        # Check if competition has any picks or results
        race_picks = RacePick.query.filter_by(competition_id=competition_id).count()
        holeshot_picks = HoleshotPick.query.filter_by(competition_id=competition_id).count()
        wildcard_picks = WildcardPick.query.filter_by(competition_id=competition_id).count()
        results = CompetitionResult.query.filter_by(competition_id=competition_id).count()
        holeshot_results = HoleshotResult.query.filter_by(competition_id=competition_id).count()
        
        if not force and (race_picks > 0 or holeshot_picks > 0 or wildcard_picks > 0 or results > 0 or holeshot_results > 0):
            return jsonify({'error': 'Kan inte ta bort tävling som har picks eller resultat'}), 400
        
        if force:
            # Force delete - remove all related data first
            RacePick.query.filter_by(competition_id=competition_id).delete()
            HoleshotPick.query.filter_by(competition_id=competition_id).delete()
            WildcardPick.query.filter_by(competition_id=competition_id).delete()
            CompetitionResult.query.filter_by(competition_id=competition_id).delete()
            HoleshotResult.query.filter_by(competition_id=competition_id).delete()
            CompetitionRiderStatus.query.filter_by(competition_id=competition_id).delete()
            CompetitionScore.query.filter_by(competition_id=competition_id).delete()
            CompetitionImage.query.filter_by(competition_id=competition_id).delete()
        
        db.session.delete(competition)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Tävling borttagen!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/competitions/migrate_start_time', methods=['POST'])
def migrate_start_time():
    """Add start_time column to competitions table if it doesn't exist"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Start fresh transaction
        db.session.rollback()  # Clear any existing transaction
        
        # Check if start_time column exists
        try:
            db.session.execute(db.text("SELECT start_time FROM competitions LIMIT 1"))
            db.session.commit()
            return jsonify({'success': True, 'message': 'start_time column already exists'})
        except Exception:
            db.session.rollback()  # Clear failed transaction
            pass
        
        # Add start_time column in a separate transaction
        try:
            db.session.execute(db.text('ALTER TABLE competitions ADD COLUMN start_time TIME'))
            db.session.commit()
            print("✅ Added start_time column successfully")
        except Exception as e:
            db.session.rollback()
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("ℹ️ start_time column already exists")
            else:
                raise e
        
        # Set default start time for all existing competitions in another transaction
        try:
            from datetime import time
            default_time = time(20, 0)  # 8:00 PM
            
            result = db.session.execute(db.text('UPDATE competitions SET start_time = :default_time WHERE start_time IS NULL'), 
                                      {'default_time': default_time})
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Added start_time column and updated {result.rowcount} competitions with default 8:00 PM'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': True, 
                'message': f'Added start_time column but failed to set defaults: {str(e)}'
            })
            
    except Exception as e:
        db.session.rollback()
        print(f"Migration error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitions/update_seasons_to_2026', methods=['POST'])
def update_seasons_to_2026():
    """Update all 2025 series and competitions to 2026"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        db.session.rollback()
        
        # Update series from 2025 to 2026
        series_2025 = Series.query.filter_by(year=2025).all()
        series_updated = 0
        for series in series_2025:
            series.year = 2026
            series_updated += 1
        
        # Update competitions from 2025 to 2026
        from datetime import date
        competitions_2025 = Competition.query.filter(
            Competition.event_date >= date(2025, 1, 1),
            Competition.event_date <= date(2025, 12, 31)
        ).all()
        competitions_updated = 0
        for comp in competitions_2025:
            if comp.event_date:
                new_date = comp.event_date.replace(year=2026)
                comp.event_date = new_date
                competitions_updated += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {series_updated} series and {competitions_updated} competitions from 2025 to 2026'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Update seasons error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitions/update_to_official_2026', methods=['POST'])
def update_to_official_2026():
    """Update all competitions to match official 2026 SMX schedule"""
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Delete all existing competitions and related data
        # First delete all related data to avoid foreign key constraints
        RacePick.query.delete()
        HoleshotPick.query.delete()
        WildcardPick.query.delete()
        CompetitionResult.query.delete()
        HoleshotResult.query.delete()
        CompetitionRiderStatus.query.delete()
        CompetitionScore.query.delete()
        CompetitionImage.query.delete()
        
        # Then delete competitions
        Competition.query.delete()
        
        # Get or create series
        supercross = Series.query.filter_by(name='Supercross', year=2026).first()
        if not supercross:
            supercross = Series(
                name='Supercross',
                year=2026,
                start_date=date(2026, 1, 10),
                end_date=date(2026, 5, 9),
                is_active=True,
                points_system='standard'
            )
            db.session.add(supercross)
        
        motocross = Series.query.filter_by(name='Motocross', year=2026).first()
        if not motocross:
            motocross = Series(
                name='Motocross',
                year=2026,
                start_date=date(2026, 5, 30),
                end_date=date(2026, 8, 29),
                is_active=True,
                points_system='standard'
            )
            db.session.add(motocross)
        
        smx_finals = Series.query.filter_by(name='SMX Finals', year=2026).first()
        if not smx_finals:
            smx_finals = Series(
                name='SMX Finals',
                year=2026,
                start_date=date(2026, 9, 12),
                end_date=date(2026, 9, 26),
                is_active=True,
                points_system='playoff'
            )
            db.session.add(smx_finals)
        
        db.session.commit()
        
        # Create all competitions with official 2026 schedule
        create_supercross_competitions(supercross.id)
        create_motocross_competitions(motocross.id)
        create_smx_finals_competitions(smx_finals.id)
        
        return jsonify({
            'success': True,
            'message': 'Updated all competitions to official 2026 SMX schedule'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Update to official 2026 error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
        start_date=date(2026, 1, 10),  # Anaheim 1
        end_date=date(2026, 5, 9),     # Salt Lake City
        is_active=True,
        points_system='standard'
    )
    
    # Create Motocross series (starts in May 2026)
    motocross = Series(
        name='Motocross',
        year=2026,
        start_date=date(2026, 5, 30),  # Fox Raceway
        end_date=date(2026, 8, 29),    # Ironman
        is_active=True,
        points_system='standard'
    )
    
    # Create SMX Finals series (starts in September 2026)
    smx_finals = Series(
        name='SMX Finals',
        year=2026,
        start_date=date(2026, 9, 12),  # Playoff 1
        end_date=date(2026, 9, 26),    # Final
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
    """Create all Supercross competitions for 2026 - includes San Francisco"""
    # Supercross races 2026 - Official SMX Schedule
    supercross_races = [
        {"name": "Anaheim 1", "date": "2026-01-10", "coast_250": "west", "is_triple_crown": False},
        {"name": "San Diego", "date": "2026-01-17", "coast_250": "west", "is_triple_crown": False},
        {"name": "Anaheim 2", "date": "2026-01-24", "coast_250": "west", "is_triple_crown": True},
        {"name": "Houston", "date": "2026-01-31", "coast_250": "west", "is_triple_crown": False},
        {"name": "Glendale", "date": "2026-02-07", "coast_250": "west", "is_triple_crown": False},
        {"name": "Seattle", "date": "2026-02-14", "coast_250": "east", "is_triple_crown": False},
        {"name": "Arlington", "date": "2026-02-21", "coast_250": "east", "is_triple_crown": False},
        {"name": "Daytona", "date": "2026-02-28", "coast_250": "east", "is_triple_crown": True},
        {"name": "Indianapolis", "date": "2026-03-07", "coast_250": "showdown", "is_triple_crown": False},
        {"name": "Birmingham", "date": "2026-03-21", "coast_250": "east", "is_triple_crown": False},
        {"name": "Detroit", "date": "2026-03-28", "coast_250": "showdown", "is_triple_crown": False},
        {"name": "St. Louis", "date": "2026-04-04", "coast_250": "east", "is_triple_crown": False},
        {"name": "Nashville", "date": "2026-04-11", "coast_250": "east", "is_triple_crown": True},
        {"name": "Cleveland", "date": "2026-04-18", "coast_250": "east", "is_triple_crown": False},
        {"name": "Philadelphia", "date": "2026-04-25", "coast_250": "west", "is_triple_crown": False},
        {"name": "Denver", "date": "2026-05-02", "coast_250": "showdown", "is_triple_crown": False},
        {"name": "Salt Lake City", "date": "2026-05-09", "coast_250": "west", "is_triple_crown": False}
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
            series="SX",
            point_multiplier=1.0,
            is_triple_crown=1 if race.get("is_triple_crown", False) else 0,
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
        {"name": "Fox Raceway National", "date": "2026-05-30", "location": "Pala, CA"},
        {"name": "Hangtown Classic", "date": "2026-06-06", "location": "Sacramento, CA"},
        {"name": "Thunder Valley National", "date": "2026-06-13", "location": "Lakewood, CO"},
        {"name": "High Point National", "date": "2026-06-20", "location": "Mount Morris, PA"},
        {"name": "RedBud National", "date": "2026-07-04", "location": "Buchanan, MI"},
        {"name": "Southwick National", "date": "2026-07-11", "location": "Southwick, MA"},
        {"name": "Spring Creek National", "date": "2026-07-18", "location": "Millville, MN"},
        {"name": "Washougal National", "date": "2026-07-25", "location": "Washougal, WA"},
        {"name": "Unadilla National", "date": "2026-08-15", "location": "New Berlin, NY"},
        {"name": "Budds Creek National", "date": "2026-08-22", "location": "Mechanicsville, MD"},
        {"name": "Ironman National", "date": "2026-08-29", "location": "Crawfordsville, IN"}
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
            series="MX",  # Motocross series
            point_multiplier=1.0,
            is_triple_crown=0,
            coast_250="both",  # In MX, all 250cc riders race together
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
        {"name": "SMX Playoff 1", "date": "2026-09-12", "phase": "playoff1", "multiplier": 1.0},
        {"name": "SMX Playoff 2", "date": "2026-09-19", "phase": "playoff2", "multiplier": 2.0},
        {"name": "SMX Final", "date": "2026-09-26", "phase": "final", "multiplier": 3.0}
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
            series="SMX",  # SMX Finals series
            point_multiplier=race["multiplier"],  # 1.0x, 2.0x, 3.0x for SMX Finals
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
                series="MX",  # Motocross series
                point_multiplier=1.0,
                is_triple_crown=0,
                coast_250="both",  # In MX, all 250cc riders race together
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
            {"name": "SMX Playoff 1", "date": "2026-09-06", "phase": "playoff1", "multiplier": 1.0},
            {"name": "SMX Playoff 2", "date": "2026-09-13", "phase": "playoff2", "multiplier": 2.0},
            {"name": "SMX Final", "date": "2026-09-20", "phase": "final", "multiplier": 3.0}
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
                point_multiplier=race["multiplier"],  # 1.0x, 2.0x, 3.0x for SMX Finals
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
    if session.get("username") != "test":
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Create all tables
        db.create_all()
        
        # Manually add missing columns to competitions table
        try:
            # Check and add series_id column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='series_id'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN series_id INTEGER"))
            
            # Check and add phase column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='phase'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN phase VARCHAR(20)"))
            
            # Check and add is_qualifying column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='competitions' AND column_name='is_qualifying'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE competitions ADD COLUMN is_qualifying BOOLEAN DEFAULT FALSE"))
            
            db.session.commit()
        except Exception as col_error:
            db.session.rollback()
        
        # Check and add missing columns to riders table
        try:
            # Check and add series_participation column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='series_participation'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN series_participation VARCHAR(50) DEFAULT 'all'"))
            
            # Check and add smx_qualified column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_qualified'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN smx_qualified BOOLEAN DEFAULT FALSE"))
            
            # Check and add smx_seed_points column
            result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='riders' AND column_name='smx_seed_points'"))
            if not result.fetchone():
                db.session.execute(db.text("ALTER TABLE riders ADD COLUMN smx_seed_points INTEGER DEFAULT 0"))
            
            db.session.commit()
        except Exception as riders_error:
            db.session.rollback()
        
        # Check if global_simulation exists and create default entry
        try:
            if not GlobalSimulation.query.first():
                global_sim = GlobalSimulation(
                    active=False,
                    simulated_time=None,
                    start_time=None,
                    scenario=None
                )
                db.session.add(global_sim)
                db.session.commit()
        except Exception as global_error:
            pass
        
        # Fix all 2025 competitions to 2026
        try:
            competitions_2025 = Competition.query.filter(Competition.event_date.like('2025-%')).all()
            for comp in competitions_2025:
                comp.event_date = comp.event_date.replace(year=2026)
            db.session.commit()
        except Exception as date_error:
            db.session.rollback()
        
        return jsonify({'success': True, 'message': f'Database tables and columns fixed. Updated {len(competitions_2025) if "competitions_2025" in locals() else 0} competitions from 2025 to 2026'})
        
    except Exception as e:
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
        "admin_new.html",
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
        # Getting admin results

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

        # Found results and holeshot results

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
        # Error in admin_get_results
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
    # Results saved for competition
    
    calculate_scores(comp_id)

    flash("Resultat sparade och poäng beräknade!", "success")
    return redirect(url_for("admin_page"))


@app.post("/admin/simulate_all_users_picks/<int:competition_id>")
def admin_simulate_all_users_picks(competition_id):
    """Simulate picks for all users to test 'Se Andras Picks' functionality"""
    if not is_admin_user():
        return redirect(url_for("login"))
    
    try:
        # Get all users except current user
        current_user_id = session["user_id"]
        users = User.query.filter(User.id != current_user_id).all()
        
        # Get all riders
        riders_450 = Rider.query.filter_by(class_name='450cc').all()
        riders_250 = Rider.query.filter_by(class_name='250cc').all()
        
        if not riders_450 or not riders_250:
            return jsonify({"error": "No riders found"}), 400
        
        for user in users:
            # Clear existing picks for this user and competition
            RacePick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()
            HoleshotPick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()
            WildcardPick.query.filter_by(user_id=user.id, competition_id=competition_id).delete()
            
            # Create random picks for 450cc (top 6)
            import random
            selected_450 = random.sample(riders_450, min(6, len(riders_450)))
            for i, rider in enumerate(selected_450, 1):
                pick = RacePick(
                    user_id=user.id,
                    competition_id=competition_id,
                    rider_id=rider.id,
                    predicted_position=i
                )
                db.session.add(pick)
            
            # Create random picks for 250cc (top 6)
            selected_250 = random.sample(riders_250, min(6, len(riders_250)))
            for i, rider in enumerate(selected_250, 1):
                pick = RacePick(
                    user_id=user.id,
                    competition_id=competition_id,
                    rider_id=rider.id,
                    predicted_position=i
                )
                db.session.add(pick)
            
            # Create holeshot picks
            holeshot_450 = HoleshotPick(
                user_id=user.id,
                competition_id=competition_id,
                rider_id=random.choice(riders_450).id,
                class_name='450cc'
            )
            db.session.add(holeshot_450)
            
            holeshot_250 = HoleshotPick(
                user_id=user.id,
                competition_id=competition_id,
                rider_id=random.choice(riders_250).id,
                class_name='250cc'
            )
            db.session.add(holeshot_250)
            
            # Create wildcard pick
            wildcard = WildcardPick(
                user_id=user.id,
                competition_id=competition_id,
                rider_id=random.choice(riders_450 + riders_250).id,
                position=random.randint(1, 6)
            )
            db.session.add(wildcard)
        
        db.session.commit()
        return jsonify({"message": f"Simulated picks for {len(users)} users"})
        
    except Exception as e:
        print(f"Error simulating picks: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/admin/simulate/<int:competition_id>")
def admin_simulate(competition_id):
    if not is_admin_user():
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

    # Don't create picks for test user - let users make their own picks
    # db.session.add(RacePick(user_id=user.id, competition_id=competition_id, rider_id=jett.id, predicted_position=1))
    # db.session.add(RacePick(user_id=user.id, competition_id=competition_id, rider_id=deegan.id, predicted_position=1))
    # db.session.add(HoleshotPick(user_id=user.id, competition_id=competition_id, rider_id=jett.id, class_name="450cc"))
    # db.session.add(HoleshotPick(user_id=user.id, competition_id=competition_id, rider_id=deegan.id, class_name="250cc"))

    # any450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.price.desc()).first()
    # if any450:
    #     db.session.add(WildcardPick(user_id=user.id, competition_id=competition_id, rider_id=any450.id, position=12))
    
    # Still need to create position 12 result for wildcard
    any450 = Rider.query.filter_by(class_name="450cc").order_by(Rider.price.desc()).first()
    if any450:
        existing_pos12 = CompetitionResult.query.filter_by(competition_id=competition_id, position=12).first()
        if not existing_pos12:
            db.session.add(CompetitionResult(competition_id=competition_id, rider_id=any450.id, position=12))

    db.session.commit()
    calculate_scores(competition_id)
    
    # Set this competition as active race and activate its series
    try:
        global_sim = GlobalSimulation.query.first()
        if not global_sim:
            global_sim = GlobalSimulation(active=True, scenario='race_in_3h')
            db.session.add(global_sim)
        else:
            global_sim.active = True
            global_sim.scenario = 'race_in_3h'
        
        global_sim.active_race_id = competition_id
        print(f"DEBUG: Set active race to {comp.name} (ID: {competition_id})")
        
        # Also activate the series for this competition
        if comp.series_id:
            # Deactivate all series first
            Series.query.update({'is_active': False})
            
            # Activate the series for this competition
            competition_series = Series.query.get(comp.series_id)
            if competition_series:
                competition_series.is_active = True
                print(f"DEBUG: Activated series '{competition_series.name}' for competition '{comp.name}'")
        
        db.session.commit()
    except Exception as e:
        print(f"DEBUG: Error setting active race: {e}")
        db.session.rollback()

    flash(f"Simulerade resultat och picks har lagts in för {comp.name}. Poäng uträknade! Race satt som aktivt.", "success")
    return redirect(url_for("admin_page"))


@app.post("/admin/set_date")
def admin_set_date():
    if session.get("username") != "test":
        return redirect(url_for("login"))
    flash("Simulerat datum är inte implementerat i denna version.", "error")
    return redirect(url_for("admin_page"))



# -------------------------------------------------
# API helpers (för templates JS) - Updated for ranking arrows
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
    
    # Lägg till rank och delta (jämför med tidigare ranking)
    result = []
    
    # Use database-backed LeaderboardHistory for persistent ranking
    try:
        # Get the most recent ranking from database
        latest_timestamp = db.session.query(db.func.max(LeaderboardHistory.created_at)).scalar()
        
        previous_ranking = {}
        if latest_timestamp:
            latest_history = db.session.query(
                LeaderboardHistory.user_id,
                LeaderboardHistory.ranking
            ).filter(LeaderboardHistory.created_at == latest_timestamp).all()
            
            previous_ranking = {str(user_id): ranking for user_id, ranking in latest_history}
            print(f"DEBUG: Found previous ranking for {len(previous_ranking)} users from {latest_timestamp}")
        else:
            print("DEBUG: No previous ranking history found - will create baseline")
            # Create initial baseline ranking (all users start at rank 0)
            for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
                previous_ranking[str(user_id)] = 0  # All start at rank 0
        
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            current_rank = i
            previous_rank = previous_ranking.get(str(user_id))
            
            if previous_rank is not None and previous_rank > 0:
                delta = current_rank - previous_rank
                print(f"DEBUG: User {username} - Previous rank: {previous_rank}, Current rank: {current_rank}, Delta: {delta}")
            else:
                # First time or baseline (rank 0) - show improvement
                delta = -current_rank
                print(f"DEBUG: User {username} - First time/baseline, Current rank: {current_rank}, Delta: {delta}")
            
            result.append({
                "user_id": user_id,
                "username": username,
                "team_name": team_name or None,
                "total_points": int(total_points),
                "rank": current_rank,
                "delta": delta
            })
        
        # Only save new ranking if there are actual changes
        has_changes = any(row["delta"] != 0 for row in result)
        if has_changes:
            print(f"DEBUG: Saving new ranking to database...")
            for row in result:
                history_entry = LeaderboardHistory(
                    user_id=row["user_id"],
                    ranking=row["rank"],
                    total_points=row["total_points"]
                )
                db.session.add(history_entry)
                print(f"DEBUG: Saved ranking - User {row['username']}: rank {row['rank']}, points {row['total_points']}, delta {row['delta']}")
            
            db.session.commit()
            print(f"DEBUG: Leaderboard history saved successfully")
        else:
            print("DEBUG: No ranking changes detected, not saving to database")
            
    except Exception as e:
        print(f"DEBUG: Error in leaderboard ranking: {e}")
        db.session.rollback()
        # Fallback to no deltas if database fails
        for i, (user_id, username, team_name, total_points) in enumerate(user_scores, 1):
            result.append({
                "user_id": user_id,
                "username": username,
                "team_name": team_name or None,
                "total_points": int(total_points),
                "rank": i,
                "delta": 0
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
    try:
        
        competitions = (
            Competition.query
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
                    Rider.name.label('rider_name'),
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
                    Rider.name.label('rider_name'),
                    HoleshotResult.class_name,
                    Rider.rider_number,
                    Rider.image_url,
                    Rider.bike_brand
                )
                .join(Rider, Rider.id == HoleshotResult.rider_id)
                .filter(HoleshotResult.competition_id == comp.id)
                .all()
            )
            
            # Add race points to each result (different point systems for different series)
            results_with_points = []
            for result in results:
                # Use appropriate point system based on series
                if comp.series == "SX":
                    points = get_smx_qualification_points(result.position)  # Supercross uses SMX points
                elif comp.series == "MX":
                    points = get_smx_qualification_points(result.position)  # Motocross uses SMX points
                elif comp.series == "SMX":
                    points = get_smx_qualification_points(result.position) * comp.point_multiplier  # SMX Finals with multiplier
                else:
                    points = get_smx_qualification_points(result.position)  # Default to SMX points
                
                result_dict = {
                    'rider_id': result.rider_id,
                    'position': result.position,
                    'rider_name': result.rider_name,
                    'class_name': result.class_name,
                    'rider_number': result.rider_number,
                    'image_url': result.image_url,
                    'bike_brand': result.bike_brand,
                    'points': points
                }
                results_with_points.append(result_dict)
            
            competition_results[comp.id] = {
                'results': results_with_points,
                'holeshots': holeshots
            }
    
        # Determine status for each competition and find the latest one
        today = get_today()
        latest_competition_id = None
        latest_competition_date = None
        
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
            if has_results and (latest_competition_id is None or comp.event_date > latest_competition_date):
                latest_competition_id = comp.id
                latest_competition_date = comp.event_date
            elif not latest_competition_id and comp.event_date and comp.event_date >= today:
                latest_competition_id = comp.id
                latest_competition_date = comp.event_date
        
        return render_template(
            "race_results.html", 
            competitions=competitions, 
            competition_results=competition_results,
            latest_competition_id=latest_competition_id,
            username=session.get("username", "Gäst"),
            is_logged_in="user_id" in session
        )
    
    except Exception as e:
        print(f"ERROR in race_results_page: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading race results: {str(e)}", 500

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
    
    # Force session refresh to ensure we see latest data
    db.session.expire_all()
    
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

@app.route("/get_other_users_picks/<int:competition_id>")
def get_other_users_picks(competition_id):
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    # Get all riders once as master list
    all_riders = Rider.query.all()
    riders_dict = {rider.id: rider for rider in all_riders}
    
    # Get all users except current user
    current_user_id = session["user_id"]
    other_users = User.query.filter(User.id != current_user_id).all()
    
    print(f"DEBUG: Found {len(other_users)} other users")
    
    users_picks = []
    for user in other_users:
        # Get race picks for this user (only top 6 per class)
        race_picks = RacePick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
        
        picks = []
        picks_450 = []
        picks_250 = []
        
        for pick in race_picks:
            rider = riders_dict.get(pick.rider_id)
            if rider:
                # Ensure we have valid rider data
                rider_number = getattr(rider, 'rider_number', '?') or '?'
                rider_name = getattr(rider, 'name', 'Unknown') or 'Unknown'
                bike_brand = getattr(rider, 'bike_brand', 'Unknown') or 'Unknown'
                
                pick_data = {
                    "position": pick.predicted_position,
                    "class": rider.class_name,
                    "rider_name": f"#{rider_number} {rider_name} ({bike_brand})"
                }
                print(f"DEBUG: Created pick_data: {pick_data}")
                
                if rider.class_name == '450cc' and len(picks_450) < 6:
                    picks_450.append(pick_data)
                elif rider.class_name == '250cc' and len(picks_250) < 6:
                    picks_250.append(pick_data)
        
        # Sort by position and take only top 6
        picks_450.sort(key=lambda x: x['position'])
        picks_250.sort(key=lambda x: x['position'])
        
        picks = picks_450 + picks_250
        
        # Get holeshot picks
        holeshot_picks = HoleshotPick.query.filter_by(user_id=user.id, competition_id=competition_id).all()
        holeshot_450 = None
        holeshot_250 = None
        
        for holeshot in holeshot_picks:
            rider = riders_dict.get(holeshot.rider_id)
            if rider and holeshot.class_name == '450cc':
                holeshot_450 = {
                    "rider_number": getattr(rider, 'rider_number', '?') or '?',
                    "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                }
            elif rider and holeshot.class_name == '250cc':
                holeshot_250 = {
                    "rider_number": getattr(rider, 'rider_number', '?') or '?',
                    "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                }
        
        # Get wildcard pick
        wildcard_pick = WildcardPick.query.filter_by(user_id=user.id, competition_id=competition_id).first()
        wildcard = None
        if wildcard_pick:
            rider = riders_dict.get(wildcard_pick.rider_id)
            if rider:
                wildcard = {
                    "position": wildcard_pick.position,
                    "rider_number": getattr(rider, 'rider_number', '?') or '?',
                    "rider_name": getattr(rider, 'name', 'Unknown') or 'Unknown'
                }
        
        print(f"DEBUG: User {user.username} - picks: {len(picks)}, holeshot_450: {holeshot_450 is not None}, holeshot_250: {holeshot_250 is not None}, wildcard: {wildcard is not None}")
        
        if picks or holeshot_450 or holeshot_250 or wildcard:  # Only include users who have made any picks
            print(f"DEBUG: Including user {user.username} - picks_450: {picks_450}")
            print(f"DEBUG: Including user {user.username} - picks_250: {picks_250}")
            user_data = {
                "username": user.username,
                "display_name": getattr(user, 'display_name', None) or user.username,
                "picks_450": picks_450,
                "picks_250": picks_250,
                "holeshot_450": holeshot_450,
                "holeshot_250": holeshot_250,
                "wildcard": wildcard
            }
            print(f"DEBUG: Adding user data: {user_data['display_name']} (username: {user_data['username']})")
            users_picks.append(user_data)
        else:
            print(f"DEBUG: Excluding user {user.username} - no picks found")
    
    print(f"DEBUG: Returning {len(users_picks)} users with picks")
    return jsonify(users_picks)

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
    
    new_rider_ids = [int(p.get("rider_id")) for p in picks if p.get("rider_id")]
    if len(new_rider_ids) != len(set(new_rider_ids)):
        return jsonify({"error": "Du kan inte välja samma förare flera gånger"}), 400
    
    # 4) Rensa tidigare picks/holeshot för användaren i denna tävling FÖRST
    # VIKTIGT: Rensa INTE resultat när picks sparas - bara picks
    deleted_picks = RacePick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_holeshots = HoleshotPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    deleted_wildcards = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).delete()
    print(f"DEBUG: Deleted {deleted_picks} old picks, {deleted_holeshots} old holeshots, {deleted_wildcards} old wildcards")

    # 5) Validera wildcard EFTER att gamla picks rensats
    wc_pick = data.get("wildcard_pick")
    wc_pos = data.get("wildcard_pos")
    if wc_pick and wc_pos:
        try:
            wc_pick_i = int(wc_pick)
            wc_pos_i = int(wc_pos)

            # Blockera OUT även för wildcard
            if wc_pick_i in out_ids:
                return jsonify({"error": "Förare är OUT för detta race"}), 400
            
            # Blockera om samma förare redan är vald i top 6 (endast 450cc)
            # Hämta 450cc rider IDs från de nya picksen
            riders_450_ids = []
            for p in picks:
                if p.get("rider_id") and p.get("class") == "450cc":
                    riders_450_ids.append(int(p.get("rider_id")))
            
            if wc_pick_i in riders_450_ids:
                return jsonify({"error": "Du kan inte välja samma förare för wildcard som i top 6"}), 400
        except Exception:
            pass

    # 6) Spara Top-6 picks
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
                print(f"DEBUG: Coast validation failed - Rider: {rider.name} (ID: {rider.id}), rider coast: {rider.coast_250}, competition coast: {comp.coast_250}")
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
            
            # Holeshot och top 6 kan vara samma förare - det är naturligt!
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
            
            # Holeshot och top 6 kan vara samma förare - det är naturligt!

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

    # 7) Wildcard – spara efter validering
    if wc_pick and wc_pos:
        try:
            wc_pick_i = int(wc_pick)
            wc_pos_i = int(wc_pos)

            existing_wc = WildcardPick.query.filter_by(user_id=uid, competition_id=comp_id).first()
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
    
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()
    
    uid = session["user_id"]

    actual = CompetitionResult.query.filter_by(competition_id=competition_id).all()
    actual_by_rider = {r.rider_id: r for r in actual}
    picks = RacePick.query.filter_by(user_id=uid, competition_id=competition_id).all()

    breakdown = []
    total = 0

    for p in picks:
        act = actual_by_rider.get(p.rider_id)
        if not act:
            # Try to get rider name for better error message
            rider = Rider.query.get(p.rider_id)
            rider_name = rider.name if rider else f"rider {p.rider_id}"
            breakdown.append(f"❌ Pick {rider_name} hittades inte i resultat")
            continue
        
        # Get rider name for display
        rider = Rider.query.get(p.rider_id)
        rider_name = rider.name if rider else f"rider {p.rider_id}"
        
        if act.position == p.predicted_position:
            breakdown.append(f"✅ Perfekt: {rider_name} på pos {p.predicted_position} (+25)")
            total += 25
        elif act.position <= 6:
            breakdown.append(f"⚠️ Top6: {rider_name} var {act.position} (+5)")
            total += 5
        else:
            breakdown.append(f"❌ Miss: {rider_name} var {act.position}")

    holopicks = HoleshotPick.query.filter_by(user_id=uid, competition_id=competition_id).all()
    holos = HoleshotResult.query.filter_by(competition_id=competition_id).all()
    holo_by_class = {h.class_name: h for h in holos}
    for hp in holopicks:
        act = holo_by_class.get(hp.class_name)
        # Get rider name for holeshot display
        rider = Rider.query.get(hp.rider_id)
        rider_name = rider.name if rider else f"rider {hp.rider_id}"
        
        if act and act.rider_id == hp.rider_id:
            breakdown.append(f"✅ Holeshot {hp.class_name}: {rider_name} rätt (+3)")
            total += 3
        else:
            breakdown.append(f"❌ Holeshot {hp.class_name}: {rider_name} fel")

    wc = WildcardPick.query.filter_by(user_id=uid, competition_id=competition_id).first()
    if wc:
        target = next((r for r in actual if r.position == wc.position), None)
        # Get rider name for wildcard display
        rider = Rider.query.get(wc.rider_id)
        rider_name = rider.name if rider else f"rider {wc.rider_id}"
        
        if target and target.rider_id == wc.rider_id:
            breakdown.append(f"✅ Wildcard: {rider_name} på pos {wc.position} (+15)")
            total += 15
        else:
            breakdown.append(f"❌ Wildcard: {rider_name} fel")

    return jsonify({"breakdown": breakdown, "total": total})

# -------------------------------------------------
# Poängberäkning
# -------------------------------------------------
def calculate_scores(comp_id: int):
    
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()
    
    users = User.query.all()
    actual_results = CompetitionResult.query.filter_by(competition_id=comp_id).all()
    actual_holeshots = HoleshotResult.query.filter_by(competition_id=comp_id).all()

    print(f"DEBUG: Found {len(users)} users, {len(actual_results)} results, {len(actual_holeshots)} holeshots")
    
    actual_results_dict = {res.rider_id: res for res in actual_results}
    actual_holeshots_dict = {hs.class_name: hs for hs in actual_holeshots}

    for user in users:
        race_points = 0
        holeshot_points = 0
        wildcard_points = 0
        picks = RacePick.query.filter_by(user_id=user.id, competition_id=comp_id).all()
        
        for pick in picks:
            actual_pos_for_pick = (
                actual_results_dict.get(pick.rider_id).position
                if pick.rider_id in actual_results_dict
                else None
            )
            if actual_pos_for_pick == pick.predicted_position:
                race_points += 25
            elif actual_pos_for_pick is not None and actual_pos_for_pick <= 6:
                race_points += 5

        holeshot_picks = HoleshotPick.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).all()
        for hp in holeshot_picks:
            actual_hs = actual_holeshots_dict.get(hp.class_name)
            if actual_hs and actual_hs.rider_id == hp.rider_id:
                holeshot_points += 3

        wc_pick = WildcardPick.query.filter_by(
            user_id=user.id, competition_id=comp_id
        ).first()
        if wc_pick:
            actual_wc = next(
                (res for res in actual_results if res.position == wc_pick.position), None
            )
            if actual_wc and actual_wc.rider_id == wc_pick.rider_id:
                wildcard_points += 15

        total_points = race_points + holeshot_points + wildcard_points

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
        score_entry.race_points = race_points
        score_entry.holeshot_points = holeshot_points
        score_entry.wildcard_points = wildcard_points
        print(f"DEBUG: {user.username} - Race: {race_points}, Holeshot: {holeshot_points}, Wildcard: {wildcard_points}, Total: {total_points}")
        
        # Debug: Check if user has any picks at all
        all_user_picks = RacePick.query.filter_by(user_id=user.id).all()
        print(f"DEBUG: {user.username} has {len(all_user_picks)} total picks across all competitions")

    db.session.commit()

    # Update season team points based on rider results (separate from race picks)
    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        # Get all riders in this season team
        team_riders = SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
        rider_ids = [tr.rider_id for tr in team_riders]
        
        total_season_points = 0
        
        # Calculate points for each rider based on their race results
        for rider_id in rider_ids:
            # Get all race results for this rider
            rider_results = CompetitionResult.query.filter_by(rider_id=rider_id).all()
            
            for result in rider_results:
                points = calculate_rider_points_for_position(result.position)
                total_season_points += points
        
        team.total_points = total_season_points
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) to {total_season_points} points based on {len(rider_ids)} riders")

    db.session.commit()
    print(f"✅ Poängberäkning klar för tävling ID: {comp_id}")
    
    # Automatically calculate league points after race scores are calculated
    try:
        print(f"🏆 Automatically calculating league points for competition {comp_id}...")
        update_league_points_for_competition(comp_id)
        print(f"✅ League points updated for competition {comp_id}")
    except Exception as e:
        print(f"❌ Error calculating league points: {e}")
        # Don't fail the entire score calculation if league points fail

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
    if not is_admin_user():
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
    if not is_admin_user():
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
    print(f"DEBUG: Before deletion - Results: {existing_results}, Holeshots: {existing_holeshots}, Scores: {existing_scores}, Out Status: {existing_out_status} (keeping OUT status)")
    
    # Delete results for this specific competition
    deleted_results = CompetitionResult.query.filter_by(competition_id=competition_id).delete()
    deleted_holeshot_results = HoleshotResult.query.filter_by(competition_id=competition_id).delete()
    deleted_scores = CompetitionScore.query.filter_by(competition_id=competition_id).delete()
    # DON'T delete OUT status - it should persist across competitions
    deleted_out_status = 0  # OUT status is kept
    
    # ALSO delete user picks for this competition
    deleted_race_picks = RacePick.query.filter_by(competition_id=competition_id).delete()
    deleted_holeshot_picks = HoleshotPick.query.filter_by(competition_id=competition_id).delete()
    deleted_wildcard_picks = WildcardPick.query.filter_by(competition_id=competition_id).delete()
    
    db.session.commit()
    
    # Update season team points after clearing competition scores (rider results system)
    all_season_teams = SeasonTeam.query.all()
    for team in all_season_teams:
        # Get all riders in this season team
        team_riders = SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
        rider_ids = [tr.rider_id for tr in team_riders]
        
        total_season_points = 0
        
        # Calculate points for each rider based on their race results
        for rider_id in rider_ids:
            # Get all race results for this rider
            rider_results = CompetitionResult.query.filter_by(rider_id=rider_id).all()
            
            for result in rider_results:
                points = calculate_rider_points_for_position(result.position)
                total_season_points += points
        
        team.total_points = total_season_points
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) to {total_season_points} points based on {len(rider_ids)} riders")
    
    db.session.commit()
    
    print(f"DEBUG: Deleted {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_race_picks} race picks, {deleted_holeshot_picks} holeshot picks, {deleted_wildcard_picks} wildcard picks for competition {competition_id} (kept OUT status)")
    
    return jsonify({
        "message": f"Cleared {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_race_picks} race picks, {deleted_holeshot_picks} holeshot picks, {deleted_wildcard_picks} wildcard picks for competition {competition_id} (kept OUT status)",
        "deleted_results": deleted_results,
        "deleted_holeshot_results": deleted_holeshot_results,
        "deleted_scores": deleted_scores,
        "deleted_out_status": 0,  # OUT status is kept
        "deleted_race_picks": deleted_race_picks,
        "deleted_holeshot_picks": deleted_holeshot_picks,
        "deleted_wildcard_picks": deleted_wildcard_picks
    })

def calculate_rider_points_for_position(position):
    """Calculate points for a rider based on their finishing position (season team system)"""
    if position is None or position == 0:
        return 0
    
    # Season team points system (separate from race picks)
    if position == 1:
        return 5
    elif position == 2:
        return 4
    elif position == 3:
        return 3
    elif position == 4:
        return 2
    elif position == 5:
        return 1
    elif position <= 10:
        return 1
    else:
        return 0

@app.get("/update_rider_numbers")
def update_rider_numbers():
    """Update rider numbers and coast assignments in database"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Update Ty Masterpool
        ty_masterpool = Rider.query.filter_by(name='Ty Masterpool').first()
        if ty_masterpool:
            ty_masterpool.rider_number = 81
            ty_masterpool.coast_250 = 'east'
            print(f"Updated Ty Masterpool: rider_number=81, coast_250=east")
        
        # Update Jordon Smith
        jordon_smith = Rider.query.filter_by(name='Jordon Smith').first()
        if jordon_smith:
            jordon_smith.rider_number = 58
            jordon_smith.coast_250 = 'east'
            print(f"Updated Jordon Smith: rider_number=58, coast_250=east")
        
        # Update Chance Hymas
        chance_hymas = Rider.query.filter_by(name='Chance Hymas').first()
        if chance_hymas:
            chance_hymas.rider_number = 49
            chance_hymas.coast_250 = 'west'
            print(f"Updated Chance Hymas: rider_number=49, coast_250=west")
        
        # Update Seth Hammaker
        seth_hammaker = Rider.query.filter_by(name='Seth Hammaker').first()
        if seth_hammaker:
            seth_hammaker.coast_250 = 'west'
            print(f"Updated Seth Hammaker: coast_250=west")
        
        db.session.commit()
        return jsonify({"message": "Rider numbers and coast assignments updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/clear_all_user_picks")
def clear_all_user_picks():
    """Clear all picks for all users - admin only"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Count picks before deletion
        race_picks_count = RacePick.query.count()
        holeshot_picks_count = HoleshotPick.query.count()
        wildcard_picks_count = WildcardPick.query.count()
        
        print(f"DEBUG: Before clearing - Race picks: {race_picks_count}, Holeshot picks: {holeshot_picks_count}, Wildcard picks: {wildcard_picks_count}")
        
        # Clear all race picks
        RacePick.query.delete()
        
        # Clear all holeshot picks
        HoleshotPick.query.delete()
        
        # Clear all wildcard picks
        WildcardPick.query.delete()
        
        db.session.commit()
        
        print(f"DEBUG: After clearing - All picks deleted successfully")
        return jsonify({"message": f"All user picks cleared successfully. Deleted {race_picks_count} race picks, {holeshot_picks_count} holeshot picks, {wildcard_picks_count} wildcard picks."})
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error clearing picks: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/clear_all_riders")
def clear_all_riders():
    """Clear all riders from database - use rider management to recreate"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Clear all riders
        Rider.query.delete()
        db.session.commit()
        return jsonify({"message": "All riders cleared. Use rider management to recreate them."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/remove_duplicate_riders")
def remove_duplicate_riders():
    """Remove duplicate riders - keep the one with highest ID"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find duplicate riders by name
        from sqlalchemy import func
        duplicates = db.session.query(
            Rider.name, 
            func.count(Rider.id).label('count'),
            func.array_agg(Rider.id).label('ids')
        ).group_by(Rider.name).having(func.count(Rider.id) > 1).all()
        
        removed_count = 0
        for name, count, ids in duplicates:
            # Keep the rider with highest ID, remove others
            ids_to_remove = sorted(ids)[:-1]  # All except the last (highest ID)
            for rider_id in ids_to_remove:
                # Check if rider is used in season_team_riders
                season_team_usage = SeasonTeamRider.query.filter_by(rider_id=rider_id).count()
                if season_team_usage > 0:
                    print(f"Skipping rider {name} (ID: {rider_id}) - used in {season_team_usage} season teams")
                    continue
                
                # Check if rider is used in race picks
                race_pick_usage = RacePick.query.filter_by(rider_id=rider_id).count()
                if race_pick_usage > 0:
                    print(f"Skipping rider {name} (ID: {rider_id}) - used in {race_pick_usage} race picks")
                    continue
                
                # Check if rider is used in holeshot picks
                holeshot_usage = HoleshotPick.query.filter_by(rider_id=rider_id).count()
                if holeshot_usage > 0:
                    print(f"Skipping rider {name} (ID: {rider_id}) - used in {holeshot_usage} holeshot picks")
                    continue
                
                # Check if rider is used in wildcard picks
                wildcard_usage = WildcardPick.query.filter_by(rider_id=rider_id).count()
                if wildcard_usage > 0:
                    print(f"Skipping rider {name} (ID: {rider_id}) - used in {wildcard_usage} wildcard picks")
                    continue
                
                # Safe to remove
                Rider.query.filter_by(id=rider_id).delete()
                removed_count += 1
                print(f"Removed duplicate rider {name} (ID: {rider_id})")
        
        db.session.commit()
        return jsonify({"message": f"Removed {removed_count} duplicate riders. Kept the ones with highest ID. Skipped riders that are still in use."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/fix_rider_duplicates")
def fix_rider_duplicates():
    """Fix rider duplicates and coast issues"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find all riders with same name
        from sqlalchemy import func
        duplicates = db.session.query(Rider.name, func.count(Rider.id)).group_by(Rider.name).having(func.count(Rider.id) > 1).all()
        
        fixed_count = 0
        for name, count in duplicates:
            print(f"Found {count} riders named {name}")
            # Keep the first one, delete the rest
            riders = Rider.query.filter_by(name=name).all()
            for rider in riders[1:]:  # Keep first, delete rest
                print(f"Deleting duplicate rider: {rider.name} (ID: {rider.id}, class: {rider.class_name})")
                db.session.delete(rider)
                fixed_count += 1
        
        # Fix Seth Hammaker specifically
        seth_riders = Rider.query.filter_by(name='Seth Hammaker').all()
        if len(seth_riders) > 1:
            print(f"Found {len(seth_riders)} Seth Hammaker riders")
            # Keep the 450cc one, delete the 250cc one
            for rider in seth_riders:
                if rider.class_name == '250cc':
                    print(f"Deleting 250cc Seth Hammaker (ID: {rider.id})")
                    db.session.delete(rider)
                    fixed_count += 1
                elif rider.class_name == '450cc':
                    # Make sure he has no coast_250
                    rider.coast_250 = None
                    print(f"Fixed 450cc Seth Hammaker (ID: {rider.id}) - removed coast_250")
        
        db.session.commit()
        return jsonify({"message": f"Fixed {fixed_count} duplicate riders. Seth Hammaker should now be 450cc only."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/update_season_team_points")
def update_season_team_points():
    """Update all season team points based on rider results"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    print("DEBUG: update_season_team_points called - calculating based on rider results")
    
    all_season_teams = SeasonTeam.query.all()
    updated_teams = []
    
    for team in all_season_teams:
        # Get all riders in this season team
        team_riders = SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
        rider_ids = [tr.rider_id for tr in team_riders]
        
        total_season_points = 0
        
        # Calculate points for each rider based on their race results
        for rider_id in rider_ids:
            # Get all race results for this rider
            rider_results = CompetitionResult.query.filter_by(rider_id=rider_id).all()
            
            for result in rider_results:
                points = calculate_rider_points_for_position(result.position)
                total_season_points += points
                print(f"DEBUG: Rider {rider_id} finished {result.position} in competition {result.competition_id}, got {points} points")
        
        old_points = team.total_points
        team.total_points = total_season_points
        updated_teams.append({
            "team_name": team.team_name,
            "user_id": team.user_id,
            "old_points": old_points,
            "new_points": total_season_points,
            "rider_count": len(rider_ids)
        })
        print(f"DEBUG: Updated season team {team.team_name} (user {team.user_id}) from {old_points} to {total_season_points} points based on {len(rider_ids)} riders")
    
    db.session.commit()
    
    return jsonify({
        "message": f"Updated {len(updated_teams)} season teams based on rider results",
        "updated_teams": updated_teams
    })

@app.get("/get_user_total_points")
def get_user_total_points():
    """Get current user's total points for team change validation"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    user_id = session["user_id"]
    
    # Calculate total points the same way as in leaderboard (includes penalties)
    user_scores = CompetitionScore.query.filter_by(user_id=user_id).all()
    total_points = sum(score.total_points or 0 for score in user_scores)
    
    # Also calculate individual components for debugging
    total_race_points = sum(score.race_points or 0 for score in user_scores)
    total_holeshot_points = sum(score.holeshot_points or 0 for score in user_scores)
    total_wildcard_points = sum(score.wildcard_points or 0 for score in user_scores)
    
    print(f"DEBUG: get_user_total_points for user {user_id}: race={total_race_points}, holeshot={total_holeshot_points}, wildcard={total_wildcard_points}, total={total_points}")
    print(f"DEBUG: Found {len(user_scores)} CompetitionScore entries for user {user_id}")
    for score in user_scores:
        print(f"DEBUG: Score entry - competition_id={score.competition_id}, race_points={score.race_points}, total_points={score.total_points}")
    
    return jsonify({
        "total_points": total_points,
        "race_points": total_race_points,
        "holeshot_points": total_holeshot_points,
        "wildcard_points": total_wildcard_points
    })

@app.post("/upload_entry_list")
def upload_entry_list():
    """Upload entry list CSV file"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            # Save to data folder
            filename = f"data/{file.filename}"
            file.save(filename)
            print(f"DEBUG: File uploaded to {filename}")
            
            # Debug: Check if file exists and show first few lines
            from pathlib import Path
            if Path(filename).exists():
                print(f"DEBUG: File exists, size: {Path(filename).stat().st_size} bytes")
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:10]
                    print(f"DEBUG: First 10 lines of {filename}:")
                    for i, line in enumerate(lines, 1):
                        print(f"  {i}: {line.strip()}")
            else:
                print(f"DEBUG: File does not exist after upload!")
            
            return jsonify({
                "success": True,
                "message": f"File {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/import_entry_lists_new")
def import_entry_lists_new():
    """Import riders from official entry lists using the new parsing function"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        from pathlib import Path
        
        def clean_rider_name(name):
            import re
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        # Parse only the files that actually exist and were uploaded
        entry_lists = []
        
        # Check which files exist
        west_file = Path("data/Entry_List_250_west.csv")
        east_file = Path("data/Entry_List_250_east.csv")
        four_fifty_file = Path("data/Entry_List_450.csv")
        
        print(f"DEBUG: Checking files:")
        print(f"DEBUG: 250 West exists: {west_file.exists()}")
        print(f"DEBUG: 250 East exists: {east_file.exists()}")
        print(f"DEBUG: 450 exists: {four_fifty_file.exists()}")
        
        # Only parse files that were recently uploaded (check modification time)
        import time
        current_time = time.time()
        recent_threshold = 300  # 5 minutes ago
        
        if west_file.exists():
            file_age = current_time - west_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_250_west.csv", "250cc"))
                print(f"DEBUG: ✅ Found recent 250 West file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 250 West file (age: {file_age:.0f}s)")
        
        if east_file.exists():
            file_age = current_time - east_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_250_east.csv", "250cc"))
                print(f"DEBUG: ✅ Found recent 250 East file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 250 East file (age: {file_age:.0f}s)")
            
        if four_fifty_file.exists():
            file_age = current_time - four_fifty_file.stat().st_mtime
            if file_age < recent_threshold:
                entry_lists.append(("data/Entry_List_450.csv", "450cc"))
                print(f"DEBUG: ✅ Found recent 450 file (age: {file_age:.0f}s)")
            else:
                print(f"DEBUG: ⏰ Skipping old 450 file (age: {file_age:.0f}s)")
        
        print(f"DEBUG: Will parse {len(entry_lists)} files: {[f[0] for f in entry_lists]}")
        
        all_riders = []
        results = {}
        
        for csv_file, class_name in entry_lists:
            csv_path = Path(csv_file)
            print(f"DEBUG: Looking for file: {csv_path}")
            print(f"DEBUG: File exists: {csv_path.exists()}")
            
            if csv_path.exists():
                print(f"DEBUG: Parsing {csv_file} for class {class_name}")
                riders = parse_csv_simple(csv_path, class_name)
                print(f"DEBUG: Found {len(riders)} riders in {csv_file}")
                print(f"DEBUG: Riders from {csv_file}: {[r['number'] for r in riders[:5]]}...")  # Show first 5 rider numbers
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                print(f"DEBUG: File not found: {csv_file}")
                results[class_name] = f"File not found: {csv_file}"
        
        # Show preview
        preview = {
            "total_riders": len(all_riders),
            "by_class": results,
            "sample_riders": all_riders[:10]
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(all_riders)} riders. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_entry_lists_new: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/import_entry_lists")
def import_entry_lists():
    """Import riders from official entry lists and replace existing riders"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        import re
        from pathlib import Path
        
        def clean_rider_name(name):
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        def parse_entry_list(csv_path, class_name):
            # Use the same parsing logic as parse_csv_simple
            riders = []
            print(f"🔥 CONFIRM PARSER - Starting to parse {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                for row_num, row in enumerate(reader, 1):
                    print(f"🔥 ROW {row_num}: {row}")
                    
                    # Skip first 7 rows (headers)
                    if row_num <= 7:
                        print(f"🔥 SKIPPING HEADER {row_num}")
                        continue
                    
                    # Check if row has content
                    if not row or len(row) == 0:
                        print(f"🔥 EMPTY ROW {row_num}")
                        continue
                        
                    # Get the text from first column
                    text = row[0].strip().strip('"')
                    print(f"🔥 TEXT: {text}")
                    
                    # Check if it starts with a number
                    if text and text[0].isdigit():
                        print(f"🔥 FOUND RIDER ROW: {text}")
                        
                        # Split by spaces
                        parts = text.split()
                        print(f"🔥 PARTS: {parts}")
                        
                        if len(parts) >= 5:
                            # Find bike brand
                            bike_idx = 2
                            for i, part in enumerate(parts[2:], 2):
                                if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                                    bike_idx = i
                                    break
                            
                            if bike_idx < len(parts):
                                name = ' '.join(parts[1:bike_idx])
                                bike = parts[bike_idx]
                                hometown = ' '.join(parts[bike_idx+1:-1])
                                team = parts[-1]
                                
                                rider_data = {
                                    'number': int(parts[0]),
                                    'name': clean_rider_name(name),
                                    'bike_brand': normalize_bike_brand(bike),
                                    'hometown': hometown.strip(),
                                    'team': team.strip(),
                                    'class': class_name
                                }
                                riders.append(rider_data)
                                print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                            else:
                                print(f"🔥 NO BIKE BRAND FOUND")
                        else:
                            print(f"🔥 NOT ENOUGH PARTS")
                    else:
                        print(f"🔥 NOT A RIDER ROW")
            
            print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
            return riders
        
        # Parse all entry lists
        entry_lists = [
            ("data/Entry_List_250_west.csv", "250cc"),
            ("data/Entry_List_250_east.csv", "250cc"), 
            ("data/Entry_List_450.csv", "450cc")
        ]
        
        all_riders = []
        results = {}
        
        for csv_file, class_name in entry_lists:
            csv_path = Path(csv_file)
            print(f"DEBUG: Looking for file: {csv_path}")
            print(f"DEBUG: File exists: {csv_path.exists()}")
            
            if csv_path.exists():
                print(f"DEBUG: Parsing {csv_file} for class {class_name}")
                riders = parse_csv_simple(csv_path, class_name)
                print(f"DEBUG: Found {len(riders)} riders in {csv_file}")
                print(f"DEBUG: Riders from {csv_file}: {[r['number'] for r in riders[:5]]}...")  # Show first 5 rider numbers
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                print(f"DEBUG: File not found: {csv_file}")
                results[class_name] = f"File not found: {csv_file}"
        
        # Show preview
        preview = {
            "total_riders": len(all_riders),
            "by_class": results,
            "sample_riders": all_riders[:10]
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(all_riders)} riders. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_entry_lists: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/confirm_import_entry_lists")
def confirm_import_entry_lists():
    """Confirm and import entry lists, replacing existing riders"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        import re
        from pathlib import Path
        
        def clean_rider_name(name):
            return re.sub(r'\s+', ' ', name.strip())
        
        def normalize_bike_brand(brand):
            brand_map = {
                'Triumph': 'Triumph', 'KTM': 'KTM', 'GasGas': 'GasGas',
                'Honda': 'Honda', 'Kawasaki': 'Kawasaki', 'Yamaha': 'Yamaha',
                'Husqvarna': 'Husqvarna', 'Suzuki': 'Suzuki', 'Beta': 'Beta'
            }
            return brand_map.get(brand, brand)
        
        def parse_entry_list(csv_path, class_name):
            # Use the same parsing logic as parse_csv_simple
            riders = []
            print(f"🔥 CONFIRM PARSER - Starting to parse {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                for row_num, row in enumerate(reader, 1):
                    print(f"🔥 ROW {row_num}: {row}")
                    
                    # Skip first 7 rows (headers)
                    if row_num <= 7:
                        print(f"🔥 SKIPPING HEADER {row_num}")
                        continue
                    
                    # Check if row has content
                    if not row or len(row) == 0:
                        print(f"🔥 EMPTY ROW {row_num}")
                        continue
                        
                    # Get the text from first column
                    text = row[0].strip().strip('"')
                    print(f"🔥 TEXT: {text}")
                    
                    # Check if it starts with a number
                    if text and text[0].isdigit():
                        print(f"🔥 FOUND RIDER ROW: {text}")
                        
                        # Split by spaces
                        parts = text.split()
                        print(f"🔥 PARTS: {parts}")
                        
                        if len(parts) >= 5:
                            # Find bike brand
                            bike_idx = 2
                            for i, part in enumerate(parts[2:], 2):
                                if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                                    bike_idx = i
                                    break
                            
                            if bike_idx < len(parts):
                                name = ' '.join(parts[1:bike_idx])
                                bike = parts[bike_idx]
                                hometown = ' '.join(parts[bike_idx+1:-1])
                                team = parts[-1]
                                
                                rider_data = {
                                    'number': int(parts[0]),
                                    'name': clean_rider_name(name),
                                    'bike_brand': normalize_bike_brand(bike),
                                    'hometown': hometown.strip(),
                                    'team': team.strip(),
                                    'class': class_name
                                }
                                riders.append(rider_data)
                                print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                            else:
                                print(f"🔥 NO BIKE BRAND FOUND")
                        else:
                            print(f"🔥 NOT ENOUGH PARTS")
                    else:
                        print(f"🔥 NOT A RIDER ROW")
            
            print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
            return riders
        
        # Parse all entry lists
        entry_lists = [
            ("data/Entry_List_250_west.csv", "250cc", "west"),
            ("data/Entry_List_250_east.csv", "250cc", "east"), 
            ("data/Entry_List_450.csv", "450cc", None)
        ]
        
        all_riders = []
        results = {}
        
        for csv_file, class_name, coast in entry_lists:
            csv_path = Path(csv_file)
            if csv_path.exists():
                riders = parse_entry_list(csv_path, class_name)
                # Add coast information to each rider
                for rider in riders:
                    rider['coast'] = coast
                all_riders.extend(riders)
                results[class_name] = len(riders)
            else:
                results[class_name] = f"File not found: {csv_file}"
        
        # Delete existing riders and import new ones
        imported_count = 0
        errors = []
        
        # Delete all existing riders
        db.session.execute(db.text("DELETE FROM riders"))
        db.session.commit()
        
        # Import new riders
        for rider_data in all_riders:
            try:
                # Use the coast information we added during parsing
                coast = rider_data.get('coast')
                
                new_rider = Rider(
                    rider_number=rider_data['number'],
                    name=rider_data['name'],
                    bike_brand=rider_data['bike_brand'],
                    class_name=rider_data['class'],
                    coast_250=coast,
                    price=100000,  # Default price
                    hometown=rider_data.get('hometown', ''),
                    team=rider_data.get('team', '')
                )
                
                db.session.add(new_rider)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Error importing {rider_data['name']}: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "results": results,
            "message": f"Successfully imported {imported_count} riders, replacing all existing riders"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in confirm_import_entry_lists: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/upload_results_csv")
def upload_results_csv():
    """Upload race results CSV file"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            filename = f"data/results_{file.filename}"
            file.save(filename)
            return jsonify({
                "success": True,
                "message": f"Results file {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading results file: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/import_results_csv")
def import_results_csv():
    """Import race results from CSV file"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        from pathlib import Path
        
        # Get the CSV file path from request
        csv_file = request.json.get('csv_file')
        if not csv_file:
            return jsonify({"error": "No CSV file specified"}), 400
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            return jsonify({"error": f"File not found: {csv_file}"}), 400
        
        # Parse CSV file
        results = []
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Expected CSV format: position, rider_number, rider_name, points, class
                    position = int(row.get('position', 0))
                    rider_number = int(row.get('rider_number', 0))
                    rider_name = row.get('rider_name', '').strip()
                    points = float(row.get('points', 0))
                    class_name = row.get('class', '').strip()
                    
                    if position > 0 and rider_number > 0 and rider_name:
                        results.append({
                            'position': position,
                            'rider_number': rider_number,
                            'rider_name': rider_name,
                            'points': points,
                            'class': class_name
                        })
                except (ValueError, KeyError) as e:
                    print(f"Error parsing row {row_num}: {e}")
                    continue
        
        # Show preview
        preview = {
            "total_results": len(results),
            "sample_results": results[:10],
            "classes": list(set([r['class'] for r in results if r['class']]))
        }
        
        return jsonify({
            "success": True,
            "preview": preview,
            "message": f"Found {len(results)} results. Ready for import."
        })
        
    except Exception as e:
        print(f"Error in import_results_csv: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/confirm_import_results")
def confirm_import_results():
    """Confirm and import race results to database"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import csv
        from pathlib import Path
        
        # Get parameters from request
        csv_file = request.json.get('csv_file')
        competition_id = request.json.get('competition_id')
        
        if not csv_file or not competition_id:
            return jsonify({"error": "Missing csv_file or competition_id"}), 400
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            return jsonify({"error": f"File not found: {csv_file}"}), 400
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        # Parse and import results
        imported_count = 0
        errors = []
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    position = int(row.get('position', 0))
                    rider_number = int(row.get('rider_number', 0))
                    rider_name = row.get('rider_name', '').strip()
                    points = float(row.get('points', 0))
                    class_name = row.get('class', '').strip()
                    
                    if position > 0 and rider_number > 0 and rider_name:
                        # Find rider by number and name
                        rider = Rider.query.filter_by(
                            rider_number=rider_number,
                            name=rider_name
                        ).first()
                        
                        if rider:
                            # Create or update competition result
                            existing_result = CompetitionResult.query.filter_by(
                                competition_id=competition_id,
                                rider_id=rider.id
                            ).first()
                            
                            if existing_result:
                                existing_result.position = position
                                existing_result.points = points
                            else:
                                new_result = CompetitionResult(
                                    competition_id=competition_id,
                                    rider_id=rider.id,
                                    position=position,
                                    points=points
                                )
                                db.session.add(new_result)
                            
                            imported_count += 1
                        else:
                            errors.append(f"Row {row_num}: Rider {rider_name} (#{rider_number}) not found")
                            
                except (ValueError, KeyError) as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue
        
        # Commit changes
        db.session.commit()
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} results"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in confirm_import_results: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/get_competitions_for_import")
def get_competitions_for_import():
    """Get list of competitions for CSV import"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        competitions = Competition.query.order_by(Competition.event_date.desc()).all()
        competition_list = []
        
        for comp in competitions:
            competition_list.append({
                "id": comp.id,
                "name": comp.name,
                "event_date": comp.event_date.isoformat() if comp.event_date else None,
                "location": getattr(comp, 'location', 'Unknown'),
                "has_results": bool(CompetitionResult.query.filter_by(competition_id=comp.id).first())
            })
        
        return jsonify({
            "success": True,
            "competitions": competition_list
        })
        
    except Exception as e:
        print(f"Error in get_competitions_for_import: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/debug_rider_images")
def debug_rider_images():
    """Debug endpoint to check rider images in database"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all riders with their image_url
        riders = Rider.query.all()
        rider_data = []
        
        for rider in riders:
            # Check if image file exists
            image_exists = False
            if rider.image_url:
                from pathlib import Path
                image_path = Path(f"static/{rider.image_url}")
                image_exists = image_path.exists()
            
            rider_data.append({
                "id": rider.id,
                "name": rider.name,
                "rider_number": rider.rider_number,
                "class_name": rider.class_name,
                "image_url": rider.image_url,
                "image_exists": image_exists,
                "bike_brand": rider.bike_brand
            })
        
        return jsonify({
            "total_riders": len(riders),
            "riders_with_images": len([r for r in rider_data if r["image_url"]]),
            "riders_with_existing_files": len([r for r in rider_data if r["image_exists"]]),
            "riders": rider_data
        })
        
    except Exception as e:
        print(f"Error in debug_rider_images: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/upload_race_results", methods=['POST'])
def upload_race_results():
    """Upload race results CSV file"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and file.filename.endswith('.csv'):
            filename = f"data/results_{file.filename}"
            file.save(filename)
            return jsonify({
                "success": True,
                "filename": filename,
                "message": f"Results file {filename} uploaded successfully"
            })
        else:
            return jsonify({"error": "Only CSV files allowed"}), 400
            
    except Exception as e:
        print(f"Error uploading race results file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/import_race_results_complete", methods=['POST'])
def import_race_results_complete():
    """Import complete race results with holeshot and wildcard picks"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        data = request.get_json()
        print(f"🔍 DEBUG: Received data: {data}")
        
        competition_id = data.get('competition_id')
        results_250 = data.get('results_250')
        results_450 = data.get('results_450')
        holeshot_250 = data.get('holeshot_250')
        holeshot_450 = data.get('holeshot_450')
        
        print(f"🔍 DEBUG: Parsed data - competition_id: {competition_id}, results_250: {results_250}, results_450: {results_450}")
        print(f"🔍 DEBUG: holeshot_250: {holeshot_250}, holeshot_450: {holeshot_450}")
        
        if not all([competition_id, results_250, results_450, holeshot_250, holeshot_450]):
            return jsonify({"error": "Missing required data"}), 400
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        imported_count = 0
        errors = []
        
        # Parse and import 250cc results
        if results_250:
            try:
                print(f"🔍 DEBUG: Starting 250cc import from CSV...")
                
                from pathlib import Path
                csv_path = Path(results_250)
                if csv_path.exists():
                    with open(csv_path, 'r', encoding='utf-8') as file:
                        import csv
                        reader = csv.reader(file)
                        
                        for row_num, row in enumerate(reader, 1):
                            if row_num <= 7:  # Skip headers
                                continue
                            
                            if len(row) >= 1 and row[0].strip():
                                full_text = row[0].strip()
                                print(f"🔍 DEBUG: 250cc row {row_num}: {full_text}")
                                
                                # Parse format: "1        38   Haiden Deegan        Yamaha        1..."
                                parts = [p for p in full_text.split() if p]
                                
                                if len(parts) >= 4:
                                    # Find rider number and position
                                    rider_number = None
                                    rider_name_parts = []
                                    position = None
                                    
                                    for i, part in enumerate(parts):
                                        if part.isdigit() and i > 0:  # Not first position
                                            if i + 1 < len(parts) and not parts[i + 1].isdigit():
                                                rider_number = int(part)
                                                # Get name parts
                                                j = i + 1
                                                while j < len(parts) and not parts[j] in ['Yamaha', 'KTM', 'Honda', 'Kawasaki', 'Triumph', 'GasGas', 'Husqvarna', 'Suzuki']:
                                                    rider_name_parts.append(parts[j])
                                                    j += 1
                                                # Get position (first number after bike)
                                                for k in range(j, len(parts)):
                                                    if parts[k].isdigit():
                                                        position = int(parts[k])
                                                        break
                                                break
                                    
                                    if rider_number and rider_name_parts and position:
                                        rider_name = ' '.join(rider_name_parts)
                                        print(f"🔍 DEBUG: Parsed - #{rider_number} {rider_name} at position {position}")
                                        
                                        # Find rider in database
                                        rider = Rider.query.filter_by(
                                            rider_number=rider_number,
                                            class_name="250cc"
                                        ).first()
                                        
                                        if rider:
                                            # Create or update result
                                            existing_result = CompetitionResult.query.filter_by(
                                                competition_id=competition_id,
                                                rider_id=rider.id
                                            ).first()
                                            
                                            if existing_result:
                                                existing_result.position = position
                                            else:
                                                new_result = CompetitionResult(
                                                    competition_id=competition_id,
                                                    rider_id=rider.id,
                                                    position=position
                                                )
                                                db.session.add(new_result)
                                            
                                            imported_count += 1
                                            print(f"🔍 DEBUG: Added 250cc result for {rider.name} at position {position}")
                                        else:
                                            print(f"🔍 DEBUG: Rider not found: #{rider_number} {rider_name}")
                                    else:
                                        print(f"🔍 DEBUG: Could not parse: {full_text}")
                
                print(f"🔍 DEBUG: Imported {imported_count} 250cc results from CSV")
            except Exception as e:
                print(f"🔍 DEBUG: Error importing 250cc results: {str(e)}")
                errors.append(f"Error importing 250cc results: {str(e)}")
        
        # Parse and import 450cc results
        if results_450:
            try:
                print(f"🔍 DEBUG: Starting 450cc import from CSV...")
                
                from pathlib import Path
                csv_path = Path(results_450)
                if csv_path.exists():
                    with open(csv_path, 'r', encoding='utf-8') as file:
                        import csv
                        reader = csv.reader(file)
                        
                        for row_num, row in enumerate(reader, 1):
                            if row_num <= 7:  # Skip headers
                                continue
                            
                            if len(row) >= 1 and row[0].strip():
                                full_text = row[0].strip()
                                print(f"🔍 DEBUG: 450cc row {row_num}: {full_text}")
                                
                                # Parse format: "1        2   Cooper Webb        Yamaha        1..."
                                parts = [p for p in full_text.split() if p]
                                
                                if len(parts) >= 4:
                                    # Find rider number and position
                                    rider_number = None
                                    rider_name_parts = []
                                    position = None
                                    
                                    for i, part in enumerate(parts):
                                        if part.isdigit() and i > 0:  # Not first position
                                            if i + 1 < len(parts) and not parts[i + 1].isdigit():
                                                rider_number = int(part)
                                                # Get name parts
                                                j = i + 1
                                                while j < len(parts) and not parts[j] in ['Yamaha', 'KTM', 'Honda', 'Kawasaki', 'Triumph', 'GasGas', 'Husqvarna', 'Suzuki']:
                                                    rider_name_parts.append(parts[j])
                                                    j += 1
                                                # Get position (first number after bike)
                                                for k in range(j, len(parts)):
                                                    if parts[k].isdigit():
                                                        position = int(parts[k])
                                                        break
                                                break
                                    
                                    if rider_number and rider_name_parts and position:
                                        rider_name = ' '.join(rider_name_parts)
                                        print(f"🔍 DEBUG: 450cc parsed - #{rider_number} {rider_name} at position {position}")
                                        
                                        # Find rider in database
                                        rider = Rider.query.filter_by(
                                            rider_number=rider_number,
                                            class_name="450cc"
                                        ).first()
                                        
                                        if rider:
                                            # Create or update result
                                            existing_result = CompetitionResult.query.filter_by(
                                                competition_id=competition_id,
                                                rider_id=rider.id
                                            ).first()
                                            
                                            if existing_result:
                                                existing_result.position = position
                                            else:
                                                new_result = CompetitionResult(
                                                    competition_id=competition_id,
                                                    rider_id=rider.id,
                                                    position=position
                                                )
                                                db.session.add(new_result)
                                            
                                            imported_count += 1
                                            print(f"🔍 DEBUG: Added 450cc result for {rider.name} at position {position}")
                                        else:
                                            print(f"🔍 DEBUG: 450cc rider not found: #{rider_number} {rider_name}")
                                    else:
                                        print(f"🔍 DEBUG: Could not parse 450cc: {full_text}")
                
                print(f"🔍 DEBUG: Imported {imported_count} 450cc results from CSV")
            except Exception as e:
                print(f"🔍 DEBUG: Error importing 450cc results: {str(e)}")
                errors.append(f"Error importing 450cc results: {str(e)}")
        
        # Add holeshot results
        try:
            print(f"🔍 DEBUG: Adding holeshot results...")
            
            # 250cc holeshot
            if holeshot_250:
                holeshot_rider_250 = Rider.query.get(holeshot_250)
                if holeshot_rider_250:
                    holeshot_result = HoleshotResult(
                        competition_id=competition_id,
                        rider_id=holeshot_250,
                        class_name="250cc"
                    )
                    db.session.add(holeshot_result)
                    print(f"🔍 DEBUG: Added 250cc holeshot: {holeshot_rider_250.name}")
            
            # 450cc holeshot
            if holeshot_450:
                holeshot_rider_450 = Rider.query.get(holeshot_450)
                if holeshot_rider_450:
                    holeshot_result = HoleshotResult(
                        competition_id=competition_id,
                        rider_id=holeshot_450,
                        class_name="450cc"
                    )
                    db.session.add(holeshot_result)
                    print(f"🔍 DEBUG: Added 450cc holeshot: {holeshot_rider_450.name}")
        except Exception as e:
            print(f"🔍 DEBUG: Error adding holeshot results: {str(e)}")
            errors.append(f"Error adding holeshot results: {str(e)}")
        
        # Note: Wildcard results are calculated automatically from the full 450cc results
        # No manual wildcard selection needed - system will calculate from user picks vs results
        
        # Commit all changes
        db.session.commit()
        
        # Calculate scores for all users after importing results
        print(f"🔍 DEBUG: Calculating scores for competition {competition_id}...")
        try:
            calculate_scores(competition_id)
            print(f"🔍 DEBUG: Scores calculated successfully")
        except Exception as e:
            print(f"🔍 DEBUG: Error calculating scores: {str(e)}")
            errors.append(f"Error calculating scores: {str(e)}")
        
        return jsonify({
            "success": True,
            "imported_count": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} race results with holeshot and wildcard picks and calculated scores"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in import_race_results_complete: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/restore_rider_images")
def restore_rider_images():
    """Restore rider images from static/riders/ directory"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        import os
        import re
        from pathlib import Path
        
        # Get static directory
        static_dir = Path(app.static_folder)
        riders_dir = static_dir / "riders"
        
        if not riders_dir.exists():
            return jsonify({
                "success": False,
                "error": "static/riders directory not found"
            })
        
        # Get all image files
        image_files = [f for f in riders_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]
        
        if not image_files:
            return jsonify({
                "success": False,
                "error": "No image files found in static/riders/"
            })
        
        # Normalize function
        def norm(s: str) -> str:
            s = (s or "").strip().lower()
            s = s.replace(".", "")
            s = re.sub(r"[\s_]+", " ", s)
            return s
        
        # Get all riders
        riders = Rider.query.all()
        
        # Index riders by number and name
        by_number = {}
        by_name = {}
        for rider in riders:
            if rider.rider_number:
                by_number[int(rider.rider_number)] = rider
            by_name[norm(rider.name)] = rider
        
        updated = 0
        skipped = 0
        
        for image_file in image_files:
            rel_path = f"riders/{image_file.name}"
            filename = image_file.stem
            
            # Try to find rider by number first
            candidate = None
            m = re.match(r"^(\d{1,3})[_\s-]", filename)
            if m:
                try:
                    num = int(m.group(1))
                    candidate = by_number.get(num)
                except Exception:
                    candidate = None
            
            # If not found by number, try by name
            if not candidate:
                # Remove leading number + separator
                tmp = re.sub(r"^\d{1,3}[_\s-]+", "", filename)
                name = norm(tmp)
                candidate = by_name.get(name)
                if not candidate:
                    # More tolerant: only letters and spaces
                    name2 = norm(re.sub(r"[^a-z0-9\s]", "", tmp))
                    candidate = by_name.get(name2)
            
            if not candidate:
                print(f"[SKIP] No match for file: {image_file.name}")
                skipped += 1
                continue
            
            # Set image_url
            candidate.image_url = rel_path
            db.session.add(candidate)
            updated += 1
            print(f"[OK] {candidate.name} -> {rel_path}")
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "updated": updated,
            "skipped": skipped,
            "message": f"Restored images for {updated} riders"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in restore_rider_images: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/debug_my_points")
def debug_my_points():
    """Debug endpoint for current user to check their points"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    user_id = session["user_id"]
    user = User.query.get(user_id)
    
    # Get all CompetitionScore entries for this user
    user_scores = CompetitionScore.query.filter_by(user_id=user_id).all()
    
    # Calculate totals
    total_race_points = sum(score.race_points or 0 for score in user_scores)
    total_holeshot_points = sum(score.holeshot_points or 0 for score in user_scores)
    total_wildcard_points = sum(score.wildcard_points or 0 for score in user_scores)
    total_points = total_race_points + total_holeshot_points + total_wildcard_points
    
    # Build detailed breakdown
    score_breakdown = []
    for score in user_scores:
        score_breakdown.append({
            "competition_id": score.competition_id,
            "total_points": score.total_points,
            "race_points": score.race_points,
            "holeshot_points": score.holeshot_points,
            "wildcard_points": score.wildcard_points,
            "is_penalty": score.competition_id is None  # Penalty entries have no competition_id
        })
    
    return jsonify({
        "username": user.username,
        "user_id": user_id,
        "total_points": total_points,
        "race_points": total_race_points,
        "holeshot_points": total_holeshot_points,
        "wildcard_points": total_wildcard_points,
        "score_entries": score_breakdown,
        "entry_count": len(user_scores)
    })

@app.get("/debug_user_scores/<string:username>")
def debug_user_scores(username):
    """Debug endpoint to check where a user's points come from"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    print(f"DEBUG: Checking scores for user {username} (ID: {user.id})")
    
    # Get all CompetitionScore entries for this user
    competition_scores = CompetitionScore.query.filter_by(user_id=user.id).all()
    
    # Get SeasonTeam info
    season_team = SeasonTeam.query.filter_by(user_id=user.id).first()
    
    # Get all picks for this user
    race_picks = RacePick.query.filter_by(user_id=user.id).all()
    holeshot_picks = HoleshotPick.query.filter_by(user_id=user.id).all()
    wildcard_picks = WildcardPick.query.filter_by(user_id=user.id).all()
    
    result = {
        "user": {
            "id": user.id,
            "username": user.username
        },
        "season_team": {
            "team_name": season_team.team_name if season_team else None,
            "total_points": season_team.total_points if season_team else 0
        },
        "competition_scores": [],
        "picks_summary": {
            "race_picks": len(race_picks),
            "holeshot_picks": len(holeshot_picks),
            "wildcard_picks": len(wildcard_picks)
        }
    }
    
    for score in competition_scores:
        comp = Competition.query.get(score.competition_id)
        result["competition_scores"].append({
            "competition_id": score.competition_id,
            "competition_name": comp.name if comp else "Unknown",
            "points": score.total_points
        })
        print(f"DEBUG: {username} has {score.total_points} points from {comp.name if comp else 'Unknown'}")
    
    total_from_scores = sum(s["points"] for s in result["competition_scores"])
    print(f"DEBUG: {username} total from CompetitionScore: {total_from_scores}")
    print(f"DEBUG: {username} SeasonTeam total_points: {season_team.total_points if season_team else 0}")
    
    return jsonify(result)

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
    if not is_admin_user():
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

@app.get("/fix_my_league_images")
def fix_my_league_images():
    """Fix league images for current user's leagues only"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    print("DEBUG: fix_my_league_images called for user", session["user_id"])
    
    # Get user's leagues
    user_leagues = db.session.query(League).join(LeagueMembership).filter(
        LeagueMembership.user_id == session["user_id"]
    ).all()
    
    fixed_count = 0
    
    for league in user_leagues:
        if league.image_url:
            # Extract filename from URL
            filename = league.image_url.split('/')[-1]
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            
            # If image file doesn't exist, clear the image_url
            if not os.path.exists(image_path):
                print(f"DEBUG: Image file missing for user's league {league.name}, clearing image_url")
                league.image_url = None
                fixed_count += 1
    
    db.session.commit()
    
    return jsonify({
        "message": f"Fixed {fixed_count} of your leagues with missing images",
        "fixed_count": fixed_count
    })


@app.post("/leagues/<int:league_id>/request")
def request_join_league(league_id):
    """Request to join a league"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is already a member
    existing_membership = LeagueMembership.query.filter_by(
        league_id=league_id, 
        user_id=session["user_id"]
    ).first()
    
    if existing_membership:
        return jsonify({"error": "already_member"}), 400
    
    # Check if user already has a pending request
    existing_request = LeagueRequest.query.filter_by(
        league_id=league_id,
        user_id=session["user_id"],
        status='pending'
    ).first()
    
    if existing_request:
        return jsonify({"error": "request_already_sent"}), 400
    
    # Create new request
    message = request.form.get("message", "").strip()
    request_obj = LeagueRequest(
        league_id=league_id,
        user_id=session["user_id"],
        message=message if message else None
    )
    
    db.session.add(request_obj)
    db.session.commit()
    
    return jsonify({"message": "Request sent successfully"})


@app.post("/leagues/<int:league_id>/approve_request/<int:request_id>")
def approve_league_request(league_id, request_id):
    """Approve a league join request (league creator only)"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is the league creator
    if league.creator_id != session["user_id"]:
        return jsonify({"error": "not_authorized"}), 403
    
    request_obj = LeagueRequest.query.get_or_404(request_id)
    
    if request_obj.league_id != league_id:
        return jsonify({"error": "invalid_request"}), 400
    
    if request_obj.status != 'pending':
        return jsonify({"error": "request_already_processed"}), 400
    
    # Approve the request
    request_obj.status = 'approved'
    request_obj.processed_at = datetime.utcnow()
    
    # Add user to league
    membership = LeagueMembership(
        league_id=league_id,
        user_id=request_obj.user_id
    )
    db.session.add(membership)
    db.session.commit()
    
    flash("Ansökan godkändes!", "success")
    return redirect(url_for("league_detail_page", league_id=league_id))


@app.post("/leagues/<int:league_id>/reject_request/<int:request_id>")
def reject_league_request(league_id, request_id):
    """Reject a league join request (league creator only)"""
    if "user_id" not in session:
        return jsonify({"error": "not_logged_in"}), 401
    
    league = League.query.get_or_404(league_id)
    
    # Check if user is the league creator
    if league.creator_id != session["user_id"]:
        return jsonify({"error": "not_authorized"}), 403
    
    request_obj = LeagueRequest.query.get_or_404(request_id)
    
    if request_obj.league_id != league_id:
        return jsonify({"error": "invalid_request"}), 400
    
    if request_obj.status != 'pending':
        return jsonify({"error": "request_already_processed"}), 400
    
    # Reject the request
    request_obj.status = 'rejected'
    request_obj.processed_at = datetime.utcnow()
    db.session.commit()
    
    flash("Ansökan avslås!", "info")
    return redirect(url_for("league_detail_page", league_id=league_id))


@app.post("/admin/leagues/<int:league_id>/delete")
def admin_delete_league(league_id):
    """Delete a league (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        league = League.query.get_or_404(league_id)
        
        # Delete all related data
        LeagueRequest.query.filter_by(league_id=league_id).delete()
        LeagueMembership.query.filter_by(league_id=league_id).delete()
        
        # Delete the league
        db.session.delete(league)
        db.session.commit()
        
        return jsonify({"message": f"League '{league.name}' deleted successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.post("/admin/leagues/<int:league_id>/toggle_public")
def admin_toggle_league_public(league_id):
    """Toggle league public/private status (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        league = League.query.get_or_404(league_id)
        
        # Toggle public status
        league.is_public = not league.is_public
        db.session.commit()
        
        status = "public" if league.is_public else "private"
        return jsonify({"message": f"League '{league.name}' is now {status}"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.post("/admin/leagues/<int:league_id>/reset_points")
def admin_reset_league_points(league_id):
    """Reset league points to 0 (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        league = League.query.get_or_404(league_id)
        
        # Reset points
        league.total_points = 0
        db.session.commit()
        
        return jsonify({"message": f"League '{league.name}' points reset to 0"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


def calculate_league_points(league_id, competition_id):
    """Calculate simple league points based on member race pick performance"""
    try:
        # Get all members in the league
        members = db.session.query(User).join(LeagueMembership).filter(
            LeagueMembership.league_id == league_id
        ).all()
        
        if not members:
            return 0
        
        # Get their race pick scores for this competition
        member_scores = []
        for member in members:
            score = CompetitionScore.query.filter_by(
                user_id=member.id,
                competition_id=competition_id
            ).first()
            if score and score.total_points:
                member_scores.append(score.total_points)
        
        if not member_scores:
            return 0
        
        # Fair calculation: same points regardless of league size
        # Use the best score in the league (or average if only one member)
        if len(member_scores) == 1:
            # Single member: use their score directly
            final_score = member_scores[0]
        else:
            # Multiple members: use the best score (encourages competition)
            final_score = max(member_scores)
        
        print(f"🏆 League {league_id}: {len(member_scores)} members, best score: {final_score:.1f}")
        
        return round(final_score, 1)
        
    except Exception as e:
        print(f"Error calculating league points: {e}")
        return 0


def update_league_points_for_competition(competition_id):
    """Update total points for all leagues based on a specific competition"""
    try:
        # Get all leagues
        leagues = League.query.all()
        
        for league in leagues:
            # Calculate points for this competition
            competition_points = calculate_league_points(league.id, competition_id)
            
            # Add to total points
            if league.total_points is None:
                league.total_points = 0
            
            league.total_points += competition_points
            
            print(f"🏆 League '{league.name}': +{competition_points} points (Total: {league.total_points})")
        
        db.session.commit()
        print(f"✅ Updated league points for {len(leagues)} leagues based on competition {competition_id}")
        
    except Exception as e:
        print(f"❌ Error updating league points: {e}")
        db.session.rollback()
        raise e


@app.post("/admin/leagues/calculate_all_points")
def calculate_all_league_points():
    """Calculate and update points for all leagues (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all competitions that have results
        competitions_with_results = db.session.query(Competition.id).join(
            CompetitionScore, Competition.id == CompetitionScore.competition_id
        ).distinct().all()
        
        # Get all leagues
        leagues = League.query.all()
        
        updated_leagues = 0
        total_points_calculated = 0
        
        for league in leagues:
            league_total = 0
            
            # Calculate points for each competition
            for comp_id_tuple in competitions_with_results:
                comp_id = comp_id_tuple[0]
                points = calculate_league_points(league.id, comp_id)
                league_total += points
            
            # Update league total points
            league.total_points = round(league_total, 1)
            updated_leagues += 1
            total_points_calculated += league_total
        
        db.session.commit()
        
        return jsonify({
            "message": f"Updated points for {updated_leagues} leagues",
            "updated_leagues": updated_leagues,
            "total_points_calculated": round(total_points_calculated, 1)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.post("/admin/leagues/<int:league_id>/calculate_points")
def calculate_league_points_single(league_id):
    """Calculate points for a specific league (admin only)"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        league = League.query.get_or_404(league_id)
        
        # Get all competitions that have results
        competitions_with_results = db.session.query(Competition.id).join(
            CompetitionScore, Competition.id == CompetitionScore.competition_id
        ).distinct().all()
        
        league_total = 0
        
        # Calculate points for each competition
        for comp_id_tuple in competitions_with_results:
            comp_id = comp_id_tuple[0]
            points = calculate_league_points(league.id, comp_id)
            league_total += points
        
        # Update league total points
        league.total_points = round(league_total, 1)
        db.session.commit()
        
        return jsonify({
            "message": f"League '{league.name}' points calculated: {league.total_points}",
            "league_name": league.name,
            "total_points": league.total_points
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.get("/fix_league_memberships_column")
def fix_league_memberships_column():
    """Fix missing joined_at column in league_memberships table"""
    try:
        from sqlalchemy import inspect
        
        if inspect(db.engine).has_table('league_memberships'):
            try:
                # Try to query joined_at column
                db.session.execute(db.text("SELECT joined_at FROM league_memberships LIMIT 1"))
                return "joined_at column already exists in league_memberships table"
            except Exception:
                # Column doesn't exist, add it
                try:
                    db.session.rollback()
                    db.session.execute(db.text("ALTER TABLE league_memberships ADD COLUMN joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                    db.session.commit()
                    return "✅ joined_at column added to league_memberships table successfully"
                except Exception as e:
                    db.session.rollback()
                    return f"❌ Error adding joined_at column: {e}"
        else:
            return "league_memberships table doesn't exist"
            
    except Exception as e:
        return f"❌ Error: {e}"




@app.get("/migrate_league_image_columns")
def migrate_league_image_columns():
    """Add image_data and image_mime_type columns to leagues table"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Check if columns already exist
        try:
            db.session.execute(db.text("SELECT image_data FROM leagues LIMIT 1"))
            db.session.execute(db.text("SELECT image_mime_type FROM leagues LIMIT 1"))
            return jsonify({"message": "Columns already exist", "status": "already_exists"})
        except Exception:
            pass  # Columns don't exist, continue with migration
        
        # Add the new columns
        db.session.execute(db.text("ALTER TABLE leagues ADD COLUMN image_data TEXT"))
        db.session.execute(db.text("ALTER TABLE leagues ADD COLUMN image_mime_type VARCHAR(50)"))
        db.session.commit()
        
        return jsonify({
            "message": "Successfully added image_data and image_mime_type columns to leagues table",
            "status": "success"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": f"Failed to add columns: {str(e)}",
            "status": "error"
        }), 500

@app.get("/league_image/<int:league_id>")
def league_image(league_id):
    """Serve league image from database as base64 data URL"""
    try:
        league = League.query.get_or_404(league_id)
        
        # Check if we have base64 data
        if hasattr(league, 'image_data') and league.image_data and hasattr(league, 'image_mime_type') and league.image_mime_type:
            from flask import Response
            import base64
            
            # Decode base64 and return as proper image
            try:
                image_data = base64.b64decode(league.image_data)
                return Response(image_data, mimetype=league.image_mime_type)
            except Exception as e:
                print(f"Error decoding base64 image: {e}")
                return "Error decoding image", 500
        
        # Fallback to file system (legacy)
        elif league.image_url:
            from flask import send_from_directory
            import os
            
            filename = league.image_url.split('/')[-1]
            directory = app.config["UPLOAD_FOLDER"]
            
            if os.path.exists(os.path.join(directory, filename)):
                return send_from_directory(directory, filename)
        
        # No image found
        return "No image found", 404
        
    except Exception as e:
        print(f"Error serving league image: {e}")
        return "Error loading image", 500

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

@app.route("/user_race_results/<int:user_id>")
def user_race_results(user_id):
    """View another user's race results and points breakdown"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        # Get the user to view
        target_user = User.query.get(user_id)
        if not target_user:
            print(f"DEBUG: User with ID {user_id} not found")
            flash(f"Användaren med ID {user_id} hittades inte.", "error")
            return redirect(url_for("index"))
        
        # Get user's season team info
        season_team = SeasonTeam.query.filter_by(user_id=user_id).first()
        
        # Get all competitions with results
        competitions = Competition.query.order_by(Competition.event_date).all()
        
        # Get user's race results for each competition
        race_results = []
        total_points = 0
        
        for competition in competitions:
            # Get user's score for this competition
            score = CompetitionScore.query.filter_by(
                user_id=user_id,
                competition_id=competition.id
            ).first()
            
            # Check if this competition has results (is completed)
            has_results = CompetitionResult.query.filter_by(competition_id=competition.id).first() is not None
            
            if score or has_results:
                race_points = score.race_points if score else 0
                holeshot_points = score.holeshot_points if score else 0
                wildcard_points = score.wildcard_points if score else 0
                total_points_for_comp = score.total_points if score else 0
                
                
                race_results.append({
                    'competition': competition,
                    'points': total_points_for_comp,
                    'race_points': race_points,
                    'holeshot_points': holeshot_points,
                    'wildcard_points': wildcard_points,
                    'has_results': has_results
                })
                if score:
                    total_points += score.total_points
        
        # Sort by competition date (most recent first)
        race_results.sort(key=lambda x: x['competition'].event_date, reverse=True)
        
        return render_template(
            "user_race_results.html",
            target_user=target_user,
            season_team=season_team,
            race_results=race_results,
            total_points=total_points,
            current_user_id=session["user_id"]
        )
        
    except Exception as e:
        print(f"Error viewing user race results: {e}")
        flash("Ett fel uppstod vid visning av race-resultaten.", "error")
        return redirect(url_for("index"))

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
        
        # Get user's race results for profile
        race_results = []
        total_points = 0
        competitions = Competition.query.order_by(Competition.event_date).all()
        for competition in competitions:
            score = CompetitionScore.query.filter_by(user_id=user_id, competition_id=competition.id).first()
            has_results = CompetitionResult.query.filter_by(competition_id=competition.id).first() is not None
            if score or has_results:
                race_results.append({
                    'competition': competition,
                    'points': score.total_points if score else 0,
                    'race_points': 0,  # CompetitionScore only has total_points
                    'holeshot_points': 0,  # CompetitionScore only has total_points
                    'wildcard_points': 0,  # CompetitionScore only has total_points
                    'has_results': has_results
                })
                if score:
                    total_points += score.total_points
        race_results.sort(key=lambda x: x['competition'].event_date, reverse=True)
        
        return render_template(
            "user_profile.html",
            target_user=target_user,
            season_team=season_team,
            team_riders=team_riders,
            current_picks_450=current_picks_450,
            current_picks_250=current_picks_250,
            upcoming_race=upcoming_race,
            picks_locked=picks_locked,
            current_user_id=session["user_id"],
            race_results=race_results,
            total_points=total_points
        )
        
    except Exception as e:
        print(f"Error viewing user profile: {e}")
        import traceback
        print(f"ERROR traceback: {traceback.format_exc()}")
        flash(f"Ett fel uppstod vid visning av profilen: {str(e)}", "error")
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

@app.get("/find_duplicate_riders")
def find_duplicate_riders():
    """Find duplicate riders based on name and number"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        from sqlalchemy import text
        
        # Find riders with same name
        same_name_query = text("""
            SELECT name, COUNT(*) as count, GROUP_CONCAT(id) as ids, GROUP_CONCAT(rider_number) as numbers
            FROM riders 
            GROUP BY name 
            HAVING COUNT(*) > 1
            ORDER BY name
        """)
        
        same_name_results = db.session.execute(same_name_query).fetchall()
        
        # Find riders with same number in same class
        same_number_query = text("""
            SELECT rider_number, class_name, COUNT(*) as count, GROUP_CONCAT(id) as ids, GROUP_CONCAT(name) as names
            FROM riders 
            GROUP BY rider_number, class_name 
            HAVING COUNT(*) > 1
            ORDER BY rider_number, class_name
        """)
        
        same_number_results = db.session.execute(same_number_query).fetchall()
        
        duplicates = {
            "same_name": [{"name": r[0], "count": r[1], "ids": r[2], "numbers": r[3]} for r in same_name_results],
            "same_number": [{"number": r[0], "class": r[1], "count": r[2], "ids": r[3], "names": r[4]} for r in same_number_results]
        }
        
        return jsonify(duplicates)
        
    except Exception as e:
        print(f"Error finding duplicates: {e}")
        return jsonify({"error": str(e)}), 500

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
        
        # Don't create riders here - use rider management as master list
        # Riders should only be created/updated through rider management interface
        print('DEBUG: Skipping rider creation - use rider management interface instead')
        
        
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
    
    # Don't create riders here - use rider management as master list
    # Riders should only be created/updated through rider management interface
    print("DEBUG: Skipping rider creation in create_test_data - use rider management interface instead")
    if False:  # Never create riders here
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
        
        # Get riders from database instead of hardcoded list
        riders_250 = []
        db_riders_250 = Rider.query.filter_by(class_name='250cc').all()
        for rider in db_riders_250:
            riders_250.append({
                'name': rider.name,
                'class_name': rider.class_name,
                'bike_brand': rider.bike_brand,
                'rider_number': rider.rider_number,
                'coast_250': rider.coast_250
            })
        
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
    # Don't delete riders - use rider management as master list
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
    
    # Don't create riders here - use rider management as master list
    # Riders should only be created/updated through rider management interface
    print("DEBUG: Skipping rider creation in force_create_data - use rider management interface instead")
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
        {'name': 'Chance Hymas', 'class_name': '250cc', 'bike_brand': 'Honda', 'rider_number': 49, 'coast_250': 'west'},
        {'name': 'Enzo Lopes', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 50, 'coast_250': 'west'},
        {'name': 'Cullin Park', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 53, 'coast_250': 'west'},
        
        # East Coast 250cc riders
        {'name': 'Ty Masterpool', 'class_name': '250cc', 'bike_brand': 'GasGas', 'rider_number': 81, 'coast_250': 'east'},
        {'name': 'Jordon Smith', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'rider_number': 58, 'coast_250': 'east'},
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
    
    # Don't create riders here - use rider management as master list
    print("DEBUG: No riders created in force_create_data - use rider management interface instead")
    
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
# CSV import function removed - use rider management as master list only

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
    
    # Don't create riders here - use rider management as master list
    # Riders should only be created/updated through rider management interface
    print("DEBUG: Skipping rider creation in create_test_data - use rider management interface instead")
    # Don't create riders here - use rider management as master list
    print("DEBUG: No riders created in create_test_data - use rider management interface instead")
    
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
            # BACKUP USER PROFILE DATA AND SEASON TEAMS BEFORE DELETION
            print("Backing up user profile data and season teams...")
            users = User.query.all()
            profile_backups = []
            season_team_backups = []
            
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
            
            # Backup season teams
            season_teams = SeasonTeam.query.all()
            for team in season_teams:
                team_riders = SeasonTeamRider.query.filter_by(season_team_id=team.id).all()
                team_backup = {
                    'user_id': team.user_id,
                    'team_name': team.team_name,
                    'total_points': team.total_points,
                    'rider_ids': [tr.rider_id for tr in team_riders]
                }
                season_team_backups.append(team_backup)
            
            print(f"Backed up {len(profile_backups)} user profiles and {len(season_team_backups)} season teams")
            
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
            
            # RESTORE SEASON TEAMS
            print("Restoring season teams...")
            for team_backup in season_team_backups:
                # Find the user by username (since user IDs might have changed)
                user = User.query.filter_by(username=profile_backups[team_backup['user_id']-1]['username']).first()
                if user:
                    # Create the season team
                    team = SeasonTeam(
                        user_id=user.id,
                        team_name=team_backup['team_name'],
                        total_points=0  # Reset points to 0
                    )
                    db.session.add(team)
                    db.session.flush()  # Get the team ID
                    
                    # Add the riders to the team
                    for rider_id in team_backup['rider_ids']:
                        team_rider = SeasonTeamRider(
                            season_team_id=team.id,
                            rider_id=rider_id
                        )
                        db.session.add(team_rider)
            
            db.session.commit()
            print(f"Restored {len(season_team_backups)} season teams with their riders")
            
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

@app.get("/set_anaheim2_active")
def set_anaheim2_active():
    """Just set Anaheim 2 as active race without creating picks/results"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find Anaheim 2 competition
        anaheim2 = Competition.query.filter_by(name="Anaheim 2").first()
        if not anaheim2:
            return jsonify({"error": "Anaheim 2 competition not found"})
        
        # Set as active race in global simulation
        global_sim = GlobalSimulation.query.first()
        if not global_sim:
            global_sim = GlobalSimulation()
            db.session.add(global_sim)
        
        global_sim.active_race_id = anaheim2.id
        global_sim.is_active = True
        db.session.commit()
        
        return jsonify({
            "message": f"Anaheim 2 set as active race (ID: {anaheim2.id})",
            "competition": {
                "id": anaheim2.id,
                "name": anaheim2.name,
                "date": anaheim2.event_date.isoformat() if anaheim2.event_date else None
            }
        })
        
    except Exception as e:
        print(f"Error setting Anaheim 2 as active: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/quick_anaheim2_simulation")
def quick_anaheim2_simulation():
    """Quick simulation for Anaheim 2 - both picks and results"""
    if session.get("username") != "test":
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Find Anaheim 2 competition
        anaheim2 = Competition.query.filter_by(name="Anaheim 2").first()
        if not anaheim2:
            return jsonify({"error": "Anaheim 2 competition not found"})
        
        competition_id = anaheim2.id
        
        # Step 1: Generate auto picks
        users = User.query.all()
        riders_450 = Rider.query.filter_by(class_name="450cc").all()
        riders_250_query = Rider.query.filter_by(class_name="250cc")
        if anaheim2.coast_250 == "both":
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == "east") | (Rider.coast_250 == "west") | (Rider.coast_250 == "both")
            )
        elif anaheim2.coast_250 in ("east", "west"):
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == anaheim2.coast_250) | (Rider.coast_250 == "both")
            )
        riders_250 = riders_250_query.all()
        riders = riders_450 + riders_250
        
        if not riders:
            return jsonify({"error": "No riders found for this competition"}), 400
        
        picks_created = 0
        for user in users:
            existing_picks = RacePick.query.filter_by(
                user_id=user.id,
                competition_id=competition_id
            ).first()
            if existing_picks:
                continue
            import random
            shuffled_riders = riders.copy()
            random.shuffle(shuffled_riders)
            for position in range(1, min(11, len(shuffled_riders) + 1)):
                pick = RacePick(
                    user_id=user.id,
                    competition_id=competition_id,
                    rider_id=shuffled_riders[position-1].id,
                    predicted_position=position
                )
                db.session.add(pick)
                picks_created += 1
        
        # Step 2: Generate simulated results
        CompetitionResult.query.filter_by(competition_id=competition_id).delete()
        HoleshotResult.query.filter_by(competition_id=competition_id).delete()
        CompetitionScore.query.filter_by(competition_id=competition_id).delete()
        
        import random
        shuffled_riders = riders.copy()
        random.shuffle(shuffled_riders)
        results_created = 0
        for position in range(1, min(21, len(shuffled_riders) + 1)):
            result = CompetitionResult(
                competition_id=competition_id,
                rider_id=shuffled_riders[position-1].id,
                position=position
            )
            db.session.add(result)
            results_created += 1
        
        db.session.commit()
        calculate_scores(competition_id)
        
        return jsonify({
            "message": f"Anaheim 2 simulation completed!",
            "picks_created": picks_created,
            "results_created": results_created,
            "users_count": len(users)
        })
        
    except Exception as e:
        print(f"Error in Anaheim 2 simulation: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/debug_users")
def debug_users():
    """Debug route to check which users exist - no login required for testing"""
    # Skip login check for debugging
    try:
        users = User.query.all()
        user_list = []
        for user in users:
            user_list.append({
                "id": user.id,
                "username": user.username,
                "display_name": getattr(user, 'display_name', None)
            })
        
        return f"""
        <h1>Users in Database</h1>
        <p>Total users: {len(users)}</p>
        <ul>
        {''.join([f'<li>ID {u["id"]}: {u["username"]} (display: {u["display_name"]})</li>' for u in user_list])}
        </ul>
        """
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.get("/simple_debug")
def simple_debug():
    """Simple debug route - no login required"""
    try:
        users = User.query.all()
        result = f"Total users: {len(users)}\n"
        for user in users:
            result += f"ID {user.id}: {user.username}\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"

@app.get("/check_anaheim2")
def check_anaheim2():
    """Check if Anaheim 2 simulation worked"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        # Find Anaheim 2 competition
        anaheim2 = Competition.query.filter_by(name="Anaheim 2").first()
        if not anaheim2:
            return jsonify({"error": "Anaheim 2 competition not found"})
        
        # Check if it has results
        results = CompetitionResult.query.filter_by(competition_id=anaheim2.id).all()
        holeshots = HoleshotResult.query.filter_by(competition_id=anaheim2.id).all()
        scores = CompetitionScore.query.filter_by(competition_id=anaheim2.id).all()
        
        return jsonify({
            "competition": {
                "id": anaheim2.id,
                "name": anaheim2.name,
                "date": anaheim2.event_date.isoformat() if anaheim2.event_date else None
            },
            "results_count": len(results),
            "holeshots_count": len(holeshots),
            "scores_count": len(scores),
            "has_results": len(results) > 0,
            "sample_results": [{"rider_id": r.rider_id, "position": r.position} for r in results[:5]]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.get("/debug_anaheim1")
def debug_anaheim1():
    """Debug Anaheim 1 results to see what's missing"""
    try:
        # Find Anaheim 1 competition
        anaheim1 = Competition.query.filter_by(name="Anaheim 1").first()
        if not anaheim1:
            return jsonify({"error": "Anaheim 1 competition not found"})
        
        # Get all results for Anaheim 1, ordered by position
        results = CompetitionResult.query.filter_by(competition_id=anaheim1.id).order_by(CompetitionResult.position.asc()).all()
        
        # Get rider names for each result
        results_with_names = []
        for result in results:
            rider = Rider.query.get(result.rider_id)
            results_with_names.append({
                "position": result.position,
                "rider_id": result.rider_id,
                "rider_name": rider.name if rider else "Unknown",
                "rider_number": rider.rider_number if rider else "Unknown",
                "class_name": rider.class_name if rider else "Unknown"
            })
        
        # Check for missing positions
        positions = [r["position"] for r in results_with_names]
        missing_positions = []
        if positions:
            max_pos = max(positions)
            for i in range(1, max_pos + 1):
                if i not in positions:
                    missing_positions.append(i)
        
        return jsonify({
            "competition": {
                "id": anaheim1.id,
                "name": anaheim1.name,
                "date": anaheim1.event_date.isoformat() if anaheim1.event_date else None
            },
            "total_results": len(results),
            "positions_found": positions,
            "missing_positions": missing_positions,
            "all_results": results_with_names
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

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
    """Trash Talk Brädan - visa alla posts"""
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
    """Skapa ny post på Trash Talk Brädan"""
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
    """Ta bort post från Trash Talk Brädan"""
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

@app.route("/migrate_admin_column")
def migrate_admin_column():
    """Add is_admin column to users table"""
    try:
        # First, rollback any failed transactions
        db.session.rollback()
        
        # Check if column already exists
        result = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='is_admin'")).fetchone()
        
        if result:
            return jsonify({
                "message": "is_admin column already exists",
                "status": "already_exists"
            })
        
        # Add the column
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        
        return jsonify({
            "message": "is_admin column added successfully",
            "status": "added"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding is_admin column: {e}")
        
        # Try with direct connection
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                conn.commit()
            return jsonify({
                "message": "is_admin column added successfully via direct connection",
                "status": "added"
            })
        except Exception as e2:
            return jsonify({"error": f"Failed to add column: {str(e2)}"}), 500

@app.route("/fix_database_transaction")
def fix_database_transaction():
    """Fix failed database transactions"""
    try:
        # Rollback any failed transactions
        db.session.rollback()
        
        # Test the connection
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
        
        return jsonify({
            "message": "Database transaction fixed successfully",
            "status": "fixed"
        })
        
    except Exception as e:
        print(f"Error fixing database transaction: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/check_user_admin_status")
def check_user_admin_status():
    """Check admin status for all users - debug route"""
    try:
        users = User.query.all()
        user_status = []
        
        for user in users:
            # Check if user has is_admin attribute
            is_admin = False
            has_is_admin_column = False
            
            try:
                if hasattr(user, 'is_admin'):
                    has_is_admin_column = True
                    is_admin = user.is_admin
                else:
                    # Fallback to old method
                    is_admin = user.username == 'test'
            except Exception as e:
                is_admin = user.username == 'test'
            
            user_status.append({
                'id': user.id,
                'username': user.username,
                'display_name': getattr(user, 'display_name', None),
                'has_is_admin_column': has_is_admin_column,
                'is_admin': is_admin,
                'is_admin_user_result': is_admin_user() if session.get('username') == user.username else 'not_current_user'
            })
        
        return jsonify({
            'users': user_status,
            'current_user': session.get('username'),
            'is_current_user_admin': is_admin_user()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fix_mx_coast_250")
def fix_mx_coast_250():
    """Fix coast_250 for existing Motocross competitions to 'both'"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Update all MX competitions to have coast_250 = "both"
        mx_competitions = Competition.query.filter_by(series="MX").all()
        updated_count = 0
        
        for comp in mx_competitions:
            if comp.coast_250 != "both":
                comp.coast_250 = "both"
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Updated {updated_count} Motocross competitions to coast_250='both'",
            "updated_count": updated_count,
            "total_mx_competitions": len(mx_competitions)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/recalculate_scores/<int:competition_id>")
def recalculate_scores(competition_id):
    """Manually recalculate scores for a specific competition"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Check if competition exists
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 404
        
        # Run score calculation
        calculate_scores(competition_id)
        
        return jsonify({
            "message": f"Scores recalculated for {competition.name}",
            "competition_id": competition_id,
            "competition_name": competition.name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recalculate_all_scores")
def recalculate_all_scores():
    """Manually recalculate scores for all competitions that have results"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Find all competitions that have results
        competitions_with_results = (
            db.session.query(Competition.id, Competition.name)
            .join(CompetitionResult, Competition.id == CompetitionResult.competition_id)
            .distinct()
            .all()
        )
        
        recalculated = []
        for comp_id, comp_name in competitions_with_results:
            try:
                calculate_scores(comp_id)
                recalculated.append(comp_name)
            except Exception as e:
                print(f"Error recalculating scores for {comp_name}: {e}")
        
        return jsonify({
            "message": f"Recalculated scores for {len(recalculated)} competitions",
            "competitions": recalculated
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/fix_duplicate_results")
def fix_duplicate_results():
    """Fix duplicate CompetitionResult entries for the same rider in the same competition"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Find duplicate results (same competition_id and rider_id)
        duplicates = (
            db.session.query(
                CompetitionResult.competition_id,
                CompetitionResult.rider_id,
                func.count(CompetitionResult.result_id).label('count')
            )
            .group_by(CompetitionResult.competition_id, CompetitionResult.rider_id)
            .having(func.count(CompetitionResult.result_id) > 1)
            .all()
        )
        
        fixed_count = 0
        for comp_id, rider_id, count in duplicates:
            # Get all results for this competition/rider combination
            results = CompetitionResult.query.filter_by(
                competition_id=comp_id, 
                rider_id=rider_id
            ).order_by(CompetitionResult.result_id).all()
            
            # Keep the first one, delete the rest
            for result in results[1:]:
                db.session.delete(result)
                fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} duplicate results",
            "duplicates_found": len(duplicates)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/create_hampus_admin")
def create_hampus_admin():
    """Make Hampus an admin user"""
    try:
        # First ensure is_admin column exists
        try:
            db.session.execute(db.text("SELECT is_admin FROM users LIMIT 1"))
        except Exception:
            # Column doesn't exist, add it
            db.session.execute(db.text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            db.session.commit()
        
        # Check if Hampus user exists
        existing_user = User.query.filter_by(username='Hampus').first()
        
        if existing_user:
            # Update existing user to be admin
            existing_user.is_admin = True
            db.session.commit()
            
            return jsonify({
                "message": "Hampus user updated to admin successfully!",
                "username": "Hampus",
                "password": "Use your existing password",
                "user_id": existing_user.id,
                "display_name": existing_user.display_name or "Hampus",
                "is_admin": True
            })
        
        # Create new Hampus admin user
        hampus_user = User(
            username='Hampus',
            password_hash=generate_password_hash('hampus123'),
            display_name='Hampus',
            is_admin=True
        )
        
        db.session.add(hampus_user)
        db.session.commit()
        
        return jsonify({
            "message": "Hampus admin user created successfully!",
            "username": "Hampus",
            "password": "hampus123",
            "user_id": hampus_user.id,
            "display_name": "Hampus",
            "is_admin": True
        })
        
    except Exception as e:
        print(f"Error creating Hampus admin: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/users")
def admin_users():
    """Admin page to manage users"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        users = User.query.all()
        user_list = []
        
        for user in users:
            # Check if user has is_admin attribute, fallback to old method
            is_admin = False
            try:
                if hasattr(user, 'is_admin'):
                    is_admin = user.is_admin
                else:
                    # Fallback to old method for backward compatibility
                    is_admin = user.username == 'test'
            except Exception:
                is_admin = user.username == 'test'
            
            user_list.append({
                'id': user.id,
                'username': user.username,
                'display_name': getattr(user, 'display_name', None),
                'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None,
                'is_admin': is_admin
            })
        
        return render_template("admin_users.html", users=user_list)
        
    except Exception as e:
        print(f"Error loading users: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/admin/leagues")
def admin_leagues():
    """Admin page to manage leagues"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        # Get all leagues with member count and creator info
        leagues_data = db.session.query(
            League,
            db.func.count(LeagueMembership.user_id).label('member_count'),
            User.username.label('creator_username')
        ).select_from(League).outerjoin(
            LeagueMembership, League.id == LeagueMembership.league_id
        ).join(
            User, League.creator_id == User.id
        ).group_by(League.id, User.username).order_by(
            League.created_at.desc()
        ).all()
        
        leagues_list = []
        for league_data in leagues_data:
            league = league_data[0]
            member_count = league_data[1]
            creator_username = league_data[2]
            
            leagues_list.append({
                'id': league.id,
                'name': league.name,
                'creator_username': creator_username,
                'member_count': member_count,
                'total_points': league.total_points or 0,
                'is_public': getattr(league, 'is_public', True),
                'created_at': league.created_at.isoformat() if hasattr(league, 'created_at') and league.created_at else None,
                'description': league.description
            })
        
        return render_template("admin_leagues.html", leagues=leagues_list)
        
    except Exception as e:
        print(f"Error loading leagues: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/toggle_admin/<int:user_id>", methods=['POST'])
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    if not is_admin_user():
        return jsonify({"error": "admin_only"}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Toggle admin status
        user.is_admin = not user.is_admin
        db.session.commit()
        
        return jsonify({
            "success": True,
            "is_admin": user.is_admin,
            "message": f"User {user.username} admin status updated to {user.is_admin}"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error toggling admin status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/delete_user/<int:user_id>", methods=['DELETE'])
def delete_user(user_id):
    """Delete a user - admin only"""
    if not is_admin_user():
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

@app.route("/debug_simulation_status")
def debug_simulation_status():
    """Debug route to check simulation status"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Check global simulation
        simulation = GlobalSimulation.query.first()
        current_time = get_current_time()
        
        return jsonify({
            "global_simulation": {
                "id": simulation.id if simulation else None,
                "active": simulation.active if simulation else False,
                "scenario": simulation.scenario if simulation else None,
                "simulated_time": simulation.simulated_time if simulation else None,
                "start_time": simulation.start_time if simulation else None
            },
            "current_time": current_time.isoformat(),
            "current_time_type": str(type(current_time))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reset_test_simulation")
def reset_test_simulation():
    """Reset test simulation to start fresh"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Update global simulation with fresh start time
        simulation = GlobalSimulation.query.first()
        if simulation:
            now = datetime.utcnow()
            simulation.start_time = now.isoformat()
            simulation.simulated_time = now.isoformat()
            db.session.commit()
            return jsonify({"message": "Test simulation reset successfully", "new_start_time": simulation.start_time})
        else:
            return jsonify({"error": "No simulation found"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/debug_missing_bike_brands")
def debug_missing_bike_brands():
    """Debug route to check which riders are missing bike_brand"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    # Find riders with NULL or empty bike_brand
    riders_without_brand = Rider.query.filter(
        (Rider.bike_brand.is_(None)) | (Rider.bike_brand == '') | (Rider.bike_brand == 'Unknown')
    ).all()
    
    # Find riders with bike_brand
    riders_with_brand = Rider.query.filter(
        Rider.bike_brand.isnot(None),
        Rider.bike_brand != '',
        Rider.bike_brand != 'Unknown'
    ).all()
    
    return jsonify({
        "riders_without_brand": [{
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "number": r.rider_number,
            "bike_brand": r.bike_brand
        } for r in riders_without_brand],
        "riders_with_brand": [{
            "id": r.id,
            "name": r.name,
            "class": r.class_name,
            "number": r.rider_number,
            "bike_brand": r.bike_brand
        } for r in riders_with_brand],
        "count_without_brand": len(riders_without_brand),
        "count_with_brand": len(riders_with_brand)
    })

@app.route("/fix_missing_bike_brands")
def fix_missing_bike_brands():
    """Fix all riders that are missing bike_brand"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Find riders with NULL or empty bike_brand
        riders_without_brand = Rider.query.filter(
            (Rider.bike_brand.is_(None)) | (Rider.bike_brand == '') | (Rider.bike_brand == 'Unknown')
        ).all()
        
        bike_brands = ['Yamaha', 'Honda', 'Kawasaki', 'KTM', 'Husqvarna', 'GasGas', 'Suzuki']
        fixed_count = 0
        
        for rider in riders_without_brand:
            # Assign bike brand based on rider number hash for consistency
            import hashlib
            hash_val = int(hashlib.md5(f"{rider.name}_{rider.rider_number}".encode()).hexdigest()[:8], 16)
            rider.bike_brand = bike_brands[hash_val % len(bike_brands)]
            fixed_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fixed {fixed_count} riders with missing bike brands",
            "fixed_count": fixed_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/race_countdown")
def race_countdown():
    """Countdown for main page - supports both real and test modes"""
    try:
        mode = request.args.get('mode', 'real')
        
        if mode == 'test':
            # Test mode - use simulated time from GlobalSimulation
            simulation = GlobalSimulation.query.filter_by(active=True).first()
            if simulation and simulation.scenario:
                # Use simulated time for test mode - calculate fresh each time
                current_simulated_time = get_current_time()
                
                # Calculate race time based on scenario - use initial simulated time for fixed race times
                # Get the initial simulated time when simulation started
                initial_simulated_time = datetime.fromisoformat(simulation.simulated_time)
                
                if simulation.scenario == 'active_race_1':
                    # Simulate race in 3 hours for testing
                    race_datetime = initial_simulated_time + timedelta(hours=3)
                    deadline_datetime = initial_simulated_time + timedelta(hours=1)
                    race_name = "Test Race (Anaheim 1)"
                elif simulation.scenario == 'race_in_3h':
                    # Simulate race in 3 hours for testing
                    race_datetime = initial_simulated_time + timedelta(hours=3)
                    deadline_datetime = initial_simulated_time + timedelta(hours=1)
                    race_name = "Test Race (3h)"
                elif simulation.scenario == 'race_in_1h':
                    # Simulate race in 1 hour for testing
                    race_datetime = initial_simulated_time + timedelta(hours=1)
                    deadline_datetime = initial_simulated_time - timedelta(hours=1)  # Already passed
                    race_name = "Test Race (1h)"
                elif simulation.scenario == 'race_in_30m':
                    # Simulate race in 30 minutes for testing
                    race_datetime = initial_simulated_time + timedelta(minutes=30)
                    deadline_datetime = initial_simulated_time - timedelta(hours=1, minutes=30)  # Already passed
                    race_name = "Test Race (30m)"
                elif simulation.scenario == 'race_tomorrow':
                    # Simulate race tomorrow
                    race_datetime = initial_simulated_time + timedelta(days=1)
                    deadline_datetime = initial_simulated_time + timedelta(hours=22)  # 2 hours before tomorrow
                    race_name = "Test Race (Tomorrow)"
                else:
                    return jsonify({"error": f"Unknown test scenario: {simulation.scenario}"})
                
                next_race = {
                    "name": race_name,
                    "event_date": race_datetime.isoformat()
                }
                
                # Calculate countdown using simulated time - this will change each call
                race_diff = race_datetime - current_simulated_time
                deadline_diff = deadline_datetime - current_simulated_time
                
                def format_countdown(td):
                    total_seconds = int(td.total_seconds())
                    if total_seconds <= 0:
                        return {
                            "total_seconds": 0,
                            "days": 0,
                            "hours": 0,
                            "minutes": 0,
                            "seconds": 0
                        }
                    
                    days = total_seconds // 86400
                    hours = (total_seconds % 86400) // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    
                    return {
                        "total_seconds": total_seconds,
                        "days": days,
                        "hours": hours,
                        "minutes": minutes,
                        "seconds": seconds
                    }
                
                # Use is_picks_locked for consistency
                # Create a dummy competition object for the test race
                class TestCompetition:
                    def __init__(self, name, event_date):
                        self.name = name
                        self.event_date = event_date
                        self.id = 999  # Dummy ID for test race
                
                test_comp = TestCompetition(race_name, race_datetime.date())
                picks_locked = is_picks_locked(test_comp)
                
                return jsonify({
                    "next_race": next_race,
                    "countdown": {
                        "race_start": format_countdown(race_diff),
                        "pick_deadline": format_countdown(deadline_diff)
                    },
                    "picks_locked": picks_locked
                })
            else:
                return jsonify({"error": "No active test simulation"})
        else:
            # Real mode - use actual race dates
            today = get_today()
            next_race_obj = (
                Competition.query
                .filter(Competition.event_date >= today)
                .order_by(Competition.event_date.asc())
                .first()
            )
            
            if not next_race_obj:
                return jsonify({"error": "No upcoming races"})
            
            # Calculate countdown to race start using start_time from database
            # Ensure event_date is a datetime object
            if isinstance(next_race_obj.event_date, str):
                event_date = datetime.fromisoformat(next_race_obj.event_date.replace('Z', '+00:00'))
            elif isinstance(next_race_obj.event_date, date) and not isinstance(next_race_obj.event_date, datetime):
                # Convert date to datetime at midnight
                event_date = datetime.combine(next_race_obj.event_date, datetime.min.time())
            else:
                event_date = next_race_obj.event_date
            
            # Use start_time from database if available, otherwise default to 8 PM
            if next_race_obj.start_time:
                race_datetime = datetime.combine(event_date.date(), next_race_obj.start_time)
            else:
                race_datetime = event_date.replace(hour=20, minute=0, second=0, microsecond=0)
            
            deadline_datetime = race_datetime - timedelta(hours=2)  # 2 hours before race
            
            next_race = {
                "name": next_race_obj.name,
                "event_date": next_race_obj.event_date.isoformat()
            }
        
        now = datetime.utcnow()
        
        # Calculate time differences
        race_diff = race_datetime - now
        deadline_diff = deadline_datetime - now
        
        def format_countdown(timedelta_obj):
            total_seconds = int(timedelta_obj.total_seconds())
            if total_seconds <= 0:
                return {
                    "total_seconds": 0,
                    "days": 0,
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 0
                }
            
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            return {
                "total_seconds": total_seconds,
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds
            }
        
        # Use is_picks_locked for consistency
        # Find the actual competition for this race
        upcoming_race = Competition.query.filter(
            Competition.event_date >= today,
            Competition.event_date <= today + timedelta(days=7)
        ).order_by(Competition.event_date).first()
        
        picks_locked = False
        if upcoming_race:
            picks_locked = is_picks_locked(upcoming_race)
        
        return jsonify({
            "next_race": next_race,
            "countdown": {
                "race_start": format_countdown(race_diff),
                "pick_deadline": format_countdown(deadline_diff)
            },
            "picks_locked": picks_locked
        })
        
    except Exception as e:
        print(f"Error in race_countdown: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/simulate_race/<int:race_id>", methods=['POST'])
def simulate_race(race_id):
    """Simulate a race - placeholder for now"""
    if session.get("username") != "test":
        return jsonify({"error": "Unauthorized"}), 403
    
    # TODO: Implement actual race simulation
    return jsonify({"message": f"Race {race_id} simulation not yet implemented"})


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
    """Get 450cc SMX qualification standings (Top 20)"""
    try:
        all_riders = calculate_smx_qualification_points()
        
        # Filter only 450cc riders (they should be at the beginning of the list)
        qualification_data = []
        position = 1
        for rider_id, data in all_riders:
            rider = data['rider']
            if rider.class_name == '450cc':
                qualification_data.append({
                    'position': position,
                    'rider_id': rider.id,
                    'rider_name': rider.name,
                    'rider_number': rider.rider_number,
                    'bike_brand': rider.bike_brand,
                    'rider_class': rider.class_name,
                    'total_points': data['total_points'],
                    'sx_points': data['sx_points'],
                    'mx_points': data['mx_points'],
                    'qualified': position <= 20
                })
                position += 1
        
        print(f"DEBUG: 450cc SMX qualification - Found {len(qualification_data)} 450cc riders")
        
        return jsonify({
            'success': True,
            'qualification': qualification_data,
            'total_qualified': len(qualification_data)
        })
        
    except Exception as e:
        print(f"ERROR in get_smx_qualification: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/smx_qualification_250cc")
def get_smx_qualification_250cc():
    """Get 250cc SMX qualification standings (Top 20)"""
    try:
        all_riders = calculate_smx_qualification_points()
        
        # Filter only 250cc riders (they should now be at the end of the list)
        qualification_data = []
        position = 1
        for rider_id, data in all_riders:
            rider = data['rider']
            if rider.class_name == '250cc':
                qualification_data.append({
                    'position': position,
                    'rider_id': rider.id,
                    'rider_name': rider.name,
                    'rider_number': rider.rider_number,
                    'bike_brand': rider.bike_brand,
                    'coast_250': rider.coast_250,
                    'total_points': data['total_points'],
                    'sx_points': data['sx_points'],
                    'mx_points': data['mx_points'],
                    'qualified': position <= 20
                })
                position += 1
        
        print(f"DEBUG: 250cc SMX qualification - Found {len(qualification_data)} 250cc riders")
        
        return jsonify({
            'success': True,
            'qualification': qualification_data,
            'total_qualified': len(qualification_data)
        })
        
    except Exception as e:
        print(f"ERROR in get_smx_qualification_250cc: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/debug_250cc")
def debug_250cc():
    """Debug endpoint to check 250cc riders and their results"""
    try:
        # Get all 250cc riders
        riders_250 = Rider.query.filter_by(class_name='250cc').all()
        
        debug_info = {
            'total_250cc_riders': len(riders_250),
            'riders': []
        }
        
        for rider in riders_250:
            # Get all results for this rider
            sx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
                CompetitionResult.rider_id == rider.id,
                Series.name.ilike('%supercross%')
            ).all()
            
            mx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
                CompetitionResult.rider_id == rider.id,
                Series.name.ilike('%motocross%')
            ).all()
            
            debug_info['riders'].append({
                'name': rider.name,
                'coast_250': rider.coast_250,
                'sx_results_count': len(sx_results),
                'mx_results_count': len(mx_results),
                'sx_positions': [r.position for r in sx_results if r.position],
                'mx_positions': [r.position for r in mx_results if r.position]
            })
        
        return jsonify(debug_info)
        
    except Exception as e:
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
        
        # Format SMX qualification overview - separate 450cc and 250cc
        smx_450cc = [(rider_id, data) for rider_id, data in smx_qualification if data['rider'].class_name == '450cc']
        smx_250cc = [(rider_id, data) for rider_id, data in smx_qualification if data['rider'].class_name == '250cc']
        
        print(f"DEBUG: SMX qualification - Total: {len(smx_qualification)}, 450cc: {len(smx_450cc)}, 250cc: {len(smx_250cc)}")
        
        smx_overview = {
            'total_qualified': len(smx_qualification),
            '450cc_top_5': [],
            '250cc_top_5': []
        }
        
        # 450cc Top 5
        for i, (rider_id, data) in enumerate(smx_450cc[:5], 1):
            rider = data['rider']
            smx_overview['450cc_top_5'].append({
                'position': i,
                'rider_name': rider.name,
                'rider_number': rider.rider_number,
                'total_points': data['total_points'],
                'sx_points': data['sx_points'],
                'mx_points': data['mx_points']
            })
        
        # 250cc Top 5
        for i, (rider_id, data) in enumerate(smx_250cc[:5], 1):
            rider = data['rider']
            smx_overview['250cc_top_5'].append({
                'position': i,
                'rider_name': rider.name,
                'rider_number': rider.rider_number,
                'coast_250': rider.coast_250,
                'total_points': data['total_points'],
                'sx_points': data['sx_points'],
                'mx_points': data['mx_points']
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
        
        # Create race datetime for testing using actual start_time if available
        race_date = next_race_date.event_date
        if hasattr(next_race_date, 'start_time') and next_race_date.start_time:
            race_datetime_local = datetime.combine(race_date, next_race_date.start_time)
        else:
            # Default to 8pm if no start_time set
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
            # Rollback any existing transaction first
            db.session.rollback()
            
            db.session.execute(db.text("""
                INSERT INTO global_simulation (id, active, simulated_time, start_time, scenario) 
                VALUES (1, :active, :simulated_time, :start_time, :scenario)
                ON CONFLICT (id) DO UPDATE SET 
                    active = :active,
                    simulated_time = :simulated_time,
                    start_time = :start_time,
                    scenario = :scenario
            """), {
                'active': True,
                'simulated_time': simulated_time.isoformat(),
                'start_time': datetime.utcnow().isoformat(),
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
        # Use actual start_time from competition if available, otherwise default to 8pm
        if hasattr(next_race, 'start_time') and next_race.start_time:
            race_hour = next_race.start_time.hour
            race_minute = next_race.start_time.minute
        else:
            # Default to 8pm if no start_time set
            race_hour, race_minute = 20, 0
        
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
    """Set simulated time for testing scenarios"""
    try:
        scenario = request.args.get('scenario', 'race_in_3h')
        competition_id = request.args.get('competition_id')
        print(f"DEBUG: set_simulated_time called with scenario: {scenario}, competition_id: {competition_id}")
        
        # Update global simulation state in database
        global_sim = GlobalSimulation.query.first()
        if not global_sim:
            global_sim = GlobalSimulation(active=True, scenario=scenario)
            db.session.add(global_sim)
        else:
            global_sim.active = True
            global_sim.scenario = scenario
        
        # Set simulated time and start time for countdown calculation
        current_real_time = datetime.utcnow()
        global_sim.start_time = current_real_time.isoformat()
        
        # Set simulated time based on scenario
        if scenario == 'race_in_3h':
            # Simulate current time as 3 hours before race
            simulated_time = current_real_time - timedelta(hours=3)
        elif scenario == 'race_in_1h':
            # Simulate current time as 1 hour before race
            simulated_time = current_real_time - timedelta(hours=1)
        elif scenario == 'race_in_30m':
            # Simulate current time as 30 minutes before race
            simulated_time = current_real_time - timedelta(minutes=30)
        else:
            # Default to current time
            simulated_time = current_real_time
        
        global_sim.simulated_time = simulated_time.isoformat()
        print(f"DEBUG: Set simulated_time to {simulated_time}, real_start_time to {current_real_time}")
        
        # If competition_id is provided, set it as active race
        if competition_id:
            try:
                competition_id = int(competition_id)
                competition = Competition.query.get(competition_id)
                if competition:
                    global_sim.active_race_id = competition_id
                    print(f"DEBUG: Set active race to {competition.name} (ID: {competition_id})")
                    
                    # Also activate the series for this competition
                    if competition.series_id:
                        # Deactivate all series first
                        Series.query.update({'is_active': False})
                        
                        # Activate the series for this competition
                        competition_series = Series.query.get(competition.series_id)
                        if competition_series:
                            competition_series.is_active = True
                            print(f"DEBUG: Activated series '{competition_series.name}' for competition '{competition.name}'")
                else:
                    print(f"DEBUG: Competition with ID {competition_id} not found")
            except ValueError:
                print(f"DEBUG: Invalid competition_id: {competition_id}")
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Simulated time set to scenario: {scenario}",
            "scenario": scenario
        })
        
    except Exception as e:
        print(f"DEBUG: Error in set_simulated_time: {e}")
        db.session.rollback()
        return jsonify({
            "error": f"Failed to set simulated time: {str(e)}"
        }), 500

@app.get("/set_active_race")
def set_active_race():
    """Set which race should be active for testing - simple approach"""
    try:
        competition_id = request.args.get('competition_id')
        
        if not competition_id:
            return jsonify({"error": "competition_id required"}), 400
        
        # Convert to integer
        try:
            competition_id = int(competition_id)
        except ValueError:
            return jsonify({"error": "competition_id must be a number"}), 400
        
        # Store active race in database using ORM
        try:
            # Get the competition to find its series
            competition = Competition.query.get(competition_id)
            if not competition:
                return jsonify({"error": "Competition not found"}), 404
            
            print(f"DEBUG: Setting active race - Competition: {competition.name}, Series ID: {competition.series_id}, Date: {competition.event_date}")
            
            # Check if record exists
            existing = GlobalSimulation.query.filter_by(id=1).first()
            
            if existing:
                # Update existing record
                existing.active = True
                existing.simulated_time = datetime.utcnow().isoformat()
                existing.start_time = datetime.utcnow().isoformat()
                existing.scenario = f'active_race_{competition_id}'
                existing.active_race_id = competition_id
            else:
                # Create new record
                new_sim = GlobalSimulation(
                    id=1,
                    active=True,
                    simulated_time=datetime.utcnow().isoformat(),
                    start_time=datetime.utcnow().isoformat(),
                    scenario=f'active_race_{competition_id}',
                    active_race_id=competition_id
                )
                db.session.add(new_sim)
            
            # Set the competition's series as active for simulation
            if competition.series_id:
                # Deactivate all series first
                Series.query.update({'is_active': False})
                
                # Activate the series for this competition
                competition_series = Series.query.get(competition.series_id)
                if competition_series:
                    competition_series.is_active = True
                    print(f"DEBUG: Activated series '{competition_series.name}' for competition '{competition.name}'")
            
            db.session.commit()
            print(f"DEBUG: Set active race to competition ID: {competition_id}")
            
        except Exception as db_error:
            print(f"Database update failed: {db_error}")
            db.session.rollback()
            return jsonify({"error": f"Database update failed: {str(db_error)}"}), 500
        
        return jsonify({
            "message": f"Active race set to competition ID: {competition_id}",
            "competition_id": competition_id,
            "clear_localStorage": True  # Signal to frontend to clear localStorage
        })
        
    except Exception as e:
        print(f"Error setting active race: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/race_picks_active")
def race_picks_active():
    """Redirect to race picks for the currently active race"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    try:
        # Get active race from global simulation
        result = db.session.execute(db.text("SELECT active_race_id FROM global_simulation WHERE id = 1")).fetchone()
        
        if result and result[0]:
            active_race_id = result[0]
            print(f"DEBUG: Redirecting to active race picks for competition ID: {active_race_id}")
            return redirect(url_for("race_picks_page", competition_id=active_race_id))
        else:
            flash("Inget aktivt race satt för simulering", "error")
            return redirect(url_for("index"))
            
    except Exception as e:
        print(f"Error getting active race: {e}")
        flash("Fel vid hämtning av aktivt race", "error")
        return redirect(url_for("index"))

@app.route("/reset_simulation")
def reset_simulation():
    """Reset simulation to real time"""
    try:
        # Clear database simulation
        try:
            db.session.execute(db.text("UPDATE global_simulation SET active = FALSE, active_race_id = NULL WHERE id = 1"))
            db.session.commit()
            print("DEBUG: Reset simulation to real time")
        except Exception as db_error:
            print(f"Database reset failed: {db_error}")
            db.session.rollback()
        
        return jsonify({"message": "Simulation reset to real time"})
        
    except Exception as e:
        print(f"Error resetting simulation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/generate_auto_picks")
def generate_auto_picks():
    """Generate automatic picks for all users for testing"""
    try:
        competition_id = request.args.get('competition_id')
        
        if not competition_id:
            return jsonify({"error": "competition_id required"}), 400
        
        # Get competition to check coast_250
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        # Get all users
        users = User.query.all()
        
        # Get all riders based on class and coast (same logic as race_picks_page)
        riders_450 = Rider.query.filter_by(class_name="450cc").all()
        
        # 250cc riders with coast logic
        riders_250_query = Rider.query.filter_by(class_name="250cc")
        if competition.coast_250 == "both":
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == "east") | (Rider.coast_250 == "west") | (Rider.coast_250 == "both")
            )
        elif competition.coast_250 in ("east", "west"):
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == competition.coast_250) | (Rider.coast_250 == "both")
            )
        riders_250 = riders_250_query.all()
        
        # Combine all riders
        riders = riders_450 + riders_250
        
        if not riders:
            return jsonify({"error": "No riders found for this competition"}), 400
        
        picks_created = 0
        
        for user in users:
            # Check if user already has picks for this competition
            existing_picks = RacePick.query.filter_by(
                user_id=user.id, 
                competition_id=competition_id
            ).first()
            
            if existing_picks:
                continue  # Skip if user already has picks
            
            # Generate random picks
            import random
            shuffled_riders = riders.copy()
            random.shuffle(shuffled_riders)
            
            # Create picks for positions 1-10
            for position in range(1, min(11, len(shuffled_riders) + 1)):
                pick = RacePick(
                    user_id=user.id,
                    
                    competition_id=competition_id,
                    rider_id=shuffled_riders[position-1].id,
                    predicted_position=position
                )
                db.session.add(pick)
                picks_created += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Generated {picks_created} auto-picks for {len(users)} users",
            "picks_created": picks_created,
            "users_count": len(users)
        })
        
    except Exception as e:
        print(f"Error generating auto picks: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/quick_simulation")
def quick_simulation():
    """Quick simulation - run through multiple races with auto-picks and results"""
    try:
        series_id = request.args.get('series_id')
        num_races = int(request.args.get('num_races', 3))
        
        if not series_id:
            return jsonify({"error": "series_id required"}), 400
        
        # Get competitions for this series
        competitions = Competition.query.filter_by(series_id=series_id).order_by(Competition.event_date).all()
        
        
        # If no competitions found, try to fix by updating existing competitions
        if not competitions:
            print(f"DEBUG: No competitions found for series_id {series_id}, trying to fix...")
            
            # Get the series name
            series = Series.query.get(series_id)
            if not series:
                print(f"DEBUG: Series with ID {series_id} not found")
                
                # Check what series exist
                all_series = Series.query.all()
                print(f"DEBUG: Available series in database: {len(all_series)}")
                for s in all_series:
                    print(f"DEBUG: - Series ID {s.id}: {s.name}")
                
                # Try to find existing Supercross series (ID 10)
                if series_id == 1:
                    print(f"DEBUG: Looking for existing Supercross series...")
                    supercross_series = Series.query.filter_by(name="Supercross").first()
                    if supercross_series:
                        print(f"DEBUG: Found existing Supercross series with ID {supercross_series.id}")
                        series = supercross_series
                        # Update the series_id to use the correct one
                        series_id = supercross_series.id
                    else:
                        return jsonify({"error": "Supercross series not found in database"}), 400
                else:
                    return jsonify({"error": f"Series with ID {series_id} not found and cannot be auto-created"}), 400
            
            print(f"DEBUG: Found series: {series.name}")
            
            # Check if there are any competitions at all
            all_comps = Competition.query.all()
            print(f"DEBUG: Total competitions in database: {len(all_comps)}")
            for comp in all_comps:
                print(f"DEBUG: - {comp.name} (series_id: {comp.series_id})")
            
            # Try to find competitions by series name or other criteria
            if series.name == "Supercross":
                # Update Supercross competitions
                supercross_comps = Competition.query.filter(
                    Competition.name.like('%Anaheim%') | 
                    Competition.name.like('%San Francisco%') | 
                    Competition.name.like('%San Diego%') |
                    Competition.name.like('%Houston%') |
                    Competition.name.like('%Tampa%') |
                    Competition.name.like('%Arlington%') |
                    Competition.name.like('%Detroit%') |
                    Competition.name.like('%Glendale%') |
                    Competition.name.like('%Seattle%') |
                    Competition.name.like('%Denver%') |
                    Competition.name.like('%Salt Lake%')
                ).all()
                
                print(f"DEBUG: Found {len(supercross_comps)} potential Supercross competitions")
                
                if not supercross_comps:
                    print(f"DEBUG: No Supercross competitions found at all!")
                    return jsonify({"error": "No Supercross competitions found in database"}), 400
                
                # Update them with correct series_id
                for comp in supercross_comps:
                    comp.series_id = series_id
                    comp.phase = "regular"
                    print(f"DEBUG: Updated {comp.name} with series_id {series_id}")
                
                db.session.commit()
                
                # Try again
                competitions = Competition.query.filter_by(series_id=series_id).order_by(Competition.event_date).all()
                print(f"DEBUG: After fix, found {len(competitions)} competitions")
            else:
                print(f"DEBUG: Series {series.name} is not Supercross, cannot auto-fix")
                return jsonify({"error": f"Cannot auto-fix series {series.name}"}), 400
        
        if not competitions:
            return jsonify({"error": "No competitions found for this series"}), 400
        
        # Check if we have enough competitions
        if len(competitions) < num_races:
            return jsonify({
                "error": f"Not enough competitions. Series has {len(competitions)} competitions but {num_races} requested"
            }), 400
        
        results = []
        
        for i, competition in enumerate(competitions[:num_races]):
            # Generate auto-picks for this competition
            users = User.query.all()
            
            # Get all riders based on class and coast (same logic as race_picks_page)
            riders_450 = Rider.query.filter_by(class_name="450cc").all()
            
            # 250cc riders with coast logic
            riders_250_query = Rider.query.filter_by(class_name="250cc")
            if competition.coast_250 == "both":
                riders_250_query = riders_250_query.filter(
                    (Rider.coast_250 == "east") | (Rider.coast_250 == "west") | (Rider.coast_250 == "both")
                )
            elif competition.coast_250 in ("east", "west"):
                riders_250_query = riders_250_query.filter(
                    (Rider.coast_250 == competition.coast_250) | (Rider.coast_250 == "both")
                )
            riders_250 = riders_250_query.all()
            
            # Combine all riders
            riders = riders_450 + riders_250
            
            if not riders:
                continue
            
            # Clear existing results for this competition first
            CompetitionResult.query.filter_by(competition_id=competition.id).delete()
            HoleshotResult.query.filter_by(competition_id=competition.id).delete()
            CompetitionScore.query.filter_by(competition_id=competition.id).delete()
            
            picks_created = 0
            
            for user in users:
                # Always generate new picks (don't skip existing ones)
                # This allows running quick simulation multiple times
                
                # Generate random picks
                import random
                shuffled_riders = riders.copy()
                random.shuffle(shuffled_riders)
                
                for position in range(1, min(11, len(shuffled_riders) + 1)):
                    pick = RacePick(
                        user_id=user.id,
                        competition_id=competition.id,
                        rider_id=shuffled_riders[position-1].id,
                        predicted_position=position
                    )
                    db.session.add(pick)
                    picks_created += 1
                    print(f"DEBUG: Created pick for user {user.username}: rider {shuffled_riders[position-1].name} at position {position}")
            
            # Generate random results
            import random
            shuffled_riders = riders.copy()
            random.shuffle(shuffled_riders)
            
            results_created = 0
            for position in range(1, min(11, len(shuffled_riders) + 1)):
                result = CompetitionResult(
                    competition_id=competition.id,
                    rider_id=shuffled_riders[position-1].id,
                    position=position
                )
                db.session.add(result)
                results_created += 1
                print(f"DEBUG: Created result: rider {shuffled_riders[position-1].name} at position {position}")
            
            # Commit picks and results before calculating scores
            db.session.commit()
            print(f"DEBUG: Committed picks and results to database")
            
            # Calculate scores for this competition
            print(f"DEBUG: About to calculate scores for {competition.name}")
            print(f"DEBUG: Created {picks_created} picks and {results_created} results")
            calculate_scores(competition.id)
            
            # Debug: Check what scores were generated
            scores_after = CompetitionScore.query.filter_by(competition_id=competition.id).all()
            print(f"DEBUG: After calculate_scores for {competition.name}:")
            for score in scores_after:
                user = User.query.get(score.user_id)
                print(f"DEBUG: - {user.username}: {score.total_points} total ({score.race_points} race + {score.holeshot_points} holeshot + {score.wildcard_points} wildcard)")
            
            results.append({
                "competition": competition.name,
                "picks_created": picks_created,
                "results_created": results_created
            })
        
        return jsonify({
            "message": f"Quick simulation completed for {len(results)} races",
            "results": results
        })
        
    except Exception as e:
        print(f"Error in quick simulation: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/generate_simulated_results")
def generate_simulated_results():
    """Generate simulated results for a specific competition"""
    try:
        competition_id = request.args.get('competition_id')
        
        if not competition_id:
            return jsonify({"error": "competition_id required"}), 400
        
        # Get competition to check coast_250
        competition = Competition.query.get(competition_id)
        if not competition:
            return jsonify({"error": "Competition not found"}), 400
        
        # Clear existing results for this competition first
        CompetitionResult.query.filter_by(competition_id=competition_id).delete()
        HoleshotResult.query.filter_by(competition_id=competition_id).delete()
        CompetitionScore.query.filter_by(competition_id=competition_id).delete()
        print(f"DEBUG: Cleared existing results for competition {competition_id}")
        
        # Get all riders based on class and coast (same logic as race_picks_page)
        riders_450 = Rider.query.filter_by(class_name="450cc").all()
        
        # 250cc riders with coast logic
        riders_250_query = Rider.query.filter_by(class_name="250cc")
        if competition.coast_250 == "both":
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == "east") | (Rider.coast_250 == "west") | (Rider.coast_250 == "both")
            )
        elif competition.coast_250 in ("east", "west"):
            riders_250_query = riders_250_query.filter(
                (Rider.coast_250 == competition.coast_250) | (Rider.coast_250 == "both")
            )
        riders_250 = riders_250_query.all()
        
        # Combine all riders
        riders = riders_450 + riders_250
        
        if not riders:
            return jsonify({"error": "No riders found for this competition"}), 400
        
        # Generate random results
        import random
        shuffled_riders = riders.copy()
        random.shuffle(shuffled_riders)
        
        results_created = 0
        for position in range(1, min(21, len(shuffled_riders) + 1)):  # Top 20 for 450cc, all for 250cc
            result = CompetitionResult(
                competition_id=competition_id,
                rider_id=shuffled_riders[position-1].id,
                position=position
            )
            db.session.add(result)
            results_created += 1
        
        db.session.commit()
        
        # Calculate scores after generating results
        calculate_scores(competition_id)
        
        return jsonify({
            "message": f"Generated {results_created} simulated results and calculated scores",
            "results_created": results_created
        })
        
    except Exception as e:
        print(f"Error generating simulated results: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/clear_all_results")
def clear_all_results():
    """Clear all results from all competitions"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Clear all competition results
        CompetitionResult.query.delete()
        HoleshotResult.query.delete()
        
        db.session.commit()
        
        return jsonify({
            "message": "All results cleared successfully",
            "cleared": "competition_results, holeshot_results"
        })
        
    except Exception as e:
        print(f"Error clearing all results: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/clear_all_picks")
def clear_all_picks():
    """Clear all picks from all competitions"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        # Clear all picks
        RacePick.query.delete()
        HoleshotPick.query.delete()
        WildcardPick.query.delete()
        
        db.session.commit()
        
        return jsonify({
            "message": "All picks cleared successfully",
            "cleared": "race_picks, holeshot_picks, wildcard_picks"
        })
        
    except Exception as e:
        print(f"Error clearing all picks: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/motocross_quiz")
def motocross_quiz():
    """Motocross Quiz game"""
    return render_template("motocross_quiz.html")

@app.route("/clear_all_data")
def clear_all_data():
    """Clear all picks and results - full reset"""
    try:
        if not is_admin_user():
            return jsonify({"error": "admin_only"}), 403
        
        print("🧹 Starting full reset - clearing all data...")
        
        # Clear all picks and results
        deleted_race_picks = RacePick.query.delete()
        deleted_holeshot_picks = HoleshotPick.query.delete()
        deleted_wildcard_picks = WildcardPick.query.delete()
        deleted_results = CompetitionResult.query.delete()
        deleted_holeshot_results = HoleshotResult.query.delete()
        # Wildcard results are calculated automatically from user picks vs race results
        deleted_scores = CompetitionScore.query.delete()
        deleted_out_status = CompetitionRiderStatus.query.delete()
        
        # Clear season team riders and reset team points
        deleted_season_team_riders = SeasonTeamRider.query.delete()
        season_teams = SeasonTeam.query.all()
        for team in season_teams:
            team.total_points = 0
        deleted_season_teams = 0  # Keep the teams but clear riders
        
        # Clear league points and scores
        try:
            # Reset league total_points to 0
            db.session.execute(db.text("UPDATE leagues SET total_points = 0"))
        except Exception as e:
            print(f"Warning: Could not reset league points: {e}")
        
        db.session.commit()
        
        print(f"✅ Full reset complete - deleted: {deleted_race_picks} race picks, {deleted_holeshot_picks} holeshot picks, {deleted_wildcard_picks} wildcard picks, {deleted_results} results, {deleted_holeshot_results} holeshot results, {deleted_scores} scores, {deleted_out_status} out status, {deleted_season_team_riders} season team riders, {deleted_season_teams} season teams")
        
        return jsonify({
            "message": "All data cleared successfully - full reset complete",
            "cleared": {
                "race_picks": deleted_race_picks,
                "holeshot_picks": deleted_holeshot_picks,
                "wildcard_picks": deleted_wildcard_picks,
                "results": deleted_results,
                "holeshot_results": deleted_holeshot_results,
                "scores": deleted_scores,
                "out_status": deleted_out_status,
                "season_team_riders": deleted_season_team_riders,
                "season_teams": deleted_season_teams
            }
        })
        
    except Exception as e:
        print(f"Error clearing all data: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

def get_current_time():
    """Get current time - either real or simulated (with time progression)"""
    # Check if we're in simulation mode
    try:
        db.session.rollback()
        result = db.session.execute(db.text("SELECT active, simulated_time, start_time FROM global_simulation WHERE id = 1")).fetchone()
        
        if result and result[0]:  # active is True
            simulated_time_str = result[1] if result[1] else None
            start_time_str = result[2] if result[2] else None
            
            if simulated_time_str and start_time_str:
                # Calculate how much real time has passed since simulation started
                initial_simulated_time = datetime.fromisoformat(simulated_time_str)
                start_time = datetime.fromisoformat(start_time_str)
                real_time_elapsed = datetime.utcnow() - start_time
                
                # Add the elapsed real time to the initial simulated time
                current_simulated_time = initial_simulated_time + real_time_elapsed
                return current_simulated_time
            elif simulated_time_str:
                # Fallback to original simulated time if no start_time
                current_simulated_time = datetime.fromisoformat(simulated_time_str)
                return current_simulated_time
    except Exception as e:
        print(f"DEBUG: Error in get_current_time: {e}")
        db.session.rollback()
    
    # Default to real time
    return datetime.utcnow()

def calculate_smx_qualification_points():
    """Calculate SMX qualification points for all riders based on Supercross and Motocross results"""
    # Get all riders
    riders = Rider.query.all()
    riders_450 = [r for r in riders if r.class_name == '450cc']
    riders_250 = [r for r in riders if r.class_name == '250cc']
    
    smx_points = {}
    
    for rider in riders:
        total_points = 0
        
        # Get Supercross results for this rider (considering coast for 250cc)
        sx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
            CompetitionResult.rider_id == rider.id,
            Series.name.ilike('%supercross%')
        ).all()
        
        # For SMX, 250cc riders get points from both East and West coasts
        # No coast filtering needed for SMX calculation
        
        # Get Motocross results for this rider (considering coast for 250cc)
        mx_results = db.session.query(CompetitionResult).join(Competition).join(Series).filter(
            CompetitionResult.rider_id == rider.id,
            Series.name.ilike('%motocross%')
        ).all()
        
        # For SMX, 250cc riders get points from both East and West coasts
        # No coast filtering needed for SMX calculation
        
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
        
    
    # Sort by class and get top 20 for each class separately
    riders_450 = [(rider_id, data) for rider_id, data in smx_points.items() if data['rider'].class_name == '450cc']
    riders_250 = [(rider_id, data) for rider_id, data in smx_points.items() if data['rider'].class_name == '250cc']
    
    # Sort each class by total points
    riders_450_sorted = sorted(riders_450, key=lambda x: x[1]['total_points'], reverse=True)
    riders_250_sorted = sorted(riders_250, key=lambda x: x[1]['total_points'], reverse=True)
    
    # Get top 20 for each class
    top_20_450 = riders_450_sorted[:20]
    top_20_250 = riders_250_sorted[:20]
    
    # Combine for backward compatibility (but now properly separated)
    top_20 = top_20_450 + top_20_250
    
    
    return top_20

def get_series_leaders():
    """Get current leaders for each series (450cc, 250cc East, 250cc West)"""
    
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
    # Rollback any existing transaction to avoid "aborted transaction" errors
    db.session.rollback()
    
    # Handle both Competition objects and competition IDs
    if isinstance(competition, int):
        # If it's an ID, fetch the competition object
        competition_obj = Competition.query.get(competition)
        if not competition_obj:
            return False
        competition_name = f"ID {competition}"
        competition_id = competition
    else:
        # If it's a Competition object
        competition_obj = competition
        competition_name = competition.name if hasattr(competition, 'name') else f"ID {competition.id}"
        competition_id = competition.id
    
    # Check if we're in simulation mode (use only global database state for consistency)
    simulation_active = False
    
    try:
        # Rollback any existing transaction first
        db.session.rollback()
        
        result = db.session.execute(db.text("SELECT active FROM global_simulation WHERE id = 1")).fetchone()
        simulation_active = result and result[0] if result else False
    except Exception as e:
        # Rollback and fallback to app globals if database table doesn't exist
        db.session.rollback()
        simulation_active = hasattr(app, 'global_simulation_active') and app.global_simulation_active
    
    if simulation_active:
        # Use the same logic as test_countdown for consistency
        # Get the scenario from global database state or use default
        try:
            result = db.session.execute(db.text("SELECT scenario FROM global_simulation WHERE id = 1")).fetchone()
            scenario = result[0] if result and result[0] else 'race_in_3h'
        except Exception as e:
            scenario = session.get('test_scenario', 'race_in_3h')
        
        # Get current time first
        current_time = get_current_time()
        
        # Use the same scenario-based logic as race_countdown
        if scenario and scenario.startswith('active_race_'):
            # Get the initial simulated time when simulation started
            try:
                result = db.session.execute(db.text("SELECT simulated_time FROM global_simulation WHERE id = 1")).fetchone()
                simulated_time_str = result[0] if result and result[0] else current_time.isoformat()
                initial_simulated_time = datetime.fromisoformat(simulated_time_str)
            except Exception as e:
                initial_simulated_time = current_time
            
            # Use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or initial_simulated_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                # Fallback to 11 AM
                fake_race_base_time = initial_simulated_time.replace(hour=11, minute=0, second=0, microsecond=0)
                race_datetime = fake_race_base_time
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_3h':
            # Check if this is the active race
            try:
                result = db.session.execute(db.text("SELECT active_race_id FROM global_simulation WHERE id = 1")).fetchone()
                active_race_id = result[0] if result and result[0] else None
                
                if active_race_id == competition_id:
                    # This is the active race - use simulated time
                    print(f"DEBUG: is_picks_locked - {competition_name} is the ACTIVE race (ID: {competition_id})")
                    if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                        # Use the competition's actual start time with simulated date
                        race_date = current_time.date()
                        race_datetime = datetime.combine(race_date, competition_obj.start_time)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                    else:
                        # Fallback to 3 hours from simulated time
                        race_datetime = current_time + timedelta(hours=3)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                else:
                    # This is not the active race - use real event date
                    print(f"DEBUG: is_picks_locked - {competition_name} is NOT the active race (ID: {competition_id}, active: {active_race_id})")
                    if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                        race_date = competition_obj.event_date or current_time.date()
                        race_datetime = datetime.combine(race_date, competition_obj.start_time)
                        deadline_datetime = race_datetime - timedelta(hours=2)
                    else:
                        # Fallback to 3 hours from now
                        race_datetime = current_time + timedelta(hours=3)
                        deadline_datetime = race_datetime - timedelta(hours=2)
            except Exception as e:
                # Fallback to original logic
                if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                    race_date = competition_obj.event_date or current_time.date()
                    race_datetime = datetime.combine(race_date, competition_obj.start_time)
                    deadline_datetime = race_datetime - timedelta(hours=2)
                else:
                    race_datetime = current_time + timedelta(hours=3)
                    deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_1h':
            # Race in 1 hour - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(hours=1)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_30m':
            # Race in 30 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=30)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_10m':
            # Race in 10 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=10)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_5m':
            # Race in 5 minutes - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=5)
                deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_in_1m':
            # Race in 1 minute - use actual competition start time if available
            if hasattr(competition_obj, 'start_time') and competition_obj.start_time:
                race_date = competition_obj.event_date or current_time.date()
                race_datetime = datetime.combine(race_date, competition_obj.start_time)
                deadline_datetime = race_datetime - timedelta(hours=2)
            else:
                race_datetime = current_time + timedelta(minutes=1)
            deadline_datetime = race_datetime - timedelta(hours=2)
        elif scenario == 'race_started':
            # Race has started
            race_datetime = current_time - timedelta(minutes=1)
            deadline_datetime = race_datetime - timedelta(hours=2)
        else:
            # Default to race in 3 hours
            race_datetime = current_time + timedelta(hours=3)
            deadline_datetime = race_datetime - timedelta(hours=2)
        
        # Calculate time differences using simulated time (same as countdown)
        # Get the current simulated time from the same source as countdown
        try:
            result = db.session.execute(db.text("SELECT simulated_time FROM global_simulation WHERE id = 1")).fetchone()
            current_simulated_time_str = result[0] if result and result[0] else current_time.isoformat()
            current_simulated_time = datetime.fromisoformat(current_simulated_time_str)
        except Exception as e:
            current_simulated_time = current_time
        
        time_to_deadline = deadline_datetime - current_simulated_time
        
        # Check if picks are locked (2 hours before race)
        # If time_to_deadline is negative, deadline has passed and picks are locked
        picks_locked = time_to_deadline.total_seconds() <= 0
    else:
        # Check if picks are locked (2 hours before race)
        race_date = competition_obj.event_date
        
        # Use start_time from database if available, otherwise default to 8 PM
        if competition_obj.start_time:
            race_datetime_local = datetime.combine(race_date, competition_obj.start_time)
        else:
            race_time_str = "20:00"  # 8pm local time default
            race_hour, race_minute = map(int, race_time_str.split(':'))
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
    
    return picks_locked

def is_season_active():
    """Check if the season is active (has active races or competitions with results)"""
    try:
        # Check if there's an active race set
        result = db.session.execute(db.text("SELECT active_race_id FROM global_simulation WHERE id = 1")).fetchone()
        if result and result[0]:
            print(f"DEBUG: is_season_active - Active race found: {result[0]}")
            return True
        
        # Check if there are any competitions with results (indicating season has started)
        competitions_with_results = db.session.execute(db.text("""
            SELECT COUNT(*) FROM competitions c 
            WHERE EXISTS (SELECT 1 FROM competition_results cr WHERE cr.competition_id = c.id)
        """)).fetchone()
        
        if competitions_with_results and competitions_with_results[0] > 0:
            print(f"DEBUG: is_season_active - Found {competitions_with_results[0]} competitions with results")
            return True
        
        print(f"DEBUG: is_season_active - No active race or results found, season not active")
        return False
        
    except Exception as e:
        print(f"DEBUG: Exception in is_season_active: {e}")
        return False

# SUPER SIMPLE CSV PARSING - This WILL work!
def parse_csv_simple(csv_path, class_name):
    import csv
    riders = []
    print(f"🔥 SIMPLE PARSER - Starting to parse {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        for row_num, row in enumerate(reader, 1):
            print(f"🔥 ROW {row_num}: {row}")
            
            # Skip first 7 rows (headers)
            if row_num <= 7:
                print(f"🔥 SKIPPING HEADER {row_num}")
                continue
            
            # Check if row has content
            if not row or len(row) == 0:
                print(f"🔥 EMPTY ROW {row_num}")
                continue
                
            # Get the text from first column
            text = row[0].strip().strip('"')
            print(f"🔥 TEXT: {text}")
            
            # Check if it starts with a number
            if text and text[0].isdigit():
                print(f"🔥 FOUND RIDER ROW: {text}")
                
                # Split by spaces
                parts = text.split()
                print(f"🔥 PARTS: {parts}")
                
                if len(parts) >= 5:
                    # Find bike brand
                    bike_idx = 2
                    for i, part in enumerate(parts[2:], 2):
                        if part in ['KTM', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'Husqvarna', 'GasGas', 'Beta', 'Triumph']:
                            bike_idx = i
                            break
                    
                    if bike_idx < len(parts):
                        name = ' '.join(parts[1:bike_idx])
                        bike = parts[bike_idx]
                        hometown = ' '.join(parts[bike_idx+1:-1])
                        team = parts[-1]
                        
                        rider_data = {
                            'number': int(parts[0]),
                            'name': name.strip(),
                            'bike_brand': bike,
                            'hometown': hometown.strip(),
                            'team': team.strip(),
                            'class': class_name
                        }
                        riders.append(rider_data)
                        print(f"🔥 ADDED RIDER: {rider_data['number']} - {rider_data['name']}")
                    else:
                        print(f"🔥 NO BIKE BRAND FOUND")
                else:
                    print(f"🔥 NOT ENOUGH PARTS")
            else:
                print(f"🔥 NOT A RIDER ROW")
    
    print(f"🔥 TOTAL RIDERS FOUND: {len(riders)}")
    return riders

if __name__ == "__main__":
    # Production vs Development configuration
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    app.run(host=host, port=port, debug=debug_mode)