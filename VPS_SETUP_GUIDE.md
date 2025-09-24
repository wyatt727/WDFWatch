# WDFWatch VPS Setup Guide

## Migration from Docker Desktop to Linux VPS

This guide helps you set up WDFWatch on a Linux VPS, replacing Docker Desktop functionality with native Docker Engine.

## Prerequisites
- Debian 12 (Bookworm) VPS
- Root or sudo access
- At least 4GB RAM (8GB recommended for LLMs)
- 20GB+ free disk space

## Quick Start

### Step 1: Install Docker Engine
```bash
# Install Docker Engine (replaces Docker Desktop)
./install-docker.sh

# After installation, activate docker group (or logout/login)
newgrp docker
```

### Step 2: Set Up WDFWatch Environment
```bash
# Initialize all services (PostgreSQL, Redis, Ollama)
./setup-wdfwatch-env.sh
```

### Step 3: Install Node.js Dependencies
```bash
# Install Node.js if not present
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install web dependencies
cd web
npm install
```

### Step 4: Initialize Database
```bash
# Run database migrations
cd web
npx prisma migrate dev
cd ..
```

### Step 5: Start the Application

#### For Development (localhost only):
```bash
cd web
npm run dev
# Access at http://localhost:3000
```

#### For Public Access:
```bash
# Use the public deployment script
./start-public.sh
# Access at http://YOUR_VPS_IP:3000
```

## Architecture Differences

### Docker Desktop vs VPS Setup

| Component | Docker Desktop | VPS (Docker Engine) |
|-----------|---------------|-------------------|
| Docker GUI | ✅ Available | ❌ CLI only |
| Database | Container with GUI | Container with CLI |
| Network | Bridge networking | Host/Bridge networking |
| Resource Limits | Set via GUI | Set via docker-compose |
| Service Access | localhost | VPS IP or localhost |

## Service URLs

### Local Development:
- Web UI: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Ollama: http://localhost:11434

### Public Access:
- Web UI: http://YOUR_VPS_IP:3000
- PostgreSQL: Internal only (security)
- Redis: Internal only (security)
- Ollama: Internal only (security)

## Managing Services

### Start Services:
```bash
docker compose up -d
```

### Stop Services:
```bash
docker compose down
```

### View Logs:
```bash
docker compose logs -f [service_name]
# Examples:
docker compose logs -f postgres
docker compose logs -f web
```

### Check Status:
```bash
docker compose ps
```

### Access Database:
```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U wdfwatch -d wdfwatch

# Or use psql directly
psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch
```

### Manage Ollama Models:
```bash
# List models
docker exec wdfwatch-ollama ollama list

# Pull a model
docker exec wdfwatch-ollama ollama pull modelname

# Remove a model
docker exec wdfwatch-ollama ollama rm modelname
```

## Data Persistence

All data is stored in Docker volumes:
- `postgres_data`: Database files
- `redis_data`: Cache data
- `ollama_data`: LLM model files

### Backup Database:
```bash
docker compose exec postgres pg_dump -U wdfwatch wdfwatch > backup.sql
```

### Restore Database:
```bash
docker compose exec -T postgres psql -U wdfwatch wdfwatch < backup.sql
```

## Troubleshooting

### Docker Permission Issues:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login, or run:
newgrp docker
```

### Port Already in Use:
```bash
# Check what's using a port
sudo lsof -i :3000
# Kill the process or change the port in docker-compose.yml
```

### Database Connection Issues:
```bash
# Check if PostgreSQL is running
docker compose ps postgres
# Check logs
docker compose logs postgres
# Restart the service
docker compose restart postgres
```

### Out of Memory:
```bash
# Check memory usage
docker stats
# Adjust limits in docker-compose.yml under deploy.resources
```

## Security Considerations

1. **Change Default Passwords**: Edit `.env` and `.env.production`
2. **Firewall**: Consider using ufw or iptables to restrict access
3. **SSL/HTTPS**: Set up nginx with Let's Encrypt for production
4. **Authentication**: Configure NextAuth for user authentication
5. **Backup**: Regular database backups are recommended

## Next Steps

1. Configure API keys via Web UI (Settings → API Keys)
2. Upload podcast transcripts
3. Configure LLM models (Settings → LLM Models)
4. Set up keywords for Twitter monitoring
5. Start processing pipeline

## Support

For issues specific to VPS setup:
- Check Docker logs: `docker compose logs`
- Verify services: `docker compose ps`
- Test connectivity: `curl http://localhost:3000`

For WDFWatch issues:
- See main README.md
- Check logs in `logs/` directory
- Review pipeline status in Web UI