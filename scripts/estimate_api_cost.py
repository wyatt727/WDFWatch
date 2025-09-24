#!/usr/bin/env python3
"""
Estimate Twitter API Cost for Keyword Search

Calculates the estimated API calls required for a keyword search.
Used by: /api/twitter/estimate endpoint
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wdf.quota_manager import QuotaManager
from wdf.keyword_optimizer import KeywordOptimizer


def main():
    """Estimate API cost for keyword search."""
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Keywords argument required'}))
        sys.exit(1)
    
    try:
        # Parse arguments
        keywords_json = sys.argv[1]
        target_tweets = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        
        # Parse keywords
        keywords_raw = json.loads(keywords_json)
        
        # Convert to dict format if needed
        if keywords_raw and isinstance(keywords_raw[0], str):
            keywords = [{"keyword": kw, "weight": 1.0} for kw in keywords_raw]
        else:
            keywords = keywords_raw
        
        # Initialize managers
        quota_mgr = QuotaManager()
        optimizer = KeywordOptimizer(quota_remaining=quota_mgr.get_remaining_quota())
        
        # Get basic cost estimate
        basic_estimate = quota_mgr.estimate_search_cost(
            num_keywords=len(keywords),
            tweets_per_keyword=target_tweets
        )
        
        # Get optimized search plan
        optimized_plan = optimizer.optimize_search_plan(
            keywords=keywords,
            quota_limit=quota_mgr.get_remaining_quota() // 10  # Use max 10% of quota
        )
        
        # Build comprehensive estimate
        estimate = {
            **basic_estimate,
            'optimization': {
                'phases': [],
                'total_optimized_calls': 0,
                'savings_percentage': 0
            },
            'recommendations': []
        }
        
        # Add optimization details
        if optimized_plan and 'strategy' in optimized_plan:
            strategy = optimized_plan['strategy']
            total_optimized = 0
            
            for phase in strategy.get('phases', []):
                phase_calls = len(phase.get('queries', []))
                estimate['optimization']['phases'].append({
                    'name': phase.get('name', 'Unknown'),
                    'keywords': phase.get('keywords', 0),
                    'queries': len(phase.get('queries', [])),
                    'api_calls': phase_calls,
                    'weight_range': phase.get('weight_range', 'N/A')
                })
                total_optimized += phase_calls
            
            estimate['optimization']['total_optimized_calls'] = total_optimized
            
            # Calculate savings
            if basic_estimate['total_api_calls'] > 0:
                savings_pct = ((basic_estimate['total_api_calls'] - total_optimized) / 
                              basic_estimate['total_api_calls']) * 100
                estimate['optimization']['savings_percentage'] = round(savings_pct, 1)
        
        # Add recommendations
        if optimized_plan and 'recommendations' in optimized_plan:
            estimate['recommendations'] = optimized_plan['recommendations']
        
        # Add quota health warning
        quota_stats = quota_mgr.get_usage_stats()
        if quota_stats['monthly_percentage'] > 70:
            estimate['recommendations'].append(
                f"Warning: Already at {quota_stats['monthly_percentage']:.0f}% of monthly quota"
            )
        
        # Print as JSON
        print(json.dumps(estimate))
        
    except Exception as e:
        # Print error as JSON
        print(json.dumps({
            'error': str(e),
            'keywords': 0,
            'queries_needed': 0,
            'pages_per_query': 0,
            'total_api_calls': 0,
            'percentage_of_remaining': 0,
            'can_afford': False,
            'remaining_after': 0
        }))
        sys.exit(1)


if __name__ == '__main__':
    main()