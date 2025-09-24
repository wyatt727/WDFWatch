"""
Constants for WDFWatch relevancy scoring system
"""

import os
import json

# Relevancy Score Thresholds - Configurable via environment variables
RELEVANCY_THRESHOLD = float(os.environ.get('WDF_RELEVANCY_THRESHOLD', '0.70'))  # Minimum score to be considered relevant
HIGH_RELEVANCY_THRESHOLD = float(os.environ.get('WDF_PRIORITY_THRESHOLD', '0.85'))  # Highly relevant tweets (prioritize)
LOW_RELEVANCY_THRESHOLD = 0.30  # Below this is definitely not relevant
REVIEW_THRESHOLD = float(os.environ.get('WDF_REVIEW_THRESHOLD', '0.50'))  # Tweets between this and relevancy threshold might need review

# Score Ranges for Display - Dynamic based on thresholds
def get_score_ranges():
    """Get score ranges based on current thresholds."""
    # Try to load from environment variable first
    ranges_json = os.environ.get('WDF_SCORE_RANGES')
    if ranges_json:
        try:
            ranges_data = json.loads(ranges_json)
            # Convert to tuple format
            return {
                name: (data['min'], data['max'])
                for name, data in ranges_data.items()
            }
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Default ranges based on current thresholds
    return {
        "high": (HIGH_RELEVANCY_THRESHOLD, 1.00),      # Highly relevant - prioritize
        "relevant": (RELEVANCY_THRESHOLD, HIGH_RELEVANCY_THRESHOLD - 0.01),  # Relevant - process normally  
        "maybe": (LOW_RELEVANCY_THRESHOLD, RELEVANCY_THRESHOLD - 0.01),     # Maybe relevant - review manually
        "skip": (0.00, LOW_RELEVANCY_THRESHOLD - 0.01),      # Not relevant - skip
    }

SCORE_RANGES = get_score_ranges()

# Backward Compatibility Mapping
CLASSIFICATION_TO_SCORE = {
    "RELEVANT": 1.00,
    "SKIP": 0.00,
}

# Parsing Patterns for Score Extraction
SCORE_PATTERNS = [
    r"^(\d*\.?\d+)$",           # 0.85, .85, 85
    r"^(\d+(?:\.\d+)?)/1(?:\.0)?$",  # 0.8/1, 0.8/1.0
    r"^(\d+(?:\.\d+)?)%$",      # 85%, 85.5%
    r"^(\d*\.?\d+)\s*out of\s*1(?:\.0)?$",  # 0.85 out of 1.0
]

# Error Messages
ERROR_MESSAGES = {
    "invalid_score": "Invalid score format. Expected a number between 0.00 and 1.00",
    "out_of_range": "Score {score} is out of range. Must be between 0.00 and 1.00",
    "parse_failed": "Could not parse score from response: {response}",
}