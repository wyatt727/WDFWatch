# Fix PostgreSQL Permission Issues

## Problem
Getting "User `wdfwatch` was denied access on the database `wdfwatch.public`" error even though:
- Environment variables are loaded correctly
- PostgreSQL container is running
- Database and user exist

## Root Cause
The pgvector/pgvector:pg16 Docker image has different permission defaults that conflict with Prisma's expectations.

## Solution

### Option 1: Use Standard PostgreSQL Image (Recommended)

1. **Update docker-compose.yml**:
   Change from:
   ```yaml
   image: pgvector/pgvector:pg16
   ```
   To:
   ```yaml
   image: postgres:16-alpine
   ```

2. **Recreate the container**:
   ```bash
   docker-compose down postgres
   docker volume rm wdfwatch_postgres-data
   docker-compose up -d postgres
   ```

3. **Wait for initialization then push schema**:
   ```bash
   sleep 10
   cd web
   npx prisma db push
   ```

### Option 2: Manual Permission Fix

If you need to keep pgvector, run these commands after container starts:

```bash
# Fix ownership and permissions
docker exec wdf-postgres psql -U wdfwatch -d postgres -c "
ALTER DATABASE wdfwatch OWNER TO wdfwatch;
GRANT ALL PRIVILEGES ON DATABASE wdfwatch TO wdfwatch;
"

docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "
ALTER SCHEMA public OWNER TO wdfwatch;
GRANT ALL ON SCHEMA public TO wdfwatch;
GRANT CREATE ON SCHEMA public TO wdfwatch;
"

# Then push schema
cd web
npx prisma db push
```

### Option 3: Use Prisma Migrate Instead

Sometimes `db push` has issues with permissions. Try using migrate:

```bash
cd web
npx prisma migrate dev --name init
```

## Verify Fix

After applying the fix, your Next.js app should connect successfully and you should see no more permission errors in the console.