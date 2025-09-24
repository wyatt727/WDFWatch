"""
API Usage Monitor

Real-time monitoring and tracking of Twitter API usage with
alerts, limits, and visualization.

Integrates with: quota_manager.py, twitter_api_v2.py
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class APIMonitor:
    """
    Monitors Twitter API usage and enforces safety limits.
    
    Features:
    - Real-time credit tracking
    - Usage pattern analysis
    - Automatic throttling
    - Alert generation
    - Historical tracking
    """
    
    def __init__(self, quota_manager=None, redis_client=None):
        """Initialize the API monitor."""
        self.quota_manager = quota_manager
        self.redis = redis_client
        
        # Usage tracking
        self.session_start = datetime.now()
        self.api_calls = []
        self.credits_used = 0
        self.queries_executed = []
        
        # Safety limits
        self.max_credits_per_session = 100
        self.max_calls_per_minute = 10
        self.alert_threshold = 50  # Alert when this many credits used
        
        # Load historical data
        self.history_file = Path("artefacts") / "api_usage_history.json"
        self.history_file.parent.mkdir(exist_ok=True)
        self._load_history()
    
    def _load_history(self):
        """Load historical usage data."""
        self.history = {
            "sessions": [],
            "total_credits_used": 0,
            "total_api_calls": 0
        }
        
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    self.history = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load usage history: {e}")
    
    def _save_history(self):
        """Save usage history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage history: {e}")
    
    def track_api_call(self, endpoint: str, credits: int = 1, 
                      query: str = None, response_count: int = 0):
        """
        Track an API call.
        
        Args:
            endpoint: API endpoint called
            credits: Credits consumed
            query: Query string used
            response_count: Number of items returned
        """
        call_data = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "credits": credits,
            "query": query[:100] if query else None,  # Truncate for storage
            "response_count": response_count
        }
        
        self.api_calls.append(call_data)
        self.credits_used += credits
        
        # Check for alerts
        if self.credits_used >= self.alert_threshold:
            self._generate_alert(
                f"High API usage: {self.credits_used} credits used in this session"
            )
        
        # Check rate limiting
        self._check_rate_limit()
        
        # Log the call
        logger.info(
            f"API call tracked: {endpoint} ({credits} credits, {response_count} results)"
        )
    
    def _check_rate_limit(self):
        """Check if we're approaching rate limits."""
        # Count recent calls (last minute)
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        recent_calls = [
            c for c in self.api_calls 
            if datetime.fromisoformat(c["timestamp"]) > one_minute_ago
        ]
        
        if len(recent_calls) >= self.max_calls_per_minute:
            logger.warning(
                f"Rate limit approaching: {len(recent_calls)} calls in last minute"
            )
            # Enforce a delay
            time.sleep(10)  # Wait 10 seconds
    
    def _generate_alert(self, message: str):
        """Generate an alert for high usage or issues."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "credits_used": self.credits_used,
            "session_duration": str(datetime.now() - self.session_start)
        }
        
        logger.warning(f"⚠️ ALERT: {message}")
        
        # Save alert to file
        alert_file = Path("artefacts") / "api_alerts.log"
        try:
            with open(alert_file, 'a') as f:
                f.write(json.dumps(alert) + "\n")
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
    
    def check_can_proceed(self, estimated_credits: int = 1) -> bool:
        """
        Check if it's safe to proceed with API calls.
        
        Args:
            estimated_credits: Estimated credits needed
            
        Returns:
            True if safe to proceed
        """
        # Check session limit
        if self.credits_used + estimated_credits > self.max_credits_per_session:
            logger.error(
                f"Session limit would be exceeded: "
                f"{self.credits_used} + {estimated_credits} > {self.max_credits_per_session}"
            )
            return False
        
        # Check quota if available
        if self.quota_manager:
            remaining = self.quota_manager.get_remaining_quota()
            if remaining < estimated_credits:
                logger.error(
                    f"Insufficient quota: {remaining} < {estimated_credits}"
                )
                return False
        
        return True
    
    def get_session_stats(self) -> Dict:
        """Get current session statistics."""
        duration = datetime.now() - self.session_start
        
        # Calculate rates
        credits_per_minute = 0
        if duration.total_seconds() > 0:
            credits_per_minute = (self.credits_used / duration.total_seconds()) * 60
        
        # Group by endpoint
        endpoint_stats = defaultdict(lambda: {"calls": 0, "credits": 0})
        for call in self.api_calls:
            endpoint = call["endpoint"]
            endpoint_stats[endpoint]["calls"] += 1
            endpoint_stats[endpoint]["credits"] += call["credits"]
        
        return {
            "session_start": self.session_start.isoformat(),
            "duration": str(duration),
            "total_calls": len(self.api_calls),
            "credits_used": self.credits_used,
            "credits_per_minute": round(credits_per_minute, 2),
            "endpoints": dict(endpoint_stats),
            "remaining_session_credits": self.max_credits_per_session - self.credits_used
        }
    
    def get_usage_summary(self) -> Dict:
        """Get comprehensive usage summary."""
        # Current session
        session_stats = self.get_session_stats()
        
        # Historical stats
        total_historical = self.history.get("total_credits_used", 0)
        
        # Quota status
        quota_status = {}
        if self.quota_manager:
            quota_status = {
                "remaining": self.quota_manager.get_remaining_quota(),
                "usage_stats": self.quota_manager.get_usage_stats()
            }
        
        # Recent queries
        recent_queries = self.queries_executed[-10:] if self.queries_executed else []
        
        return {
            "current_session": session_stats,
            "historical": {
                "total_credits_all_time": total_historical + self.credits_used,
                "total_sessions": len(self.history.get("sessions", [])) + 1,
                "average_credits_per_session": (
                    total_historical / len(self.history.get("sessions", []))
                    if self.history.get("sessions") else 0
                )
            },
            "quota": quota_status,
            "recent_queries": recent_queries,
            "alerts": {
                "credits_used": self.credits_used >= self.alert_threshold,
                "approaching_limit": self.credits_used >= self.max_credits_per_session * 0.8
            }
        }
    
    def end_session(self):
        """End the current session and save statistics."""
        session_data = {
            "start": self.session_start.isoformat(),
            "end": datetime.now().isoformat(),
            "credits_used": self.credits_used,
            "api_calls": len(self.api_calls),
            "queries": len(self.queries_executed)
        }
        
        # Update history
        self.history["sessions"].append(session_data)
        self.history["total_credits_used"] += self.credits_used
        self.history["total_api_calls"] += len(self.api_calls)
        
        # Save history
        self._save_history()
        
        logger.info(
            f"Session ended: {self.credits_used} credits used in {len(self.api_calls)} calls"
        )
    
    def generate_dashboard(self) -> str:
        """Generate a text dashboard of API usage."""
        stats = self.get_usage_summary()
        session = stats["current_session"]
        
        dashboard = []
        dashboard.append("="*60)
        dashboard.append("API USAGE DASHBOARD")
        dashboard.append("="*60)
        dashboard.append(f"Session Start: {session['session_start']}")
        dashboard.append(f"Duration: {session['duration']}")
        dashboard.append("")
        
        # Current session
        dashboard.append("CURRENT SESSION:")
        dashboard.append(f"  API Calls: {session['total_calls']}")
        dashboard.append(f"  Credits Used: {session['credits_used']}/{self.max_credits_per_session}")
        dashboard.append(f"  Rate: {session['credits_per_minute']} credits/min")
        dashboard.append(f"  Remaining: {session['remaining_session_credits']} credits")
        dashboard.append("")
        
        # Endpoint breakdown
        if session["endpoints"]:
            dashboard.append("ENDPOINTS USED:")
            for endpoint, data in session["endpoints"].items():
                dashboard.append(f"  {endpoint}: {data['calls']} calls, {data['credits']} credits")
            dashboard.append("")
        
        # Quota status
        if stats["quota"]:
            dashboard.append("QUOTA STATUS:")
            dashboard.append(f"  Remaining: {stats['quota'].get('remaining', 'Unknown')}")
            dashboard.append("")
        
        # Alerts
        alerts = stats["alerts"]
        if any(alerts.values()):
            dashboard.append("⚠️ ALERTS:")
            if alerts["credits_used"]:
                dashboard.append(f"  High credit usage ({self.credits_used} credits)")
            if alerts["approaching_limit"]:
                dashboard.append(f"  Approaching session limit")
            dashboard.append("")
        
        # Historical
        hist = stats["historical"]
        dashboard.append("HISTORICAL USAGE:")
        dashboard.append(f"  Total Credits Used: {hist['total_credits_all_time']}")
        dashboard.append(f"  Total Sessions: {hist['total_sessions']}")
        dashboard.append(f"  Avg per Session: {hist['average_credits_per_session']:.1f}")
        
        dashboard.append("="*60)
        
        return "\n".join(dashboard)
    
    def set_safety_limits(self, max_credits: int = None, max_rate: int = None):
        """
        Update safety limits.
        
        Args:
            max_credits: Maximum credits per session
            max_rate: Maximum calls per minute
        """
        if max_credits:
            self.max_credits_per_session = max_credits
            logger.info(f"Updated session credit limit to {max_credits}")
        
        if max_rate:
            self.max_calls_per_minute = max_rate
            logger.info(f"Updated rate limit to {max_rate} calls/min")


# Global monitor instance
_api_monitor = None

def get_api_monitor():
    """Get or create the global API monitor instance."""
    global _api_monitor
    if _api_monitor is None:
        _api_monitor = APIMonitor()
    return _api_monitor


def track_api_usage(endpoint: str, credits: int = 1, **kwargs):
    """Convenience function to track API usage."""
    monitor = get_api_monitor()
    monitor.track_api_call(endpoint, credits, **kwargs)


if __name__ == "__main__":
    # Demo the dashboard
    monitor = APIMonitor()
    
    # Simulate some API calls
    monitor.track_api_call("search", credits=1, response_count=50)
    monitor.track_api_call("search", credits=1, response_count=45)
    monitor.track_api_call("tweet_lookup", credits=1, response_count=1)
    
    # Show dashboard
    print(monitor.generate_dashboard())
    
    # End session
    monitor.end_session()