# Alternative Fix: Use Different Port for Docker PostgreSQL

If you need to keep your local PostgreSQL running, use a different port for Docker.

## Step 1: Update docker-compose.yml

Change the PostgreSQL port mapping from 5432 to 5433:

```yaml
postgres:
  image: postgres:16-alpine
  container_name: wdf-postgres
  ports:
    - "5433:5432"  # Changed from "5432:5432"
```

## Step 2: Recreate Container

```bash
docker-compose down postgres
docker-compose up -d postgres
```

## Step 3: Update .env.local

Change the DATABASE_URL to use port 5433:

```
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5433/wdfwatch?schema=public&connection_limit=1
```

## Step 4: Fix Permissions

```bash
# Wait for container to start
sleep 5

# Fix permissions
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "
ALTER SCHEMA public OWNER TO wdfwatch;
GRANT ALL ON SCHEMA public TO wdfwatch;
"

# Generate Prisma client
export DATABASE_URL="postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5433/wdfwatch?schema=public"
npx prisma generate
```

## Step 5: Restart Next.js

```bash
npm run dev
```

This way both PostgreSQL instances can coexist:
- Local PostgreSQL: localhost:5432
- Docker PostgreSQL: localhost:5433