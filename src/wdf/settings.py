"""
WDF Pipeline settings module

This module provides a typed configuration interface using pydantic-settings.
Configuration can be loaded from settings.toml or environment variables.
"""

import os
from pathlib import Path

# Fix DEBUG environment variable conflict with Next.js/Prisma
# Prisma sets DEBUG='prisma:client' which breaks Pydantic boolean parsing
if os.getenv("DEBUG") and not os.getenv("DEBUG").lower() in ["true", "false", "1", "0"]:
    # Save the original value if needed for debugging
    _original_debug = os.getenv("DEBUG")
    # Clear it to prevent Pydantic validation error
    del os.environ["DEBUG"]

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMModels(BaseSettings):
    """LLM model configuration"""
    # Legacy model names for backward compatibility
    gemini: str = "gemini-2.5-pro"
    gemma: str = "gemma3n:e4b"
    deepseek: str = "deepseek-r1:latest"
    
    # Task-specific model configuration
    summarization: str = "gemini-2.5-pro"
    fewshot: str = "gemini-2.5-pro"
    classification: str = "gemma3n:e4b"
    response: str = "claude-sonnet"  # Changed default to Claude
    
    # Provider selection
    response_provider: str = "claude"  # "claude" or "ollama"


class WDFSettings(BaseSettings):
    """Main settings class for the WDF pipeline"""
    
    # File paths
    transcript_dir: Path = Path("transcripts")
    artefacts_dir: Path = Path("artefacts")
    
    # Service connections
    ollama_host: str = "http://localhost:11434"
    redis_url: str = "redis://localhost:6379/0"
    
    # Prefect configuration
    prefect_workspace: str = "wdf-prod"
    
    # Operational flags
    mock_mode: bool = True
    debug: bool = False
    random_seed: int = 42  # For deterministic mock data

    @field_validator('debug', mode='before')
    @classmethod
    def validate_debug(cls, v):
        """Handle non-boolean DEBUG values from Next.js/Prisma"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            # Handle boolean-like strings
            if v.lower() in ['true', '1', 'yes']:
                return True
            elif v.lower() in ['false', '0', 'no', '']:
                return False
            # For non-boolean strings (like 'prisma:client'), default to False
            return False
        return bool(v)
    
    # LLM models configuration
    llm_models: LLMModels = Field(default_factory=LLMModels)
    
    # Rate limits (legacy, kept for backward compatibility)
    twitter_rate_limit_budget: int = 300  # API calls per 15-minute window
    
    model_config = SettingsConfigDict(
        env_prefix="WDF_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )
    
    def get_run_dir(self, run_id: str) -> Path:
        """Get the directory for a specific run's artefacts"""
        return self.artefacts_dir / run_id


# Global settings instance
settings = WDFSettings()


def get_settings() -> WDFSettings:
    """Get the global settings instance"""
    return settings 