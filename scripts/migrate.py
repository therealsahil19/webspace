#!/usr/bin/env python3
"""
Database migration script for production deployments.
This script handles database migrations safely with backup and rollback capabilities.
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import get_database_url
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_command(command, check=True):
    """Run a shell command and return the result."""
    logger.info(f"Running command: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        raise


def create_backup():
    """Create a database backup before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backups/backup_{timestamp}.sql"
    
    # Ensure backup directory exists
    os.makedirs("backups", exist_ok=True)
    
    database_url = get_database_url()
    
    # Extract connection details from DATABASE_URL
    # Format: postgresql://user:password@host:port/database
    if not database_url.startswith("postgresql://"):
        raise ValueError("Invalid database URL format")
    
    # Parse URL components
    url_parts = database_url.replace("postgresql://", "").split("/")
    db_name = url_parts[-1]
    host_part = url_parts[0]
    
    if "@" in host_part:
        auth_part, host_port = host_part.split("@")
        user, password = auth_part.split(":")
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host, port = host_port, "5432"
    else:
        raise ValueError("Database URL must include authentication")
    
    # Set environment variables for pg_dump
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    backup_command = f"pg_dump -h {host} -p {port} -U {user} -d {db_name} -f {backup_file}"
    
    logger.info(f"Creating database backup: {backup_file}")
    run_command(backup_command)
    
    logger.info(f"Backup created successfully: {backup_file}")
    return backup_file


def check_database_connection():
    """Check if database is accessible."""
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_current_migration():
    """Get the current migration version."""
    try:
        result = run_command("alembic current", check=False)
        if result.returncode == 0:
            current = result.stdout.strip()
            logger.info(f"Current migration: {current}")
            return current
        else:
            logger.warning("Could not determine current migration")
            return None
    except Exception as e:
        logger.error(f"Error getting current migration: {e}")
        return None


def run_migrations():
    """Run database migrations."""
    logger.info("Starting database migrations")
    
    # Check for pending migrations
    result = run_command("alembic check", check=False)
    if result.returncode == 0:
        logger.info("No pending migrations")
        return True
    
    # Run migrations
    try:
        run_command("alembic upgrade head")
        logger.info("Migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def rollback_migration(target_revision=None):
    """Rollback to a specific migration or previous version."""
    if target_revision:
        command = f"alembic downgrade {target_revision}"
        logger.info(f"Rolling back to revision: {target_revision}")
    else:
        command = "alembic downgrade -1"
        logger.info("Rolling back to previous migration")
    
    try:
        run_command(command)
        logger.info("Rollback completed successfully")
        return True
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False


def restore_backup(backup_file):
    """Restore database from backup file."""
    if not os.path.exists(backup_file):
        logger.error(f"Backup file not found: {backup_file}")
        return False
    
    database_url = get_database_url()
    
    # Parse URL components (same as in create_backup)
    url_parts = database_url.replace("postgresql://", "").split("/")
    db_name = url_parts[-1]
    host_part = url_parts[0]
    
    auth_part, host_port = host_part.split("@")
    user, password = auth_part.split(":")
    if ":" in host_port:
        host, port = host_port.split(":")
    else:
        host, port = host_port, "5432"
    
    # Set environment variables for psql
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    # Drop and recreate database
    logger.info("Dropping and recreating database")
    run_command(f"dropdb -h {host} -p {port} -U {user} {db_name}")
    run_command(f"createdb -h {host} -p {port} -U {user} {db_name}")
    
    # Restore from backup
    restore_command = f"psql -h {host} -p {port} -U {user} -d {db_name} -f {backup_file}"
    
    logger.info(f"Restoring database from backup: {backup_file}")
    run_command(restore_command)
    
    logger.info("Database restored successfully")
    return True


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration script")
    parser.add_argument("--backup", action="store_true", help="Create backup only")
    parser.add_argument("--migrate", action="store_true", help="Run migrations")
    parser.add_argument("--rollback", help="Rollback to specific revision")
    parser.add_argument("--restore", help="Restore from backup file")
    parser.add_argument("--safe", action="store_true", help="Safe migration with backup")
    
    args = parser.parse_args()
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    try:
        # Check database connection
        if not check_database_connection():
            logger.error("Cannot connect to database. Aborting.")
            sys.exit(1)
        
        if args.backup:
            create_backup()
        
        elif args.migrate:
            if not run_migrations():
                logger.error("Migration failed")
                sys.exit(1)
        
        elif args.rollback:
            if not rollback_migration(args.rollback):
                logger.error("Rollback failed")
                sys.exit(1)
        
        elif args.restore:
            if not restore_backup(args.restore):
                logger.error("Restore failed")
                sys.exit(1)
        
        elif args.safe:
            # Safe migration: backup, migrate, verify
            logger.info("Starting safe migration process")
            
            # Get current migration for potential rollback
            current_migration = get_current_migration()
            
            # Create backup
            backup_file = create_backup()
            
            # Run migrations
            if run_migrations():
                logger.info("Safe migration completed successfully")
            else:
                logger.error("Migration failed, consider restoring from backup")
                logger.info(f"Backup file: {backup_file}")
                sys.exit(1)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()