#!/usr/bin/env python3
"""Check users in database"""
import sys
sys.path.append('.')

from main import app, db, User
from werkzeug.security import check_password_hash

def check_users():
    with app.app_context():
        try:
            print("📋 Checking users in database...\n")
            
            users = User.query.all()
            
            if not users:
                print("❌ No users found in database!")
                return False
            
            print(f"Found {len(users)} user(s):\n")
            
            for user in users:
                print(f"  User ID: {user.id}")
                print(f"  Username: {user.username}")
                print(f"  Email: {getattr(user, 'email', 'N/A')}")
                print(f"  Is Admin: {getattr(user, 'is_admin', 'N/A')}")
                
                # Test password
                test_passwords = ['password', 'test123', 'spliffan']
                for pwd in test_passwords:
                    if check_password_hash(user.password_hash, pwd):
                        print(f"  ✅ Password matches: '{pwd}'")
                        break
                else:
                    print(f"  ❌ Password doesn't match: password, test123, spliffan")
                
                print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    check_users()

