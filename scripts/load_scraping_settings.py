#!/usr/bin/env python3
"""
Load Scraping Settings from Database

Retrieves the configured scraping settings including days_back parameter
for proper volume calculations in keyword tracking.

Used by: scrape.py task to get actual search window
"""

import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if we're in web mode
if os.getenv('WDF_WEB_MODE', 'false').lower() != 'true':
    # Not in web mode, use defaults
    print(json.dumps({
        'maxTweets': 100,
        'maxResultsPerKeyword': 10,  # Conservative default (NOT 100!)
        'daysBack': 7,
        'minLikes': 0,
        'minRetweets': 0,
        'minReplies': 0,
        'excludeReplies': False,
        'excludeRetweets': False,
        'language': 'en'
    }))
    sys.exit(0)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    # Get database URL from environment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        # Try to construct from individual components
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME', 'wdfwatch')
        DB_USER = os.getenv('DB_USER', 'postgres')
        DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get scraping settings
    cursor.execute("""
        SELECT value 
        FROM "Setting" 
        WHERE key = 'scraping_config'
    """)
    
    result = cursor.fetchone()
    
    if result and result['value']:
        settings = result['value']
        # If it's a string, parse it
        if isinstance(settings, str):
            settings = json.loads(settings)
        
        # Ensure maxResultsPerKeyword exists (backward compatibility)
        if 'maxResultsPerKeyword' not in settings:
            settings['maxResultsPerKeyword'] = 10  # Conservative default
    else:
        # Use defaults
        settings = {
            'maxTweets': 100,
            'maxResultsPerKeyword': 10,  # Conservative default (NOT 100!)
            'daysBack': 7,
            'minLikes': 0,
            'minRetweets': 0,
            'minReplies': 0,
            'excludeReplies': False,
            'excludeRetweets': False,
            'language': 'en'
        }
    
    # Clean up
    cursor.close()
    conn.close()
    
    # Output as JSON
    print(json.dumps(settings))
    
except Exception as e:
    # On error, return defaults
    print(json.dumps({
        'maxTweets': 100,
        'maxResultsPerKeyword': 10,  # Conservative default (NOT 100!)
        'daysBack': 7,
        'minLikes': 0,
        'minRetweets': 0,
        'minReplies': 0,
        'excludeReplies': False,
        'excludeRetweets': False,
        'language': 'en',
        'error': str(e)
    }), file=sys.stderr)
    sys.exit(1)