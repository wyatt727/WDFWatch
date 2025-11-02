# WDFWatch API Service

FastAPI backend service for WDFWatch pipeline operations.

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Run worker (in separate terminal)
python -m app.workers.worker

# Or use Makefile
make dev      # Run API server
make worker   # Run worker
```

## Environment Variables

The backend API loads environment variables from `.env` in the **project root** (not `backend/api/`).

The `.env` file should be in the project root directory (`/Users/pentester/Tools/WDFWatch/.env`), alongside `.env.wdfwatch` if you're using that optional file.

See `ENV_SETUP.md` in the project root for complete environment variable documentation.

**Key Variables**:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string  
- `WDF_REDIS_URL`: Redis URL for WDF pipeline (often same as REDIS_URL)
- `CLAUDE_CLI_PATH`: Path to Claude CLI executable
- `PROJECT_ROOT`: Auto-calculated from config file location (no need to set)

**Note**: The backend automatically calculates `PROJECT_ROOT` from the config file location, so you don't need to set it manually.

## API Endpoints

- `GET /health` - Health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe
- `POST /episodes/{id}/pipeline/run` - Run pipeline
- `GET /episodes/{id}/pipeline/status` - Get pipeline status
- `GET /events/{episode_id}` - SSE stream for events
- `POST /tweets/single/generate` - Generate single tweet response
- `GET /queue/jobs` - List jobs
- `GET /queue/jobs/{job_id}` - Get job status
- `GET /settings/llm-models` - Get LLM model config
- `PUT /settings/llm-models` - Update LLM model config

## Architecture

- **FastAPI**: REST API server
- **RQ**: Background job queue with Redis
- **Workers**: Background job processors
- **Events**: Redis pub/sub for real-time updates

## Project Structure

```
backend/api/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── routes/              # API routes
│   ├── services/            # Business logic
│   ├── workers/             # RQ workers
│   └── models/              # Pydantic models
├── requirements.txt
├── Dockerfile
└── Makefile
```

