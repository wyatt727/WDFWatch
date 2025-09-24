# WDFWatch Web UI

Modern web interface for the WDFWatch Twitter engagement pipeline, built with Next.js 14, TypeScript, and PostgreSQL.

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- Docker (optional, for containerized development)

### Development Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set up environment variables**
   ```bash
   cp env.example .env.local
   # Edit .env.local with your database credentials
   ```

3. **Initialize database**
   ```bash
   # Using Docker
   docker-compose up postgres -d
   
   # Run migrations
   npm run db:push
   ```

4. **Start development server**
   ```bash
   npm run dev
   ```

   Visit http://localhost:3000

### Using Docker

```bash
# Start all services (PostgreSQL, Redis, Web UI)
docker-compose up web

# Or run everything in background
docker-compose up -d
```

## 📁 Project Structure

```
web/
├── app/                    # Next.js App Router pages
│   ├── (dashboard)/       # Dashboard routes with layout
│   │   ├── inbox/         # Tweet discovery interface
│   │   ├── review/        # Draft approval workflow
│   │   └── episodes/      # Episode management
│   └── api/               # API route handlers
├── components/            # React components
│   ├── tweets/           # Tweet-related components
│   ├── drafts/           # Draft management components
│   └── layout/           # Layout components (nav, header)
├── hooks/                # Custom React hooks
├── lib/                  # Utilities and configurations
├── prisma/               # Database schema and migrations
└── public/               # Static assets
```

## 🛠️ Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript compiler check
- `npm run db:push` - Push schema changes to database
- `npm run db:migrate` - Run database migrations
- `npm run db:studio` - Open Prisma Studio GUI

## 🔄 Data Migration

Migrate existing data from JSON files to PostgreSQL:

```bash
# Run migration script
python ../scripts/migrate_data.py

# Validate migration
python ../scripts/validate_migration.py
```

## 🎯 Key Features

- **Real-time Updates**: Server-Sent Events for live status changes
- **Quota Management**: Visual Twitter API quota tracking
- **Human-in-the-Loop**: Interactive draft approval workflow
- **Audit Trail**: Complete action history for compliance
- **Performance**: Optimized with React Query caching
- **Accessibility**: WCAG AA compliant with keyboard navigation

## 🧪 Testing

```bash
# Run unit tests
npm test

# Run integration tests
npm run test:integration

# Run E2E tests
npm run test:e2e
```

## 📊 Database Schema

Key tables:
- `podcast_episodes` - Episode data with embeddings
- `tweets` - Discovered tweets with classification
- `draft_replies` - AI-generated responses
- `audit_log` - Complete action history
- `quota_usage` - API quota tracking

See `prisma/schema.prisma` for full schema definition.

## 🚢 Production Deployment

1. Build the application:
   ```bash
   npm run build
   ```

2. Set production environment variables

3. Run database migrations:
   ```bash
   npm run db:migrate:deploy
   ```

4. Start the server:
   ```bash
   npm start
   ```

## 📝 Environment Variables

See `env.example` for all available environment variables. Key variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection for caching
- `NEXTAUTH_SECRET` - Authentication secret
- `PYTHON_API_URL` - Python backend API URL

## 🤝 Contributing

1. Follow the existing code style (Prettier + ESLint)
2. Write tests for new features
3. Update documentation as needed
4. Submit PR with clear description

## 📄 License

[Same as parent project]