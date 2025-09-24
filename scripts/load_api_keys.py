#!/usr/bin/env python3
"""
Load API Keys from Database

This script loads API keys from the web UI database and sets them as
environment variables for the Python pipeline to use.

Usage:
    python scripts/load_api_keys.py
    
This will print export commands that can be evaluated in bash:
    eval $(python scripts/load_api_keys.py)
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "web" / "scripts"))

from web_bridge import get_api_keys_if_web_mode

def main():
    """Load API keys and print export commands"""
    # Temporarily enable web mode to fetch keys
    old_web_mode = os.environ.get("WDF_WEB_MODE")
    os.environ["WDF_WEB_MODE"] = "true"
    
    try:
        # Fetch API keys from database
        api_keys = get_api_keys_if_web_mode()
        
        if not api_keys:
            print("# No API keys found in database", file=sys.stderr)
            return 1
        
        # Generate export commands for bash
        exports = []
        
        # Twitter API keys
        if api_keys.get("twitter"):
            twitter = api_keys["twitter"]
            if twitter.get("apiKey"):
                exports.append(f'export TWITTER_API_KEY="{twitter["apiKey"]}"')
            if twitter.get("apiSecret"):
                exports.append(f'export TWITTER_API_SECRET="{twitter["apiSecret"]}"')
            if twitter.get("bearerToken"):
                exports.append(f'export TWITTER_BEARER_TOKEN="{twitter["bearerToken"]}"')
            if twitter.get("accessToken"):
                exports.append(f'export TWITTER_ACCESS_TOKEN="{twitter["accessToken"]}"')
            if twitter.get("accessTokenSecret"):
                exports.append(f'export TWITTER_ACCESS_TOKEN_SECRET="{twitter["accessTokenSecret"]}"')
        
        # Gemini API key
        if api_keys.get("gemini", {}).get("apiKey"):
            exports.append(f'export GEMINI_API_KEY="{api_keys["gemini"]["apiKey"]}"')
            exports.append(f'export GOOGLE_API_KEY="{api_keys["gemini"]["apiKey"]}"')  # Alternative name
        
        # OpenAI API key (for future use)
        if api_keys.get("openai", {}).get("apiKey"):
            exports.append(f'export OPENAI_API_KEY="{api_keys["openai"]["apiKey"]}"')
        
        # Print export commands
        for export in exports:
            print(export)
        
        # Also print a comment about what was loaded
        print(f"# Loaded {len(exports)} API key(s) from database", file=sys.stderr)
        
        return 0
        
    finally:
        # Restore original web mode setting
        if old_web_mode is not None:
            os.environ["WDF_WEB_MODE"] = old_web_mode
        elif "WDF_WEB_MODE" in os.environ:
            del os.environ["WDF_WEB_MODE"]


if __name__ == "__main__":
    sys.exit(main())