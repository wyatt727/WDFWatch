#!/bin/bash
# Complete fix for WDFWatch database permission issues

echo "=== Fixing WDFWatch Database Permissions ==="

# 1. Fix database permissions
echo "Step 1: Fixing database permissions..."
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "
-- Change schema ownership
ALTER SCHEMA public OWNER TO wdfwatch;

-- Grant all privileges on schema
GRANT ALL ON SCHEMA public TO wdfwatch;
GRANT CREATE ON SCHEMA public TO wdfwatch;

-- Grant privileges on all tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wdfwatch;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wdfwatch;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO wdfwatch;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO wdfwatch;
"

# 2. Test the connection
echo -e "\nStep 2: Testing database connection..."
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "SELECT current_database(), current_user, has_database_privilege(current_user, current_database(), 'CREATE');"

# 3. Generate Prisma client with environment variable
echo -e "\nStep 3: Generating Prisma client..."
export DATABASE_URL="postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch?schema=public"
npx prisma generate

echo -e "\n=== Database fix complete! ==="
echo "Now restart your Next.js server with: npm run dev"