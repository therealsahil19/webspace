# SpaceX Launch Tracker - Deployment Guide

This guide provides step-by-step instructions for deploying the SpaceX Launch Tracker application.

## Quick Start

### 1. Prerequisites

Ensure you have the following installed:
- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.11+
- Git

### 2. Clone and Setup

```bash
git clone <repository-url>
cd spacex-launch-tracker

# Generate production secrets
python scripts/manage_secrets.py generate --environment production

# Review and update .env.production with your specific values
nano .env.production
```

### 3. Deploy

```bash
# Deploy to production
python scripts/deploy.py production

# Or use Docker Compose directly
docker-compose -f docker-compose.prod.yml up -d
```

## Deployment Options

### Option 1: Automated CI/CD (Recommended)

The application includes a GitHub Actions workflow that automatically:
- Runs tests on pull requests
- Builds and pushes Docker images
- Deploys to staging (develop branch) and production (main branch)

**Setup:**
1. Fork the repository
2. Add required secrets to GitHub repository settings
3. Push to `main` branch to trigger production deployment

### Option 2: Manual Deployment Script

Use the deployment script for controlled manual deployments:

```bash
# Deploy to production with all safety checks
python scripts/deploy.py production

# Deploy without running migrations
python scripts/deploy.py production --skip-migration

# Run health checks only
python scripts/deploy.py production --health-check
```

### Option 3: Direct Docker Compose

For simple deployments without additional safety checks:

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Development deployment
docker-compose up -d
```

## Environment Configuration

### Required Environment Variables

Copy and customize the environment file:

```bash
cp .env.production.example .env.production
```

**Critical variables to update:**

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/database

# Authentication
JWT_SECRET_KEY=<generate-secure-key>
ADMIN_PASSWORD=<secure-admin-password>

# Domain configuration
API_CORS_ORIGINS=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### Secrets Management

Generate secure secrets automatically:

```bash
# Generate all secrets
python scripts/manage_secrets.py generate --environment production

# Validate secrets
python scripts/manage_secrets.py validate --environment production

# Rotate secrets
python scripts/manage_secrets.py rotate --environment production
```

## Database Setup

### Initial Setup

The application uses PostgreSQL with Alembic for migrations:

```bash
# Run migrations safely with backup
python scripts/migrate.py --safe

# Or run migrations directly
alembic upgrade head
```

### Production Database

For production, use a managed database service or set up PostgreSQL with:
- Regular backups
- SSL connections
- Strong authentication
- Monitoring

## Monitoring and Health Checks

### Health Endpoints

- `GET /health` - Overall application health
- `GET /health/database` - Database connectivity
- `GET /health/redis` - Redis connectivity
- `GET /health/celery` - Background task status

### Service Monitoring

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Check specific service
docker logs spacex_backend_prod -f
```

## SSL/HTTPS Setup

### Using Let's Encrypt

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificates
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual Certificate Setup

1. Place certificates in `nginx/ssl/`
2. Update `nginx/nginx.conf` with certificate paths
3. Restart Nginx container

## Scaling and Performance

### Horizontal Scaling

Scale individual services:

```bash
# Scale backend workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# Scale with Docker Swarm
docker stack deploy -c docker-compose.prod.yml spacex-tracker
```

### Performance Optimization

1. **Database**: Use connection pooling, optimize queries
2. **Redis**: Configure memory limits and persistence
3. **Nginx**: Enable caching, compression
4. **Application**: Monitor memory usage, optimize scraping intervals

## Backup and Recovery

### Automated Backups

```bash
# Create database backup
python scripts/migrate.py --backup

# Schedule daily backups (crontab)
0 2 * * * /path/to/scripts/migrate.py --backup
```

### Recovery Procedures

```bash
# Restore from backup
python scripts/migrate.py --restore backups/backup_20240131_120000.sql

# Rollback deployment
python scripts/deploy.py production --rollback
```

## Troubleshooting

### Common Issues

1. **Database connection errors**: Check DATABASE_URL and network connectivity
2. **Redis connection errors**: Verify Redis container is running
3. **Migration failures**: Check migration logs and database permissions
4. **SSL certificate errors**: Verify certificate paths and permissions

### Debug Commands

```bash
# Check container status
docker ps -a

# View container logs
docker logs <container-name>

# Execute commands in container
docker exec -it spacex_backend_prod bash

# Test database connection
docker exec spacex_postgres_prod pg_isready -U spacex_user
```

## Security Checklist

- [ ] Strong passwords for all services
- [ ] JWT secret is cryptographically secure
- [ ] Database uses SSL connections
- [ ] Redis requires authentication
- [ ] CORS origins are properly configured
- [ ] Rate limiting is enabled
- [ ] Security headers are configured
- [ ] Regular security updates
- [ ] Secrets are not in version control

## Support

For deployment issues:
1. Check the [deployment documentation](docs/deployment.md)
2. Review application logs
3. Check GitHub Issues
4. Contact the development team

## Production Checklist

Before going live:

- [ ] Environment variables configured
- [ ] Secrets generated and validated
- [ ] Database migrations completed
- [ ] SSL certificates installed
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Backup strategy implemented
- [ ] Security review completed
- [ ] Performance testing done
- [ ] Documentation updated