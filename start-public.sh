#!/bin/bash
# WDFWatch Public Deployment Script

set -e

echo "🚀 Starting WDFWatch Public Deployment"
echo "======================================="

# Generate secure secrets if not already set
if [ ! -f .env.production.configured ]; then
    echo "⚙️  Generating secure secrets..."
    
    # Generate NEXTAUTH_SECRET
    NEXTAUTH_SECRET=$(openssl rand -base64 32)
    sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=$NEXTAUTH_SECRET|" .env.production
    
    # Generate ENCRYPTION_KEY
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env.production
    
    # Generate WEB_API_KEY
    WEB_API_KEY=$(openssl rand -hex 16)
    sed -i "s|WEB_API_KEY=.*|WEB_API_KEY=$WEB_API_KEY|" .env.production
    
    # Mark as configured
    touch .env.production.configured
    echo "✅ Secrets generated and saved"
else
    echo "ℹ️  Using existing secrets"
fi

# Load environment variables
export $(cat .env.production | grep -v '^#' | xargs)

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    echo "   Run: ./install-docker.sh"
    exit 1
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.public.yml down 2>/dev/null || true

# Build the web application
echo "🔨 Building web application..."
docker compose -f docker-compose.public.yml build web

# Start services
echo "🚀 Starting services..."
docker compose -f docker-compose.public.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🏥 Checking service health..."
docker compose -f docker-compose.public.yml ps

# Run database migrations
echo "📊 Running database migrations..."
docker compose -f docker-compose.public.yml exec -T web npx prisma migrate deploy || true

# Display access information
echo ""
echo "========================================="
echo "✅ WDFWatch is now publicly accessible!"
echo "========================================="
echo ""
echo "🌐 Web Interface: http://148.113.207.205:3000"
echo ""
echo "📝 Next Steps:"
echo "1. Access the web interface at the URL above"
echo "2. Configure API keys in Settings → API Keys"
echo "3. Upload a podcast transcript to start processing"
echo ""
echo "🔒 Security Notes:"
echo "- Change the default database password in .env.production"
echo "- Consider setting up SSL with a domain name"
echo "- Configure authentication if needed"
echo ""
echo "📋 Useful Commands:"
echo "- View logs: docker compose -f docker-compose.public.yml logs -f"
echo "- Stop services: docker compose -f docker-compose.public.yml down"
echo "- Restart services: docker compose -f docker-compose.public.yml restart"
echo ""