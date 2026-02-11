#!/usr/bin/env python3
"""
Migration script to add rider_points column to competition_results table
Run this script: python run_migration_local.py
"""
import sys
sys.path.append('.')

from main import app, db

def run_migration():
    with app.app_context():
        try:
            print("🔄 Starting migration to add rider_points column...")
            
            # Check if column already exists (for SQLite)
            try:
                result = db.session.execute(db.text("PRAGMA table_info(competition_results)"))
                cols = [row[1] for row in result.fetchall()]
                if 'rider_points' in cols:
                    print("✅ rider_points column already exists!")
                    return True
            except:
                # Not SQLite, or PRAGMA not supported - try to add anyway
                pass
            
            # Add rider_points column to competition_results table for WSX manual entry
            print("➕ Adding rider_points column...")
            db.session.execute(db.text("ALTER TABLE competition_results ADD COLUMN rider_points INTEGER"))
            
            db.session.commit()
            print("✅ Migration completed successfully! rider_points column added to competition_results table.")
            
        except Exception as e:
            # Check if error is "duplicate column" - that's okay
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✅ rider_points column already exists (duplicate column error is OK)")
                db.session.rollback()
                return True
            
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

