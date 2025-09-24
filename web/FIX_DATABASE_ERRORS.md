# Fix for Persistent DATABASE_URL Errors

Since you've already copied the .env.local file but are still seeing errors, here's a comprehensive solution:

## 1. Stop All Running Processes

First, completely stop any running Next.js dev servers:
```bash
# Kill any running Next.js processes
pkill -f "next dev" || true
```

## 2. Clear Next.js Cache

```bash
cd /Users/pentester/Tools/WDFWatch/web
rm -rf .next
rm -rf node_modules/.cache
```

## 3. Regenerate Prisma Client

```bash
npx prisma generate
```

## 4. Verify Database is Running

```bash
# Check if PostgreSQL container is running
docker ps | grep wdf-postgres

# If not running, start it:
cd /Users/pentester/Tools/WDFWatch
docker-compose up postgres -d
```

## 5. Test Database Connection

```bash
# Test the connection directly
npx prisma db push --skip-generate
```

## 6. Start Fresh Development Server

```bash
npm run dev
```

## Alternative: Use Direct Environment Variables

If the above doesn't work, try running with environment variables directly:

```bash
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch npm run dev
```

## If Still Having Issues

The build-output.txt shows these are runtime errors, not build-time errors. This suggests the environment variables aren't being loaded properly by Next.js. Try:

1. **Check Node Version**: Ensure you're using Node.js 18+ (required for Next.js 14)
   ```bash
   node --version
   ```

2. **Reinstall Dependencies**:
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

3. **Use Environment Variable Debugging**:
   Create a test API route at `web/app/api/test-env/route.ts`:
   ```typescript
   export async function GET() {
     return Response.json({
       hasDbUrl: !!process.env.DATABASE_URL,
       nodeEnv: process.env.NODE_ENV,
       cwd: process.cwd()
     })
   }
   ```
   Then visit http://localhost:3000/api/test-env to debug.