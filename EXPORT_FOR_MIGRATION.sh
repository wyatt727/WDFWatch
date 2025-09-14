#!/bin/bash

# PostgreSQL Export Script - Run this BEFORE migration on CURRENT server
# This creates the PostgreSQL dump that was missing from your migration

echo "=== WDFWatch PostgreSQL Export for Migration ==="
echo ""

# Check for Docker PostgreSQL
if docker ps | grep -q postgres; then
    echo "Found PostgreSQL in Docker"

    # Export from Docker PostgreSQL
    echo "Exporting database from Docker container..."
    docker exec wdfwatch-postgres pg_dump \
        -U wdfwatch \
        -d wdfwatch \
        --no-owner \
        --no-privileges \
        --verbose \
        > wdfwatch_postgresql_$(date +%Y%m%d_%H%M%S).sql

    if [ $? -eq 0 ]; then
        DUMP_FILE=$(ls -t wdfwatch_postgresql_*.sql | head -1)
        gzip $DUMP_FILE
        echo "✅ Database exported to: ${DUMP_FILE}.gz"
        echo ""
        echo "Add this file to your migration package before transferring!"
    fi
else
    # Export from local PostgreSQL
    echo "Enter PostgreSQL connection details:"
    read -p "Database name (default: wdfwatch): " DB_NAME
    DB_NAME=${DB_NAME:-wdfwatch}
    read -p "Database user (default: wdf): " DB_USER
    DB_USER=${DB_USER:-wdf}
    read -sp "Database password: " DB_PASS
    echo

    PGPASSWORD=$DB_PASS pg_dump \
        -h localhost \
        -U $DB_USER \
        -d $DB_NAME \
        --no-owner \
        --no-privileges \
        --verbose \
        > wdfwatch_postgresql_$(date +%Y%m%d_%H%M%S).sql

    if [ $? -eq 0 ]; then
        DUMP_FILE=$(ls -t wdfwatch_postgresql_*.sql | head -1)
        gzip $DUMP_FILE
        echo "✅ Database exported to: ${DUMP_FILE}.gz"
    fi
fi