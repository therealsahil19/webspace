# GitHub Secrets Setup Guide

This document outlines all the GitHub secrets required for the CI/CD pipeline to function properly.

## Required Secrets

### Container Registry
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions (no setup needed)

### Staging Environment
- `STAGING_HOST` - IP address or hostname of staging server
- `STAGING_USER` - SSH username for staging server
- `STAGING_SSH_KEY` - Private SSH key for staging server access
- `STAGING_PORT` - SSH port (optional, defaults to 22)
- `STAGING_DATABASE_URL` - PostgreSQL connection string for staging
- `STAGING_REDIS_URL` - Redis connection string for staging
- `STAGING_JWT_SECRET` - JWT secret key for staging environment
- `STAGING_ADMIN_USERNAME` - Admin username for staging
- `STAGING_ADMIN_PASSWORD` - Admin password for staging

### Production Environment
- `PRODUCTION_HOST` - IP address or hostname of production server
- `PRODUCTION_USER` - SSH username for production server
- `PRODUCTION_SSH_KEY` - Private SSH key for production server access
- `PRODUCTION_PORT` - SSH port (optional, defaults to 22)
- `PRODUCTION_DATABASE_URL` - PostgreSQL connection string for production
- `PRODUCTION_REDIS_URL` - Redis connection string for production
- `PRODUCTION_JWT_SECRET` - JWT secret key for production environment
- `PRODUCTION_ADMIN_USERNAME` - Admin username for production
- `PRODUCTION_ADMIN_PASSWORD` - Admin password for production
- `PRODUCTION_DOMAIN` - Production domain name (e.g., spacex-tracker.com)
- `PRODUCTION_ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `PRODUCTION_DB_USER` - Database username for backups
- `PRODUCTION_ADMIN_TOKEN` - Admin API token for health checks

### Notifications (Optional)
- `SLACK_WEBHOOK` - Slack webhook URL for deployment notifications

## Setting Up Secrets

### 1. Navigate to Repository Settings
1. Go to your GitHub repository
2. Click on "Settings" tab
3. In the left sidebar, click "Secrets and variables" → "Actions"

### 2. Add Repository Secrets
Click "New repository secret" and add each secret listed above.

### 3. Environment-Specific Secrets
For better security, you can also set up environment-specific secrets:

1. Go to "Environments" in repository settings
2. Create "staging" and "production" environments
3. Add environment-specific secrets to each environment
4. Configure protection rules (e.g., require reviews for production)

## Secret Value Examples

### Database URLs
```
# PostgreSQL
postgresql://username:password@hostname:5432/database_name

# Example
postgresql://spacex_user:secure_password@db.example.com:5432/spacex_tracker
```

### Redis URLs
```
# Redis
redis://hostname:6379/0

# With password
redis://:password@hostname:6379/0

# Example
redis://cache.example.com:6379/0
```

### SSH Key Setup
```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "github-actions@spacex-tracker"

# Copy public key to server
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server

# Use private key content as STAGING_SSH_KEY or PRODUCTION_SSH_KEY secret
cat ~/.ssh/id_ed25519
```

### JWT Secret Generation
```bash
# Generate secure JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Server Setup Requirements

### Directory Structure
Ensure your servers have the following directory structure:
```
/opt/spacex-launch-tracker/
├── docker-compose.yml (for staging)
├── docker-compose.prod.yml (for production)
├── .env (staging environment file)
├── .env.production (production environment file)
└── backups/ (for database backups)
```

### Docker Installation
Ensure Docker and Docker Compose are installed on your servers:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Firewall Configuration
Ensure the following ports are accessible:
- SSH (22 or custom port)
- HTTP (80) - for Let's Encrypt challenges
- HTTPS (443) - for production traffic
- Application ports as configured in docker-compose files

## Security Best Practices

1. **Use Strong Passwords**: Generate secure passwords for all accounts
2. **Rotate Secrets Regularly**: Update secrets periodically
3. **Limit SSH Access**: Use key-based authentication only
4. **Environment Separation**: Use different credentials for staging and production
5. **Backup Secrets**: Store secrets securely outside of GitHub
6. **Monitor Access**: Review secret usage in GitHub Actions logs

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Verify SSH key format (should be private key, not public)
   - Check server firewall settings
   - Ensure SSH service is running on target port

2. **Database Connection Failed**
   - Verify database URL format
   - Check database server accessibility
   - Confirm credentials are correct

3. **Docker Commands Failed**
   - Ensure Docker is installed and running
   - Check user permissions for Docker commands
   - Verify Docker Compose file exists

### Testing Secrets
You can test your secrets by running a simple workflow that echoes masked values:

```yaml
- name: Test secrets (masked)
  run: |
    echo "Host: ${{ secrets.PRODUCTION_HOST }}"
    echo "User: ${{ secrets.PRODUCTION_USER }}"
    echo "Database URL configured: ${{ secrets.PRODUCTION_DATABASE_URL != '' }}"
```

## Next Steps

After setting up all secrets:

1. Test the pipeline with a staging deployment
2. Verify all health checks pass
3. Test rollback procedures
4. Set up monitoring and alerting
5. Document any environment-specific configurations

For additional help, refer to the main deployment documentation in `deployment.md`.