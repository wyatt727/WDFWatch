# FINAL Database Fix - Port Conflict Resolution

## The Real Problem
You have **TWO PostgreSQL instances** running:
1. A local PostgreSQL on your Mac (using port 5432)
2. The Docker PostgreSQL container (also trying to use port 5432)

When you connect to `localhost:5432`, you're connecting to the **local PostgreSQL** which doesn't have the `wdfwatch` user, not the Docker container!

## Solution Options

### Option 1: Stop Local PostgreSQL (Recommended)
```bash
# Stop the local PostgreSQL service
brew services stop postgresql@16
# OR if installed differently:
sudo -u postgres pg_ctl stop -D /usr/local/var/postgres
```

Then test the connection to Docker PostgreSQL:
```bash
psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch -c "SELECT 1;"
```

### Option 2: Use Different Port for Docker PostgreSQL
1. Update `docker-compose.yml`:
   ```yaml
   postgres:
     ports:
       - "5433:5432"  # Changed from 5432:5432
   ```

2. Update `.env.local`:
   ```
   DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5433/wdfwatch?schema=public
   ```

3. Restart Docker container:
   ```bash
   docker-compose down postgres
   docker-compose up -d postgres
   ```

### Option 3: Use Docker Container IP Directly
Update `.env.local` to use the container's IP:
```
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@172.21.0.2:5432/wdfwatch?schema=public
```

## Recommended Fix Steps

1. **Stop local PostgreSQL**:
   ```bash
   brew services stop postgresql
   # OR
   brew services stop postgresql@14
   brew services stop postgresql@15
   brew services stop postgresql@16
   ```

2. **Verify only Docker PostgreSQL is running**:
   ```bash
   lsof -i :5432
   # Should only show com.docke process
   ```

3. **Copy the corrected env file**:
   ```bash
   cp env.local.txt .env.local
   ```

4. **Restart Next.js**:
   ```bash
   npm run dev
   ```

## Why This Happened
- macOS often has PostgreSQL installed via Homebrew
- Both local and Docker PostgreSQL default to port 5432
- The local instance takes precedence for localhost connections
- Prisma was trying to connect to the wrong PostgreSQL instance

## Verification
After fixing, this should work:
```bash
psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch -c "\\dt"
```

And show the WDFWatch tables.