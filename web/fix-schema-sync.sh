#!/bin/bash
# Fix schema synchronization issues

echo "🔧 Fixing schema synchronization..."
echo

# Add any missing columns that Prisma expects
echo "1. Adding missing columns..."
docker exec wdf-postgres psql -U wdfwatch -d wdfwatch -c "
-- Add updated_by column to settings if missing
ALTER TABLE settings ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100);

-- Ensure all timestamp columns exist
ALTER TABLE podcast_episodes ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE podcast_episodes ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
" > /dev/null 2>&1

echo "✅ Schema columns updated"

# Regenerate Prisma client
echo -e "\n2. Regenerating Prisma client..."
export DATABASE_URL="postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch?schema=public"
npx prisma generate > /dev/null 2>&1
echo "✅ Prisma client regenerated"

echo -e "\n🎉 Schema sync complete! Restart your Next.js server."