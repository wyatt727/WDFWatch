# WDFWatch - AI-Powered Social Media Engagement Platform

An enterprise-grade AI pipeline for the "War, Divorce, or Federalism" podcast that discovers, classifies, and generates responses to relevant social media conversations. Features a modern web dashboard with human-in-the-loop moderation, configurable LLM models, and comprehensive analytics.

## 🚀 Key Features

- **Web Dashboard**: Full-featured Next.js interface for pipeline management
- **AI-Powered Classification**: Automatically identifies relevant tweets using configurable LLMs
- **Smart Response Generation**: Creates contextual, engaging responses under 280 characters
- **Human-in-the-Loop**: Approve, edit, or reject AI-generated content before publishing
- **Episode File Management**: Isolated file storage per episode prevents data conflicts
- **API Safety**: No automatic Twitter API calls - all scraping requires manual trigger
- **Tweet Cache System**: Test pipeline without API calls using cached data
- **Configurable Models**: Choose different LLMs for each pipeline task
- **Real-time Analytics**: Monitor performance, quota usage, and engagement metrics
- **Enterprise Security**: Encrypted API key storage with AES-256-CBC

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph WebUI[Web Dashboard]
        Episodes(Episode Management)
        Keywords(Keyword Configuration)
        Settings(Settings & API Keys)
        Analytics(Analytics Dashboard)
        Review(Tweet Review Interface)
    end
    
    subgraph Pipeline[AI Pipeline]
        Transcript(Transcript Analysis)
        FewShot(Few-shot Examples)
        Scrape(Tweet Discovery)
        Classify(Classification)
        Generate(Response Generation)
        Moderate(Human Moderation)
        Publish(Publishing)
        
        Transcript --> FewShot
        FewShot --> Scrape
        Scrape --> Classify
        Classify --> Generate
        Generate --> Moderate
        Moderate --> Publish
    end
    
    subgraph Storage[Data Layer]
        PostgreSQL[(PostgreSQL + pgvector)]
        FileSystem(File System Cache)
        TweetCache(Tweet Cache)
    end
    
    subgraph LLMs[AI Models]
        Gemini(Gemini 2.5 Pro)
        Ollama(Ollama Models)
    end
    
    Episodes --> Transcript
    Keywords --> Scrape
    Settings --> LLMs
    Review --> Moderate
    Analytics --> WebUI
    
    Transcript -.-> Gemini
    FewShot -.-> Gemini
    Classify -.-> Ollama
    Generate -.-> Ollama
    
    Pipeline --> Storage
    Scrape --> TweetCache
    Moderate --> PostgreSQL
    Publish --> PostgreSQL
```

## 🚦 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 16+ with pgvector extension
- Docker and Docker Compose
- Ollama (for local LLM inference)
- Redis (for rate limiting)

### Quick Start

1. **Clone and Install**
```bash
git clone https://github.com/wyatt727/WDFWatch.git
cd WDFWatch
make bootstrap  # Installs all dependencies
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start Services**
```bash
# Development mode
docker-compose up -d postgres redis ollama
cd web && npm run dev  # Web UI on http://localhost:3000
python main.py         # Run pipeline

# Production mode
docker-compose -f docker-compose.prod.yml up -d
```

4. **Configure via Web UI**
- Navigate to http://localhost:3000/settings
- Add API keys (Twitter/X, Gemini, OpenAI)
- Configure keywords for tweet discovery
- Select LLM models for each task

## 🎮 Usage Modes

### Web Dashboard (Recommended)

The modern web interface provides:
- **Episode Management**: Upload transcripts and trigger processing
- **Keyword Configuration**: Manage search terms with categories and priorities
- **Tweet Inbox**: Real-time classification results with filtering
- **Review Interface**: Approve/edit/reject AI responses
- **Analytics**: Track performance metrics and API usage
- **Settings**: Configure API keys, models, and scraping parameters

### CLI Mode (Legacy)

For automation and scripting:
```bash
# Full pipeline run
python main.py

# Episode-based pipeline run
python main.py --episode-id 123

# Individual tasks
python src/wdf/tasks/scrape.py --run-id=test-123 --episode-id 123
python src/wdf/tasks/classify.py --run-id=test-123 --episode-id 123
python src/wdf/tasks/deepseek.py --run-id=test-123 --episode-id 123

# With specific options
python main.py --debug --workers 4 --non-interactive --episode-id 123

# Migrate legacy files to episode structure
python scripts/migrate_episodes.py --episode-id 123
```

## 🔧 Configuration

### Environment Variables

```bash
# Core Settings
WDF_WEB_MODE=true                    # Enable web UI integration
WDF_NO_AUTO_SCRAPE=true              # Disable automatic Twitter API calls
WDF_MOCK_MODE=false                  # Use real Twitter API (when false)
WDF_GENERATE_SAMPLES=true            # Generate sample tweets for testing

# Infrastructure
WDF_OLLAMA_HOST=http://localhost:11434
WDF_REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://user:pass@localhost:5432/wdfwatch

# Security
ENCRYPTION_KEY=your-32-byte-key-here  # For API key encryption
WEB_API_KEY=your-internal-api-key     # Python<->Web communication

# LLM Models (can be configured via Web UI)
WDF_LLM_MODEL_SUMMARIZATION=gemini-2.5-pro
WDF_LLM_MODEL_CLASSIFICATION=gemma3n:e4b
WDF_LLM_MODEL_RESPONSE=deepseek-r1:latest
```

### API Keys Management

API keys are now managed through the Web UI at `/settings/api-keys`:
- Secure encryption before database storage
- Support for Twitter/X, Gemini, and OpenAI
- Keys are never exposed in logs or UI
- Python pipeline automatically loads keys from database

## 📊 Pipeline Workflow

### Episode File Management
Each episode has its own isolated file structure:
```
episodes/
├── 20250120-ep123-federal-overreach/
│   ├── inputs/               # User-uploaded files
│   ├── outputs/              # Generated files
│   └── pipeline-config.json  # File mappings
```

This prevents data conflicts when processing multiple episodes and enables:
- Parallel episode processing
- Easy file management via web UI
- Clear audit trails per episode
- Migration from legacy file structure

### 1. **Transcript Analysis** 
- Upload transcript via web dashboard
- Gemini 2.5 Pro generates comprehensive summary
- Extracts relevant keywords for tweet discovery

### 2. **Tweet Discovery** (Manual Trigger Required)
- Keywords loaded from database or UI
- Manual scraping trigger prevents accidental API usage
- Results cached for development/testing
- Intelligent cache with 90-day retention

### 3. **AI Classification**
- Configurable model (default: gemma3n:e4b)
- Binary classification: RELEVANT/SKIP
- Uses few-shot examples for context
- Parallel processing with worker threads

### 4. **Response Generation**
- Configurable model (default: deepseek-r1:latest)
- Creates engaging responses under 280 characters
- Includes podcast context and episode link
- Automatic retry with exponential backoff

### 5. **Human Review**
- Web-based approval interface
- Edit responses before publishing
- Audit trail of all actions
- Batch operations supported

### 6. **Publishing**
- Manual approval required
- Respects Twitter API rate limits
- Prevents duplicate posts
- Comprehensive error handling

## 🛠️ Development

### Project Structure
```
WDFWatch/
├── web/                    # Next.js web application
│   ├── app/               # App router pages
│   ├── components/        # React components
│   ├── lib/              # Utilities and database
│   └── prisma/           # Database schema
├── src/wdf/              # Python pipeline
│   ├── tasks/            # Pipeline stages
│   ├── settings.py       # Configuration
│   └── web_bridge.py     # Web integration
├── scripts/              # Utility scripts
├── transcripts/          # Input/output files
├── artefacts/            # Run artifacts
└── docker-compose.yml    # Service definitions
```

### Testing
```bash
# Python tests
make test

# Web UI tests
cd web && npm test

# Integration tests
WDF_MOCK_MODE=true python main.py --non-interactive
```

### Database Management
```bash
# Run migrations
cd web && npx prisma migrate dev

# Seed development data
cd web && npx prisma db seed

# View database
cd web && npx prisma studio
```

## 📈 Monitoring & Analytics

### Built-in Analytics Dashboard
- Tweet classification metrics
- Response approval rates
- Model performance comparison
- API quota usage tracking
- Pipeline execution times

### Prometheus Metrics
Available at `http://localhost:8000/metrics`:
- `processing_latency_seconds` - Pipeline stage timings
- `tweets_classified_total` - Classification counts
- `responses_generated_total` - Generation counts
- `tweets_published_total` - Publishing metrics

### Grafana Dashboard
Import `ops/grafana/wdf-dashboard.json` for visualization

## 🚀 Production Deployment

### Using Docker Compose
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# With monitoring stack
docker-compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

### Security Considerations
- All API keys encrypted at rest
- HTTPS enforced in production
- Rate limiting on all endpoints
- Audit logging for compliance
- No automatic external API calls

## 🔍 Troubleshooting

### Common Issues

**Tweet Cache Empty**
```bash
# Import existing tweets
python scripts/manage_tweet_cache.py import artefacts/*/tweets.json

# View cache statistics
python scripts/manage_tweet_cache.py stats
```

**API Keys Not Loading**
```bash
# Test key loading
python scripts/load_api_keys.py --show

# Validate configuration
eval $(python scripts/load_api_keys.py)
```

**Model Not Available**
```bash
# Validate all models
python scripts/validate_llm_models.py

# Pull missing Ollama model
ollama pull deepseek-r1:latest
```

### Logs
- Web UI: `web/logs/`
- Pipeline: `logs/pipeline.log`
- Docker: `docker-compose logs -f [service]`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

See `CONTRIBUTING.md` for detailed guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Anthropic Claude for AI capabilities
- The WDF Podcast team for domain expertise
- Open source community for amazing tools

---

For more information, visit the [documentation](docs/) or join our [Discord community](https://discord.gg/wdfpodcast).