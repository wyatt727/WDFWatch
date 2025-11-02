"""
Response models for API endpoints.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    status: Literal["queued", "started", "progress", "completed", "failed", "cancelled", "unknown"]
    progress: Optional[float] = Field(None, ge=0, le=100, description="Progress percentage")
    message: Optional[str] = None
    errors: Optional[list[str]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PipelineRunResponse(BaseModel):
    """Response from pipeline run request."""
    job_id: str
    episode_id: str
    status: Literal["queued", "started"]
    message: str


class SingleTweetResponse(BaseModel):
    """Response from single tweet generation."""
    success: bool
    response: Optional[str] = None
    character_count: Optional[int] = None
    error: Optional[str] = None

