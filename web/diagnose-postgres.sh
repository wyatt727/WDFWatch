#!/bin/bash
# Diagnostic script for PostgreSQL connection issues

echo "=== PostgreSQL Connection Diagnostic ==="
echo

# 1. Check what's listening on port 5432
echo "1. Checking port 5432..."
lsof -i :5432 | grep LISTEN
echo

# 2. Check brew services
echo "2. Checking brew services..."
brew services list | grep postgres
echo

# 3. Try to connect to PostgreSQL
echo "3. Testing connection to localhost:5432..."
psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch -c "SELECT current_user, current_database();" 2>&1
echo

# 4. Check Docker container
echo "4. Checking Docker PostgreSQL container..."
docker ps | grep postgres
echo

# 5. Test connection to Docker directly
echo "5. Testing connection to Docker PostgreSQL..."
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "SELECT current_user, current_database();"
echo

# 6. Check Docker container IP
echo "6. Getting Docker container IP..."
DOCKER_IP=$(docker inspect wdf-postgres | grep -A 5 '"IPAddress"' | grep -E '"IPAddress": "[0-9]' | head -1 | awk -F'"' '{print $4}')
echo "Docker PostgreSQL IP: $DOCKER_IP"
echo

# 7. Test connection using Docker IP
echo "7. Testing connection using Docker IP..."
if [ ! -z "$DOCKER_IP" ]; then
    psql postgresql://wdfwatch:wdfwatch_dev_2025@$DOCKER_IP:5432/wdfwatch -c "SELECT 1;" 2>&1
fi
echo

echo "=== Diagnostic Complete ==="
echo
echo "Next Steps:"
echo "1. If you see 'postgres' process on port 5432, run: brew services stop postgresql@15"
echo "2. If connection to Docker IP works but localhost doesn't, use the Docker IP in your .env.local"
echo "3. Or change Docker port to 5433 in docker-compose.yml"