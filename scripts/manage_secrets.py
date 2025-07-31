#!/usr/bin/env python3
"""
Secrets management script for SpaceX Launch Tracker.
Handles generation and management of secure secrets for production deployment.
"""

import os
import sys
import secrets
import string
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_secure_password(length=32, include_symbols=True):
    """Generate a cryptographically secure password."""
    alphabet = string.ascii_letters + string.digits
    if include_symbols:
        alphabet += "!@#$%^&*"
    
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_jwt_secret(length=64):
    """Generate a secure JWT secret key."""
    return secrets.token_urlsafe(length)


def generate_api_key(length=32):
    """Generate a secure API key."""
    return secrets.token_urlsafe(length)


def create_env_file(environment="production"):
    """Create environment file with generated secrets."""
    if environment == "production":
        env_file = ".env.production"
        template_file = ".env.production.example"
    else:
        env_file = ".env"
        template_file = ".env.example"
    
    if not os.path.exists(template_file):
        logger.error(f"Template file not found: {template_file}")
        return False
    
    # Read template
    with open(template_file, 'r') as f:
        template_content = f.read()
    
    # Generate secrets
    secrets_map = {
        'SECURE_PASSWORD': generate_secure_password(32),
        'SECURE_ADMIN_PASSWORD_HERE': generate_secure_password(16, include_symbols=False),
        'GENERATE_SECURE_RANDOM_KEY_HERE': generate_jwt_secret(),
        'SECURE_REDIS_PASSWORD_HERE': generate_secure_password(24, include_symbols=False),
        'your_super_secret_jwt_key_here_change_in_production': generate_jwt_secret(),
        'change_this_password_in_production': generate_secure_password(16, include_symbols=False),
    }
    
    # Replace placeholders with generated secrets
    content = template_content
    for placeholder, secret in secrets_map.items():
        content = content.replace(placeholder, secret)
    
    # Write environment file
    with open(env_file, 'w') as f:
        f.write(content)
    
    logger.info(f"Environment file created: {env_file}")
    logger.warning("Please review and update the generated environment file with your specific configuration")
    
    return True


def generate_docker_secrets():
    """Generate Docker secrets for Docker Swarm deployment."""
    secrets = {
        'postgres_password': generate_secure_password(32, include_symbols=False),
        'redis_password': generate_secure_password(24, include_symbols=False),
        'jwt_secret': generate_jwt_secret(),
        'admin_password': generate_secure_password(16, include_symbols=False),
    }
    
    # Create secrets directory
    secrets_dir = Path("secrets")
    secrets_dir.mkdir(exist_ok=True)
    
    # Write secrets to files
    for secret_name, secret_value in secrets.items():
        secret_file = secrets_dir / f"{secret_name}.txt"
        with open(secret_file, 'w') as f:
            f.write(secret_value)
        
        # Set restrictive permissions
        os.chmod(secret_file, 0o600)
        
        logger.info(f"Generated secret: {secret_name}")
    
    # Create Docker secrets creation script
    script_content = "#!/bin/bash\n\n"
    script_content += "# Create Docker secrets\n"
    for secret_name in secrets.keys():
        script_content += f"docker secret create {secret_name} secrets/{secret_name}.txt\n"
    
    script_file = secrets_dir / "create_docker_secrets.sh"
    with open(script_file, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_file, 0o755)
    
    logger.info("Docker secrets generated in 'secrets/' directory")
    logger.info("Run 'secrets/create_docker_secrets.sh' to create Docker secrets")
    
    return True


def rotate_secrets(environment="production"):
    """Rotate existing secrets in environment file."""
    if environment == "production":
        env_file = ".env.production"
    else:
        env_file = ".env"
    
    if not os.path.exists(env_file):
        logger.error(f"Environment file not found: {env_file}")
        return False
    
    # Read current environment file
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Secrets to rotate
    secret_keys = [
        'JWT_SECRET_KEY',
        'ADMIN_PASSWORD',
        'POSTGRES_PASSWORD',
        'REDIS_PASSWORD'
    ]
    
    # Update secrets
    updated_lines = []
    for line in lines:
        updated_line = line
        for key in secret_keys:
            if line.startswith(f"{key}="):
                if key == 'JWT_SECRET_KEY':
                    new_secret = generate_jwt_secret()
                else:
                    new_secret = generate_secure_password(24, include_symbols=False)
                updated_line = f"{key}={new_secret}\n"
                logger.info(f"Rotated secret: {key}")
                break
        updated_lines.append(updated_line)
    
    # Write updated file
    with open(env_file, 'w') as f:
        f.writelines(updated_lines)
    
    logger.info(f"Secrets rotated in: {env_file}")
    logger.warning("Remember to restart services after rotating secrets")
    
    return True


def validate_secrets(environment="production"):
    """Validate that all required secrets are present and secure."""
    if environment == "production":
        env_file = ".env.production"
    else:
        env_file = ".env"
    
    if not os.path.exists(env_file):
        logger.error(f"Environment file not found: {env_file}")
        return False
    
    # Read environment file
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    
    # Required secrets with minimum lengths
    required_secrets = {
        'JWT_SECRET_KEY': 32,
        'ADMIN_PASSWORD': 8,
        'POSTGRES_PASSWORD': 8,
    }
    
    # Validation results
    validation_passed = True
    
    for key, min_length in required_secrets.items():
        if key not in env_vars:
            logger.error(f"Missing required secret: {key}")
            validation_passed = False
            continue
        
        value = env_vars[key]
        
        # Check length
        if len(value) < min_length:
            logger.error(f"Secret {key} is too short (minimum {min_length} characters)")
            validation_passed = False
        
        # Check for default/example values
        insecure_values = [
            'change_this_password_in_production',
            'your_super_secret_jwt_key_here_change_in_production',
            'SECURE_PASSWORD',
            'GENERATE_SECURE_RANDOM_KEY_HERE',
            'password',
            '123456',
            'admin'
        ]
        
        if value in insecure_values:
            logger.error(f"Secret {key} contains insecure default value")
            validation_passed = False
    
    # Check JWT secret strength
    if 'JWT_SECRET_KEY' in env_vars:
        jwt_secret = env_vars['JWT_SECRET_KEY']
        if len(set(jwt_secret)) < 10:  # Check character diversity
            logger.warning("JWT_SECRET_KEY has low character diversity")
    
    if validation_passed:
        logger.info("All secrets validation passed")
    else:
        logger.error("Secrets validation failed")
    
    return validation_passed


def backup_secrets(environment="production"):
    """Create a backup of current secrets."""
    if environment == "production":
        env_file = ".env.production"
    else:
        env_file = ".env"
    
    if not os.path.exists(env_file):
        logger.error(f"Environment file not found: {env_file}")
        return False
    
    # Create backup directory
    backup_dir = Path("backups/secrets")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Create backup filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{env_file}.backup_{timestamp}"
    
    # Copy environment file to backup
    import shutil
    shutil.copy2(env_file, backup_file)
    
    # Set restrictive permissions
    os.chmod(backup_file, 0o600)
    
    logger.info(f"Secrets backed up to: {backup_file}")
    return True


def main():
    """Main secrets management function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Secrets management for SpaceX Launch Tracker")
    parser.add_argument("action", choices=[
        "generate", "rotate", "validate", "backup", "docker-secrets"
    ], help="Action to perform")
    parser.add_argument("--environment", choices=["development", "production"], 
                       default="production", help="Target environment")
    
    args = parser.parse_args()
    
    try:
        if args.action == "generate":
            if create_env_file(args.environment):
                logger.info("Secrets generation completed")
            else:
                logger.error("Secrets generation failed")
                sys.exit(1)
        
        elif args.action == "rotate":
            if rotate_secrets(args.environment):
                logger.info("Secrets rotation completed")
            else:
                logger.error("Secrets rotation failed")
                sys.exit(1)
        
        elif args.action == "validate":
            if validate_secrets(args.environment):
                logger.info("Secrets validation passed")
            else:
                logger.error("Secrets validation failed")
                sys.exit(1)
        
        elif args.action == "backup":
            if backup_secrets(args.environment):
                logger.info("Secrets backup completed")
            else:
                logger.error("Secrets backup failed")
                sys.exit(1)
        
        elif args.action == "docker-secrets":
            if generate_docker_secrets():
                logger.info("Docker secrets generation completed")
            else:
                logger.error("Docker secrets generation failed")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"Secrets management failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()