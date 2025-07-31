#!/usr/bin/env python3
"""
Deployment script for SpaceX Launch Tracker.
Handles deployment to staging and production environments.
"""

import os
import sys
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/deployment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_command(command, check=True, cwd=None):
    """Run a shell command and return the result."""
    logger.info(f"Running command: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        raise


def check_prerequisites():
    """Check if all prerequisites are met for deployment."""
    logger.info("Checking deployment prerequisites")
    
    # Check if Docker is running
    try:
        run_command("docker --version")
        run_command("docker-compose --version")
    except subprocess.CalledProcessError:
        logger.error("Docker or Docker Compose not available")
        return False
    
    # Check if required environment files exist
    env_files = ['.env.production']
    for env_file in env_files:
        if not os.path.exists(env_file):
            logger.error(f"Required environment file missing: {env_file}")
            return False
    
    logger.info("Prerequisites check passed")
    return True


def pull_latest_images(environment):
    """Pull the latest Docker images."""
    logger.info(f"Pulling latest images for {environment}")
    
    if environment == "production":
        compose_file = "docker-compose.prod.yml"
    else:
        compose_file = "docker-compose.yml"
    
    try:
        run_command(f"docker-compose -f {compose_file} pull")
        logger.info("Images pulled successfully")
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to pull images")
        return False


def run_health_checks():
    """Run health checks on deployed services."""
    logger.info("Running health checks")
    
    services = [
        ("Backend API", "http://localhost:8000/health"),
        ("Frontend", "http://localhost:3000"),
    ]
    
    for service_name, url in services:
        logger.info(f"Checking {service_name} at {url}")
        
        # Wait for service to be ready
        max_retries = 30
        for attempt in range(max_retries):
            try:
                result = run_command(f"curl -f {url}", check=False)
                if result.returncode == 0:
                    logger.info(f"{service_name} is healthy")
                    break
                else:
                    if attempt < max_retries - 1:
                        logger.info(f"Waiting for {service_name} to be ready... (attempt {attempt + 1})")
                        time.sleep(10)
                    else:
                        logger.error(f"{service_name} health check failed")
                        return False
            except Exception as e:
                logger.error(f"Health check error for {service_name}: {e}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(10)
    
    logger.info("All health checks passed")
    return True


def deploy_environment(environment, skip_migration=False):
    """Deploy to specified environment."""
    logger.info(f"Starting deployment to {environment}")
    
    # Set compose file based on environment
    if environment == "production":
        compose_file = "docker-compose.prod.yml"
        env_file = ".env.production"
    else:
        compose_file = "docker-compose.yml"
        env_file = ".env"
    
    # Check if environment file exists
    if not os.path.exists(env_file):
        logger.error(f"Environment file not found: {env_file}")
        return False
    
    try:
        # Stop existing services
        logger.info("Stopping existing services")
        run_command(f"docker-compose -f {compose_file} down", check=False)
        
        # Pull latest images
        if not pull_latest_images(environment):
            return False
        
        # Run database migrations if not skipped
        if not skip_migration:
            logger.info("Running database migrations")
            # Start only database services for migration
            run_command(f"docker-compose -f {compose_file} up -d postgres redis")
            
            # Wait for database to be ready
            time.sleep(10)
            
            # Run migrations
            migration_result = run_command("python scripts/migrate.py --safe", check=False)
            if migration_result.returncode != 0:
                logger.error("Database migration failed")
                return False
        
        # Start all services
        logger.info("Starting all services")
        run_command(f"docker-compose -f {compose_file} up -d")
        
        # Wait for services to start
        time.sleep(30)
        
        # Run health checks
        if not run_health_checks():
            logger.error("Health checks failed")
            return False
        
        logger.info(f"Deployment to {environment} completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return False


def rollback_deployment(environment):
    """Rollback to previous deployment."""
    logger.info(f"Rolling back deployment in {environment}")
    
    if environment == "production":
        compose_file = "docker-compose.prod.yml"
    else:
        compose_file = "docker-compose.yml"
    
    try:
        # Stop current services
        run_command(f"docker-compose -f {compose_file} down")
        
        # Pull previous images (this would need to be implemented based on your tagging strategy)
        logger.info("Rolling back to previous images")
        # This is a placeholder - implement based on your image tagging strategy
        
        # Start services with previous images
        run_command(f"docker-compose -f {compose_file} up -d")
        
        # Run health checks
        if run_health_checks():
            logger.info("Rollback completed successfully")
            return True
        else:
            logger.error("Rollback health checks failed")
            return False
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False


def cleanup_old_images():
    """Clean up old Docker images to save space."""
    logger.info("Cleaning up old Docker images")
    
    try:
        # Remove dangling images
        run_command("docker image prune -f", check=False)
        
        # Remove unused images older than 24 hours
        run_command("docker image prune -a --filter 'until=24h' -f", check=False)
        
        logger.info("Image cleanup completed")
        return True
    except Exception as e:
        logger.error(f"Image cleanup failed: {e}")
        return False


def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deployment script for SpaceX Launch Tracker")
    parser.add_argument("environment", choices=["staging", "production"], help="Target environment")
    parser.add_argument("--skip-migration", action="store_true", help="Skip database migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous deployment")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old Docker images")
    parser.add_argument("--health-check", action="store_true", help="Run health checks only")
    
    args = parser.parse_args()
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    try:
        # Check prerequisites
        if not check_prerequisites():
            logger.error("Prerequisites check failed")
            sys.exit(1)
        
        if args.health_check:
            if run_health_checks():
                logger.info("Health checks passed")
                sys.exit(0)
            else:
                logger.error("Health checks failed")
                sys.exit(1)
        
        elif args.rollback:
            if rollback_deployment(args.environment):
                logger.info("Rollback completed successfully")
                sys.exit(0)
            else:
                logger.error("Rollback failed")
                sys.exit(1)
        
        elif args.cleanup:
            if cleanup_old_images():
                logger.info("Cleanup completed successfully")
                sys.exit(0)
            else:
                logger.error("Cleanup failed")
                sys.exit(1)
        
        else:
            # Normal deployment
            if deploy_environment(args.environment, args.skip_migration):
                logger.info("Deployment completed successfully")
                
                # Optional cleanup after successful deployment
                cleanup_old_images()
                
                sys.exit(0)
            else:
                logger.error("Deployment failed")
                sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Deployment script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()