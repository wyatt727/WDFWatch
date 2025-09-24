#!/usr/bin/env python3
"""
fewshot_generator.py - Generate few-shot examples for tweet classification

This script generates few-shot examples for classifying tweets as either 
RELEVANT or SKIP for the War, Divorce, or Federalism podcast.

The generated examples will include:
- A diverse mix of 40 tweets (by default)
- Some RELEVANT tweets without hashtags
- Some SKIP tweets with topic-related hashtags but irrelevant content
- A variety of tweet styles, lengths, and tones

Usage:
  python fewshot_generator.py [--force] [--model MODEL_NAME] [--run-id RUN_ID]
"""

import argparse
import logging
import sys
from pathlib import Path

import structlog

from src.wdf.tasks.fewshot import run as run_fewshot
from src.wdf.settings import settings


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate diverse few-shot examples for tweet classification"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force regeneration even if examples already exist"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default=settings.llm_models.gemini,
        help=f"Model name (default: {settings.llm_models.gemini})"
    )
    parser.add_argument(
        "--run-id", 
        type=str, 
        help="Run ID for artefact storage"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    logger = structlog.get_logger()
    logger.info(
        "Starting few-shot example generation",
        force=args.force,
        model=args.model,
        run_id=args.run_id
    )
    
    try:
        # Run the few-shot generation task
        output_path = run_fewshot(
            run_id=args.run_id,
            model=args.model,
            force=args.force
        )
        
        logger.info(
            "Few-shot examples generated successfully",
            output_path=str(output_path)
        )
        
        return 0
        
    except Exception as e:
        logger.error(
            "Error generating few-shot examples",
            error=str(e)
        )
        return 1


if __name__ == "__main__":
    sys.exit(main()) 