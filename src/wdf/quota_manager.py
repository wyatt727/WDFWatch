"""
Twitter API Quota Management Module

Tracks and manages Twitter API usage to prevent quota exhaustion.
Provides real-time monitoring and intelligent rate limiting.

Integrates with: twitter_client.py, scrape.py, web_bridge.py
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
import redis
from prometheus_client import Counter, Gauge

from .settings import settings

logger = logging.getLogger(__name__)

# Prometheus metrics
API_CALLS = Counter(
    "twitter_api_calls_total",
    "Total Twitter API calls made",
    ["endpoint", "status"]
)
QUOTA_REMAINING = Gauge(
    "twitter_quota_remaining",
    "Remaining Twitter API quota"
)
QUOTA_USAGE_RATE = Gauge(
    "twitter_quota_usage_rate",
    "API calls per hour"
)


class QuotaManager:
    """
    Manages Twitter API quota and rate limiting.
    
    Features:
    - Real-time quota tracking
    - Rate limit enforcement
    - Usage prediction
    - Automatic backoff
    - Database persistence
    """
    
    # Twitter API v2 limits (Basic/Free tier)
    MONTHLY_READ_LIMIT = 10000  # Total reads per month
    RATE_LIMIT_WINDOW = 900  # 15 minutes in seconds
    RATE_LIMIT_SEARCHES = 180  # Searches per 15 min window
    
    # Conservative limits to avoid hitting actual limits
    SAFETY_MARGIN = 0.9  # Use only 90% of actual limits
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize quota manager.
        
        Args:
            redis_client: Optional Redis client for distributed tracking
        """
        self.redis = redis_client or redis.Redis.from_url(settings.redis_url)
        self.quota_file = Path(settings.artefacts_dir) / "quota_state.json"
        
        # Redis keys
        self.monthly_usage_key = "twitter:quota:monthly_usage"
        self.rate_limit_key = "twitter:quota:rate_limit"
        self.last_reset_key = "twitter:quota:last_reset"
        
        # Load or initialize quota state
        self._load_quota_state()
        
    def _load_quota_state(self):
        """Load quota state from Redis or file."""
        try:
            # Try Redis first
            monthly_usage = self.redis.get(self.monthly_usage_key)
            if monthly_usage:
                self.monthly_usage = int(monthly_usage)
            else:
                # Fall back to file
                if self.quota_file.exists():
                    with open(self.quota_file) as f:
                        state = json.load(f)
                    self.monthly_usage = state.get('monthly_usage', 0)
                    
                    # Sync to Redis
                    self.redis.set(self.monthly_usage_key, self.monthly_usage)
                else:
                    self.monthly_usage = 0
                    
            # Check for month reset
            self._check_monthly_reset()
            
            # Update Prometheus metric
            QUOTA_REMAINING.set(self.get_remaining_quota())
            
        except Exception as e:
            logger.error(f"Failed to load quota state: {e}")
            self.monthly_usage = 0
    
    def _save_quota_state(self):
        """Persist quota state to Redis and file."""
        try:
            # Save to Redis
            self.redis.set(self.monthly_usage_key, self.monthly_usage)
            
            # Save to file as backup
            state = {
                'monthly_usage': self.monthly_usage,
                'last_updated': datetime.utcnow().isoformat(),
                'month': datetime.utcnow().strftime('%Y-%m')
            }
            with open(self.quota_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            # Update Prometheus
            QUOTA_REMAINING.set(self.get_remaining_quota())
            
        except Exception as e:
            logger.error(f"Failed to save quota state: {e}")
    
    def _check_monthly_reset(self):
        """Check if we've entered a new month and reset quota."""
        last_reset = self.redis.get(self.last_reset_key)
        current_month = datetime.utcnow().strftime('%Y-%m')
        
        if last_reset:
            last_reset = last_reset.decode('utf-8')
            if last_reset != current_month:
                # New month - reset quota
                logger.info(f"New month detected, resetting quota (was {self.monthly_usage})")
                self.monthly_usage = 0
                self.redis.set(self.last_reset_key, current_month)
                self._save_quota_state()
        else:
            # First run
            self.redis.set(self.last_reset_key, current_month)
    
    def get_remaining_quota(self) -> int:
        """Get remaining monthly quota."""
        remaining = self.MONTHLY_READ_LIMIT - self.monthly_usage
        return max(0, remaining)
    
    def check_quota_available(self, required_calls: int = 1) -> Tuple[bool, str]:
        """
        Check if sufficient quota is available.
        
        Args:
            required_calls: Number of API calls needed
            
        Returns:
            Tuple of (is_available, reason_if_not)
        """
        remaining = self.get_remaining_quota()
        
        # Apply safety margin
        safe_remaining = int(remaining * self.SAFETY_MARGIN)
        
        if required_calls > safe_remaining:
            reason = f"Insufficient quota: {required_calls} calls needed, only {safe_remaining} available"
            logger.warning(reason)
            return False, reason
            
        # Check if we're approaching daily limit
        daily_limit = self.MONTHLY_READ_LIMIT // 30  # Rough daily limit
        daily_usage = self._get_daily_usage()
        
        if daily_usage + required_calls > daily_limit:
            reason = f"Would exceed daily limit: {daily_usage + required_calls} > {daily_limit}"
            logger.warning(reason)
            return False, reason
            
        return True, "OK"
    
    def check_rate_limit(self) -> Tuple[bool, float]:
        """
        Check if we're within rate limits.
        
        Returns:
            Tuple of (is_ok, seconds_to_wait_if_limited)
        """
        # Get current window usage
        window_key = f"{self.rate_limit_key}:{int(time.time() // self.RATE_LIMIT_WINDOW)}"
        current_usage = self.redis.get(window_key)
        
        if current_usage:
            current_usage = int(current_usage)
            safe_limit = int(self.RATE_LIMIT_SEARCHES * self.SAFETY_MARGIN)
            
            if current_usage >= safe_limit:
                # Calculate wait time until next window
                current_window = int(time.time() // self.RATE_LIMIT_WINDOW)
                next_window_time = (current_window + 1) * self.RATE_LIMIT_WINDOW
                wait_time = next_window_time - time.time()
                
                logger.warning(f"Rate limited: {current_usage}/{safe_limit} calls in window, wait {wait_time:.1f}s")
                return False, wait_time
        
        return True, 0
    
    def record_api_call(self, endpoint: str = "search", success: bool = True, calls_used: int = 1):
        """
        Record an API call for quota tracking.
        
        Args:
            endpoint: API endpoint called
            success: Whether the call succeeded
            calls_used: Number of API calls consumed
        """
        if success:
            # Update monthly usage
            self.monthly_usage += calls_used
            self._save_quota_state()
            
            # Update rate limit window
            window_key = f"{self.rate_limit_key}:{int(time.time() // self.RATE_LIMIT_WINDOW)}"
            self.redis.incrby(window_key, calls_used)
            self.redis.expire(window_key, self.RATE_LIMIT_WINDOW + 60)  # Expire after window + buffer
            
            # Record daily usage
            daily_key = f"twitter:quota:daily:{datetime.utcnow().strftime('%Y-%m-%d')}"
            self.redis.incrby(daily_key, calls_used)
            self.redis.expire(daily_key, 86400 * 7)  # Keep for 7 days
            
        # Update Prometheus metrics
        API_CALLS.labels(endpoint=endpoint, status="success" if success else "failure").inc(calls_used)
        
        logger.info(
            f"API call recorded: {endpoint} {'✓' if success else '✗'} "
            f"({calls_used} calls, {self.get_remaining_quota()} remaining)"
        )
    
    def _get_daily_usage(self) -> int:
        """Get today's API usage."""
        daily_key = f"twitter:quota:daily:{datetime.utcnow().strftime('%Y-%m-%d')}"
        usage = self.redis.get(daily_key)
        return int(usage) if usage else 0
    
    def get_usage_stats(self) -> Dict:
        """
        Get comprehensive usage statistics.
        
        Returns:
            Dictionary with usage stats and predictions
        """
        remaining = self.get_remaining_quota()
        daily_usage = self._get_daily_usage()
        
        # Calculate usage rate
        days_in_month = 30
        days_elapsed = datetime.utcnow().day
        days_remaining = days_in_month - days_elapsed
        
        if days_elapsed > 0:
            avg_daily_usage = self.monthly_usage / days_elapsed
            projected_monthly = avg_daily_usage * days_in_month
        else:
            avg_daily_usage = 0
            projected_monthly = 0
        
        # Calculate when quota will be exhausted
        if avg_daily_usage > 0 and remaining > 0:
            days_until_exhausted = remaining / avg_daily_usage
            exhaustion_date = datetime.utcnow() + timedelta(days=days_until_exhausted)
        else:
            days_until_exhausted = float('inf')
            exhaustion_date = None
        
        stats = {
            'monthly_limit': self.MONTHLY_READ_LIMIT,
            'monthly_usage': self.monthly_usage,
            'monthly_remaining': remaining,
            'monthly_percentage': (self.monthly_usage / self.MONTHLY_READ_LIMIT) * 100,
            'daily_usage': daily_usage,
            'daily_average': avg_daily_usage,
            'projected_monthly': projected_monthly,
            'days_until_exhausted': days_until_exhausted,
            'exhaustion_date': exhaustion_date.isoformat() if exhaustion_date else None,
            'days_remaining_in_month': days_remaining,
            'recommended_daily_limit': remaining / max(1, days_remaining) if days_remaining > 0 else 0
        }
        
        # Update Prometheus gauge
        QUOTA_USAGE_RATE.set(avg_daily_usage * 24)  # Convert to hourly rate
        
        return stats
    
    def estimate_search_cost(self, num_keywords: int, tweets_per_keyword: int = 100) -> Dict:
        """
        Estimate API cost for a keyword search operation.
        
        Args:
            num_keywords: Number of keywords to search
            tweets_per_keyword: Target tweets per keyword
            
        Returns:
            Cost estimate dictionary
        """
        # Assume we can batch keywords with OR operators
        # Max 25 OR conditions per query
        queries_needed = (num_keywords + 24) // 25
        
        # Each query might need pagination
        pages_per_query = (tweets_per_keyword + 99) // 100  # 100 tweets per page
        
        total_calls = queries_needed * pages_per_query
        
        # Check against quota
        remaining = self.get_remaining_quota()
        can_afford = total_calls <= remaining * self.SAFETY_MARGIN
        
        estimate = {
            'keywords': num_keywords,
            'queries_needed': queries_needed,
            'pages_per_query': pages_per_query,
            'total_api_calls': total_calls,
            'percentage_of_remaining': (total_calls / max(1, remaining)) * 100,
            'can_afford': can_afford,
            'remaining_after': max(0, remaining - total_calls)
        }
        
        if not can_afford:
            # Suggest alternatives
            affordable_keywords = int((remaining * self.SAFETY_MARGIN) / pages_per_query * 25)
            estimate['suggestion'] = f"Reduce to {affordable_keywords} keywords to stay within quota"
        
        return estimate
    
    def wait_if_rate_limited(self) -> bool:
        """
        Check rate limit and wait if necessary.
        
        Returns:
            True if we had to wait, False otherwise
        """
        is_ok, wait_time = self.check_rate_limit()
        
        if not is_ok and wait_time > 0:
            logger.info(f"Rate limited, waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            return True
            
        return False
    
    def get_quota_health(self) -> str:
        """
        Get a simple health status for the quota.
        
        Returns:
            Health status: 'healthy', 'warning', or 'critical'
        """
        stats = self.get_usage_stats()
        
        if stats['monthly_percentage'] < 70:
            return 'healthy'
        elif stats['monthly_percentage'] < 90:
            return 'warning'
        else:
            return 'critical'