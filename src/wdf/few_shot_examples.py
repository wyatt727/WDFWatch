"""
Dynamic few-shot examples loader

This module dynamically loads few-shot examples from the JSON file generated
by the fewshot task. It exposes the examples as a list that can be imported
by other modules.
"""

import json
import logging
from pathlib import Path

from .settings import settings

# Default path to few-shot examples
FEWSHOTS_PATH = Path(settings.transcript_dir) / "fewshots.json"

# Logger
logger = logging.getLogger(__name__)


def load_examples(path: Path = FEWSHOTS_PATH):
    """
    Load few-shot examples from a JSON file
    
    Args:
        path: Path to the JSON file
        
    Returns:
        list: List of (tweet, label) tuples
    """
    try:
        with open(path, "r") as f:
            examples = json.load(f)
            
        # Validate format
        if not isinstance(examples, list):
            logger.error("Few-shot examples file is not a list")
            return []
            
        for i, example in enumerate(examples):
            if not isinstance(example, list) or len(example) != 2:
                logger.error(f"Invalid example at index {i}: {example}")
                return []
                
            tweet, label = example
            if not isinstance(tweet, str) or not isinstance(label, str):
                logger.error(f"Invalid types in example at index {i}: {example}")
                return []
                
            if label not in ("RELEVANT", "SKIP"):
                logger.error(f"Invalid label in example at index {i}: {label}")
                return []
                
        return examples
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to load few-shot examples: {e}")
        return []


# Load examples at module import time
FEW_SHOT_EXAMPLES = load_examples()

# Log the number of examples loaded
if FEW_SHOT_EXAMPLES:
    logger.info(f"Loaded {len(FEW_SHOT_EXAMPLES)} few-shot examples")
else:
    logger.warning("No few-shot examples loaded")


def get_balanced_examples(count: int = 8) -> list:
    """
    Get a balanced set of examples with equal RELEVANT and SKIP items
    
    Args:
        count: Number of examples to return
        
    Returns:
        list: Balanced list of examples
    """
    if not FEW_SHOT_EXAMPLES:
        logger.warning("No few-shot examples available")
        return []
        
    relevant = [ex for ex in FEW_SHOT_EXAMPLES if ex[1] == "RELEVANT"]
    skip = [ex for ex in FEW_SHOT_EXAMPLES if ex[1] == "SKIP"]
    
    # Calculate how many of each type to select
    half = count // 2
    remaining = count - (half * 2)  # Handle odd numbers
    
    # Select examples from each category
    selected_relevant = relevant[:half + remaining]
    selected_skip = skip[:half]
    
    # If we don't have enough examples, use what we have
    if len(selected_relevant) < half + remaining:
        logger.warning(f"Not enough RELEVANT examples, using {len(selected_relevant)}")
        
    if len(selected_skip) < half:
        logger.warning(f"Not enough SKIP examples, using {len(selected_skip)}")
        
    # Combine and return
    result = selected_relevant + selected_skip
    
    return result 