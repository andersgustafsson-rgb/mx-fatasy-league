#!/usr/bin/env python3
import os
import sys

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    from app import app, db, User, SeasonTeam
    from werkzeug.security import generate_password_hash
    
    print("Starting database debug...")
    
    with app.app_context():
        # Check if database exists
        print("Creating tables...")
        db.create_all()
        
        # Check users
        users = User.query.all()
        print(f"Found {len(users)} users")
        for u in users:
            print(f"  - {u.username} (ID: {u.id})")
        
        # Check season teams
        teams = SeasonTeam.query.all()
        print(f"Found {len(teams)} season teams")
        for t in teams:
            print(f"  - User {t.user_id}: {t.team_name} ({t.total_points} points)")
        
        # If no data, create some
        if len(users) == 0:
            print("Creating test user...")
            test_user = User(username="test", password_hash=generate_password_hash("password"))
            db.session.add(test_user)
            db.session.commit()
            print("Test user created")
        
        if len(teams) == 0:
            print("Creating test season team...")
            test_user = User.query.filter_by(username="test").first()
            if test_user:
                team = SeasonTeam(user_id=test_user.id, team_name="Test Team", total_points=150)
                db.session.add(team)
                db.session.commit()
                print("Test season team created")
        
        # Test the API query
        print("\nTesting API query...")
        rows = (
            db.session.query(User.username, SeasonTeam.team_name, SeasonTeam.total_points)
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .order_by(SeasonTeam.total_points.desc().nullslast())
            .all()
        )
        print(f"API query returned {len(rows)} rows:")
        for row in rows:
            print(f"  - {row}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
