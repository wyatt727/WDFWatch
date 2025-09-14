#!/bin/bash
# Production Deployment Script for WDFWatch
# Part of Phase 4 Production Infrastructure Setup
#
# Usage:
#   ./scripts/deploy-production.sh [command]
#
# Commands:
#   setup     - Initial setup of production environment
#   deploy    - Deploy or update the application
#   backup    - Create a backup of the database
#   restore   - Restore from a backup
#   status    - Check status of all services
#   logs      - View logs from all services

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_NAME="wdfwatch-prod"
BACKUP_DIR="./backups"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check for environment file
    if [ ! -f ".env.production" ]; then
        log_error ".env.production file not found. Please create it from .env.production.example"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

setup_production() {
    log_info "Setting up production environment..."
    
    # Create necessary directories
    mkdir -p nginx/ssl
    mkdir -p monitoring/prometheus
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/grafana/datasources
    mkdir -p scripts
    mkdir -p "$BACKUP_DIR"
    
    # Generate self-signed SSL certificate if none exists
    if [ ! -f "nginx/ssl/fullchain.pem" ]; then
        log_warn "No SSL certificate found. Generating self-signed certificate..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/privkey.pem \
            -out nginx/ssl/fullchain.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=wdfwatch.example.com"
    fi
    
    # Create monitoring configuration
    create_monitoring_config
    
    # Pull all images
    log_info "Pulling Docker images..."
    docker-compose -f "$COMPOSE_FILE" pull
    
    # Initialize database
    log_info "Initializing database..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres
    sleep 10  # Wait for PostgreSQL to start
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" run --rm web npm run db:push
    
    log_info "Setup completed successfully!"
}

create_monitoring_config() {
    # Create Prometheus configuration
    cat > monitoring/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'web'
    static_configs:
      - targets: ['web:3000']
    metrics_path: '/api/metrics'

  - job_name: 'pipeline'
    static_configs:
      - targets: ['pipeline:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']
EOF

    # Create Grafana datasource
    mkdir -p monitoring/grafana/datasources
    cat > monitoring/grafana/datasources/prometheus.yml <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF
}

deploy_application() {
    log_info "Deploying WDFWatch..."
    
    check_prerequisites
    
    # Load environment variables
    set -a
    source .env.production
    set +a
    
    # Build images
    log_info "Building Docker images..."
    docker-compose -f "$COMPOSE_FILE" build
    
    # Start services
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 30
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" exec web npm run db:push
    
    # Download Ollama models
    log_info "Downloading Ollama models..."
    docker-compose -f "$COMPOSE_FILE" exec ollama ollama pull gemma3n:e4b
    docker-compose -f "$COMPOSE_FILE" exec ollama ollama pull deepseek-r1:latest
    
    # Check deployment status
    check_status
    
    log_info "Deployment completed successfully!"
    log_info "Application is available at: https://wdfwatch.example.com"
    log_info "Grafana is available at: http://localhost:3001 (admin/${GRAFANA_PASSWORD})"
}

backup_database() {
    log_info "Creating database backup..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/wdfwatch_backup_$TIMESTAMP.sql"
    
    # Create backup
    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        > "$BACKUP_FILE"
    
    # Compress backup
    gzip "$BACKUP_FILE"
    
    log_info "Backup created: ${BACKUP_FILE}.gz"
    
    # Clean old backups (keep last 7 days)
    find "$BACKUP_DIR" -name "wdfwatch_backup_*.sql.gz" -mtime +7 -delete
}

restore_database() {
    if [ -z "${1:-}" ]; then
        log_error "Please provide backup file path"
        echo "Usage: $0 restore <backup_file>"
        exit 1
    fi
    
    BACKUP_FILE="$1"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    log_warn "This will restore the database from: $BACKUP_FILE"
    log_warn "All current data will be lost!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    log_info "Restoring database..."
    
    # Decompress if needed
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        gunzip -c "$BACKUP_FILE" | docker-compose -f "$COMPOSE_FILE" exec -T postgres psql \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB"
    else
        docker-compose -f "$COMPOSE_FILE" exec -T postgres psql \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            < "$BACKUP_FILE"
    fi
    
    log_info "Database restored successfully"
}

check_status() {
    log_info "Checking service status..."
    
    # Check Docker containers
    docker-compose -f "$COMPOSE_FILE" ps
    
    # Check web health
    if curl -f -s http://localhost:3000/api/health > /dev/null; then
        log_info "Web service: ${GREEN}Healthy${NC}"
    else
        log_error "Web service: Unhealthy"
    fi
    
    # Check database connection
    if docker-compose -f "$COMPOSE_FILE" exec postgres pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
        log_info "Database: ${GREEN}Ready${NC}"
    else
        log_error "Database: Not ready"
    fi
    
    # Check Redis
    if docker-compose -f "$COMPOSE_FILE" exec redis redis-cli ping > /dev/null 2>&1; then
        log_info "Redis: ${GREEN}Ready${NC}"
    else
        log_error "Redis: Not ready"
    fi
}

view_logs() {
    SERVICE="${1:-}"
    
    if [ -z "$SERVICE" ]; then
        # Show logs from all services
        docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
    else
        # Show logs from specific service
        docker-compose -f "$COMPOSE_FILE" logs -f --tail=100 "$SERVICE"
    fi
}

# Main script logic
case "${1:-}" in
    setup)
        setup_production
        ;;
    deploy)
        deploy_application
        ;;
    backup)
        backup_database
        ;;
    restore)
        restore_database "${2:-}"
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs "${2:-}"
        ;;
    *)
        echo "WDFWatch Production Deployment Script"
        echo ""
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  setup     - Initial setup of production environment"
        echo "  deploy    - Deploy or update the application"
        echo "  backup    - Create a backup of the database"
        echo "  restore   - Restore from a backup"
        echo "  status    - Check status of all services"
        echo "  logs      - View logs from all services"
        echo ""
        echo "Examples:"
        echo "  $0 setup                          # Initial setup"
        echo "  $0 deploy                         # Deploy application"
        echo "  $0 backup                         # Create backup"
        echo "  $0 restore backups/backup.sql.gz  # Restore from backup"
        echo "  $0 logs web                       # View web service logs"
        ;;
esac