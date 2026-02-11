#!/usr/bin/env python3
"""
Setup local development to use production database (read-only mode)
WARNING: Make sure you're careful not to modify production data!
"""
import os
from dotenv import load_dotenv

load_dotenv()

def setup_local_production():
    """Setup .env file to connect to production database locally"""
    
    production_db_url = os.getenv('DATABASE_URL')
    
    if not production_db_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("\n📋 To connect to production database locally:")
        print("   1. Go to Render Dashboard → Your PostgreSQL database")
        print("   2. Copy the 'Internal Database URL' or 'Connection String'")
        print("   3. Add it to your .env file as:")
        print("      DATABASE_URL=postgresql://user:pass@host:port/dbname")
        print("\n⚠️  WARNING: This will connect to PRODUCTION database!")
        print("   Be very careful not to modify production data!")
        return False
    
    if 'postgresql' not in production_db_url:
        print("❌ DATABASE_URL is not a PostgreSQL database")
        return False
    
    print("✅ Production DATABASE_URL found!")
    print(f"   Host: {production_db_url.split('@')[1].split('/')[0] if '@' in production_db_url else 'unknown'}")
    print("\n⚠️  WARNING: Local app will now connect to PRODUCTION database!")
    print("   Make sure you:")
    print("   - Only test read operations")
    print("   - Don't modify production data")
    print("   - Use a separate .env file for local testing")
    print("\n💡 Tip: Create a .env.local file with production DATABASE_URL")
    print("   and use: python -m dotenv -f .env.local run python main.py")
    
    return True

if __name__ == "__main__":
    setup_local_production()

