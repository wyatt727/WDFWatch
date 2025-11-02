"""
FastAPI application entry point for WDFWatch API service.
Provides REST API endpoints for pipeline operations and job management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logging import configure_logging
from app.routes import health, episodes, events, tweets, queue, settings as settings_routes

# Configure structured logging
configure_logging()

# Configure logging
import structlog
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting WDFWatch API service")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Project root: {settings.PROJECT_ROOT}")
    logger.info(f"Episodes directory: {settings.EPISODES_DIR}")
    
    # Ensure episodes directory exists
    settings.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    
    yield
    
    logger.info("Shutting down WDFWatch API service")


# Create FastAPI app
app = FastAPI(
    title="WDFWatch API",
    description="REST API for WDFWatch pipeline operations",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(episodes.router, prefix="/episodes", tags=["episodes"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(tweets.router, prefix="/tweets", tags=["tweets"])
app.include_router(queue.router, prefix="/queue", tags=["queue"])
app.include_router(settings_routes.router, prefix="/settings", tags=["settings"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if settings.DEBUG else None},
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "WDFWatch API",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )

