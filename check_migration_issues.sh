#!/bin/bash

echo "=== Checking Migration Issues ==="

# 1. Check directories exist
echo -e "\n1. Directory Structure:"
ls -la claude-pipeline/ 2>/dev/null | head -5
ls -la claude-pipeline/episodes/ 2>/dev/null | head -3

# 2. Check Docker volumes
echo -e "\n2. Docker Volumes:"
docker inspect wdf-web 2>/dev/null | grep -A5 "Mounts"

# 3. Check database constraints
echo -e "\n3. Database Constraints:"
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "\d podcast_episodes" 2>/dev/null | grep -E "(UNIQUE|FOREIGN|PRIMARY)"

# 4. Check environment variables
echo -e "\n4. Critical Environment Variables:"
grep -E "(UPLOAD|WEB_API_KEY|DATABASE_URL)" web/.env 2>/dev/null | head -5

# 5. Check Redis
echo -e "\n5. Redis Status:"
docker ps | grep redis

# 6. Check file permissions
echo -e "\n6. File Permissions:"
stat -c "%a %U %G %n" claude-pipeline/episodes 2>/dev/null

# 7. Check API endpoint
echo -e "\n7. API Health Check:"
curl -s http://localhost:3000/api/health 2>/dev/null || echo "API not responding"

# 8. Check logs
echo -e "\n8. Recent Web Errors:"
docker logs wdf-web 2>&1 | grep -i error | tail -5
