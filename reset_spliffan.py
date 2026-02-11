#!/usr/bin/env python3
"""
Reset spliffan user password - run: python reset_spliffan.py
"""
import sys
sys.path.append('.')

from main import app, db, User
from werkzeug.security import generate_password_hash

def reset_spliffan():
    with app.app_context():
        try:
            print("🔄 Resetting spliffan user...")
            
            # Check if spliffan exists
            spliffan = User.query.filter_by(username='spliffan').first()
            
            if spliffan:
                # Update password
                spliffan.password_hash = generate_password_hash('password')
                # Make sure is_admin is set
                try:
                    if hasattr(spliffan, 'is_admin'):
                        spliffan.is_admin = True
                except:
                    pass
                db.session.commit()
                print(f"✅ Updated spliffan user (ID: {spliffan.id})")
                print("   Username: spliffan")
                print("   Password: password")
                print("   Is Admin: True")
            else:
                # Create spliffan user
                spliffan = User(
                    username='spliffan',
                    password_hash=generate_password_hash('password'),
                    email='spliffan@example.com'
                )
                try:
                    spliffan.is_admin = True
                except:
                    pass
                db.session.add(spliffan)
                db.session.commit()
                print(f"✅ Created spliffan user (ID: {spliffan.id})")
                print("   Username: spliffan")
                print("   Password: password")
                print("   Is Admin: True")
            
            # Also check/create test user
            test_user = User.query.filter_by(username='test').first()
            if test_user:
                test_user.password_hash = generate_password_hash('password')
                try:
                    test_user.is_admin = True
                except:
                    pass
                db.session.commit()
                print(f"✅ Updated test user (ID: {test_user.id})")
                print("   Username: test")
                print("   Password: password")
            else:
                test_user = User(
                    username='test',
                    password_hash=generate_password_hash('password'),
                    email='test@example.com'
                )
                try:
                    test_user.is_admin = True
                except:
                    pass
                db.session.add(test_user)
                db.session.commit()
                print(f"✅ Created test user (ID: {test_user.id})")
                print("   Username: test")
                print("   Password: password")
            
            print("\n🎉 Done! You can now login with:")
            print("   Username: spliffan")
            print("   Password: password")
            print("   OR")
            print("   Username: test")
            print("   Password: password")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = reset_spliffan()
    sys.exit(0 if success else 1)

