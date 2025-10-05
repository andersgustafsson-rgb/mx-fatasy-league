#!/usr/bin/env python3
"""
MX Fantasy League - Backup Script
Skapar backup av databas och uploads
"""

import os
import shutil
import sqlite3
from datetime import datetime
import argparse

def backup_database(db_path, backup_dir):
    """Backup SQLite database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"fantasy_mx_{timestamp}.db")
    
    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)
    
    # Copy database file
    shutil.copy2(db_path, backup_file)
    print(f"Database backed up to: {backup_file}")
    return backup_file

def backup_uploads(uploads_path, backup_dir):
    """Backup uploads directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uploads_backup = os.path.join(backup_dir, f"uploads_{timestamp}")
    
    if os.path.exists(uploads_path):
        shutil.copytree(uploads_path, uploads_backup)
        print(f"Uploads backed up to: {uploads_backup}")
        return uploads_backup
    else:
        print("No uploads directory found")
        return None

def cleanup_old_backups(backup_dir, keep_days=30):
    """Remove backups older than specified days"""
    import time
    
    current_time = time.time()
    cutoff_time = current_time - (keep_days * 24 * 60 * 60)
    
    for filename in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, filename)
        if os.path.isfile(file_path) or os.path.isdir(file_path):
            file_time = os.path.getctime(file_path)
            if file_time < cutoff_time:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                print(f"Removed old backup: {filename}")

def main():
    parser = argparse.ArgumentParser(description='Backup MX Fantasy League')
    parser.add_argument('--db-path', default='instance/fantasy_mx.db', 
                       help='Path to database file')
    parser.add_argument('--uploads-path', default='static/uploads', 
                       help='Path to uploads directory')
    parser.add_argument('--backup-dir', default='backups', 
                       help='Backup directory')
    parser.add_argument('--keep-days', type=int, default=30, 
                       help='Keep backups for this many days')
    
    args = parser.parse_args()
    
    print("Starting backup...")
    
    # Create backup directory
    os.makedirs(args.backup_dir, exist_ok=True)
    
    # Backup database
    if os.path.exists(args.db_path):
        backup_database(args.db_path, args.backup_dir)
    else:
        print(f"Database not found at: {args.db_path}")
    
    # Backup uploads
    backup_uploads(args.uploads_path, args.backup_dir)
    
    # Cleanup old backups
    cleanup_old_backups(args.backup_dir, args.keep_days)
    
    print("Backup completed!")

if __name__ == "__main__":
    main()
