#!/usr/bin/env python3
"""
Backup production PostgreSQL database to local SQLite for testing
Run this script to sync production data locally
"""
import sys
import os
sys.path.append('.')

from main import app, db
from dotenv import load_dotenv
import subprocess
from datetime import datetime

load_dotenv()

def backup_production_to_local():
    """Backup production PostgreSQL database to local SQLite"""
    
    production_db_url = os.getenv('DATABASE_URL')
    
    if not production_db_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("   Set DATABASE_URL in .env file with production database URL")
        return False
    
    if 'postgresql' not in production_db_url:
        print("❌ DATABASE_URL is not a PostgreSQL database")
        print(f"   Current: {production_db_url}")
        return False
    
    print("🔄 Backing up production database...")
    print(f"   Source: {production_db_url.split('@')[1] if '@' in production_db_url else 'production'}")
    
    try:
        # Parse DATABASE_URL to extract connection info
        # Format: postgresql://user:password@host:port/database
        import urllib.parse
        parsed = urllib.parse.urlparse(production_db_url)
        
        # Use pg_dump to export PostgreSQL database
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = f"backups/production_backup_{timestamp}.sql"
        
        os.makedirs("backups", exist_ok=True)
        
        # Build pg_dump command
        # Note: pg_dump needs to be installed locally
        cmd = [
            'pg_dump',
            '--no-owner',
            '--no-acl',
            '--clean',
            '--if-exists',
            production_db_url,
            '-f', dump_file
        ]
        
        print(f"📦 Running pg_dump...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ pg_dump failed: {result.stderr}")
            print("\n💡 Alternative: Use Render dashboard to download database backup")
            print("   1. Go to Render Dashboard → Your PostgreSQL database")
            print("   2. Click 'Download' or 'Export'")
            print("   3. Save the .sql file")
            return False
        
        print(f"✅ Backup created: {dump_file}")
        print(f"   Size: {os.path.getsize(dump_file) / 1024 / 1024:.2f} MB")
        
        print("\n⚠️  Note: To import this into SQLite, you'll need to:")
        print("   1. Convert PostgreSQL dump to SQLite format, or")
        print("   2. Connect locally to the same PostgreSQL database")
        print("\n   For now, use the production DATABASE_URL in your .env file")
        print("   to connect directly to production database (be careful!)")
        
        return True
        
    except FileNotFoundError:
        print("❌ pg_dump not found. Install PostgreSQL client tools:")
        print("   Windows: Download from https://www.postgresql.org/download/windows/")
        print("   Or use Render dashboard to download backup manually")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = backup_production_to_local()
    sys.exit(0 if success else 1)

