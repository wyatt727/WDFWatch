#!/bin/bash
# Quick fix for PostgreSQL port conflict

echo "🔧 Fixing PostgreSQL port conflict..."
echo

# Stop local PostgreSQL
echo "1. Stopping local PostgreSQL..."
brew services stop postgresql@15
sleep 2

# Verify only Docker is listening
echo -e "\n2. Verifying port 5432..."
LISTENERS=$(lsof -i :5432 | grep LISTEN | wc -l)
if [ "$LISTENERS" -eq "1" ]; then
    echo "✅ Only Docker PostgreSQL is running"
else
    echo "⚠️  Multiple processes on port 5432:"
    lsof -i :5432 | grep LISTEN
fi

# Test connection
echo -e "\n3. Testing Docker PostgreSQL connection..."
if psql postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch -c "SELECT 'Connection successful!' as status;" 2>/dev/null; then
    echo "✅ Database connection successful!"
    
    # Run permission fixes
    echo -e "\n4. Fixing database permissions..."
    docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "
    ALTER SCHEMA public OWNER TO wdfwatch;
    GRANT ALL ON SCHEMA public TO wdfwatch;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wdfwatch;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wdfwatch;
    " > /dev/null 2>&1
    echo "✅ Permissions fixed"
    
    # Generate Prisma client
    echo -e "\n5. Regenerating Prisma client..."
    export DATABASE_URL="postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch?schema=public"
    npx prisma generate > /dev/null 2>&1
    echo "✅ Prisma client generated"
    
    echo -e "\n🎉 All fixed! Now restart your Next.js server:"
    echo "   npm run dev"
else
    echo "❌ Connection failed. Run ./diagnose-postgres.sh for details"
fi