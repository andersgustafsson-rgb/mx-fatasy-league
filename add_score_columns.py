#!/usr/bin/env python3
"""
Migration script to add separate score columns to competition_scores table
"""
import sys
sys.path.append('.')
from main import app, db

def run_migration():
    with app.app_context():
        try:
            print("🔄 Starting migration to add score columns...")
            
            # Check if columns already exist
            result = db.session.execute(db.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'competition_scores' 
                AND column_name IN ('race_points', 'holeshot_points', 'wildcard_points')
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            print(f"📋 Existing columns: {existing_columns}")
            
            # Add missing columns
            if 'race_points' not in existing_columns:
                print("➕ Adding race_points column...")
                db.session.execute(db.text('ALTER TABLE competition_scores ADD COLUMN race_points INTEGER DEFAULT 0'))
            else:
                print("✅ race_points column already exists")
                
            if 'holeshot_points' not in existing_columns:
                print("➕ Adding holeshot_points column...")
                db.session.execute(db.text('ALTER TABLE competition_scores ADD COLUMN holeshot_points INTEGER DEFAULT 0'))
            else:
                print("✅ holeshot_points column already exists")
                
            if 'wildcard_points' not in existing_columns:
                print("➕ Adding wildcard_points column...")
                db.session.execute(db.text('ALTER TABLE competition_scores ADD COLUMN wildcard_points INTEGER DEFAULT 0'))
            else:
                print("✅ wildcard_points column already exists")
            
            db.session.commit()
            print("🎉 Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
