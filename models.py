from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

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
    admin_message = db.Column(db.Text, nullable=True)  # Admin announcement message
    admin_message_priority = db.Column(db.String(20), nullable=True, default='info')  # 'important' or 'info'
    admin_message_active = db.Column(db.Boolean, default=False)  # Whether announcement is active

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
    coast_250 = db.Column(db.String(10), nullable=True)
    timezone = db.Column(db.String(50), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    phase = db.Column(db.String(20), nullable=True)
    is_qualifying = db.Column(db.Boolean, default=False)
    series_ref = db.relationship('Series', backref='competitions', lazy=True)
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
    @property
    def start_time(self):
        if not self.has_start_time_column():
            return None
        try:
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
    class_name = db.Column("class", db.String(10), nullable=False)
    classes = db.Column(db.String(50), nullable=True)
    rider_number = db.Column(db.Integer)
    bike_brand = db.Column(db.String(50))
    image_url = db.Column(db.String(200))
    price = db.Column(db.Integer, nullable=False)
    coast_250 = db.Column(db.String(10), nullable=True)
    series_participation = db.Column(db.String(50), default='all')
    smx_qualified = db.Column(db.Boolean, default=False)
    smx_seed_points = db.Column(db.Integer, default=0)
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
    image_url = db.Column(db.String(200))
    image_data = db.Column(db.Text)
    image_mime_type = db.Column(db.String(50))
    description = db.Column(db.String(255))
    is_public = db.Column(db.Boolean, default=True)
    total_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    message = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('league_id', 'user_id', name='uq_league_request'),)

class BulletinPost(db.Model):
    __tablename__ = "bulletin_posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), default="general")
    parent_id = db.Column(db.Integer, db.ForeignKey("bulletin_posts.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    user = db.relationship("User", backref="bulletin_posts")
    parent = db.relationship("BulletinPost", remote_side=[id], backref="replies")
    reactions = db.relationship("BulletinReaction", backref="post", cascade="all, delete-orphan")

class BulletinReaction(db.Model):
    __tablename__ = "bulletin_reactions"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("bulletin_posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="bulletin_reactions")
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
    __table_args__ = (
        db.Index('idx_leaderboard_history_user_created', 'user_id', 'created_at'),
    )

class CompetitionRiderStatus(db.Model):
    __tablename__ = "competition_rider_status"
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="OUT")
    __table_args__ = (
        db.UniqueConstraint("competition_id", "rider_id", name="uq_comp_rider"),
    )

class CompetitionResult(db.Model):
    __tablename__ = "competition_results"
    result_id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("competitions.id"))
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    position = db.Column(db.Integer, nullable=False)
    rider_points = db.Column(db.Integer, nullable=True)  # Total points for WSX riders (manual entry)
    competition = db.relationship('Competition', backref='results', lazy=True)
    rider = db.relationship('Rider', backref='results', lazy=True)
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
    image_url = db.Column(db.String(300), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    competition = db.relationship("Competition",
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
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class FinishedSeriesStats(db.Model):
    """Archive table for finished series statistics"""
    __tablename__ = "finished_series_stats"
    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey("series.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    total_points = db.Column(db.Integer, nullable=False, default=0)
    race_points = db.Column(db.Integer, nullable=False, default=0)
    holeshot_points = db.Column(db.Integer, nullable=False, default=0)
    wildcard_points = db.Column(db.Integer, nullable=False, default=0)
    competitions_participated = db.Column(db.Integer, nullable=False, default=0)
    archived_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        db.UniqueConstraint('series_id', 'user_id', name='uq_finished_series_user'),
        db.Index('idx_finished_series_stats_series', 'series_id'),
        db.Index('idx_finished_series_stats_user', 'user_id'),
    )