#!/usr/bin/env python3
"""
Load scoring configuration from database and export as environment variables.

This script fetches the scoring thresholds from the PostgreSQL database
and exports them as environment variables for the Python pipeline to use.

Usage:
    # Load config and export as environment variables
    eval $(python web/scripts/load_scoring_config.py)
    
    # Show current configuration
    python web/scripts/load_scoring_config.py --show
    
    # Reset to defaults
    python web/scripts/load_scoring_config.py --reset
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Optional

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("# Warning: psycopg2 not installed. Using default configuration.", file=sys.stderr)

# Default configuration
DEFAULT_CONFIG = {
    "relevancy_threshold": 0.70,
    "score_ranges": {
        "high": {"min": 0.85, "max": 1.00, "label": "Highly Relevant"},
        "relevant": {"min": 0.70, "max": 0.84, "label": "Relevant"},
        "maybe": {"min": 0.30, "max": 0.69, "label": "Maybe Relevant"},
        "skip": {"min": 0.00, "max": 0.29, "label": "Not Relevant"}
    },
    "priority_threshold": 0.85,
    "review_threshold": 0.50
}

SETTINGS_KEY = 'scoring_config'


def get_db_connection():
    """Get database connection from environment variables."""
    if not HAS_PSYCOPG2:
        return None
        
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        # Try to load from .env.local
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip()
                        break
    
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")
    
    return psycopg2.connect(db_url)


def load_config() -> Dict[str, Any]:
    """Load scoring configuration from database."""
    try:
        conn = get_db_connection()
        if not conn:
            return DEFAULT_CONFIG
            
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value FROM settings WHERE key = %s",
            (SETTINGS_KEY,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        else:
            return DEFAULT_CONFIG
            
    except Exception as e:
        print(f"# Error loading config from database: {e}", file=sys.stderr)
        return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]) -> bool:
    """Save scoring configuration to database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO settings (key, value, created_at, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """, (SETTINGS_KEY, json.dumps(config)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"# Error saving config to database: {e}", file=sys.stderr)
        return False


def export_config(config: Dict[str, Any]):
    """Export configuration as shell environment variables."""
    # Export main thresholds
    print(f"export WDF_RELEVANCY_THRESHOLD={config['relevancy_threshold']}")
    
    if 'priority_threshold' in config:
        print(f"export WDF_PRIORITY_THRESHOLD={config['priority_threshold']}")
    
    if 'review_threshold' in config:
        print(f"export WDF_REVIEW_THRESHOLD={config['review_threshold']}")
    
    # Export score ranges as JSON
    if 'score_ranges' in config:
        ranges_json = json.dumps(config['score_ranges']).replace('"', '\\"')
        print(f"export WDF_SCORE_RANGES=\"{ranges_json}\"")


def show_config(config: Dict[str, Any]):
    """Display current configuration."""
    print("# Current Scoring Configuration")
    print(f"# Relevancy Threshold: {config['relevancy_threshold']}")
    
    if 'priority_threshold' in config:
        print(f"# Priority Threshold: {config['priority_threshold']}")
    
    if 'review_threshold' in config:
        print(f"# Review Threshold: {config['review_threshold']}")
    
    if 'score_ranges' in config:
        print("# Score Ranges:")
        for name, range_config in config['score_ranges'].items():
            print(f"#   {range_config['label']}: {range_config['min']:.2f} - {range_config['max']:.2f}")


def main():
    parser = argparse.ArgumentParser(description='Load scoring configuration from database')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--reset', action='store_true', help='Reset to default configuration')
    parser.add_argument('--set-threshold', type=float, metavar='VALUE',
                        help='Set relevancy threshold (0.00-1.00)')
    
    args = parser.parse_args()
    
    if args.reset:
        if save_config(DEFAULT_CONFIG):
            print("# Configuration reset to defaults", file=sys.stderr)
            export_config(DEFAULT_CONFIG)
        else:
            sys.exit(1)
    
    elif args.set_threshold is not None:
        if not 0.0 <= args.set_threshold <= 1.0:
            print("# Error: Threshold must be between 0.00 and 1.00", file=sys.stderr)
            sys.exit(1)
        
        config = load_config()
        config['relevancy_threshold'] = args.set_threshold
        
        # Update score ranges
        config['score_ranges']['relevant']['min'] = args.set_threshold
        config['score_ranges']['maybe']['max'] = max(0, args.set_threshold - 0.01)
        
        if save_config(config):
            print(f"# Relevancy threshold set to {args.set_threshold}", file=sys.stderr)
            export_config(config)
        else:
            sys.exit(1)
    
    elif args.show:
        config = load_config()
        show_config(config)
    
    else:
        # Default: export configuration
        config = load_config()
        export_config(config)


if __name__ == '__main__':
    main()