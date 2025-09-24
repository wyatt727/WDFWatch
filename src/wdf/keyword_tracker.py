"""
Keyword Effectiveness Tracking Module

Tracks the performance of keywords over time to identify which yield
the most relevant results and optimize future searches.

Integrates with: keyword_optimizer.py, twitter_api_v2.py, web_bridge.py
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import redis
from prometheus_client import Counter, Gauge, Histogram

from .settings import settings

logger = logging.getLogger(__name__)

# Prometheus metrics
KEYWORD_HITS = Counter(
    "keyword_hits_total",
    "Total times a keyword matched tweets",
    ["keyword"]
)
KEYWORD_RELEVANCE = Histogram(
    "keyword_relevance_score",
    "Average relevance score for keyword matches",
    ["keyword"],
    buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
)
KEYWORD_EFFECTIVENESS = Gauge(
    "keyword_effectiveness",
    "Overall effectiveness score for keywords",
    ["keyword"]
)


class KeywordTracker:
    """
    Tracks keyword performance and effectiveness.
    
    Features:
    - Hit rate tracking (how often keywords match)
    - Relevance tracking (average relevance of matches)
    - Trend analysis (performance over time)
    - Recommendations for weight adjustments
    - Database persistence
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize keyword tracker.
        
        Args:
            redis_client: Optional Redis client for distributed tracking
        """
        self.redis = redis_client or redis.Redis.from_url(settings.redis_url)
        self.tracking_file = Path(settings.artefacts_dir) / "keyword_tracking.json"
        
        # Redis keys
        self.hits_key = "keywords:hits:{keyword}"
        self.relevance_key = "keywords:relevance:{keyword}"
        self.history_key = "keywords:history:{keyword}:{date}"
        
        # Load historical data
        self._load_tracking_data()
    
    def _load_tracking_data(self):
        """Load tracking data from file if Redis is empty."""
        try:
            if self.tracking_file.exists():
                with open(self.tracking_file) as f:
                    data = json.load(f)
                    
                # Sync to Redis if needed
                for keyword, stats in data.get('keywords', {}).items():
                    hits_key = self.hits_key.format(keyword=keyword)
                    if not self.redis.exists(hits_key):
                        self.redis.set(hits_key, stats.get('hits', 0))
                        
                        # Store relevance scores
                        rel_key = self.relevance_key.format(keyword=keyword)
                        if 'relevance_scores' in stats:
                            for score in stats['relevance_scores']:
                                self.redis.lpush(rel_key, score)
                            self.redis.ltrim(rel_key, 0, 999)  # Keep last 1000
                            
        except Exception as e:
            logger.error(f"Failed to load tracking data: {e}")
    
    def record_keyword_match(self, keyword: str, relevance_score: float, 
                           tweet_id: str = None, tweet_text: str = None):
        """
        Record a keyword match from search results.
        
        Args:
            keyword: The keyword that matched
            relevance_score: Relevance score of the match (0-1)
            tweet_id: Optional tweet ID
            tweet_text: Optional tweet text for analysis
        """
        # Update hit count
        hits_key = self.hits_key.format(keyword=keyword)
        self.redis.incr(hits_key)
        
        # Track relevance score
        rel_key = self.relevance_key.format(keyword=keyword)
        self.redis.lpush(rel_key, relevance_score)
        self.redis.ltrim(rel_key, 0, 999)  # Keep last 1000 scores
        
        # Record daily history
        today = datetime.utcnow().strftime('%Y-%m-%d')
        history_key = self.history_key.format(keyword=keyword, date=today)
        
        history_data = {
            'hits': 1,
            'relevance': relevance_score,
            'timestamp': datetime.utcnow().isoformat()
        }
        if tweet_id:
            history_data['tweet_id'] = tweet_id
            
        self.redis.lpush(history_key, json.dumps(history_data))
        self.redis.expire(history_key, 86400 * 30)  # Keep for 30 days
        
        # Update Prometheus metrics
        KEYWORD_HITS.labels(keyword=keyword).inc()
        KEYWORD_RELEVANCE.labels(keyword=keyword).observe(relevance_score)
        
        logger.debug(
            f"Recorded match for '{keyword}': "
            f"relevance={relevance_score:.2f}, tweet={tweet_id}"
        )
    
    def record_classification_result(self, keyword: str, classification: str, 
                                   score: float, tweet_id: str = None,
                                   search_window_days: int = None):
        """
        Record the actual classification result for a keyword match.
        This is called AFTER the tweet has been classified as RELEVANT or SKIP.
        
        Args:
            keyword: The keyword that matched
            classification: 'RELEVANT' or 'SKIP'
            score: The classification score (0-1)
            tweet_id: Optional tweet ID
            search_window_days: Number of days searched (for volume calculations)
        """
        # Track search window if provided
        if search_window_days:
            window_key = f"keywords:search_window:{keyword}"
            self.redis.set(window_key, search_window_days)
            self.redis.expire(window_key, 86400 * 30)  # Keep for 30 days
        # Track classification outcomes
        class_key = f"keywords:classification:{keyword}"
        self.redis.hincrby(class_key, classification, 1)
        
        # Track success rate (relevant classifications)
        if classification == 'RELEVANT':
            success_key = f"keywords:success:{keyword}"
            self.redis.incr(success_key)
            
            # Track high-quality matches
            if score >= 0.8:
                quality_key = f"keywords:high_quality:{keyword}"
                self.redis.incr(quality_key)
        else:
            # Track failures (skip classifications)
            failure_key = f"keywords:failure:{keyword}"
            self.redis.incr(failure_key)
        
        # Update effectiveness based on actual classification
        effectiveness_score = score if classification == 'RELEVANT' else score * 0.2
        
        # Track effectiveness scores
        eff_key = f"keywords:effectiveness:{keyword}"
        self.redis.lpush(eff_key, effectiveness_score)
        self.redis.ltrim(eff_key, 0, 999)  # Keep last 1000
        
        # Update Prometheus metrics
        KEYWORD_EFFECTIVENESS.labels(keyword=keyword).set(effectiveness_score)
        
        logger.debug(
            f"Recorded classification for '{keyword}': "
            f"{classification} (score={score:.2f}, effectiveness={effectiveness_score:.2f})"
        )
    
    def get_keyword_stats(self, keyword: str) -> Dict:
        """
        Get comprehensive statistics for a keyword.
        
        Args:
            keyword: The keyword to analyze
            
        Returns:
            Dictionary with keyword statistics
        """
        hits_key = self.hits_key.format(keyword=keyword)
        rel_key = self.relevance_key.format(keyword=keyword)
        class_key = f"keywords:classification:{keyword}"
        success_key = f"keywords:success:{keyword}"
        failure_key = f"keywords:failure:{keyword}"
        quality_key = f"keywords:high_quality:{keyword}"
        eff_key = f"keywords:effectiveness:{keyword}"
        window_key = f"keywords:search_window:{keyword}"
        
        # Get hit count
        hits = self.redis.get(hits_key)
        hit_count = int(hits) if hits else 0
        
        # Get classification stats
        classifications = self.redis.hgetall(class_key)
        relevant_count = int(classifications.get(b'RELEVANT', 0)) if classifications else 0
        skip_count = int(classifications.get(b'SKIP', 0)) if classifications else 0
        total_classified = relevant_count + skip_count
        
        # Get success/failure counts
        success_count = int(self.redis.get(success_key) or 0)
        failure_count = int(self.redis.get(failure_key) or 0)
        quality_count = int(self.redis.get(quality_key) or 0)
        
        # Calculate success rate
        success_rate = (relevant_count / total_classified) if total_classified > 0 else 0
        
        # Get search window (days back)
        search_window = self.redis.get(window_key)
        search_days = int(search_window) if search_window else 7  # Default to 7 days
        
        # Get effectiveness scores
        effectiveness_scores = []
        eff_scores = self.redis.lrange(eff_key, 0, -1)
        for score in eff_scores:
            try:
                effectiveness_scores.append(float(score))
            except (ValueError, TypeError):
                continue
        
        # Get relevance scores (for backward compatibility)
        relevance_scores = []
        scores = self.redis.lrange(rel_key, 0, -1)
        for score in scores:
            try:
                relevance_scores.append(float(score))
            except (ValueError, TypeError):
                continue
        
        # Calculate statistics
        if relevance_scores:
            avg_relevance = sum(relevance_scores) / len(relevance_scores)
            max_relevance = max(relevance_scores)
            min_relevance = min(relevance_scores)
            
            # Calculate trend (compare recent vs older)
            recent = relevance_scores[:100]
            older = relevance_scores[100:200] if len(relevance_scores) > 100 else []
            
            if older:
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older)
                trend = recent_avg - older_avg
            else:
                trend = 0
        else:
            avg_relevance = 0
            max_relevance = 0
            min_relevance = 0
            trend = 0
        
        # Calculate effectiveness score using classification success rate if available
        # Pass relevant_count for volume-based scoring
        effectiveness = self._calculate_effectiveness(
            hit_count, avg_relevance, success_rate, 
            relevant_count=relevant_count,
            search_days=search_days  # Use actual search window
        )
        
        # Use effectiveness scores if available, otherwise fall back to relevance
        if effectiveness_scores:
            avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores)
        else:
            avg_effectiveness = effectiveness
        
        # Calculate volume metrics
        tweets_per_day = relevant_count / max(1, search_days) if relevant_count else 0
        
        return {
            'keyword': keyword,
            'hit_count': hit_count,
            'classified_count': total_classified,
            'relevant_count': relevant_count,
            'skip_count': skip_count,
            'success_rate': success_rate,
            'high_quality_count': quality_count,
            'average_relevance': avg_relevance,
            'average_effectiveness': avg_effectiveness,
            'max_relevance': max_relevance,
            'min_relevance': min_relevance,
            'trend': trend,
            'effectiveness': effectiveness,
            'sample_size': len(relevance_scores),
            'search_days': search_days,
            'tweets_per_day': tweets_per_day,
            'volume_score': min(1.0, tweets_per_day / 5)  # Normalized volume (5+ tweets/day = max)
        }
    
    def _calculate_effectiveness(self, hits: int, avg_relevance: float, 
                                success_rate: float = None, relevant_count: int = 0,
                                search_days: int = 7) -> float:
        """
        Calculate overall effectiveness score for a keyword.
        
        Args:
            hits: Number of times keyword matched
            avg_relevance: Average relevance score
            success_rate: Classification success rate (RELEVANT/total)
            relevant_count: Absolute number of relevant tweets found
            search_days: Number of days searched
            
        Returns:
            Effectiveness score (0-1)
        """
        import math
        
        # Calculate volume score (relevant tweets per day)
        tweets_per_day = relevant_count / max(1, search_days)
        
        # Normalize volume score (logarithmic, caps at ~10 relevant tweets/day)
        volume_score = min(1.0, math.log10(max(1, tweets_per_day * 10)) / 1.5)
        
        # Calculate confidence based on sample size
        # Need at least 10 samples for high confidence
        sample_confidence = min(1.0, hits / 10)
        
        if success_rate is not None and hits >= 5:  # Minimum 5 samples
            # Balanced scoring:
            # 40% weight on volume (how many relevant tweets we get)
            # 40% weight on success rate (efficiency)
            # 20% weight on sample confidence
            
            # Adjust success rate by confidence
            adjusted_success = success_rate * sample_confidence
            
            effectiveness = (
                volume_score * 0.4 +           # Rewards high-yield keywords
                adjusted_success * 0.4 +       # Rewards high precision
                sample_confidence * 0.2        # Penalizes low sample sizes
            )
            
            # Apply penalty for very low volume (< 1 relevant tweet per day)
            if tweets_per_day < 1:
                effectiveness *= 0.7
                
        else:
            # Not enough data - use exploratory score
            hit_score = min(1.0, math.log10(max(1, hits)) / 3)
            effectiveness = (hit_score * 0.3) + (avg_relevance * 0.3) + 0.4  # Bias toward exploration
        
        return min(1.0, effectiveness)
    
    def get_all_keyword_stats(self) -> List[Dict]:
        """
        Get statistics for all tracked keywords.
        
        Returns:
            List of keyword statistics sorted by effectiveness
        """
        # Get all keywords
        pattern = self.hits_key.format(keyword='*')
        pattern = pattern.replace('{keyword}', '*')
        
        all_stats = []
        for key in self.redis.scan_iter(match=pattern):
            # Extract keyword from key
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            keyword = key_str.replace('keywords:hits:', '')
            
            stats = self.get_keyword_stats(keyword)
            all_stats.append(stats)
            
            # Update Prometheus gauge
            KEYWORD_EFFECTIVENESS.labels(keyword=keyword).set(stats['effectiveness'])
        
        # Sort by effectiveness
        all_stats.sort(key=lambda x: x['effectiveness'], reverse=True)
        
        return all_stats
    
    def get_weight_recommendations(self, keywords: List[Dict[str, float]]) -> List[Dict]:
        """
        Get recommendations for keyword weight adjustments.
        
        Args:
            keywords: Current keywords with weights
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for kw_dict in keywords:
            keyword = kw_dict['keyword']
            current_weight = kw_dict.get('weight', 1.0)
            
            stats = self.get_keyword_stats(keyword)
            
            # Skip if no data
            if stats['hit_count'] == 0:
                continue
            
            # Calculate recommended weight based on effectiveness
            recommended_weight = stats['effectiveness']
            
            # Only recommend if significant difference
            weight_diff = abs(recommended_weight - current_weight)
            if weight_diff > 0.15:
                recommendation = {
                    'keyword': keyword,
                    'current_weight': current_weight,
                    'recommended_weight': round(recommended_weight, 2),
                    'reason': self._get_recommendation_reason(stats, current_weight, recommended_weight),
                    'confidence': min(1.0, stats['sample_size'] / 100),  # Higher confidence with more data
                    'stats': stats
                }
                recommendations.append(recommendation)
        
        # Sort by confidence and impact
        recommendations.sort(
            key=lambda x: x['confidence'] * abs(x['recommended_weight'] - x['current_weight']),
            reverse=True
        )
        
        return recommendations
    
    def _get_recommendation_reason(self, stats: Dict, current: float, recommended: float) -> str:
        """Generate human-readable recommendation reason."""
        if recommended > current:
            if stats['average_relevance'] > 0.8:
                return f"High relevance ({stats['average_relevance']:.2f}) - increase weight"
            elif stats['hit_count'] > 100:
                return f"High hit rate ({stats['hit_count']} hits) - increase weight"
            else:
                return "Better performance than current weight suggests"
        else:
            if stats['average_relevance'] < 0.4:
                return f"Low relevance ({stats['average_relevance']:.2f}) - decrease weight"
            elif stats['trend'] < -0.2:
                return "Declining performance trend - decrease weight"
            else:
                return "Lower performance than current weight suggests"
    
    def get_trending_keywords(self, days: int = 7) -> List[Dict]:
        """
        Get keywords with improving performance trends.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of trending keywords
        """
        all_stats = self.get_all_keyword_stats()
        
        trending = []
        for stats in all_stats:
            if stats['trend'] > 0.1 and stats['sample_size'] >= 10:
                trending.append({
                    'keyword': stats['keyword'],
                    'trend': stats['trend'],
                    'current_effectiveness': stats['effectiveness'],
                    'average_relevance': stats['average_relevance']
                })
        
        trending.sort(key=lambda x: x['trend'], reverse=True)
        return trending[:10]  # Top 10 trending
    
    def get_underperforming_keywords(self, threshold: float = 0.3) -> List[Dict]:
        """
        Identify keywords that consistently underperform.
        
        Args:
            threshold: Effectiveness threshold
            
        Returns:
            List of underperforming keywords
        """
        all_stats = self.get_all_keyword_stats()
        
        underperforming = []
        for stats in all_stats:
            # Check if keyword has poor classification success rate
            if stats.get('success_rate', 1) < threshold and stats.get('classified_count', 0) >= 10:
                api_waste = stats.get('skip_count', 0)  # Tweets that wasted API calls
                underperforming.append({
                    'keyword': stats['keyword'],
                    'success_rate': stats.get('success_rate', 0),
                    'effectiveness': stats['effectiveness'],
                    'average_relevance': stats['average_relevance'],
                    'hit_count': stats['hit_count'],
                    'api_calls_wasted': api_waste,
                    'recommendation': f'Remove or reduce weight - {api_waste} API calls resulted in SKIP'
                })
        
        underperforming.sort(key=lambda x: x['api_calls_wasted'], reverse=True)
        return underperforming
    
    def get_api_waste_report(self) -> Dict:
        """
        Generate a report on API call waste by keyword.
        
        Returns:
            Report showing which keywords are wasting the most API calls
        """
        all_stats = self.get_all_keyword_stats()
        
        total_classified = sum(s.get('classified_count', 0) for s in all_stats)
        total_skipped = sum(s.get('skip_count', 0) for s in all_stats)
        total_relevant = sum(s.get('relevant_count', 0) for s in all_stats)
        
        # Find worst offenders
        worst_keywords = []
        for stats in all_stats:
            if stats.get('skip_count', 0) > 0:
                worst_keywords.append({
                    'keyword': stats['keyword'],
                    'skip_count': stats.get('skip_count', 0),
                    'relevant_count': stats.get('relevant_count', 0),
                    'success_rate': stats.get('success_rate', 0),
                    'waste_percentage': (stats.get('skip_count', 0) / max(1, stats.get('classified_count', 1))) * 100
                })
        
        worst_keywords.sort(key=lambda x: x['skip_count'], reverse=True)
        
        return {
            'summary': {
                'total_tweets_classified': total_classified,
                'total_relevant': total_relevant,
                'total_skipped': total_skipped,
                'overall_success_rate': (total_relevant / max(1, total_classified)),
                'api_calls_wasted': total_skipped,
                'efficiency_percentage': (total_relevant / max(1, total_classified)) * 100
            },
            'worst_keywords': worst_keywords[:10],  # Top 10 waste contributors
            'recommendations': self._generate_waste_recommendations(worst_keywords)
        }
    
    def _generate_waste_recommendations(self, worst_keywords: List[Dict]) -> List[str]:
        """Generate recommendations to reduce API waste."""
        recommendations = []
        
        # Calculate total waste
        total_waste = sum(k['skip_count'] for k in worst_keywords)
        
        if total_waste > 100:
            recommendations.append(
                f"Critical: {total_waste} API calls resulted in SKIP classifications. "
                "Immediate keyword optimization required."
            )
        
        # Find keywords to remove
        remove_candidates = [k for k in worst_keywords if k['success_rate'] < 0.2]
        if remove_candidates:
            keywords_to_remove = ', '.join(k['keyword'] for k in remove_candidates[:5])
            recommendations.append(
                f"Remove these keywords with <20% success rate: {keywords_to_remove}"
            )
        
        # Find keywords to reduce weight
        reduce_candidates = [k for k in worst_keywords if 0.2 <= k['success_rate'] < 0.5]
        if reduce_candidates:
            keywords_to_reduce = ', '.join(k['keyword'] for k in reduce_candidates[:5])
            recommendations.append(
                f"Reduce weight for these keywords with 20-50% success rate: {keywords_to_reduce}"
            )
        
        # Calculate potential savings
        if worst_keywords[:5]:
            potential_savings = sum(k['skip_count'] for k in worst_keywords[:5])
            recommendations.append(
                f"Removing the 5 worst keywords would save {potential_savings} API calls "
                f"({(potential_savings / max(1, total_waste)) * 100:.1f}% of waste)"
            )
        
        return recommendations
    
    def export_tracking_data(self) -> Dict:
        """
        Export all tracking data for analysis.
        
        Returns:
            Complete tracking data dictionary
        """
        all_stats = self.get_all_keyword_stats()
        recommendations = self.get_weight_recommendations(
            [{'keyword': s['keyword'], 'weight': 0.5} for s in all_stats]
        )
        trending = self.get_trending_keywords()
        underperforming = self.get_underperforming_keywords()
        
        export_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_keywords': len(all_stats),
                'average_effectiveness': sum(s['effectiveness'] for s in all_stats) / len(all_stats) if all_stats else 0,
                'trending_count': len(trending),
                'underperforming_count': len(underperforming)
            },
            'keywords': all_stats,
            'recommendations': recommendations,
            'trending': trending,
            'underperforming': underperforming
        }
        
        # Save to file
        with open(self.tracking_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported tracking data: {len(all_stats)} keywords")
        
        return export_data
    
    def reset_keyword_data(self, keyword: str):
        """
        Reset tracking data for a specific keyword.
        
        Args:
            keyword: Keyword to reset
        """
        hits_key = self.hits_key.format(keyword=keyword)
        rel_key = self.relevance_key.format(keyword=keyword)
        
        self.redis.delete(hits_key)
        self.redis.delete(rel_key)
        
        # Delete history
        pattern = self.history_key.format(keyword=keyword, date='*')
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)
        
        logger.info(f"Reset tracking data for keyword: {keyword}")