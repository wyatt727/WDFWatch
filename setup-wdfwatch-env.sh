#!/bin/bash
# WDFWatch Environment Setup Script
# Sets up the complete environment after Docker installation

set -e

echo "🚀 WDFWatch Environment Setup"
echo "=============================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please install Docker first:"
    echo "   Run: ./install-docker.sh"
    exit 1
fi

echo "✅ Docker is installed and running"

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p web/prisma
mkdir -p transcripts
mkdir -p artefacts
mkdir -p logs
mkdir -p episodes

# Check if we have Prisma schema
if [ ! -f "web/prisma/schema.prisma" ]; then
    echo "📝 Creating Prisma schema..."
    cat > web/prisma/schema.prisma << 'EOF'
// This is your Prisma schema file
// Learn more about it in the docs: https://pris.ly/d/prisma-schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Episode {
  id             String   @id @default(cuid())
  title          String
  description    String?
  transcriptPath String?
  videoUrl       String?
  status         String   @default("pending")
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt
  
  tweets         Tweet[]
  drafts         DraftReply[]
}

model Tweet {
  id             String   @id @default(cuid())
  tweetId        String   @unique
  text           String
  authorUsername String
  authorName     String?
  createdAt      DateTime
  metrics        Json?
  classification String?
  score          Float?
  episodeId      String?
  
  episode        Episode? @relation(fields: [episodeId], references: [id])
  drafts         DraftReply[]
  
  @@index([classification])
  @@index([episodeId])
}

model DraftReply {
  id          String   @id @default(cuid())
  tweetId     String
  episodeId   String?
  content     String
  status      String   @default("pending") // pending, approved, rejected
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  
  tweet       Tweet    @relation(fields: [tweetId], references: [id])
  episode     Episode? @relation(fields: [episodeId], references: [id])
  
  @@index([status])
  @@index([tweetId])
}

model Settings {
  id        String   @id @default(cuid())
  key       String   @unique
  value     Json
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model AuditLog {
  id        String   @id @default(cuid())
  action    String
  entity    String
  entityId  String?
  userId    String?
  metadata  Json?
  createdAt DateTime @default(now())
  
  @@index([entity, entityId])
  @@index([userId])
  @@index([createdAt])
}
EOF
fi

# Create docker-compose override for development
echo "🐳 Creating Docker Compose configuration..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg16
    container_name: wdfwatch-postgres
    environment:
      POSTGRES_USER: wdfwatch
      POSTGRES_PASSWORD: wdfwatch_dev_2025
      POSTGRES_DB: wdfwatch
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U wdfwatch"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis for caching and queuing
  redis:
    image: redis:7-alpine
    container_name: wdfwatch-redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Ollama for local LLM
  ollama:
    image: ollama/ollama:latest
    container_name: wdfwatch-ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0
    deploy:
      resources:
        limits:
          memory: 8G

volumes:
  postgres_data:
  redis_data:
  ollama_data:
EOF

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "🔧 Creating .env file..."
    cat > .env << 'EOF'
# Development Environment Variables
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch?schema=public
REDIS_URL=redis://localhost:6379/0

# Application settings
WDF_MOCK_MODE=false
WDF_WEB_MODE=true
WDF_NO_AUTO_SCRAPE=true
NODE_ENV=development

# Ollama
WDF_OLLAMA_HOST=http://localhost:11434

# Web UI
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=development-secret-change-in-production
ENCRYPTION_KEY=development-key-32-bytes-change-it
WEB_API_KEY=development-api-key

# Python environment
WDF_REDIS_URL=redis://localhost:6379/0
EOF
    echo "✅ Created .env file"
else
    echo "ℹ️  Using existing .env file"
fi

echo ""
echo "🚀 Starting Docker services..."
docker compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

echo "📊 Checking service status..."
docker compose ps

echo ""
echo "🎯 Installing Ollama models (this may take a while)..."
# Pull the default models
docker exec wdfwatch-ollama ollama pull gemma2:2b 2>/dev/null || echo "Note: Model pulling will continue in background"
docker exec wdfwatch-ollama ollama pull deepseek-r1:1.5b 2>/dev/null || echo "Note: Model pulling will continue in background"

echo ""
echo "=============================="
echo "✅ WDFWatch Environment Ready!"
echo "=============================="
echo ""
echo "📋 Services running:"
echo "   - PostgreSQL: localhost:5432"
echo "   - Redis: localhost:6379"
echo "   - Ollama: localhost:11434"
echo ""
echo "🎯 Next steps:"
echo "   1. Install Node.js dependencies:"
echo "      cd web && npm install"
echo ""
echo "   2. Run database migrations:"
echo "      cd web && npx prisma migrate dev"
echo ""
echo "   3. Start the web interface:"
echo "      cd web && npm run dev"
echo ""
echo "   4. Access WDFWatch at:"
echo "      http://localhost:3000"
echo ""
echo "📝 For public access, run:"
echo "   ./start-public.sh"
echo ""
echo "🛑 To stop services:"
echo "   docker compose down"
echo ""