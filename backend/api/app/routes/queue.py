"""
Queue management endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.models.requests import QueueProcessRequest
from app.services.queue import get_queue, get_job, get_redis_connection
from app.workers.jobs import process_tweet_queue_job

router = APIRouter()


@router.post("/process")
async def process_queue(request: QueueProcessRequest):
    """Process queue items."""
    queue = get_queue()
    job = queue.enqueue(process_tweet_queue_job, kwargs={"batch_size": request.batch_size})

    return {
        "message": "Queue processing job enqueued",
        "batch_size": request.batch_size,
        "job_id": job.id,
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    try:
        job = get_job(job_id)
        
        return {
            "job_id": job.id,
            "status": job.get_status(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "result": job.result if job.is_finished else None,
            "exc_info": job.exc_info if job.is_failed else None,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found: {e}")


@router.get("/jobs")
async def list_jobs(status: str = None, limit: int = 50):
    """List jobs in the queue."""
    redis_conn = get_redis_connection()
    queue = get_queue()
    
    # Get jobs from queue
    jobs = []
    if status:
        # Filter by status
        if status == "queued":
            job_ids = queue.get_job_ids()
        elif status == "started":
            job_ids = queue.started_job_registry.get_job_ids()
        elif status == "finished":
            job_ids = queue.finished_job_registry.get_job_ids()
        elif status == "failed":
            job_ids = queue.failed_job_registry.get_job_ids()
        else:
            job_ids = []
    else:
        job_ids = queue.get_job_ids()
    
    # Fetch job details
    for job_id in job_ids[:limit]:
        try:
            job = get_job(job_id)
            jobs.append({
                "job_id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at.isoformat() if job.created_at else None,
            })
        except Exception:
            continue
    
    return {
        "jobs": jobs,
        "total": len(jobs),
    }


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a job."""
    try:
        job = get_job(job_id)
        job.cancel()
        return {"message": f"Job {job_id} cancelled", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found: {e}")

