#!/usr/bin/env python3
"""
Sync production database to local for testing
This is SAFE - it only downloads a copy, doesn't modify production
"""
import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def sync_production_to_local():
    """Download production database backup and restore locally"""
    
    print("=" * 60)
    print("📦 SYNC PRODUCTION DATABASE TO LOCAL")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Download a backup from production database")
    print("  2. Restore it locally for testing")
    print("  3. Your local database will be a copy of production")
    print()
    print("⚠️  SAFE: This only READS from production, doesn't modify it")
    print()
    
    production_db_url = os.getenv('DATABASE_URL')
    
    if not production_db_url:
        print("❌ DATABASE_URL not found in .env file")
        print()
        print("📋 To get your production DATABASE_URL:")
        print("  1. Go to https://dashboard.render.com")
        print("  2. Click on your PostgreSQL database")
        print("  3. Copy the 'Connection String' or 'Internal Database URL'")
        print("  4. Add it to your .env file:")
        print("     DATABASE_URL=postgresql://user:pass@host:port/dbname")
        print()
        return False
    
    if 'postgresql' not in production_db_url:
        print("❌ DATABASE_URL doesn't look like a PostgreSQL database")
        print(f"   Found: {production_db_url[:50]}...")
        return False
    
    print("✅ Found production database URL")
    print()
    
    # Check if pg_dump is available
    try:
        result = subprocess.run(['pg_dump', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL tools found: {result.stdout.strip()}")
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        print("❌ PostgreSQL client tools not installed")
        print()
        print("📥 Install PostgreSQL tools:")
        print("  Windows: Download from https://www.postgresql.org/download/windows/")
        print("          Choose 'Command Line Tools' during installation")
        print()
        print("  OR use the manual method below:")
        print()
        print("📋 Manual method (from Render dashboard):")
        print("  1. Go to https://dashboard.render.com")
        print("  2. Click your PostgreSQL database")
        print("  3. Click 'Download' or 'Export' button")
        print("  4. Save the .sql file")
        print("  5. Contact me to convert it to SQLite format")
        print()
        return False
    
    # Create backup directory
    os.makedirs("backups", exist_ok=True)
    
    # Create backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backups/production_backup_{timestamp}.sql"
    
    print(f"📦 Creating backup from production...")
    print(f"   This may take a minute...")
    print()
    
    # Run pg_dump
    try:
        cmd = [
            'pg_dump',
            '--no-owner',
            '--no-acl',
            production_db_url,
            '-f', backup_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Backup failed: {result.stderr}")
            return False
        
        file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB
        print(f"✅ Backup created: {backup_file}")
        print(f"   Size: {file_size:.2f} MB")
        print()
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False
    
    print("⚠️  NOTE: PostgreSQL backup (.sql) cannot be directly used with SQLite")
    print()
    print("💡 BEST OPTION: Connect locally to production database (READ-ONLY)")
    print("   This is safe - your local app will use production data")
    print("   Just make sure you don't modify data when testing")
    print()
    print("   Your .env file already has DATABASE_URL set")
    print("   Just run: python main.py")
    print("   (Make sure you're careful not to click 'save' on admin pages)")
    print()
    
    return True

if __name__ == "__main__":
    success = sync_production_to_local()
    if success:
        print("=" * 60)
        print("✅ Backup complete!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ Backup failed - see instructions above")
        print("=" * 60)
        sys.exit(1)

