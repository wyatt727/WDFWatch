"""
WDF Pipeline Prefect Flow

This module defines the Prefect flow for the WDF pipeline.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional

import redis
import structlog
from prefect import flow, task
from prefect.context import get_run_context
from prometheus_client import Counter, Gauge

from .settings import settings
from .tasks import (
    classify,
    deepseek,
    fewshot,
    moderation,
    scrape,
    summarise,
    watch
)

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics for pipeline success/failure
PIPELINE_SUCCESS = Counter(
    "pipeline_success_total",
    "Number of successful pipeline runs",
    ["run_id", "model"]
)
PIPELINE_FAILURE = Counter(
    "pipeline_failure_total",
    "Number of failed pipeline runs",
    ["run_id", "error", "model"]
)

# Redis queue metrics
REDIS_QUEUE_LENGTH = Gauge(
    "redis_queue_length",
    "Number of items in Redis queue",
    ["queue", "env"]
)

# Initialize Redis client
redis_client = None
try:
    redis_client = redis.Redis.from_url(settings.redis_url)
    logger.info("Redis client initialized", url=settings.redis_url)
except Exception as e:
    logger.warning("Failed to initialize Redis client", error=str(e))


def update_queue_metrics():
    """Update Redis queue metrics"""
    if not redis_client:
        return
        
    try:
        # Get moderation queue length
        moderation_queue_length = redis_client.llen("moderation:queue") or 0
        REDIS_QUEUE_LENGTH.labels(queue="moderation", env="prod" if not settings.mock_mode else "dev").set(moderation_queue_length)
        
        # Get other queue lengths if needed
        # tweets_queue_length = redis_client.llen("tweets:queue") or 0
        # REDIS_QUEUE_LENGTH.labels(queue="tweets", env="prod" if not settings.mock_mode else "dev").set(tweets_queue_length)
    except Exception as e:
        logger.warning("Failed to update Redis queue metrics", error=str(e))

@task(name="summarize_transcript")
def summarize_transcript_task(run_id: str) -> Dict[str, Path]:
    """
    Summarize the podcast transcript
    
    Args:
        run_id: Run ID for artefact storage
        
    Returns:
        Dict[str, Path]: Paths to the summary and keywords files
    """
    logger.info("Running summarize_transcript task", run_id=run_id)
    summary_path, keywords_path = summarise.run(run_id=run_id)
    return {
        "summary": summary_path,
        "keywords": keywords_path
    }


@task(name="scrape_tweets")
def scrape_tweets_task(run_id: str, keywords_path: Path) -> Path:
    """
    Scrape tweets based on keywords
    
    Args:
        run_id: Run ID for artefact storage
        keywords_path: Path to the keywords file
        
    Returns:
        Path: Path to the tweets file
    """
    logger.info("Running scrape_tweets task", run_id=run_id, keywords_path=str(keywords_path))
    return scrape.run(run_id=run_id)


@task(name="generate_fewshots")
def generate_fewshots_task(run_id: str) -> Path:
    """
    Generate few-shot examples
    
    Args:
        run_id: Run ID for artefact storage
        
    Returns:
        Path: Path to the few-shot examples file
    """
    logger.info("Running generate_fewshots task", run_id=run_id)
    return fewshot.run(run_id=run_id)


@task(name="classify_tweets")
def classify_tweets_task(run_id: str, fewshots_path: Path) -> Path:
    """
    Classify tweets as RELEVANT or SKIP
    
    Args:
        run_id: Run ID for artefact storage
        fewshots_path: Path to the few-shot examples file
        
    Returns:
        Path: Path to the classified tweets file
    """
    logger.info("Running classify_tweets task", run_id=run_id)
    return classify.run(run_id=run_id, fewshots_path=fewshots_path)


@task(name="generate_responses")
def generate_responses_task(run_id: str, num_workers: int = None) -> Path:
    """
    Generate responses to relevant tweets
    
    Args:
        run_id: Run ID for artefact storage
        num_workers: Optional number of worker threads for parallel processing
        
    Returns:
        Path: Path to the responses file
    """
    logger.info("Running generate_responses task", run_id=run_id, num_workers=num_workers or "default")
    return deepseek.run(run_id=run_id, num_workers=num_workers)


@task(name="moderate_tweets")
def moderate_tweets_task(run_id: str, non_interactive: bool = False) -> Path:
    """
    Moderate generated tweet responses
    
    Args:
        run_id: Run ID for artefact storage
        non_interactive: If True, skip the interactive moderation
        
    Returns:
        Path: Path to the responses file
    """
    logger.info("Running moderate_tweets task", run_id=run_id, non_interactive=non_interactive)
    return moderation.run(run_id=run_id, non_interactive=non_interactive)


@flow(name="wdf-pipeline")
def wdf_pipeline_flow(
    run_id: Optional[str] = None,
    mock_mode: Optional[bool] = None,
    non_interactive: bool = False,
    num_workers: Optional[int] = None
) -> Dict[str, Path]:
    """
    Run the WDF pipeline flow
    
    Args:
        run_id: Optional run ID for artefact storage
        mock_mode: Optional override for mock mode setting
        non_interactive: If True, skip the interactive moderation
        num_workers: Optional number of worker threads for parallel processing
        
    Returns:
        Dict[str, Path]: Paths to the output files
    """
    # Override mock mode if specified - do this first to affect all downstream operations
    if mock_mode is not None:
        settings.mock_mode = mock_mode
        logger.info("Mock mode overridden", mock_mode=mock_mode)
    
    # Get run context
    context = get_run_context()
    
    # Generate run_id if not provided
    if not run_id:
        run_id = context.flow_run.name.replace(" ", "_").lower()
        
    logger.info("Starting WDF pipeline flow", run_id=run_id)
    
    # Get model names for metrics
    gemma_model = settings.llm_models.gemma
    deepseek_model = settings.llm_models.deepseek
    
    try:
        # Update Redis queue metrics at the start
        update_queue_metrics()
        
        # Run tasks in sequence
        summary_results = summarize_transcript_task(run_id)
        tweets_path = scrape_tweets_task(run_id, summary_results["keywords"])
        fewshots_path = generate_fewshots_task(run_id)
        classified_path = classify_tweets_task(run_id, fewshots_path)
        responses_path = generate_responses_task(run_id, num_workers=num_workers)
        
        # Update Redis queue metrics before moderation
        update_queue_metrics()
        
        moderated_path = moderate_tweets_task(run_id, non_interactive)
        
        # Update Redis queue metrics after moderation
        update_queue_metrics()
        
        logger.info("WDF pipeline flow completed", run_id=run_id)
        PIPELINE_SUCCESS.labels(run_id=run_id, model=f"{gemma_model},{deepseek_model}").inc()
        
        return {
            "summary": summary_results["summary"],
            "keywords": summary_results["keywords"],
            "tweets": tweets_path,
            "fewshots": fewshots_path,
            "classified": classified_path,
            "responses": responses_path,
            "moderated": moderated_path
        }
    except Exception as e:
        logger.error("WDF pipeline flow failed", run_id=run_id, error=str(e))
        PIPELINE_FAILURE.labels(run_id=run_id, error=type(e).__name__, model=f"{gemma_model},{deepseek_model}").inc()
        raise


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="WDF pipeline flow")
    parser.add_argument("--run-id", help="Run ID for artefact storage")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive moderation")
    parser.add_argument("--num-workers", type=int, help="Number of worker threads for parallel processing")
    args = parser.parse_args()
    
    # Run the flow
    wdf_pipeline_flow(
        run_id=args.run_id,
        mock_mode=args.mock,
        non_interactive=args.non_interactive,
        num_workers=args.num_workers
    ) 