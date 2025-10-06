#!/usr/bin/env python3
"""
Reset Database Script - Run this whenever the database has issues
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Competition, Rider, SimDate
from werkzeug.security import generate_password_hash
from datetime import datetime

def reset_database():
    """Completely reset and recreate the database with all data"""
    with app.app_context():
        print("🗑️  Dropping all tables...")
        db.drop_all()
        
        print("🔨 Creating all tables...")
        db.create_all()
        
        print("👤 Creating test user...")
        test_user = User(
            username='test',
            password_hash=generate_password_hash('password'),
            email='test@example.com'
        )
        db.session.add(test_user)
        
        print("🏁 Creating competitions...")
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
        
        print("🏍️  Creating riders...")
        riders_450 = [
            {'name': 'Eli Tomac', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'price': 100},
            {'name': 'Cooper Webb', 'class_name': '450cc', 'bike_brand': 'KTM', 'price': 95},
            {'name': 'Chase Sexton', 'class_name': '450cc', 'bike_brand': 'Honda', 'price': 90},
            {'name': 'Jason Anderson', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'price': 85},
            {'name': 'Ken Roczen', 'class_name': '450cc', 'bike_brand': 'Suzuki', 'price': 80},
            {'name': 'Justin Barcia', 'class_name': '450cc', 'bike_brand': 'GasGas', 'price': 75},
            {'name': 'Aaron Plessinger', 'class_name': '450cc', 'bike_brand': 'KTM', 'price': 70},
            {'name': 'Malcolm Stewart', 'class_name': '450cc', 'bike_brand': 'Husqvarna', 'price': 65},
            {'name': 'Dylan Ferrandis', 'class_name': '450cc', 'bike_brand': 'Yamaha', 'price': 60},
            {'name': 'Adam Cianciarulo', 'class_name': '450cc', 'bike_brand': 'Kawasaki', 'price': 55}
        ]
        
        riders_250 = [
            {'name': 'Jett Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'price': 100},
            {'name': 'Hunter Lawrence', 'class_name': '250cc', 'bike_brand': 'Honda', 'price': 95},
            {'name': 'RJ Hampshire', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'price': 90},
            {'name': 'Max Vohland', 'class_name': '250cc', 'bike_brand': 'KTM', 'price': 85},
            {'name': 'Cameron McAdoo', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'price': 80},
            {'name': 'Seth Hammaker', 'class_name': '250cc', 'bike_brand': 'Kawasaki', 'price': 75},
            {'name': 'Pierce Brown', 'class_name': '250cc', 'bike_brand': 'GasGas', 'price': 70},
            {'name': 'Jalek Swoll', 'class_name': '250cc', 'bike_brand': 'Husqvarna', 'price': 65},
            {'name': 'Stilez Robertson', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'price': 60},
            {'name': 'Levi Kitchen', 'class_name': '250cc', 'bike_brand': 'Yamaha', 'price': 55}
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
        
        print("📅 Creating sim date...")
        sim_date = SimDate(value='2025-10-06')
        db.session.add(sim_date)
        
        print("💾 Saving to database...")
        db.session.commit()
        
        print("✅ Database reset complete!")
        print(f"   - Users: {User.query.count()}")
        print(f"   - Competitions: {Competition.query.count()}")
        print(f"   - Riders: {Rider.query.count()}")
        print(f"   - Sim Date: {SimDate.query.first().value if SimDate.query.first() else 'None'}")
        print("\n🚀 You can now start the app with: python app.py")

if __name__ == "__main__":
    reset_database()
