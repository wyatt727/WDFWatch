# WDFWatch Setup Guide

Complete guide for setting up WDFWatch in development and production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Docker Setup](#docker-setup)
- [Worker Scaling](#worker-scaling)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.11+**: For backend API and pipeline
- **Node.js 20+**: For Next.js web application
- **PostgreSQL 16+**: Database (or use Docker container)
- **Redis 7+**: Queue and cache (or use Docker container)
- **Docker & Docker Compose**: For containerized deployment (optional)

### Required Accounts

- **Anthropic Claude API**: For AI pipeline operations
- **Twitter API**: For tweet scraping and posting (optional)

## Development Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd WDFWatch
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend/api

# Install Python dependencies
pip install -r requirements.txt

# Or use poetry (if available)
poetry install
```

### 3. Frontend Setup

```bash
# Navigate to web directory
cd web

# Install Node.js dependencies
npm install

# Generate Prisma client
npx prisma generate
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Required variables:
# - DATABASE_URL: PostgreSQL connection string
# - REDIS_URL: Redis connection string
# - CLAUDE_CLI_PATH: Path to Claude CLI executable
# - API_KEY: Internal API authentication key
```

### 5. Database Setup

```bash
# Run migrations
cd web
npx prisma migrate dev

# Or deploy migrations in production
npx prisma migrate deploy
```

### 6. Start Services

**Terminal 1 - FastAPI Backend:**
```bash
cd backend/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 2 - RQ Worker:**
```bash
cd backend/api
python -m app.workers.worker default
```

**Terminal 3 - Next.js Frontend:**
```bash
cd web
npm run dev
```

### 7. Verify Setup

- FastAPI API: http://localhost:8001/docs
- Next.js Web: http://localhost:3000
- Health Check: http://localhost:8001/health/ready

## Docker Setup

### Quick Start

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Individual Services

```bash
# Start only database services
docker-compose up -d postgres redis

# Start API services
docker-compose up -d fastapi rq-worker

# Start web application
docker-compose up -d web
```

### Development with Docker

```bash
# Start infrastructure only
docker-compose up -d postgres redis

# Run API locally (connects to Docker services)
cd backend/api
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch \
REDIS_URL=redis://localhost:6379/0 \
uvicorn app.main:app --reload
```

## Worker Scaling

### Local Development

Run multiple workers:

```bash
# Terminal 1
python -m app.workers.worker default

# Terminal 2
python -m app.workers.worker default

# Terminal 3
python -m app.workers.worker default
```

### Docker Scaling

```bash
# Scale RQ workers to 4 instances
docker-compose up -d --scale rq-worker=4

# Or use Makefile
make deploy-scale WORKERS=4
```

### Production Scaling

For production, use:
- Docker Compose scaling
- Kubernetes deployments
- Cloud provider auto-scaling

## Configuration

### Environment Variables

**Backend API** (`backend/api/app/config.py`):
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CLAUDE_CLI_PATH`: Path to Claude CLI
- `JOB_TIMEOUT`: Job timeout in seconds (default: 3600)
- `JOB_MAX_RETRIES`: Max retry attempts (default: 3)
- `CORS_ALLOWED_ORIGINS`: Comma-separated allowed origins

**Next.js Web** (`web/.env.local`):
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `NEXTAUTH_SECRET`: NextAuth.js secret
- `NEXT_PUBLIC_API_URL`: FastAPI backend URL

### Claude CLI Setup

```bash
# Install Claude CLI (if not already installed)
# See: https://claude.ai/cli

# Verify installation
claude --version

# Set path in .env
CLAUDE_CLI_PATH=/path/to/claude
```

## Troubleshooting

### Common Issues

**1. Database Connection Errors**

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql -h localhost -U wdfwatch -d wdfwatch

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

**2. Redis Connection Errors**

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli ping

# Check REDIS_URL in .env
echo $REDIS_URL
```

**3. Worker Not Processing Jobs**

```bash
# Check worker logs
docker-compose logs rq-worker

# Check queue status
docker-compose exec fastapi python -c "from app.services.queue import get_queue; print(get_queue().count)"

# Restart worker
docker-compose restart rq-worker
```

**4. Migration Errors**

```bash
# Reset database (development only!)
cd web
npx prisma migrate reset

# Apply migrations
npx prisma migrate deploy
```

**5. Port Conflicts**

```bash
# Check what's using ports
lsof -i :8001  # FastAPI
lsof -i :3000  # Next.js
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# Stop conflicting services or change ports in docker-compose.yml
```

### Debug Mode

**Enable debug logging:**

```bash
# Backend
DEBUG=true uvicorn app.main:app --reload

# Next.js
DEBUG=* npm run dev
```

**View structured logs:**

```bash
# Backend logs (JSON format in production)
docker-compose logs -f fastapi | jq

# Worker logs
docker-compose logs -f rq-worker
```

## Next Steps

- Read [DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md) for production deployment
- Read [ARCHITECTURE.md](../ARCHITECTURE.md) for system architecture
- Read [CLAUDE.md](../CLAUDE.md) for Claude pipeline details

