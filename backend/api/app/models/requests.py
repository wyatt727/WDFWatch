"""
Request models for API endpoints.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class EpisodeRunRequest(BaseModel):
    """Request to run pipeline for an episode."""
    stages: Optional[list[Literal["summarize", "classify", "respond", "moderate"]]] = Field(
        default=["summarize", "classify", "respond"],
        description="Pipeline stages to run"
    )
    force: bool = Field(default=False, description="Force regeneration even if outputs exist")
    skip_scraping: bool = Field(default=False, description="Skip tweet scraping, use cached")
    skip_moderation: bool = Field(default=False, description="Skip human moderation")


class SingleTweetRequest(BaseModel):
    """Request to generate response for a single tweet."""
    tweet_id: Optional[str] = Field(None, description="Twitter tweet ID")
    tweet_text: str = Field(..., description="Tweet text content")
    episode_id: Optional[str] = Field(None, description="Episode ID for context")
    custom_context: Optional[str] = Field(None, description="Custom context string")
    video_url: Optional[str] = Field(None, description="Video URL to include")


class QueueProcessRequest(BaseModel):
    """Request to process queue items."""
    batch_size: int = Field(default=10, ge=1, le=100, description="Number of items to process")


class SettingsUpdateRequest(BaseModel):
    """Request to update settings."""
    llm_models: Optional[dict] = None
    scoring_config: Optional[dict] = None

