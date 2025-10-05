#!/usr/bin/env python3
"""
MX Fantasy League - Restore Script
Återställer databas och uploads från backup
"""

import os
import shutil
import argparse
from datetime import datetime

def list_backups(backup_dir):
    """List available backups"""
    if not os.path.exists(backup_dir):
        print("No backup directory found")
        return []
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("fantasy_mx_") and filename.endswith(".db"):
            file_path = os.path.join(backup_dir, filename)
            timestamp = os.path.getctime(file_path)
            backups.append((filename, timestamp))
    
    # Sort by timestamp (newest first)
    backups.sort(key=lambda x: x[1], reverse=True)
    return backups

def restore_database(backup_file, db_path):
    """Restore database from backup"""
    # Create backup of current database
    if os.path.exists(db_path):
        current_backup = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, current_backup)
        print(f"Current database backed up to: {current_backup}")
    
    # Restore from backup
    shutil.copy2(backup_file, db_path)
    print(f"Database restored from: {backup_file}")

def restore_uploads(backup_dir, uploads_path):
    """Restore uploads from backup"""
    # Find latest uploads backup
    uploads_backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("uploads_"):
            file_path = os.path.join(backup_dir, filename)
            if os.path.isdir(file_path):
                timestamp = os.path.getctime(file_path)
                uploads_backups.append((filename, timestamp))
    
    if not uploads_backups:
        print("No uploads backup found")
        return
    
    # Sort by timestamp (newest first)
    uploads_backups.sort(key=lambda x: x[1], reverse=True)
    latest_uploads = os.path.join(backup_dir, uploads_backups[0][0])
    
    # Create backup of current uploads
    if os.path.exists(uploads_path):
        current_backup = f"{uploads_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(uploads_path, current_backup)
        print(f"Current uploads backed up to: {current_backup}")
        shutil.rmtree(uploads_path)
    
    # Restore uploads
    shutil.copytree(latest_uploads, uploads_path)
    print(f"Uploads restored from: {latest_uploads}")

def main():
    parser = argparse.ArgumentParser(description='Restore MX Fantasy League from backup')
    parser.add_argument('--backup-dir', default='backups', 
                       help='Backup directory')
    parser.add_argument('--db-path', default='instance/fantasy_mx.db', 
                       help='Path to database file')
    parser.add_argument('--uploads-path', default='static/uploads', 
                       help='Path to uploads directory')
    parser.add_argument('--backup-file', 
                       help='Specific backup file to restore (optional)')
    parser.add_argument('--list', action='store_true', 
                       help='List available backups')
    
    args = parser.parse_args()
    
    if args.list:
        backups = list_backups(args.backup_dir)
        if backups:
            print("Available backups:")
            for filename, timestamp in backups:
                date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {filename} ({date_str})")
        else:
            print("No backups found")
        return
    
    if not os.path.exists(args.backup_dir):
        print(f"Backup directory not found: {args.backup_dir}")
        return
    
    if args.backup_file:
        # Restore specific backup
        backup_file = os.path.join(args.backup_dir, args.backup_file)
        if not os.path.exists(backup_file):
            print(f"Backup file not found: {backup_file}")
            return
    else:
        # Restore latest backup
        backups = list_backups(args.backup_dir)
        if not backups:
            print("No database backups found")
            return
        backup_file = os.path.join(args.backup_dir, backups[0][0])
    
    print(f"Restoring from: {backup_file}")
    
    # Create necessary directories
    os.makedirs(os.path.dirname(args.db_path), exist_ok=True)
    os.makedirs(args.uploads_path, exist_ok=True)
    
    # Restore database
    restore_database(backup_file, args.db_path)
    
    # Restore uploads
    restore_uploads(args.backup_dir, args.uploads_path)
    
    print("Restore completed!")

if __name__ == "__main__":
    main()
