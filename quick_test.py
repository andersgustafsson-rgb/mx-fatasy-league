from app import app, db, User, SeasonTeam
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create tables if they don't exist
    db.create_all()
    
    # Create test user if not exists
    test_user = User.query.filter_by(username="test").first()
    if not test_user:
        test_user = User(username="test", password_hash=generate_password_hash("password"))
        db.session.add(test_user)
        db.session.commit()
        print("Created test user")
    else:
        print("Test user already exists")
    
    # Create season team for test user
    team = SeasonTeam.query.filter_by(user_id=test_user.id).first()
    if not team:
        team = SeasonTeam(user_id=test_user.id, team_name="Test Team", total_points=150)
        db.session.add(team)
        db.session.commit()
        print("Created season team")
    else:
        print("Season team already exists")
    
    # Check what we have
    users = User.query.all()
    teams = SeasonTeam.query.all()
    print(f"Users: {len(users)}")
    print(f"Teams: {len(teams)}")
    
    # Test the API query
    rows = (
        db.session.query(User.username, SeasonTeam.team_name, SeasonTeam.total_points)
        .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
        .order_by(SeasonTeam.total_points.desc().nullslast())
        .all()
    )
    print(f"API query result: {rows}")
