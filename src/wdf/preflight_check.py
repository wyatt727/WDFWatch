"""
Pre-flight Check Module

Validates configuration and environment before making Twitter API calls
to prevent accidental quota exhaustion and ensure proper setup.

Integrates with: twitter_api_v2.py, scrape.py, settings
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PreflightChecker:
    """
    Performs safety checks before Twitter API usage.
    
    Features:
    - Validates API credentials
    - Checks quota availability
    - Verifies safe settings
    - Estimates API usage
    - Provides warnings and recommendations
    """
    
    def __init__(self, settings: Dict = None):
        """Initialize with optional settings override."""
        self.settings = settings or {}
        
        # Load safe defaults
        self.safe_defaults = self._load_safe_defaults()
        
        # Track check results
        self.warnings = []
        self.errors = []
        self.recommendations = []
    
    def _load_safe_defaults(self) -> Dict:
        """Load safe default configuration."""
        config_path = Path(__file__).parent.parent.parent / "config" / "safe_defaults.json"
        
        if config_path.exists():
            try:
                with open(config_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load safe defaults: {e}")
        
        # Fallback defaults
        return {
            "settings": {
                "maxTweets": 20,
                "daysBack": 3,
                "minLikes": 5
            },
            "safety": {
                "maxApiCallsPerRun": 10
            }
        }
    
    def check_environment(self) -> bool:
        """
        Check environment variables and safety settings.
        
        Returns:
            True if environment is safe for API usage
        """
        # Check if auto-scrape is disabled
        if os.getenv("WDF_NO_AUTO_SCRAPE", "false").lower() == "true":
            self.recommendations.append("✅ Auto-scrape is disabled (safe mode)")
        else:
            self.warnings.append("⚠️ Auto-scrape is enabled - API calls will be made automatically")
        
        # Check if in mock mode
        if os.getenv("WDF_MOCK_MODE", "false").lower() == "true":
            self.recommendations.append("✅ Mock mode enabled - no real API calls")
            return True
        
        # Check for API credentials
        has_credentials = all([
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        ])
        
        if not has_credentials:
            self.errors.append("❌ Twitter API credentials not configured")
            return False
        
        return True
    
    def check_settings_safety(self, settings: Dict) -> bool:
        """
        Validate that settings are within safe limits.
        
        Args:
            settings: Scraping settings to validate
            
        Returns:
            True if settings are safe
        """
        safe_settings = self.safe_defaults.get("settings", {})
        
        # Check maxTweets
        max_tweets = settings.get("maxTweets", 100)
        safe_max = safe_settings.get("maxTweets", 20)
        
        if max_tweets > safe_max * 5:  # More than 5x safe default
            self.warnings.append(
                f"⚠️ maxTweets ({max_tweets}) is very high for initial testing. "
                f"Recommended: {safe_max}"
            )
        
        # Check daysBack
        days_back = settings.get("daysBack", 7)
        if days_back > 7:
            self.warnings.append(
                f"⚠️ daysBack ({days_back}) > 7 requires Academic access. "
                "Limiting to 7 days for standard access."
            )
        
        # Check engagement thresholds
        if all([
            settings.get("minLikes", 0) == 0,
            settings.get("minRetweets", 0) == 0,
            settings.get("minReplies", 0) == 0
        ]):
            self.warnings.append(
                "⚠️ No engagement thresholds set - will retrieve all tweets. "
                "Consider setting minLikes, minRetweets, or minReplies to reduce volume."
            )
        
        # Check exclusions
        if not settings.get("excludeReplies") and not settings.get("excludeRetweets"):
            self.recommendations.append(
                "💡 Consider excluding replies and retweets to focus on original content"
            )
        
        return len(self.errors) == 0
    
    def estimate_api_usage(self, keywords: List, settings: Dict) -> Dict:
        """
        Estimate API credit usage before execution.
        
        Args:
            keywords: List of keywords to search
            settings: Scraping settings
            
        Returns:
            Dictionary with usage estimates
        """
        max_tweets = settings.get("maxTweets", 100)
        num_keywords = len(keywords)
        
        # Estimate queries needed
        # With OR operators, we can combine up to 25 keywords per query
        queries_needed = (num_keywords + 24) // 25
        
        # Each query can return up to 100 tweets per page
        pages_per_query = (max_tweets + 99) // 100
        
        # Total API calls
        estimated_calls = queries_needed * pages_per_query
        
        # Check against safe limits
        safe_limit = self.safe_defaults.get("safety", {}).get("maxApiCallsPerRun", 10)
        
        estimate = {
            "keywords": num_keywords,
            "queries_needed": queries_needed,
            "pages_per_query": pages_per_query,
            "estimated_api_calls": estimated_calls,
            "safe_limit": safe_limit,
            "within_safe_limit": estimated_calls <= safe_limit
        }
        
        if not estimate["within_safe_limit"]:
            self.warnings.append(
                f"⚠️ Estimated {estimated_calls} API calls exceeds safe limit of {safe_limit}. "
                f"Consider reducing keywords or maxTweets."
            )
        
        return estimate
    
    def check_quota_available(self, quota_manager=None) -> bool:
        """
        Check if sufficient API quota is available.
        
        Args:
            quota_manager: Optional QuotaManager instance
            
        Returns:
            True if quota is sufficient
        """
        if not quota_manager:
            # Can't check without quota manager
            self.recommendations.append(
                "💡 Unable to check quota - ensure you have sufficient API credits"
            )
            return True
        
        try:
            remaining = quota_manager.get_remaining_quota()
            
            if remaining < 100:
                self.errors.append(
                    f"❌ Low API quota remaining: {remaining}. "
                    "Wait for quota reset or reduce usage."
                )
                return False
            elif remaining < 1000:
                self.warnings.append(
                    f"⚠️ Limited API quota remaining: {remaining}. "
                    "Use conservative settings."
                )
            else:
                self.recommendations.append(
                    f"✅ Sufficient API quota available: {remaining}"
                )
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to check quota: {e}")
            return True
    
    def run_all_checks(self, keywords: List = None, settings: Dict = None, 
                       quota_manager=None) -> Tuple[bool, Dict]:
        """
        Run all pre-flight checks.
        
        Args:
            keywords: Optional keywords list
            settings: Optional settings dict
            quota_manager: Optional QuotaManager instance
            
        Returns:
            Tuple of (safe_to_proceed, check_results)
        """
        self.warnings = []
        self.errors = []
        self.recommendations = []
        
        settings = settings or self.settings
        keywords = keywords or []
        
        # Run checks
        env_ok = self.check_environment()
        settings_ok = self.check_settings_safety(settings)
        quota_ok = self.check_quota_available(quota_manager)
        
        # Estimate usage if keywords provided
        usage_estimate = None
        if keywords:
            usage_estimate = self.estimate_api_usage(keywords, settings)
        
        # Compile results
        results = {
            "timestamp": datetime.now().isoformat(),
            "environment_ok": env_ok,
            "settings_ok": settings_ok,
            "quota_ok": quota_ok,
            "safe_to_proceed": env_ok and settings_ok and quota_ok and len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "usage_estimate": usage_estimate
        }
        
        # Log summary
        if results["safe_to_proceed"]:
            logger.info("✅ Pre-flight checks passed - safe to proceed")
        else:
            logger.warning(f"⚠️ Pre-flight checks failed: {len(self.errors)} errors, {len(self.warnings)} warnings")
            for error in self.errors:
                logger.error(error)
        
        return results["safe_to_proceed"], results
    
    def get_safe_settings_recommendation(self, current_settings: Dict) -> Dict:
        """
        Get recommended safe settings based on current configuration.
        
        Args:
            current_settings: Current settings dict
            
        Returns:
            Recommended safe settings
        """
        safe = self.safe_defaults.get("settings", {}).copy()
        
        # Start very conservative
        if not current_settings:
            return safe
        
        # Gradually increase from safe defaults
        current_max = current_settings.get("maxTweets", 100)
        
        if current_max <= 20:
            safe["maxTweets"] = 20
        elif current_max <= 50:
            safe["maxTweets"] = 30
        elif current_max <= 100:
            safe["maxTweets"] = 50
        else:
            safe["maxTweets"] = 75
        
        # Always recommend engagement filters
        safe["minLikes"] = max(3, current_settings.get("minLikes", 0))
        safe["minRetweets"] = max(1, current_settings.get("minRetweets", 0))
        
        # Recommend exclusions
        safe["excludeReplies"] = True
        safe["excludeRetweets"] = True
        
        return safe
    
    def generate_report(self, results: Dict) -> str:
        """
        Generate human-readable pre-flight check report.
        
        Args:
            results: Check results dict
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("="*60)
        report.append("PRE-FLIGHT CHECK REPORT")
        report.append("="*60)
        report.append(f"Timestamp: {results['timestamp']}")
        report.append("")
        
        # Overall status
        if results["safe_to_proceed"]:
            report.append("✅ SAFE TO PROCEED")
        else:
            report.append("❌ NOT SAFE TO PROCEED")
        
        report.append("")
        
        # Errors
        if results["errors"]:
            report.append("ERRORS:")
            for error in results["errors"]:
                report.append(f"  {error}")
            report.append("")
        
        # Warnings
        if results["warnings"]:
            report.append("WARNINGS:")
            for warning in results["warnings"]:
                report.append(f"  {warning}")
            report.append("")
        
        # Recommendations
        if results["recommendations"]:
            report.append("RECOMMENDATIONS:")
            for rec in results["recommendations"]:
                report.append(f"  {rec}")
            report.append("")
        
        # Usage estimate
        if results.get("usage_estimate"):
            est = results["usage_estimate"]
            report.append("USAGE ESTIMATE:")
            report.append(f"  Keywords: {est['keywords']}")
            report.append(f"  Queries needed: {est['queries_needed']}")
            report.append(f"  Estimated API calls: {est['estimated_api_calls']}")
            report.append(f"  Safe limit: {est['safe_limit']}")
            report.append(f"  Within safe limit: {est['within_safe_limit']}")
        
        report.append("="*60)
        
        return "\n".join(report)


def run_preflight_check(keywords=None, settings=None):
    """
    Convenience function to run pre-flight checks.
    
    Returns:
        True if safe to proceed
    """
    checker = PreflightChecker()
    safe, results = checker.run_all_checks(keywords, settings)
    
    # Print report
    print(checker.generate_report(results))
    
    return safe


if __name__ == "__main__":
    # Run standalone pre-flight check
    import sys
    
    # Load settings if available
    settings = {
        "maxTweets": 20,
        "daysBack": 3,
        "minLikes": 5,
        "excludeReplies": True,
        "excludeRetweets": True
    }
    
    # Sample keywords
    keywords = ["federalism", "constitutional", "state rights"]
    
    # Run check
    if run_preflight_check(keywords, settings):
        print("\n✅ System ready for Twitter API usage")
        sys.exit(0)
    else:
        print("\n❌ Please address issues before using Twitter API")
        sys.exit(1)