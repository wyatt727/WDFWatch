#!/usr/bin/env python3
"""
Claude Few-shot Generation Task

This module generates few-shot examples using Claude via the CLI.
Provides a drop-in replacement for the Gemini-based fewshot.py when Claude is selected.

Integrates with: main.py, web UI LLM model selection
Related files: fewshot.py (original Gemini implementation)
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import structlog
from prometheus_client import Counter, Histogram

from ..settings import settings
from ..prompt_utils import build_fewshot_prompt, get_prompt_template
from ..episode_files import get_episode_file_manager
from ..claude_config import build_claude_command

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics
FEWSHOT_LATENCY = Histogram(
    "claude_fewshot_latency_seconds", 
    "Time taken to generate few-shot examples with Claude",
    ["run_id"],
    buckets=[1, 5, 10, 30, 60, 120]
)
FEWSHOT_ERRORS = Counter(
    "claude_fewshot_errors_total",
    "Number of Claude few-shot generation errors"
)
FEWSHOT_SUCCESS = Counter(
    "claude_fewshot_success_total",
    "Number of successful Claude few-shot generations"
)

# File paths
OVERVIEW_PATH = Path(settings.transcript_dir) / "podcast_overview.txt"
SUMMARY_PATH = Path(settings.transcript_dir) / "summary.md"
FEWSHOTS_PATH = Path(settings.transcript_dir) / "fewshots.json"
FEWSHOTS_HASH_PATH = Path(settings.transcript_dir) / "fewshots.hash"

# Constants
REQUIRED_EXAMPLES = 40
MIN_RELEVANT_PERCENT = 20  # Percentage of examples that should score >= 0.70


def build_prompt(overview: str, summary: str) -> str:
    """
    Build the prompt for generating few-shot examples
    
    Args:
        overview: Podcast overview text
        summary: Podcast summary text
        
    Returns:
        str: Formatted prompt
    """
    # Use database prompt if available, otherwise use hardcoded default
    return build_fewshot_prompt(
        required_examples=REQUIRED_EXAMPLES,
        overview=overview,
        summary=summary
    )


def parse_examples(response: str) -> List[Tuple[str, float]]:
    """
    Parse the Claude response into a list of (tweet, score) tuples
    
    Args:
        response: Claude response text
        
    Returns:
        List[Tuple[str, float]]: List of (tweet, score) tuples where score is 0.00-1.00
    """
    # Clean up the response
    lines_original = [l.strip() for l in response.splitlines() if l.strip()]
    lines = []
    started_examples = False
    
    for line in lines_original:
        # Skip any lines that look like explanations or instructions
        if not started_examples and not ("\t" in line):
            continue
        
        # Once we find a line with a tab, we've started the examples
        if "\t" in line:
            started_examples = True
            lines.append(line)
        elif started_examples and line:  # Only include non-empty lines after we've started examples
            lines.append(line)
    
    examples = []
    
    for line in lines:
        if not line or line.startswith('#'):
            continue
            
        # Try to parse the line as tweet<TAB>score
        if '\t' in line:
            parts = line.split('\t', 1)
            if len(parts) == 2:
                tweet_text = parts[0].strip()
                score_text = parts[1].strip()
                
                # Remove quotes if present
                if tweet_text.startswith('"') and tweet_text.endswith('"'):
                    tweet_text = tweet_text[1:-1]
                
                # Parse score
                try:
                    # Handle both decimal scores (0.85) and word labels (RELEVANT/SKIP)
                    if score_text.upper() in ['RELEVANT', 'HIGH']:
                        score = 0.85
                    elif score_text.upper() in ['SKIP', 'LOW', 'NONE']:
                        score = 0.15
                    else:
                        # Try to parse as float
                        score = float(score_text)
                        # Ensure score is in valid range
                        score = max(0.0, min(1.0, score))
                except ValueError:
                    logger.warning(f"Could not parse score: {score_text}, defaulting to 0.50")
                    score = 0.50
                
                examples.append((tweet_text, score))
    
    return examples


def generate_examples(overview: str, summary: str, run_id: str = "unknown") -> List[Tuple[str, float]]:
    """
    Generate few-shot examples via the `claude` CLI.
    
    Args:
        overview: Podcast overview text
        summary: Podcast summary text
        run_id: Run ID for metrics
        
    Returns:
        List[Tuple[str, float]]: List of (tweet, score) tuples
    """
    prompt = build_prompt(overview, summary)
    
    logger.info(
        "Calling Claude CLI to generate few-shot examples",
        run_id=run_id,
        prompt_length=len(prompt)
    )

    with FEWSHOT_LATENCY.labels(run_id=run_id).time():
        # Use optimized Claude command with no-MCP config
        result = subprocess.run(
            build_claude_command(prompt),
            text=True,
            capture_output=True,
            timeout=10  # Should complete in ~7 seconds with no-MCP config
        )

    if result.returncode != 0:
        logger.error(
            "Claude CLI failed",
            returncode=result.returncode,
            stderr=result.stderr
        )
        FEWSHOT_ERRORS.inc()
        raise RuntimeError("Claude CLI error – see log for details")

    response = result.stdout.strip()
    examples = parse_examples(response)
    
    logger.info(
        "Generated few-shot examples with Claude",
        run_id=run_id,
        num_examples=len(examples)
    )
    
    FEWSHOT_SUCCESS.inc()
    return examples


def validate_examples(examples: List[Tuple[str, float]]) -> bool:
    """
    Validate that the examples meet quality requirements
    
    Args:
        examples: List of (tweet, score) tuples
        
    Returns:
        bool: True if examples are valid, False otherwise
    """
    if len(examples) < REQUIRED_EXAMPLES:
        logger.warning(
            "Insufficient examples generated",
            generated=len(examples),
            required=REQUIRED_EXAMPLES
        )
        return False
    
    # Check that we have a good mix of relevant and non-relevant
    relevant_count = sum(1 for _, score in examples if score >= 0.70)
    relevant_percent = (relevant_count / len(examples)) * 100
    
    if relevant_percent < MIN_RELEVANT_PERCENT:
        logger.warning(
            "Too few relevant examples",
            relevant_count=relevant_count,
            relevant_percent=relevant_percent,
            min_percent=MIN_RELEVANT_PERCENT
        )
        return False
    
    if relevant_percent > 80:
        logger.warning(
            "Too many relevant examples, may lack diversity",
            relevant_count=relevant_count,
            relevant_percent=relevant_percent
        )
        # Don't fail, just warn
    
    return True


def run(run_id: str = None, episode_id: str = None) -> Path:
    """
    Run the Claude few-shot generation task
    
    Args:
        run_id: Optional run ID for artefact storage
        episode_id: Optional episode ID for file management
        
    Returns:
        Path: Path to the fewshots file
    """
    logger.info(
        "Starting Claude few-shot generation task",
        run_id=run_id,
        episode_id=episode_id
    )
    
    # Use episode file manager if episode_id provided
    use_episode_files = episode_id or os.environ.get('WDF_EPISODE_ID')
    if use_episode_files:
        file_manager = get_episode_file_manager(episode_id)
        logger.info(
            "Using episode file manager",
            episode_dir=file_manager.episode_dir
        )
        overview_path = file_manager.get_input_path('podcast_overview')
        summary_path = file_manager.get_output_path('summary')
        output_path = file_manager.get_output_path('fewshots')
    else:
        overview_path = OVERVIEW_PATH
        summary_path = SUMMARY_PATH
        output_path = FEWSHOTS_PATH
    
    # Read input files
    if not overview_path.exists():
        logger.error(f"Overview file not found: {overview_path}")
        raise FileNotFoundError(f"Overview file not found: {overview_path}")
    
    if not summary_path.exists():
        logger.error(f"Summary file not found: {summary_path}")
        raise FileNotFoundError(f"Summary file not found: {summary_path}")
    
    overview = overview_path.read_text()
    summary = summary_path.read_text()
    
    try:
        # Generate examples with Claude
        examples = generate_examples(overview, summary, run_id or "unknown")
        
        # Validate examples
        if not validate_examples(examples):
            logger.warning("Examples failed validation, retrying...")
            # Retry once if validation fails
            examples = generate_examples(overview, summary, run_id or "unknown")
            if not validate_examples(examples):
                logger.error("Examples failed validation after retry")
                # Continue anyway with what we have
        
        # Convert to the expected format for the classifier
        # Format: [["tweet text", "RELEVANT" or "SKIP"], ...]
        formatted_examples = []
        for tweet, score in examples:
            label = "RELEVANT" if score >= 0.70 else "SKIP"
            formatted_examples.append([tweet, label])
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(formatted_examples, f, indent=2)
        
        logger.info(
            "Claude few-shot generation complete",
            output_path=str(output_path),
            num_examples=len(formatted_examples),
            relevant_count=sum(1 for _, label in formatted_examples if label == "RELEVANT")
        )
        
        # Save to artefacts if run_id provided
        if run_id:
            artefact_dir = settings.get_run_dir(run_id)
            artefact_dir.mkdir(parents=True, exist_ok=True)
            artefact_path = artefact_dir / "fewshots.json"
            
            with open(artefact_path, 'w') as f:
                json.dump(formatted_examples, f, indent=2)
            
            logger.info(f"Saved few-shot examples to artefacts: {artefact_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(
            "Failed to generate few-shot examples with Claude",
            error=str(e),
            run_id=run_id
        )
        FEWSHOT_ERRORS.inc()
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
    
    # Set up argument parser for command line usage
    import argparse
    parser = argparse.ArgumentParser(description="Generate few-shot examples using Claude")
    parser.add_argument("--run-id", type=str, help="Run ID for artefact storage")
    parser.add_argument("--episode-id", type=str, help="Episode ID for file management")
    args = parser.parse_args()
    
    # Run the task
    output_path = run(run_id=args.run_id, episode_id=args.episode_id)
    print(f"Few-shot examples saved to: {output_path}")