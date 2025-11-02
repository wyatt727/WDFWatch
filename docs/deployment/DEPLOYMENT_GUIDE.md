# WDFWatch Deployment Guide

This guide covers deploying WDFWatch in production environments using Docker Compose.

## Prerequisites

- Docker Engine 20.10+ and Docker Compose 2.0+
- PostgreSQL 16+ (or use included container)
- Redis 7+ (or use included container)
- Minimum 4GB RAM, 2 CPU cores recommended
- Disk space: 10GB minimum (50GB+ recommended for episode storage)

## Quick Start

### 1. Environment Setup

```bash
# Copy production environment template
cp .env.production.example .env.production

# Edit .env.production with your production values
nano .env.production

# Required variables to set:
# - DATABASE_URL (with strong password)
# - REDIS_URL (with password)
# - NEXTAUTH_SECRET (generate strong secret)
# - API_KEY (for internal API auth)
# - CORS_ALLOWED_ORIGINS (your production domains)
# - Twitter API credentials
```

### 2. Build Images

```bash
# Build all services
make deploy-build

# Or manually:
docker-compose -f docker-compose.prod.yml build
```

### 3. Database Migration

```bash
# Run Prisma migrations
make deploy-migrate

# Or manually:
cd web
npx prisma migrate deploy
cd ..
```

### 4. Start Services

```bash
# Start all services
make deploy-start

# Or manually:
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Verify Deployment

```bash
# Check service health
make deploy-health

# Or manually:
docker-compose -f docker-compose.prod.yml ps
curl http://localhost:8001/health/ready
curl http://localhost:3000/api/health
```

## Deployment Targets

The Makefile provides convenient deployment targets:

```bash
make deploy-build      # Build Docker images
make deploy-push       # Push images to registry (if configured)
make deploy-migrate    # Run database migrations
make deploy-start      # Start all services
make deploy-stop       # Stop all services
make deploy-restart    # Restart all services
make deploy-scale      # Scale worker services
make deploy-logs       # View service logs
make deploy-health     # Check service health
make deploy-clean      # Clean up stopped containers
```

## Service Architecture

### Services Overview

- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache and queue (port 6379)
- **fastapi**: FastAPI backend API (port 8001)
- **rq-worker**: Background job workers (scalable)
- **web**: Next.js web application (port 3000)
- **nginx**: Reverse proxy (ports 80/443) - optional
- **ollama**: Local LLM models (port 11434) - optional

### Scaling Workers

```bash
# Scale RQ workers to 4 instances
docker-compose -f docker-compose.prod.yml up -d --scale rq-worker=4

# Or use Makefile:
make deploy-scale WORKERS=4
```

## Configuration

### Environment Variables

Production configuration is managed via `.env.production`. Key variables:

**Database:**
- `DATABASE_URL`: PostgreSQL connection string
- `POSTGRES_USER`, `POSTGRES_PASSWORD`: Database credentials

**Redis:**
- `REDIS_URL`: Redis connection string (with password)
- `REDIS_PASSWORD`: Redis password

**Security:**
- `API_KEY`: Internal API authentication key
- `NEXTAUTH_SECRET`: NextAuth.js secret (min 32 chars)
- `WEB_API_KEY`: Web UI API key

**CORS:**
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins

**Application:**
- `ENVIRONMENT=production`
- `DEBUG=false`
- `WEB_URL`: Production web URL
- `NEXT_PUBLIC_API_URL`: Production API URL

### Generating Secrets

```bash
# Generate NextAuth secret
openssl rand -base64 32

# Generate API key
openssl rand -hex 32

# Generate Redis password
openssl rand -base64 24
```

## Database Management

### Migrations

```bash
# Apply migrations
make deploy-migrate

# Rollback (if needed)
cd web
npx prisma migrate resolve --rolled-back <migration_name>
```

### Backups

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U wdfwatch wdfwatch_prod > backup_$(date +%Y%m%d).sql

# Restore backup
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U wdfwatch wdfwatch_prod < backup_YYYYMMDD.sql
```

## Monitoring

### Health Checks

All services include healthcheck endpoints:

- FastAPI: `GET /health/ready`
- Next.js: `GET /api/health`
- Redis: `redis-cli ping`
- PostgreSQL: `pg_isready`

### Logs

```bash
# View all logs
make deploy-logs

# View specific service
docker-compose -f docker-compose.prod.yml logs -f fastapi
docker-compose -f docker-compose.prod.yml logs -f rq-worker
docker-compose -f docker-compose.prod.yml logs -f web
```

### Resource Usage

```bash
# Check resource usage
docker stats

# Check disk usage
docker system df
```

## Rollback Procedures

### Rollback Database Migration

```bash
cd web
npx prisma migrate resolve --rolled-back <migration_name>
```

### Rollback Service Update

```bash
# Stop current services
make deploy-stop

# Checkout previous version
git checkout <previous-version-tag>

# Rebuild and restart
make deploy-build
make deploy-start
```

### Emergency Rollback

```bash
# Stop all services immediately
docker-compose -f docker-compose.prod.yml down

# Restore from backup
# (see Database Management section)

# Restart services
make deploy-start
```

## Troubleshooting

### Service Won't Start

1. Check logs: `make deploy-logs`
2. Verify environment variables: `docker-compose -f docker-compose.prod.yml config`
3. Check health: `make deploy-health`
4. Verify dependencies: Ensure postgres and redis are healthy

### Database Connection Issues

1. Verify DATABASE_URL in `.env.production`
2. Check postgres container: `docker-compose -f docker-compose.prod.yml ps postgres`
3. Test connection: `docker-compose -f docker-compose.prod.yml exec postgres psql -U wdfwatch -d wdfwatch_prod`

### Redis Connection Issues

1. Verify REDIS_URL in `.env.production`
2. Check redis container: `docker-compose -f docker-compose.prod.yml ps redis`
3. Test connection: `docker-compose -f docker-compose.prod.yml exec redis redis-cli ping`

### Worker Not Processing Jobs

1. Check worker logs: `docker-compose -f docker-compose.prod.yml logs rq-worker`
2. Verify Redis connection
3. Check job queue: `docker-compose -f docker-compose.prod.yml exec fastapi python -c "from app.services.queue import get_queue; print(get_queue().count)"`

### High Memory Usage

1. Scale workers: `make deploy-scale WORKERS=2`
2. Check for memory leaks: `docker stats`
3. Restart services: `make deploy-restart`
```

## Production Checklist

Before deploying to production:

- [ ] Set strong passwords for all services
- [ ] Configure CORS_ALLOWED_ORIGINS
- [ ] Set ENVIRONMENT=production
- [ ] Set DEBUG=false
- [ ] Generate and set NEXTAUTH_SECRET
- [ ] Generate and set API_KEY
- [ ] Configure Redis password
- [ ] Configure PostgreSQL password
- [ ] Set up SSL/TLS certificates (if using nginx)
- [ ] Configure backup schedule
- [ ] Set up monitoring and alerting
- [ ] Test health endpoints
- [ ] Verify database migrations
- [ ] Test worker scaling
- [ ] Verify log rotation
- [ ] Document rollback procedures

## Security Considerations

### Production Security Checklist

- [ ] Use strong, unique passwords for all services
- [ ] Enable Redis password authentication
- [ ] Enable PostgreSQL password authentication
- [ ] Configure CORS to only allow production domains
- [ ] Use HTTPS for all external communication
- [ ] Rotate secrets regularly
- [ ] Keep Docker images updated
- [ ] Limit container resource usage
- [ ] Use read-only filesystems where possible
- [ ] Enable audit logging
- [ ] Monitor for security vulnerabilities

## Advanced Configuration

### Custom Docker Registry

```bash
# Build with custom registry
docker build -t registry.example.com/wdfwatch-fastapi:latest -f backend/api/Dockerfile .
docker push registry.example.com/wdfwatch-fastapi:latest

# Update docker-compose.prod.yml to use custom image
```

### Kubernetes Deployment

For Kubernetes deployments, see `k8s/` directory (if available) or adapt docker-compose configuration to Kubernetes manifests.

### Load Balancing

For high availability, use a load balancer (nginx, Traefik, or cloud provider LB) in front of FastAPI and web services.

## Maintenance

### Regular Maintenance Tasks

- **Daily**: Monitor logs, check health endpoints
- **Weekly**: Review resource usage, check for updates
- **Monthly**: Rotate secrets, review security, update dependencies
- **Quarterly**: Full backup and restore test, disaster recovery drill

### Updates

```bash
# Pull latest code
git pull

# Rebuild images
make deploy-build

# Run migrations (if any)
make deploy-migrate

# Restart services
make deploy-restart
```

## Support

For issues or questions:

1. Check logs: `make deploy-logs`
2. Review health: `make deploy-health`
3. Check documentation: `docs/` directory
4. Review architecture: `ARCHITECTURE.md`

