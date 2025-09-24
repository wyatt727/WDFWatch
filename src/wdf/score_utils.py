"""
Utilities for parsing and validating relevancy scores
"""

import re
from typing import Optional, Union, Tuple
import logging

from .constants import (
    SCORE_PATTERNS,
    ERROR_MESSAGES,
    CLASSIFICATION_TO_SCORE,
    RELEVANCY_THRESHOLD,
    SCORE_RANGES
)

logger = logging.getLogger(__name__)


def parse_score(response: str) -> Optional[float]:
    """
    Parse a relevancy score from various formats.
    
    Args:
        response: The model response containing a score
        
    Returns:
        float: The parsed score between 0.00 and 1.00, or None if parsing fails
    """
    # Clean the response
    response = response.strip()
    
    # Check for backward compatibility - binary classification
    if response.upper() in CLASSIFICATION_TO_SCORE:
        return CLASSIFICATION_TO_SCORE[response.upper()]
    
    # Try each pattern
    for pattern in SCORE_PATTERNS:
        match = re.match(pattern, response, re.IGNORECASE)
        if match:
            try:
                score_str = match.group(1)
                score = float(score_str)
                
                # Handle percentage format
                if response.endswith('%'):
                    score = score / 100.0
                
                # Validate range
                if 0.0 <= score <= 1.0:
                    return round(score, 2)  # Round to 2 decimal places
                else:
                    logger.warning(ERROR_MESSAGES["out_of_range"].format(score=score))
                    return None
                    
            except ValueError:
                continue
    
    # If all patterns fail, log and return None
    logger.warning(ERROR_MESSAGES["parse_failed"].format(response=response))
    return None


def validate_score(score: Union[float, str]) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Validate a relevancy score.
    
    Args:
        score: The score to validate (can be float or string)
        
    Returns:
        Tuple of (is_valid, parsed_score, error_message)
    """
    # If it's already a float, just validate range
    if isinstance(score, (int, float)):
        if 0.0 <= score <= 1.0:
            return True, float(score), None
        else:
            return False, None, ERROR_MESSAGES["out_of_range"].format(score=score)
    
    # If it's a string, parse it first
    if isinstance(score, str):
        parsed = parse_score(score)
        if parsed is not None:
            return True, parsed, None
        else:
            return False, None, ERROR_MESSAGES["invalid_score"]
    
    # Invalid type
    return False, None, f"Invalid score type: {type(score)}"


def score_to_classification(score: float) -> str:
    """
    Convert a relevancy score to a binary classification.
    
    Args:
        score: The relevancy score (0.00-1.00)
        
    Returns:
        str: "RELEVANT" or "SKIP"
    """
    return "RELEVANT" if score >= RELEVANCY_THRESHOLD else "SKIP"


def score_to_label(score: float) -> str:
    """
    Convert a relevancy score to a human-readable label.
    
    Args:
        score: The relevancy score (0.00-1.00)
        
    Returns:
        str: Label like "high", "relevant", "maybe", or "skip"
    """
    # Dynamically get score ranges in case they've been updated
    from .constants import get_score_ranges
    current_ranges = get_score_ranges()
    
    for label, (min_score, max_score) in current_ranges.items():
        if min_score <= score <= max_score:
            return label
    return "unknown"


def format_score_for_display(score: float) -> str:
    """
    Format a score for display in the UI.
    
    Args:
        score: The relevancy score (0.00-1.00)
        
    Returns:
        str: Formatted string like "0.85 (High)"
    """
    label = score_to_label(score)
    return f"{score:.2f} ({label.capitalize()})"


def is_relevant(score: float) -> bool:
    """
    Check if a score indicates the tweet is relevant.
    
    Args:
        score: The relevancy score (0.00-1.00)
        
    Returns:
        bool: True if score >= RELEVANCY_THRESHOLD
    """
    return score >= RELEVANCY_THRESHOLD