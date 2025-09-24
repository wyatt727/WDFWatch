#!/usr/bin/env python3
"""
Sync Keywords Script
Synchronizes keywords between PostgreSQL database and JSON files

This script ensures backward compatibility by syncing enabled keywords
from the database to the keywords.json file used by the pipeline.

Related files:
- /web/scripts/web_bridge.py (Database connection)
- /src/wdf/tasks/scrape.py (Keyword loading)
- /transcripts/keywords.json (Output file)
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict

# Add web scripts to path
sys.path.insert(0, str(Path(__file__).parent))
from web_bridge import WebUIBridge

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def sync_keywords_to_json(episode_id: str = None, output_path: str = None) -> bool:
    """
    Sync enabled keywords from database to JSON file
    
    Args:
        episode_id: Optional episode ID to fetch episode-specific keywords
        output_path: Optional output path (defaults to transcripts/keywords.json)
        
    Returns:
        bool: True if sync was successful
    """
    bridge = WebUIBridge()
    
    try:
        # Get default output path if not provided
        if not output_path:
            output_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "transcripts", "keywords.json"
            )
        
        # Fetch keywords from database
        keywords = bridge.get_enabled_keywords(episode_id)
        
        if not keywords:
            logger.warning("No enabled keywords found in database")
            return False
        
        # Sync to file
        bridge.sync_keywords_to_file(keywords, output_path)
        
        logger.info(f"Successfully synced {len(keywords)} keywords to {output_path}")
        
        # Also emit SSE event to notify UI
        bridge.emit_sse_event({
            "type": "keywords_synced",
            "count": len(keywords),
            "episodeId": episode_id
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync keywords: {e}")
        return False
        
    finally:
        bridge.close()


def main():
    """Main entry point for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync keywords from database to JSON")
    parser.add_argument(
        "--episode-id",
        type=str,
        help="Episode ID to fetch episode-specific keywords"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for keywords JSON file"
    )
    args = parser.parse_args()
    
    success = sync_keywords_to_json(args.episode_id, args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()