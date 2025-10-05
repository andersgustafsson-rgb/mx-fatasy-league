#!/usr/bin/env python3
from app import app, db, User, SeasonTeam, Competition, Rider
from werkzeug.security import generate_password_hash

def test_database():
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Check if test user exists
        test_user = User.query.filter_by(username="test").first()
        if not test_user:
            print("Creating test user...")
            test_user = User(username="test", password_hash=generate_password_hash("password"))
            db.session.add(test_user)
            db.session.commit()
        
        # Check if test user has a season team
        team = SeasonTeam.query.filter_by(user_id=test_user.id).first()
        if not team:
            print("Creating test season team...")
            team = SeasonTeam(user_id=test_user.id, team_name="Test Team", total_points=150)
            db.session.add(team)
            db.session.commit()
        
        # Check data
        users = User.query.all()
        teams = SeasonTeam.query.all()
        
        print(f"Users: {[(u.username, u.id) for u in users]}")
        print(f"SeasonTeams: {[(t.user_id, t.team_name, t.total_points) for t in teams]}")
        
        # Test the API endpoint
        from flask import jsonify
        rows = (
            db.session.query(User.username, SeasonTeam.team_name, SeasonTeam.total_points)
            .outerjoin(SeasonTeam, SeasonTeam.user_id == User.id)
            .order_by(SeasonTeam.total_points.desc().nullslast())
            .all()
        )
        
        result = []
        for i, (username, team_name, total_points) in enumerate(rows, 1):
            result.append({
                "username": username,
                "team_name": team_name or None,
                "total_points": total_points or 0,
                "rank": i,
                "delta": 0
            })
        
        print(f"API result: {result}")

if __name__ == "__main__":
    test_database()
