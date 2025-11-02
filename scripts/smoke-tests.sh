#!/usr/bin/env bash
# Smoke tests for deployment validation
# Runs integration tests against docker-compose stack

set -e

echo "Starting deployment smoke tests..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=0
    
    echo -e "${YELLOW}Waiting for $service to be ready...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service is ready${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}✗ $service failed to become ready${NC}"
    return 1
}

# Start services
echo -e "${YELLOW}Starting Docker Compose services...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check PostgreSQL
check_service "PostgreSQL" "http://localhost:5432" || exit 1

# Check Redis
check_service "Redis" "http://localhost:6379" || exit 1

# Check FastAPI
check_service "FastAPI" "http://localhost:8001/health/ready" || exit 1

# Check Next.js
check_service "Next.js" "http://localhost:3000/api/health" || exit 1

# Run integration tests
echo -e "${YELLOW}Running integration tests...${NC}"
cd backend/api
pytest tests/test_integration.py -v || {
    echo -e "${RED}Integration tests failed${NC}"
    exit 1
}

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
cd ../../web
npx prisma migrate deploy || {
    echo -e "${RED}Migrations failed${NC}"
    exit 1
}

# Test API endpoints
echo -e "${YELLOW}Testing API endpoints...${NC}"

# Health check
curl -f http://localhost:8001/health/ready || exit 1

# Metrics endpoint
curl -f http://localhost:8001/health/metrics || exit 1

# Web health check
curl -f http://localhost:3000/api/health || exit 1

echo -e "${GREEN}All smoke tests passed!${NC}"

# Cleanup (optional)
read -p "Stop Docker Compose services? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose -f docker-compose.prod.yml down
fi

