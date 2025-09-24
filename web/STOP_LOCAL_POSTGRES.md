# Stop Local PostgreSQL - Required Fix

## Problem Identified
You have **PostgreSQL 15 running locally** via Homebrew, which is blocking the Docker PostgreSQL container.

### Current Status:
- ✅ Docker PostgreSQL is running on port 5432
- ❌ Local PostgreSQL 15 is ALSO running on port 5432
- ❌ Local PostgreSQL is taking precedence for localhost connections

## Solution: Stop Local PostgreSQL

Run this command:
```bash
brew services stop postgresql@15
```

## Verify It's Stopped

1. Check services:
   ```bash
   brew services list | grep postgres
   # Should show "stopped" or "none" for postgresql@15
   ```

2. Check port 5432:
   ```bash
   lsof -i :5432 | grep LISTEN
   # Should only show com.docke (Docker)
   ```

3. Test Docker PostgreSQL connection:
   ```bash
   psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch -c "SELECT 1;"
   # Should return:
   #  ?column? 
   # ----------
   #         1
   ```

## After Stopping Local PostgreSQL

1. **Restart your Next.js server**:
   ```bash
   # Stop current server (Ctrl+C)
   npm run dev
   ```

2. **If you still get errors**, run the database fix:
   ```bash
   ./fix-database.sh
   ```

## Prevent Future Issues

To prevent PostgreSQL from starting automatically:
```bash
brew services stop postgresql@15
brew unlink postgresql@15  # Optional: removes from PATH
```

Or if you need local PostgreSQL for other projects, configure Docker to use a different port (5433) in docker-compose.yml.