#!/usr/bin/env python3
"""
Get Twitter API Quota Statistics

Returns JSON-formatted quota statistics for the web UI.
Used by: /api/twitter/quota endpoint
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wdf.quota_manager import QuotaManager


def main():
    """Get and print quota statistics as JSON."""
    try:
        # Initialize quota manager
        quota_mgr = QuotaManager()
        
        # Get usage statistics
        stats = quota_mgr.get_usage_stats()
        
        # Print as JSON
        print(json.dumps(stats))
        
    except Exception as e:
        # Print error as JSON
        error_response = {
            'error': str(e),
            'monthly_limit': 10000,
            'monthly_usage': 0,
            'monthly_remaining': 10000,
            'monthly_percentage': 0,
            'daily_usage': 0,
            'daily_average': 0,
            'projected_monthly': 0,
            'days_until_exhausted': float('inf'),
            'exhaustion_date': None,
            'days_remaining_in_month': 30,
            'recommended_daily_limit': 333
        }
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == '__main__':
    main()