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

# Flask app & config
app = Flask(__name__)

# Configuration from environment variables
app.secret_key = os.getenv('SECRET_KEY', 'din_hemliga_nyckel_har_change_in_production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default

# Uploads
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads", "leagues")
os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Database
db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Competition(db.Model):
    __tablename__ = "competitions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    coast_250 = db.Column(db.String(10), nullable=True)
    series = db.Column(db.String(10), nullable=False, default='SX')
    point_multiplier = db.Column(db.Float, nullable=False, default=1.0)

class Rider(db.Model):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(10), nullable=False)
    bike_brand = db.Column(db.String(50), nullable=True)
    price = db.Column(db.Integer, nullable=False, default=50)

class SeasonTeam(db.Model):
    __tablename__ = "season_teams"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    total_points = db.Column(db.Integer, default=0)

class SeasonTeamRider(db.Model):
    __tablename__ = "season_team_riders"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('season_teams.id'), nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=False)


# Helper functions
def get_today():
    try:
        row = db.session.execute(db.text("SELECT value FROM sim_date LIMIT 1")).first()
        if row and row[0]:
            return datetime.strptime(row[0], "%Y-%m-%d").date()
    except Exception:
        pass
    return date.today()

def create_test_data():
    with app.app_context():
        # Create test users
        if not User.query.filter_by(username='test').first():
            test_user = User(
                username='test',
                password_hash=generate_password_hash('password'),
                email='test@example.com'
            )
            db.session.add(test_user)
            print("Created test user")
        
        if not User.query.filter_by(username='test2').first():
            test2_user = User(
                username='test2',
                password_hash=generate_password_hash('password'),
                email='test2@example.com'
            )
            db.session.add(test2_user)
            print("Created test2 user")
        
        # Create competitions
        if Competition.query.count() == 0:
            competitions = [
                {'name': 'Anaheim 1', 'event_date': '2025-01-04', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
                {'name': 'San Diego', 'event_date': '2025-01-11', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
                {'name': 'Anaheim 2', 'event_date': '2025-01-18', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
                {'name': 'Houston', 'event_date': '2025-01-25', 'coast_250': 'west', 'series': 'SX', 'point_multiplier': 1.0},
                {'name': 'Tampa', 'event_date': '2025-02-01', 'coast_250': 'east', 'series': 'SX', 'point_multiplier': 1.0}
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
            print("Created competitions")
        
        # Create riders
        if Rider.query.count() == 0:
            riders_450 = [
                {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'price': 100},
                {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'price': 95},
                {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'price': 90},
                {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'price': 85},
                {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'price': 80}
            ]
            
            riders_250 = [
                {'name': 'Jett Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'price': 100},
                {'name': 'Hunter Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'price': 95},
                {'name': 'RJ Hampshire', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'price': 90},
                {'name': 'Max Vohland', 'class_name': '250cc', 'bike_brand': 'KTM', 'price': 85},
                {'name': 'Cameron McAdoo', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'price': 80}
            ]
            
            all_riders = riders_450 + riders_250
            for rider_data in all_riders:
                rider = Rider(
                    name=rider_data['name'],
                    class_name=rider_data['class_name'],
                    bike_brand=rider_data['bike_brand'],
                    price=rider_data['price']
                )
                db.session.add(rider)
            print("Created riders")
        
        # Create default sim_date
        
        db.session.commit()
        print("Database initialization complete!")

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    today = get_today()
    
    # Get upcoming race
    upcoming_race = Competition.query.filter(Competition.event_date >= today).order_by(Competition.event_date).first()
    
    # Get user's season team
    my_team = SeasonTeam.query.filter_by(user_id=session['user_id']).first()
    team_riders = []
    if my_team:
        team_riders = db.session.query(Rider).join(SeasonTeamRider).filter(SeasonTeamRider.team_id == my_team.id).all()
    
    return render_template('index.html', 
                         username=user.username,
                         upcoming_race=upcoming_race,
                         my_team=my_team,
                         team_riders=team_riders)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        
        flash('Felaktigt användarnamn eller lösenord', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register')
def register():
    return f"""
    <h1>Registrering</h1>
    <p>För att registrera dig, kontakta administratören.</p>
    <p><a href="/login">Tillbaka till inloggning</a></p>
    """

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.username != 'test':
        flash('Du har inte behörighet att komma åt denna sida', 'error')
        return redirect(url_for('index'))
    
    competitions = Competition.query.order_by(Competition.event_date).all()
    riders = Rider.query.order_by(Rider.class_name, Rider.name).all()
    today = get_today()
    
    return render_template('admin.html', 
                         username=user.username,
                         competitions=competitions,
                         riders=riders,
                         today=today)

@app.route('/season_team')
def season_team():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    my_team = SeasonTeam.query.filter_by(user_id=session['user_id']).first()
    team_riders = []
    if my_team:
        team_riders = db.session.query(Rider).join(SeasonTeamRider).filter(SeasonTeamRider.team_id == my_team.id).all()
    
    return render_template('season_team.html', 
                         username=user.username,
                         my_team=my_team,
                         team_riders=team_riders)

@app.route('/season_team_builder')
def season_team_builder():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    my_team = SeasonTeam.query.filter_by(user_id=session['user_id']).first()
    team_riders = []
    if my_team:
        team_riders = db.session.query(Rider).join(SeasonTeamRider).filter(SeasonTeamRider.team_id == my_team.id).all()
    
    all_riders = Rider.query.order_by(Rider.class_name, Rider.name).all()
    
    return render_template('season_team_builder.html',
                         username=user.username,
                         my_team=my_team,
                         team_riders=team_riders,
                         all_riders=all_riders,
                         riders=all_riders)

@app.route('/race_picks')
def race_picks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    today = get_today()
    upcoming_race = Competition.query.filter(Competition.event_date >= today).order_by(Competition.event_date).first()
    
    if not upcoming_race:
        flash('Ingen kommande tävling hittades', 'error')
        return redirect(url_for('index'))
    
    riders_450 = Rider.query.filter_by(class_name='450cc').order_by(Rider.name).all()
    riders_250 = Rider.query.filter_by(class_name='250cc').order_by(Rider.name).all()
    
    return render_template('race_picks.html',
                         username=user.username,
                         upcoming_race=upcoming_race,
                         riders_450=riders_450,
                         riders_250=riders_250)

@app.route('/my_scores')
def my_scores():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    my_team = SeasonTeam.query.filter_by(user_id=session['user_id']).first()
    
    # Create placeholder data for the template
    total = my_team.total_points if my_team else 0
    best = {'name': '—', 'points': 0}  # Placeholder
    history = []  # Placeholder - no race history yet
    
    return render_template('user_stats.html',
                         username=user.username,
                         my_team=my_team,
                         total=total,
                         best=best,
                         history=history)

# API Routes
@app.route('/get_season_leaderboard')
def get_season_leaderboard():
    teams = SeasonTeam.query.order_by(SeasonTeam.total_points.desc()).all()
    leaderboard = []
    
    for team in teams:
        user = User.query.get(team.user_id)
        leaderboard.append({
            'username': user.username,
            'team_name': team.team_name,
            'total_points': team.total_points,
            'delta': 0  # Placeholder
        })
    
    return jsonify(leaderboard)

# Initialize database for Render
with app.app_context():
    db.create_all()
    create_test_data()

if __name__ == "__main__":
    # Production vs Development configuration
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    app.run(host=host, port=port, debug=debug_mode)
