# Deployment Guide

This document provides comprehensive instructions for deploying the SpaceX Launch Tracker application to staging and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [CI/CD Pipeline](#cicd-pipeline)
4. [Manual Deployment](#manual-deployment)
5. [Database Migrations](#database-migrations)
6. [Monitoring and Health Checks](#monitoring-and-health-checks)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (for production database)
- Redis 7+ (for caching and task queue)

### Access Requirements

- GitHub repository access with appropriate permissions
- Container registry access (GitHub Container Registry)
- Production server SSH access
- Database administrator credentials

## Environment Setup

### Environment Variables

The application uses environment variables for configuration. Copy the appropriate example file and update with your values:

```bash
# For development
cp .env.example .env

# For production
cp .env.production.example .env.production
```

### Critical Production Variables

Update these variables in `.env.production`:

```bash
# Database - Use strong credentials
DATABASE_URL=postgresql://prod_user:SECURE_PASSWORD@db_host:5432/spacex_launches_prod

# Authentication - Generate secure keys
JWT_SECRET_KEY=GENERATE_SECURE_RANDOM_KEY_HERE
ADMIN_PASSWORD=SECURE_ADMIN_PASSWORD_HERE

# Redis - Use password protection
REDIS_PASSWORD=SECURE_REDIS_PASSWORD_HERE

# API Configuration
API_CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### Secrets Management

For production deployments, use a secrets management system:

#### GitHub Secrets (for CI/CD)

Add these secrets to your GitHub repository:

- `POSTGRES_PASSWORD`: Database password
- `REDIS_PASSWORD`: Redis password
- `JWT_SECRET_KEY`: JWT signing key
- `ADMIN_PASSWORD`: Admin user password

#### Docker Secrets (for Docker Swarm)

```bash
# Create secrets
echo "your_postgres_password" | docker secret create postgres_password -
echo "your_redis_password" | docker secret create redis_password -
echo "your_jwt_secret" | docker secret create jwt_secret -
```

## CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline automatically:

1. **Tests**: Runs backend and frontend tests
2. **Builds**: Creates Docker images
3. **Pushes**: Uploads images to GitHub Container Registry
4. **Deploys**: Deploys to staging/production based on branch

### Pipeline Triggers

- **Pull Requests**: Run tests only
- **Push to `develop`**: Deploy to staging
- **Push to `main`**: Deploy to production

### Manual Pipeline Trigger

```bash
# Trigger deployment via GitHub CLI
gh workflow run ci-cd.yml --ref main
```

## Manual Deployment

### Using Deployment Script

The deployment script provides a safe, automated deployment process:

```bash
# Deploy to staging
python scripts/deploy.py staging

# Deploy to production
python scripts/deploy.py production

# Deploy without running migrations
python scripts/deploy.py production --skip-migration

# Run health checks only
python scripts/deploy.py production --health-check
```

### Manual Docker Compose Deployment

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps
```

### Staging Deployment

```bash
# Staging uses the regular docker-compose.yml
docker-compose down
docker-compose pull
docker-compose up -d
```

## Database Migrations

### Safe Migration Process

The migration script provides backup and rollback capabilities:

```bash
# Safe migration with automatic backup
python scripts/migrate.py --safe

# Create backup only
python scripts/migrate.py --backup

# Run migrations only
python scripts/migrate.py --migrate

# Rollback to previous version
python scripts/migrate.py --rollback -1

# Rollback to specific revision
python scripts/migrate.py --rollback abc123

# Restore from backup
python scripts/migrate.py --restore backups/backup_20240131_120000.sql
```

### Migration Best Practices

1. **Always backup before migrations**
2. **Test migrations on staging first**
3. **Run migrations during low-traffic periods**
4. **Monitor application after migrations**
5. **Keep recent backups available**

### Manual Migration Commands

```bash
# Check current migration status
alembic current

# Check for pending migrations
alembic check

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show migration history
alembic history
```

## Monitoring and Health Checks

### Health Check Endpoints

The application provides several health check endpoints:

- `GET /health` - Overall application health
- `GET /health/database` - Database connectivity
- `GET /health/redis` - Redis connectivity
- `GET /health/celery` - Celery worker status

### Service Health Checks

```bash
# Check all services
curl -f http://localhost:8000/health

# Check specific components
curl -f http://localhost:8000/health/database
curl -f http://localhost:8000/health/redis
curl -f http://localhost:8000/health/celery
```

### Docker Health Checks

Services include built-in Docker health checks:

```bash
# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# View health check logs
docker inspect --format='{{json .State.Health}}' spacex_backend_prod
```

### Log Monitoring

```bash
# View application logs
docker-compose -f docker-compose.prod.yml logs -f backend

# View specific service logs
docker logs spacex_backend_prod -f

# View migration logs
tail -f logs/migration.log

# View deployment logs
tail -f logs/deployment.log
```

## Rollback Procedures

### Automatic Rollback

```bash
# Rollback using deployment script
python scripts/deploy.py production --rollback
```

### Manual Rollback Steps

1. **Stop current services**:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   ```

2. **Restore database from backup** (if needed):
   ```bash
   python scripts/migrate.py --restore backups/backup_YYYYMMDD_HHMMSS.sql
   ```

3. **Deploy previous image version**:
   ```bash
   # Update image tags in docker-compose.prod.yml to previous version
   # Then restart services
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Verify rollback**:
   ```bash
   python scripts/deploy.py production --health-check
   ```

### Database Rollback

```bash
# Rollback database to previous migration
python scripts/migrate.py --rollback -1

# Or rollback to specific revision
python scripts/migrate.py --rollback abc123def456
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check database container
docker logs spacex_postgres_prod

# Test database connection
docker exec spacex_postgres_prod pg_isready -U spacex_user

# Check database URL format
echo $DATABASE_URL
```

#### 2. Redis Connection Errors

```bash
# Check Redis container
docker logs spacex_redis_prod

# Test Redis connection
docker exec spacex_redis_prod redis-cli ping
```

#### 3. Migration Failures

```bash
# Check migration logs
cat logs/migration.log

# Check current migration status
alembic current

# Manually fix migration issues
alembic stamp head  # Only if you're sure the database is correct
```

#### 4. Service Startup Issues

```bash
# Check service logs
docker-compose -f docker-compose.prod.yml logs backend

# Check resource usage
docker stats

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

### Performance Issues

#### 1. High Memory Usage

```bash
# Check memory usage
docker stats --no-stream

# Adjust container memory limits in docker-compose.prod.yml
```

#### 2. Slow Database Queries

```bash
# Check database performance
docker exec spacex_postgres_prod psql -U spacex_user -d spacex_launches -c "SELECT * FROM pg_stat_activity;"

# Analyze slow queries
docker exec spacex_postgres_prod psql -U spacex_user -d spacex_launches -c "SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

### Emergency Procedures

#### 1. Complete System Failure

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Restore from backup
python scripts/migrate.py --restore backups/latest_backup.sql

# Start with known good configuration
docker-compose -f docker-compose.prod.yml up -d
```

#### 2. Data Corruption

```bash
# Stop application services (keep database running)
docker-compose -f docker-compose.prod.yml stop backend frontend celery-worker celery-beat

# Restore database from backup
python scripts/migrate.py --restore backups/backup_before_corruption.sql

# Restart services
docker-compose -f docker-compose.prod.yml start backend frontend celery-worker celery-beat
```

## Security Considerations

### Production Security Checklist

- [ ] Strong passwords for all services
- [ ] JWT secret key is cryptographically secure
- [ ] Database connections use SSL
- [ ] Redis requires authentication
- [ ] CORS origins are properly configured
- [ ] Rate limiting is enabled
- [ ] Security headers are configured
- [ ] Container images are regularly updated
- [ ] Secrets are not stored in code or logs

### SSL/TLS Configuration

Configure SSL certificates for production:

```bash
# Using Let's Encrypt with Certbot
certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Or place certificates in nginx/ssl/ directory
# Update nginx configuration to use SSL
```

## Maintenance

### Regular Maintenance Tasks

1. **Weekly**:
   - Review application logs
   - Check disk space usage
   - Verify backup integrity

2. **Monthly**:
   - Update container images
   - Review security patches
   - Clean up old Docker images
   - Rotate log files

3. **Quarterly**:
   - Review and update dependencies
   - Performance optimization review
   - Disaster recovery testing

### Backup Strategy

```bash
# Automated daily backups (add to cron)
0 2 * * * /path/to/scripts/migrate.py --backup

# Weekly full system backup
0 3 * * 0 tar -czf /backups/full_backup_$(date +\%Y\%m\%d).tar.gz /app /backups/*.sql

# Cleanup old backups (keep 30 days)
find /backups -name "backup_*.sql" -mtime +30 -delete
```

## Support and Contacts

For deployment issues:

1. Check this documentation
2. Review application logs
3. Check GitHub Issues
4. Contact the development team

Remember to always test deployments in staging before production!