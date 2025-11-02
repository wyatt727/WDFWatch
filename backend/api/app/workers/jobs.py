"""
Background job definitions for RQ workers.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings
from app.services.queue import get_redis_connection
from app.services.events import events_service
from app.services.pipeline_cache import pipeline_cache_service
from app.services.tweet_queue import QueueItem, tweet_queue_service
from app.services.retry import get_retry_metadata, handle_job_failure
from rq import get_current_job

logger = logging.getLogger(__name__)


def run_pipeline_job(
    episode_id: str,
    stages: list[str],
    force: bool = False,
    skip_scraping: bool = False,
    skip_moderation: bool = False,
) -> Dict[str, Any]:
    """
    Run pipeline job for an episode.
    
    This function is called by RQ workers to execute the pipeline.
    
    Args:
        episode_id: Episode identifier
        stages: List of stages to run (e.g., ['summarize', 'classify', 'respond'])
        force: Force regeneration
        skip_scraping: Skip tweet scraping
        skip_moderation: Skip moderation
        
    Returns:
        Dictionary with job results
    """
    # Get current job ID from RQ context
    job = get_current_job()
    job_id = job.id if job else f"pipeline-{episode_id}"
    
    logger.info(f"Starting pipeline job for episode {episode_id}", extra={
        "episode_id": episode_id,
        "job_id": job_id,
        "stages": stages,
        "force": force,
    })
    
    # Publish job started event
    events_service.publish_job_event(
        job_id=job_id,
        status="started",
        message=f"Starting pipeline with stages: {', '.join(stages)}",
    )
    
    # Publish stage start events with progress tracking
    for i, stage in enumerate(stages):
        progress = (i / len(stages)) * 100 if stages else 0
        events_service.publish_pipeline_event(
            episode_id=episode_id,
            stage=stage,
            status="started",
            progress=progress,
            message=f"Starting {stage} stage",
            items_processed=0,
            items_total=len(stages),
        )
    
    # Build orchestrator command
    orchestrator_path = settings.ORCHESTRATOR_PATH
    if not orchestrator_path.exists():
        raise FileNotFoundError(f"Orchestrator not found at {orchestrator_path}")
    
    cmd = [
        sys.executable,
        str(orchestrator_path),
        "--episode-id", episode_id,
        "--stages", ",".join(stages),
    ]
    
    if force:
        cmd.append("--force")
    if skip_scraping:
        cmd.append("--skip-scraping")
    if skip_moderation:
        cmd.append("--skip-moderation")
    
    # Set up environment
    env = {
        "WDF_WEB_MODE": "true",
        "WDF_EPISODE_ID": episode_id,
        "PYTHONPATH": str(settings.PROJECT_ROOT),
        **dict(os.environ.items()),
    }
    
    # Change to project root
    cwd = str(settings.PROJECT_ROOT)
    
    logger.info(f"Executing: {' '.join(cmd)}")
    logger.info(f"Working directory: {cwd}")
    
    try:
        # Run orchestrator
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=settings.JOB_TIMEOUT,
            stdin=subprocess.DEVNULL,  # Prevent stdin reading
        )
        
        if result.returncode != 0:
            error_msg = result.stderr[-1000:] if result.stderr else "Unknown error"
            logger.error(f"Pipeline job failed: {error_msg}")
            raise RuntimeError(f"Pipeline execution failed: {error_msg}")
        
        logger.info(f"Pipeline job completed successfully for episode {episode_id}")
        
        # Publish job completed event
        events_service.publish_job_event(
            job_id=job_id,
            status="completed",
            message="Pipeline completed successfully",
            progress=100.0,
        )
        
        # Publish stage completion events with progress tracking
        for i, stage in enumerate(stages):
            progress = ((i + 1) / len(stages)) * 100 if stages else 100.0
            events_service.publish_pipeline_event(
                episode_id=episode_id,
                stage=stage,
                status="completed",
                progress=progress,
                message=f"{stage} stage completed",
                items_processed=i + 1,
                items_total=len(stages),
            )
        
        # Cache result if not forced
        job_result = {
            "success": True,
            "episode_id": episode_id,
            "stages": stages,
            "job_id": job_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        
        if not force:
            try:
                pipeline_cache_service.set_cached_result(
                    episode_id=episode_id,
                    stages=stages,
                    result=job_result,
                    force=False
                )
            except Exception as e:
                logger.warning(f"Failed to cache pipeline result: {e}", exc_info=True)
        
        return job_result
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"Pipeline job timed out after {settings.JOB_TIMEOUT}s")
        retry_meta = get_retry_metadata()
        handle_job_failure(job_id, e, retry_meta["retry_count"])
        raise RuntimeError(f"Pipeline execution timed out after {settings.JOB_TIMEOUT}s")
    except Exception as e:
        logger.error(f"Pipeline job error: {e}", exc_info=True)
        retry_meta = get_retry_metadata()
        handle_job_failure(job_id, e, retry_meta["retry_count"])
        raise


def generate_single_tweet_job(
    tweet_text: str,
    tweet_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    custom_context: Optional[str] = None,
    video_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate response for a single tweet using claude-pipeline/single_tweet.py.
    
    Args:
        tweet_text: Tweet text content
        tweet_id: Optional tweet ID
        episode_id: Optional episode ID for context
        custom_context: Optional custom context
        video_url: Optional video URL
        
    Returns:
        Dictionary with response and metadata
    """
    # Get current job ID from RQ context
    job = get_current_job()
    job_id = job.id if job else f"tweet-{tweet_id or 'unknown'}"
    
    logger.info(f"Starting single tweet generation", extra={
        "tweet_id": tweet_id,
        "episode_id": episode_id,
        "job_id": job_id,
    })
    
    # Publish job started event
    events_service.publish_job_event(
        job_id=job_id,
        status="started",
        message="Starting single tweet response generation",
    )
    
    # Build single_tweet.py command
    single_tweet_path = settings.CLAUDE_PIPELINE_DIR / "single_tweet.py"
    if not single_tweet_path.exists():
        error_msg = f"Single tweet script not found at {single_tweet_path}"
        logger.error(error_msg)
        events_service.publish_job_event(
            job_id=job_id,
            status="failed",
            message=error_msg,
        )
        return {
            "success": False,
            "error": error_msg,
        }


def process_tweet_queue_job(
    batch_size: int = 10,
    relevance_threshold: float = 0.70,
) -> Dict[str, Any]:
    """Process a batch of tweet queue items."""

    job = get_current_job()
    job_id = job.id if job else "queue-processor"

    events_service.publish_job_event(
        job_id=job_id,
        status="started",
        message=f"Processing up to {batch_size} queued tweets",
    )

    items = tweet_queue_service.fetch_pending_items(batch_size=batch_size)
    if not items:
        events_service.publish_job_event(
            job_id=job_id,
            status="completed",
            progress=100.0,
            message="No pending items in queue",
        )
        return {"processed": 0, "failed": 0, "skipped": 0}

    processed = 0
    failed = 0
    skipped = 0

    for item in items:
        try:
            outcome = _process_queue_item(item, relevance_threshold)
            if outcome == "processed":
                processed += 1
            elif outcome == "skipped":
                skipped += 1
            else:
                failed += 1
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Queue item processing failed", extra={"queue_id": item.id})
            tweet_queue_service.mark_failed(item.id, error=str(exc))
            events_service.publish_queue_event(
                queue_id=item.id,
                status="failed",
                message="Unhandled exception during processing",
                metadata={"error": str(exc)},
            )
            failed += 1

    summary_message = (
        f"Processed {processed} item(s); "
        f"skipped {skipped} below threshold; "
        f"failed {failed}."
    )

    events_service.publish_job_event(
        job_id=job_id,
        status="completed",
        progress=100.0,
        message=summary_message,
    )

    return {
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
        "batch_size": batch_size,
    }


def _process_queue_item(item: QueueItem, threshold: float) -> str:
    """Process a single queue item and return outcome label."""

    logger.info(
        "Processing queue item",
        extra={
            "queue_id": item.id,
            "twitter_id": item.twitter_id,
            "priority": item.priority,
        },
    )

    if not item.tweet_text:
        error_msg = "Tweet content unavailable"
        tweet_queue_service.mark_failed(item.id, error=error_msg)
        events_service.publish_queue_event(
            queue_id=item.id,
            status="failed",
            message=error_msg,
        )
        return "failed"

    score = item.relevance_score
    if score is not None and score < threshold:
        tweet_queue_service.mark_completed(
            item.id,
            metadata={
                "reason": "below_threshold",
                "relevance_score": score,
                "threshold": threshold,
            },
        )
        events_service.publish_queue_event(
            queue_id=item.id,
            status="skipped",
            message="Tweet below relevance threshold",
            metadata={"score": score, "threshold": threshold},
        )
        return "skipped"

    tweet_queue_service.mark_completed(
        item.id,
        metadata={"reason": "processed", "relevance_score": score},
    )
    events_service.publish_queue_event(
        queue_id=item.id,
        status="processed",
        message="Tweet marked as processed",
        metadata={"score": score},
    )
    return "processed"
    
    # Import single_tweet module directly instead of subprocess
    # This is more reliable and allows better error handling
    try:
        # Add project root to Python path
        project_root_str = str(settings.PROJECT_ROOT)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
        
        # Import the responder class
        from claude_pipeline.single_tweet import ClaudeSingleTweetResponder
        
        # Determine episode context path if episode_id is provided
        episode_context_path = None
        if episode_id:
            # Look for EPISODE_CONTEXT.md in episode directory
            episode_dir = settings.EPISODES_DIR / f"episode_{episode_id}"
            episode_context_file = episode_dir / "EPISODE_CONTEXT.md"
            if episode_context_file.exists():
                episode_context_path = str(episode_context_file)
            else:
                # Fallback to summary.md
                summary_file = episode_dir / "summary.md"
                if summary_file.exists():
                    episode_context_path = str(summary_file)
        
        # Create responder instance
        responder = ClaudeSingleTweetResponder()
        
        # Generate response
        result = responder.respond_to_tweet(
            tweet_text=tweet_text,
            tweet_id=tweet_id,
            episode_id=episode_id,
            episode_context_path=episode_context_path,
            custom_context=custom_context,
            video_url=video_url,
        )
        
        if result.get("success"):
            logger.info(f"Single tweet generation completed successfully")
            events_service.publish_job_event(
                job_id=job_id,
                status="completed",
                message="Response generated successfully",
                progress=100.0,
            )
            return result
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Single tweet generation failed: {error_msg}")
            events_service.publish_job_event(
                job_id=job_id,
                status="failed",
                message=error_msg,
            )
            return result
            
    except ImportError as e:
        error_msg = f"Failed to import single_tweet module: {e}"
        logger.error(error_msg, exc_info=True)
        events_service.publish_job_event(
            job_id=job_id,
            status="failed",
            message=error_msg,
        )
        return {
            "success": False,
            "error": error_msg,
        }
    except Exception as e:
        error_msg = f"Single tweet generation error: {e}"
        logger.error(error_msg, exc_info=True)
        events_service.publish_job_event(
            job_id=job_id,
            status="failed",
            message=error_msg,
        )
        return {
            "success": False,
            "error": error_msg,
        }

