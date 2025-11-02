"""
Episode management endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.models.requests import EpisodeRunRequest
from app.models.responses import PipelineRunResponse, JobStatus
from app.services.pipeline import pipeline_service
from app.services.pipeline_cache import pipeline_cache_service
from app.services.queue import get_queue
from app.services.retry import enqueue_with_retries
from app.workers.jobs import run_pipeline_job
from datetime import datetime

router = APIRouter()


@router.post("/{episode_id}/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(episode_id: str, request: EpisodeRunRequest):
    """Run pipeline for an episode."""
    # Validate episode
    if not pipeline_service.validate_episode(episode_id):
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found")
    
    # Check cache if not forcing
    if not request.force:
        cached_result = pipeline_cache_service.get_cached_result(
            episode_id=episode_id,
            stages=request.stages,
            force=False
        )
        if cached_result:
            return PipelineRunResponse(
                job_id=cached_result.get("job_id", "cached"),
                episode_id=episode_id,
                status="cached",
                message=f"Using cached result for stages: {', '.join(request.stages)}",
            )
    
    # Check stage dependencies
    for stage in request.stages:
        can_run, reason = pipeline_service.can_run_stage(episode_id, stage)
        if not can_run:
            raise HTTPException(status_code=400, detail=f"Cannot run stage {stage}: {reason}")
    
    # Enqueue job with retry configuration
    queue = get_queue()
    job = enqueue_with_retries(
        queue,
        run_pipeline_job,
        episode_id=episode_id,
        stages=request.stages,
        force=request.force,
        skip_scraping=request.skip_scraping,
        skip_moderation=request.skip_moderation,
        job_timeout=3600,  # 1 hour timeout
        result_ttl=86400,  # Keep results for 24 hours
    )
    
    return PipelineRunResponse(
        job_id=job.id,
        episode_id=episode_id,
        status="queued",
        message=f"Pipeline job queued with {len(request.stages)} stages",
    )


@router.get("/{episode_id}/pipeline/status", response_model=JobStatus)
async def get_pipeline_status(episode_id: str, job_id: Optional[str] = None):
    """Get pipeline status for an episode."""
    if job_id:
        # Get job status from RQ
        from app.services.queue import get_job
        try:
            job = get_job(job_id)
            return JobStatus(
                job_id=job.id,
                status=job.get_status(),
                progress=None,  # RQ doesn't provide progress by default
                message=job.exc_info if job.is_failed else None,
                errors=[job.exc_info] if job.is_failed else None,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.ended_at,
            )
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found: {e}")
    else:
        # Get status from filesystem
        status = pipeline_service.get_pipeline_status(episode_id)
        return JobStatus(
            job_id="unknown",
            status="completed" if status["completed_stages"] else "unknown",
            progress=None,
            message=f"Completed stages: {', '.join(status['completed_stages'])}",
            created_at=datetime.now(),
        )


@router.get("/{episode_id}/files")
async def get_episode_files(episode_id: str):
    """Get list of files in episode directory."""
    files = pipeline_service.episodes_repo.get_episode_files(episode_id)
    return {"episode_id": episode_id, "files": files}


@router.get("/{episode_id}/files/{filename}")
async def get_episode_file(episode_id: str, filename: str):
    """Get contents of an episode file."""
    content = pipeline_service.episodes_repo.read_episode_file(episode_id, filename)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    return {"episode_id": episode_id, "filename": filename, "content": content}


@router.get("/{episode_id}/pipeline/cache")
async def get_pipeline_cache(episode_id: str):
    """Get cache entries for an episode."""
    entries = pipeline_cache_service.list_cache_entries(episode_id=episode_id)
    return {
        "episode_id": episode_id,
        "entries": entries,
        "count": len(entries),
    }


@router.delete("/{episode_id}/pipeline/cache")
async def clear_pipeline_cache(episode_id: str):
    """Clear cache entries for an episode."""
    deleted = pipeline_cache_service.invalidate_cache(episode_id)
    return {
        "episode_id": episode_id,
        "deleted": deleted,
        "message": f"Cleared {deleted} cache entries",
    }

