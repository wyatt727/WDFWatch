"""
Twitter Search Boundary Management

Tracks search boundaries per keyword to avoid re-fetching already-seen tweets.
Implements checkpoint strategy from API_Conservation.md to save read credits.

Core strategy:
- Store first/last tweet IDs from each keyword search
- Use since_id/until_id to only fetch new/missed tweets
- Never re-fetch tweets in already-searched timeline segments

Integrates with: twitter_api_v2.py, quota_manager.py
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import redis

logger = logging.getLogger(__name__)


class SearchBoundary:
    """Represents search boundaries for a single keyword."""
    
    def __init__(self, keyword: str, newest_id: str = None, oldest_id: str = None,
                 last_search: datetime = None, results_count: int = 0,
                 search_window_days: int = 7):
        self.keyword = keyword
        self.newest_id = newest_id  # Most recent tweet we've seen
        self.oldest_id = oldest_id  # Oldest tweet we've seen
        self.last_search = last_search or datetime.utcnow()
        self.results_count = results_count
        self.search_window_days = search_window_days
        
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'keyword': self.keyword,
            'newest_id': self.newest_id,
            'oldest_id': self.oldest_id,
            'last_search': self.last_search.isoformat() if self.last_search else None,
            'results_count': self.results_count,
            'search_window_days': self.search_window_days
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SearchBoundary':
        """Deserialize from dictionary."""
        return cls(
            keyword=data['keyword'],
            newest_id=data.get('newest_id'),
            oldest_id=data.get('oldest_id'),
            last_search=datetime.fromisoformat(data['last_search']) if data.get('last_search') else None,
            results_count=data.get('results_count', 0),
            search_window_days=data.get('search_window_days', 7)
        )


class SearchBoundaryManager:
    """
    Manages search boundaries to prevent re-fetching tweets.
    
    Features:
    - Persistent storage of boundaries per keyword
    - Smart search parameter generation (since_id/until_id)
    - Automatic boundary updates after searches
    - Edge case handling for window changes
    """
    
    def __init__(self, storage_path: Path = None, redis_client: redis.Redis = None):
        """
        Initialize boundary manager.
        
        Args:
            storage_path: Path to store boundaries JSON file
            redis_client: Optional Redis for distributed tracking
        """
        self.storage_path = storage_path or Path("artefacts/search_boundaries.json")
        self.redis = redis_client
        self.boundaries: Dict[str, SearchBoundary] = {}
        
        # Load existing boundaries
        self._load_boundaries()
        
    def _load_boundaries(self):
        """Load boundaries from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for keyword, boundary_data in data.items():
                        self.boundaries[keyword] = SearchBoundary.from_dict(boundary_data)
                logger.info(f"Loaded search boundaries for {len(self.boundaries)} keywords")
            except Exception as e:
                logger.error(f"Failed to load boundaries: {e}")
                
    def _save_boundaries(self):
        """Persist boundaries to storage."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            data = {k: v.to_dict() for k, v in self.boundaries.items()}
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            # Also save to Redis if available
            if self.redis:
                for keyword, boundary in self.boundaries.items():
                    key = f"search:boundary:{keyword}"
                    self.redis.set(key, json.dumps(boundary.to_dict()))
                    self.redis.expire(key, 86400 * 30)  # Keep for 30 days
                    
        except Exception as e:
            logger.error(f"Failed to save boundaries: {e}")
    
    def get_search_params(self, keyword: str, max_results: int = 10, 
                         search_window_days: int = 7) -> Dict:
        """
        Get optimized search parameters for a keyword.
        
        Returns dict with:
        - since_id: Search for tweets newer than this
        - until_id: Search for tweets older than this  
        - search_type: 'initial', 'new_only', 'new_and_old', 'old_only'
        - expected_duplicates: Estimated duplicate count
        """
        params = {
            'search_type': 'initial',
            'expected_duplicates': 0
        }
        
        # Check for existing boundary
        if keyword not in self.boundaries:
            logger.info(f"No boundaries for '{keyword}' - initial search")
            return params
            
        boundary = self.boundaries[keyword]
        
        # Check if search window changed significantly
        if search_window_days > boundary.search_window_days * 1.5:
            logger.info(
                f"Search window expanded for '{keyword}' "
                f"({boundary.search_window_days}→{search_window_days} days), resetting boundaries"
            )
            del self.boundaries[keyword]
            return params
        
        # Check age of last search
        age = datetime.utcnow() - boundary.last_search
        
        # Always search for new tweets since our newest
        if boundary.newest_id:
            params['since_id'] = boundary.newest_id
            params['search_type'] = 'new_only'
            logger.info(
                f"Searching '{keyword}' for new tweets since ID {boundary.newest_id} "
                f"(last search: {age.days}d {age.seconds//3600}h ago)"
            )
        
        # Search for older tweets if we got FULL results last time (likely more available)
        # If we got < max_results, we exhausted the window - no older tweets to find
        if boundary.results_count >= max_results and boundary.oldest_id:
            params['until_id'] = boundary.oldest_id
            params['search_type'] = 'new_and_old' if 'since_id' in params else 'old_only'
            logger.info(
                f"Also searching '{keyword}' for older tweets before ID {boundary.oldest_id} "
                f"(previous search found full {boundary.results_count} results, likely more available)"
            )
        elif boundary.results_count < max_results:
            logger.info(
                f"Not searching older for '{keyword}' - previous search only found "
                f"{boundary.results_count}/{max_results} (exhausted search window)"
            )
        
        return params
    
    def update_boundaries(self, keyword: str, tweets: List[Dict], 
                         search_window_days: int = 7):
        """
        Update boundaries after a search.
        
        Args:
            keyword: The keyword that was searched
            tweets: List of tweets returned (sorted newest first)
            search_window_days: Search window used
        """
        if not tweets:
            logger.info(f"No tweets for '{keyword}', not updating boundaries")
            return
            
        # Get newest and oldest tweet IDs
        newest_id = tweets[0]['id']  # First tweet (most recent)
        oldest_id = tweets[-1]['id']  # Last tweet (oldest)
        
        if keyword in self.boundaries:
            # Merge with existing boundaries
            boundary = self.boundaries[keyword]
            
            # Extend the range if we found newer/older tweets
            if newest_id > (boundary.newest_id or ''):
                logger.info(f"Extended '{keyword}' newer boundary: {boundary.newest_id} → {newest_id}")
                boundary.newest_id = newest_id
                
            if not boundary.oldest_id or oldest_id < boundary.oldest_id:
                logger.info(f"Extended '{keyword}' older boundary: {boundary.oldest_id} → {oldest_id}")
                boundary.oldest_id = oldest_id
                
            boundary.last_search = datetime.utcnow()
            boundary.results_count = len(tweets)
            boundary.search_window_days = search_window_days
            
        else:
            # Create new boundary
            self.boundaries[keyword] = SearchBoundary(
                keyword=keyword,
                newest_id=newest_id,
                oldest_id=oldest_id,
                last_search=datetime.utcnow(),
                results_count=len(tweets),
                search_window_days=search_window_days
            )
            logger.info(
                f"Created boundaries for '{keyword}': "
                f"newest={newest_id}, oldest={oldest_id}, count={len(tweets)}"
            )
        
        # Persist updates
        self._save_boundaries()
    
    def estimate_savings(self) -> Dict:
        """
        Estimate API quota savings from using boundaries.
        
        Returns:
            Dictionary with savings statistics
        """
        total_keywords = len(self.boundaries)
        keywords_with_full_results = sum(
            1 for b in self.boundaries.values() 
            if b.results_count >= 10  # Assuming default max_results
        )
        
        # Estimate duplicates avoided
        duplicates_avoided = sum(
            b.results_count for b in self.boundaries.values()
        )
        
        # Calculate time coverage
        total_days_covered = sum(
            (datetime.utcnow() - b.last_search).days 
            for b in self.boundaries.values()
        )
        
        return {
            'keywords_tracked': total_keywords,
            'keywords_fully_searched': keywords_with_full_results,
            'estimated_duplicates_avoided': duplicates_avoided,
            'average_days_since_search': total_days_covered / max(1, total_keywords),
            'estimated_reads_saved': duplicates_avoided,  # Each duplicate is a wasted read
            'percentage_of_monthly_quota_saved': (duplicates_avoided / 10000) * 100
        }
    
    def reset_keyword(self, keyword: str):
        """Reset boundaries for a specific keyword."""
        if keyword in self.boundaries:
            del self.boundaries[keyword]
            self._save_boundaries()
            logger.info(f"Reset boundaries for '{keyword}'")
    
    def reset_all(self):
        """Reset all boundaries (use with caution)."""
        self.boundaries.clear()
        self._save_boundaries()
        logger.info("Reset all search boundaries")
    
    def get_boundary_info(self, keyword: str) -> Optional[Dict]:
        """Get boundary information for a keyword."""
        if keyword in self.boundaries:
            return self.boundaries[keyword].to_dict()
        return None
    
    def cleanup_old_boundaries(self, days: int = 30):
        """Remove boundaries older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = []
        
        for keyword in list(self.boundaries.keys()):
            if self.boundaries[keyword].last_search < cutoff:
                removed.append(keyword)
                del self.boundaries[keyword]
        
        if removed:
            self._save_boundaries()
            logger.info(f"Removed {len(removed)} old boundaries (>{days} days)")
            
        return removed