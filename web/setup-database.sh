#!/bin/bash
# Setup script for WDFWatch database

echo "Setting up WDFWatch database..."

# Export environment variables
export DATABASE_URL="postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch"
export REDIS_URL="redis://localhost:6379/0"

# Generate Prisma client
echo "Generating Prisma client..."
npx prisma generate

# Push database schema
echo "Pushing database schema..."
npx prisma db push

echo "Database setup complete!"