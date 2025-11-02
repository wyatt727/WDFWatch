"""
Tweet-related endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.models.requests import SingleTweetRequest
from app.models.responses import SingleTweetResponse
from app.services.queue import get_queue
from app.workers.jobs import generate_single_tweet_job

router = APIRouter()


@router.post("/single/generate", response_model=SingleTweetResponse)
async def generate_single_tweet(request: SingleTweetRequest):
    """Generate response for a single tweet."""
    # Enqueue job for single tweet generation
    queue = get_queue()
    job = queue.enqueue(
        generate_single_tweet_job,
        tweet_text=request.tweet_text,
        tweet_id=request.tweet_id,
        episode_id=request.episode_id,
        custom_context=request.custom_context,
        video_url=request.video_url,
        job_timeout=300,  # 5 minutes timeout for single tweet
        result_ttl=3600,  # Keep results for 1 hour
    )
    
    # Wait for job to complete (for single tweet, we can wait)
    try:
        result = job.result(timeout=300)  # 5 minute timeout
        
        if result.get("success"):
            return SingleTweetResponse(
                success=True,
                response=result.get("response"),
                character_count=len(result.get("response", "")),
            )
        else:
            return SingleTweetResponse(
                success=False,
                error=result.get("error", "Unknown error"),
            )
    except Exception as e:
        return SingleTweetResponse(
            success=False,
            error=f"Job failed: {str(e)}",
        )

