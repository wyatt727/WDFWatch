"""
Summarization task

This module handles the summarization of podcast transcripts using configured LLM.
It calls the Node.js script and validates the output.
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

import structlog
from prometheus_client import Counter, Histogram

from ..settings import settings

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics
SUMMARY_LATENCY = Histogram(
    "summary_latency_seconds", 
    "Time taken to generate summary",
    ["run_id"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)
SUMMARY_ERRORS = Counter(
    "summary_errors_total",
    "Number of summary generation errors"
)
SUMMARY_SUCCESS = Counter(
    "summary_success_total",
    "Number of successful summary generations"
)

# File paths
TRANSCRIPT_PATH = Path(settings.transcript_dir) / "latest.txt"
OVERVIEW_PATH = Path(settings.transcript_dir) / "podcast_overview.txt"
SUMMARY_PATH = Path(settings.transcript_dir) / "summary.md"
KEYWORDS_PATH = Path(settings.transcript_dir) / "keywords.json"


def validate_outputs() -> bool:
    """
    Validate that the summary and keywords files exist and have the expected format
    
    Returns:
        bool: True if valid, False otherwise
    """
    # Check if files exist
    if not SUMMARY_PATH.exists() or not KEYWORDS_PATH.exists():
        logger.error(
            "Summary or keywords file missing",
            summary_exists=SUMMARY_PATH.exists(),
            keywords_exists=KEYWORDS_PATH.exists()
        )
        return False
        
    # Check if keywords file is valid JSON
    try:
        with open(KEYWORDS_PATH, "r") as f:
            keywords = json.load(f)
        
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            logger.error(
                "Keywords file has invalid format",
                expected="list of strings",
                path=str(KEYWORDS_PATH)
            )
            return False
            
        if len(keywords) < 3:
            logger.warning(
                "Keywords list is suspiciously short",
                count=len(keywords),
                path=str(KEYWORDS_PATH)
            )
            
    except json.JSONDecodeError:
        logger.error(
            "Keywords file is not valid JSON",
            path=str(KEYWORDS_PATH)
        )
        return False
        
    # Check if summary file has content
    summary_content = SUMMARY_PATH.read_text()
    if len(summary_content) < 100:
        logger.error(
            "Summary file is suspiciously short",
            length=len(summary_content),
            path=str(SUMMARY_PATH)
        )
        return False
        
    return True


def run_transcript_summarizer(max_retries: int = 3, run_id: str = "unknown") -> bool:
    """
    Run the transcript_summarizer.js script with retries
    
    Args:
        max_retries: Maximum number of retry attempts
        run_id: Run ID for metrics labeling
        
    Returns:
        bool: True if successful, False otherwise
    """
    cmd = ["node", "scripts/transcript_summarizer.js"]
    if settings.debug:
        cmd.append("--verbose")
        
    for attempt in range(max_retries):
        try:
            logger.info(
                "Running transcript_summarizer.js",
                attempt=attempt + 1,
                max_retries=max_retries
            )
            
            # Run the script and capture output
            with SUMMARY_LATENCY.labels(run_id=run_id).time():
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
            logger.info(
                "transcript_summarizer.js completed successfully",
                stdout=result.stdout.strip()
            )
            
            # Validate the output
            if validate_outputs():
                SUMMARY_SUCCESS.inc()
                return True
            else:
                logger.error("Output validation failed")
                SUMMARY_ERRORS.inc()
                
        except subprocess.CalledProcessError as e:
            logger.error(
                "transcript_summarizer.js failed",
                returncode=e.returncode,
                stdout=e.stdout,
                stderr=e.stderr
            )
            SUMMARY_ERRORS.inc()
            
        except Exception as e:
            logger.error(
                "Unexpected error running transcript_summarizer.js",
                error=str(e)
            )
            SUMMARY_ERRORS.inc()
            
        # Wait before retrying
        if attempt < max_retries - 1:
            backoff = 2 ** attempt  # Exponential backoff
            logger.info(f"Retrying in {backoff} seconds...", backoff=backoff)
            time.sleep(backoff)
            
    return False


def run(run_id: str = None) -> Tuple[Path, Path]:
    """
    Run the summarization task
    
    Args:
        run_id: Optional run ID for artefact storage
        
    Returns:
        Tuple[Path, Path]: Paths to the summary and keywords files
    """
    logger.info("Starting summarization task", run_id=run_id)
    
    # Create artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_dir.mkdir(parents=True, exist_ok=True)
    
    # Run the summarization script
    success = run_transcript_summarizer(run_id=run_id or "unknown")
    
    if not success:
        raise RuntimeError("Failed to generate summary after multiple attempts")
    
    # Copy to artefacts directory if run_id is provided
    if run_id:
        artefact_summary = artefact_dir / "summary.md"
        artefact_keywords = artefact_dir / "keywords.json"
        
        # Copy files
        artefact_summary.write_text(SUMMARY_PATH.read_text())
        artefact_keywords.write_text(KEYWORDS_PATH.read_text())
        
        logger.info(
            "Copied summary and keywords to artefacts directory",
            summary_path=str(artefact_summary),
            keywords_path=str(artefact_keywords)
        )
        
        return artefact_summary, artefact_keywords
    
    return SUMMARY_PATH, KEYWORDS_PATH


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Run the task
    run() 