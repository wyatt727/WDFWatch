"""
Configuration management for WDFWatch API service.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Calculate project root relative to this config file
# This file is at: backend/api/app/config.py
# So project root is: backend/api/app/config.py -> .. -> .. -> .. -> project root
_CONFIG_FILE_PATH = Path(__file__).resolve()
_PROJECT_ROOT = _CONFIG_FILE_PATH.parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Project root - should be set to repository root
    PROJECT_ROOT: Path = _PROJECT_ROOT
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_RELOAD: bool = os.getenv("ENVIRONMENT", "development") == "development"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch"
    )
    # Remove Prisma-specific query parameters
    DATABASE_URL_CLEAN: str = DATABASE_URL.split("?")[0]
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")  # Optional Redis password
    
    # Pipeline Configuration
    CLAUDE_PIPELINE_DIR: Path = PROJECT_ROOT / "claude-pipeline"
    EPISODES_DIR: Path = CLAUDE_PIPELINE_DIR / "episodes"
    ORCHESTRATOR_PATH: Path = CLAUDE_PIPELINE_DIR / "orchestrator.py"
    
    # Claude CLI
    CLAUDE_CLI_PATH: str = os.getenv("CLAUDE_CLI_PATH", "/Users/pentester/.claude/local/claude")
    CLAUDE_TIMEOUT: int = int(os.getenv("CLAUDE_TIMEOUT", "1800"))  # 30 minutes default
    
    # Job Queue
    JOB_TIMEOUT: int = int(os.getenv("JOB_TIMEOUT", "3600"))  # 1 hour default
    JOB_RESULT_TTL: int = int(os.getenv("JOB_RESULT_TTL", "86400"))  # 24 hours
    JOB_MAX_RETRIES: int = int(os.getenv("JOB_MAX_RETRIES", "3"))  # Max retry attempts
    JOB_RETRY_DELAY: int = int(os.getenv("JOB_RETRY_DELAY", "30"))  # Initial retry delay in seconds
    JOB_RETRY_BACKOFF: float = float(os.getenv("JOB_RETRY_BACKOFF", "2.0"))  # Exponential backoff multiplier
    
    # Web UI Integration
    WEB_URL: str = os.getenv("WEB_URL", "http://localhost:3000")
    WEB_API_KEY: str = os.getenv("WEB_API_KEY", "development-internal-api-key")
    
    # Security
    API_KEY: Optional[str] = os.getenv("API_KEY")  # For internal API auth
    
    # CORS Configuration
    CORS_ALLOWED_ORIGINS: list[str] = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001"
    ).split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else [
        "http://localhost:3000",
        "http://localhost:3001"
    ]
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    class Config:
        # Load .env from project root (where all environment files are located)
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings

