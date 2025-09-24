"""
Keyword Learning and Dynamic Weight Adjustment Module

Implements a self-improving system that learns keyword effectiveness
across episodes and automatically adjusts weights for future searches.

Integrates with: keyword_tracker.py, keyword_optimizer.py, summarization tasks
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import redis
from collections import defaultdict
import math

from .settings import settings
from .keyword_tracker import KeywordTracker

logger = logging.getLogger(__name__)


class KeywordLearner:
    """
    Manages dynamic keyword weight learning across episodes.
    
    Features:
    - Persistent keyword performance history
    - Automatic weight adjustment based on past performance
    - Decay mechanism for old data
    - Exploration vs exploitation balance
    - Similar keyword recognition
    """
    
    # Learning parameters
    LEARNING_RATE = 0.3  # How much to adjust weights based on new data
    DECAY_FACTOR = 0.95  # How much to decay old performance data per month
    EXPLORATION_WEIGHT = 0.6  # Default weight for new/unknown keywords
    MIN_WEIGHT = 0.05  # Never reduce weight below this
    MAX_WEIGHT = 1.0  # Maximum weight
    
    # Performance thresholds
    HIGH_PERFORMER_THRESHOLD = 0.7  # Success rate to be considered high performer
    LOW_PERFORMER_THRESHOLD = 0.3   # Success rate to be considered low performer
    MIN_SAMPLES_FOR_CONFIDENCE = 10  # Minimum classifications before trusting the data
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize the keyword learner."""
        self.redis = redis_client or redis.Redis.from_url(settings.redis_url)
        self.tracker = KeywordTracker(self.redis)
        
        # Persistent storage for learned weights
        self.weights_file = Path(settings.artefacts_dir) / "learned_keyword_weights.json"
        self.performance_key = "keywords:learned:performance:{keyword}"
        self.last_update_key = "keywords:learned:last_update:{keyword}"
        
        # Load existing learned weights
        self._load_learned_weights()
    
    def _load_learned_weights(self):
        """Load previously learned keyword weights."""
        self.learned_weights = {}
        
        try:
            if self.weights_file.exists():
                with open(self.weights_file) as f:
                    data = json.load(f)
                    self.learned_weights = data.get('weights', {})
                    logger.info(f"Loaded {len(self.learned_weights)} learned keyword weights")
        except Exception as e:
            logger.error(f"Failed to load learned weights: {e}")
            self.learned_weights = {}
    
    def _save_learned_weights(self):
        """Persist learned weights to file."""
        try:
            data = {
                'weights': self.learned_weights,
                'last_updated': datetime.utcnow().isoformat(),
                'total_keywords': len(self.learned_weights)
            }
            with open(self.weights_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learned weights: {e}")
    
    def apply_learned_weights(self, keywords: List[Dict[str, float]], 
                             episode_context: str = None) -> List[Dict[str, float]]:
        """
        Apply learned weights to keywords for a new episode.
        
        Args:
            keywords: List of keyword dicts with initial weights
            episode_context: Optional context about the episode topic
            
        Returns:
            Keywords with adjusted weights based on historical performance
        """
        adjusted_keywords = []
        adjustments_made = 0
        
        for kw_dict in keywords:
            keyword = kw_dict['keyword']
            original_weight = kw_dict.get('weight', 1.0)
            
            # Check if we have historical data for this keyword
            historical_weight = self.get_learned_weight(keyword)
            
            if historical_weight is not None:
                # Apply learned weight with learning rate
                adjusted_weight = (original_weight * (1 - self.LEARNING_RATE) + 
                                 historical_weight * self.LEARNING_RATE)
                
                # Check confidence in the historical data
                stats = self.tracker.get_keyword_stats(keyword)
                confidence = min(1.0, stats.get('classified_count', 0) / self.MIN_SAMPLES_FOR_CONFIDENCE)
                
                # Blend with confidence
                final_weight = (original_weight * (1 - confidence) + 
                              adjusted_weight * confidence)
                
                logger.info(
                    f"Adjusted '{keyword}' weight: {original_weight:.2f} → {final_weight:.2f} "
                    f"(historical: {historical_weight:.2f}, confidence: {confidence:.2f})"
                )
                
                adjustments_made += 1
            else:
                # New keyword - use exploration weight
                final_weight = self.EXPLORATION_WEIGHT
                
                # Check for similar keywords
                similar = self.find_similar_keywords(keyword)
                if similar:
                    # Use average performance of similar keywords
                    similar_weights = [self.get_learned_weight(s) for s in similar]
                    similar_weights = [w for w in similar_weights if w is not None]
                    if similar_weights:
                        final_weight = sum(similar_weights) / len(similar_weights)
                        logger.info(
                            f"New keyword '{keyword}' using similar keyword weights: {final_weight:.2f}"
                        )
            
            adjusted_keywords.append({
                'keyword': keyword,
                'weight': max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, final_weight)),
                'original_weight': original_weight,
                'adjustment_type': 'learned' if historical_weight else 'exploratory'
            })
        
        logger.info(
            f"Applied learned weights: {adjustments_made}/{len(keywords)} keywords adjusted"
        )
        
        return adjusted_keywords
    
    def get_learned_weight(self, keyword: str) -> Optional[float]:
        """
        Get the learned weight for a keyword based on historical performance.
        
        Args:
            keyword: The keyword to look up
            
        Returns:
            Learned weight (0-1) or None if no history
        """
        # Check cache first
        if keyword in self.learned_weights:
            # Apply time decay
            last_update = self.redis.get(self.last_update_key.format(keyword=keyword))
            if last_update:
                last_update_time = datetime.fromisoformat(last_update.decode('utf-8'))
                months_old = (datetime.utcnow() - last_update_time).days / 30
                decay = self.DECAY_FACTOR ** months_old
                return self.learned_weights[keyword] * decay
            return self.learned_weights[keyword]
        
        # Check tracker for performance data
        stats = self.tracker.get_keyword_stats(keyword)
        
        # Need minimum samples to have confidence
        if stats.get('classified_count', 0) < self.MIN_SAMPLES_FOR_CONFIDENCE:
            return None
        
        # Calculate weight based on success rate
        success_rate = stats.get('success_rate', 0)
        
        # Apply sigmoid transformation for smoother weights
        # This maps success_rate to a weight between MIN_WEIGHT and MAX_WEIGHT
        weight = self.MIN_WEIGHT + (self.MAX_WEIGHT - self.MIN_WEIGHT) / (1 + math.exp(-10 * (success_rate - 0.5)))
        
        return weight
    
    def update_learned_weights(self, episode_id: str = None):
        """
        Update learned weights based on latest classification results.
        
        Args:
            episode_id: Optional episode ID for context
        """
        logger.info(f"Updating learned weights for episode: {episode_id}")
        
        # Get all keyword statistics
        all_stats = self.tracker.get_all_keyword_stats()
        
        updates = 0
        for stats in all_stats:
            keyword = stats['keyword']
            
            # Skip if insufficient data
            if stats.get('classified_count', 0) < 3:  # Need at least 3 samples from this episode
                continue
            
            # Calculate new weight based on performance
            success_rate = stats.get('success_rate', 0)
            new_weight = self.MIN_WEIGHT + (self.MAX_WEIGHT - self.MIN_WEIGHT) / (1 + math.exp(-10 * (success_rate - 0.5)))
            
            # Apply learning rate if we have existing weight
            if keyword in self.learned_weights:
                old_weight = self.learned_weights[keyword]
                # Exponential moving average
                self.learned_weights[keyword] = (old_weight * (1 - self.LEARNING_RATE) + 
                                                new_weight * self.LEARNING_RATE)
                
                logger.debug(
                    f"Updated '{keyword}': {old_weight:.3f} → {self.learned_weights[keyword]:.3f} "
                    f"(success_rate: {success_rate:.2f})"
                )
            else:
                # First time seeing this keyword
                self.learned_weights[keyword] = new_weight
                logger.debug(
                    f"New keyword '{keyword}' weight: {new_weight:.3f} "
                    f"(success_rate: {success_rate:.2f})"
                )
            
            # Update timestamp
            self.redis.set(
                self.last_update_key.format(keyword=keyword),
                datetime.utcnow().isoformat()
            )
            
            updates += 1
        
        # Save to persistent storage
        if updates > 0:
            self._save_learned_weights()
            logger.info(f"Updated {updates} keyword weights")
        
        # Generate performance report
        self._generate_learning_report(episode_id)
    
    def find_similar_keywords(self, keyword: str, threshold: float = 0.7) -> List[str]:
        """
        Find keywords similar to the given one.
        
        Args:
            keyword: The keyword to find similar ones for
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of similar keywords
        """
        similar = []
        keyword_lower = keyword.lower()
        keyword_words = set(keyword_lower.split())
        
        for known_keyword in self.learned_weights.keys():
            known_lower = known_keyword.lower()
            
            # Exact substring match
            if keyword_lower in known_lower or known_lower in keyword_lower:
                similar.append(known_keyword)
                continue
            
            # Word overlap
            known_words = set(known_lower.split())
            overlap = len(keyword_words & known_words)
            if overlap > 0:
                similarity = overlap / max(len(keyword_words), len(known_words))
                if similarity >= threshold:
                    similar.append(known_keyword)
        
        return similar
    
    def get_keyword_recommendations(self) -> Dict:
        """
        Get recommendations for keyword management.
        
        Returns:
            Dictionary with categorized keyword recommendations
        """
        all_stats = self.tracker.get_all_keyword_stats()
        
        high_performers = []
        low_performers = []
        rising_stars = []
        needs_exploration = []
        
        for stats in all_stats:
            keyword = stats['keyword']
            success_rate = stats.get('success_rate', 0)
            classified_count = stats.get('classified_count', 0)
            trend = stats.get('trend', 0)
            
            if classified_count >= self.MIN_SAMPLES_FOR_CONFIDENCE:
                tweets_per_day = stats.get('tweets_per_day', 0)
                
                # High performer: good success rate AND decent volume
                if success_rate >= self.HIGH_PERFORMER_THRESHOLD and tweets_per_day >= 1:
                    high_performers.append({
                        'keyword': keyword,
                        'success_rate': success_rate,
                        'weight': self.learned_weights.get(keyword, 0),
                        'tweets_per_day': tweets_per_day,
                        'total_yield': stats.get('relevant_count', 0)
                    })
                elif success_rate <= self.LOW_PERFORMER_THRESHOLD:
                    low_performers.append({
                        'keyword': keyword,
                        'success_rate': success_rate,
                        'weight': self.learned_weights.get(keyword, 0),
                        'api_waste': stats.get('skip_count', 0)
                    })
                
                if trend > 0.1:
                    rising_stars.append({
                        'keyword': keyword,
                        'trend': trend,
                        'current_rate': success_rate
                    })
            else:
                # Not enough data
                needs_exploration.append({
                    'keyword': keyword,
                    'samples': classified_count
                })
        
        # Sort high performers by total yield (relevant tweets found)
        high_performers.sort(key=lambda x: x.get('total_yield', 0), reverse=True)
        
        return {
            'high_performers': high_performers[:10],
            'low_performers': sorted(low_performers, key=lambda x: x['api_waste'], reverse=True)[:10],
            'rising_stars': sorted(rising_stars, key=lambda x: x['trend'], reverse=True)[:5],
            'needs_exploration': needs_exploration[:10],
            'total_learned': len(self.learned_weights),
            'recommendations': self._generate_recommendations(high_performers, low_performers)
        }
    
    def _generate_recommendations(self, high_performers: List, low_performers: List) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if high_performers:
            top_keywords = ', '.join(k['keyword'] for k in high_performers[:5])
            recommendations.append(
                f"Prioritize these high-performing keywords: {top_keywords}"
            )
        
        if low_performers:
            # Calculate total waste
            total_waste = sum(k['api_waste'] for k in low_performers)
            if total_waste > 50:
                worst = ', '.join(k['keyword'] for k in low_performers[:3])
                recommendations.append(
                    f"Remove these keywords wasting {total_waste} API calls: {worst}"
                )
        
        # Check overall efficiency
        avg_weight = sum(self.learned_weights.values()) / len(self.learned_weights) if self.learned_weights else 0
        if avg_weight < 0.4:
            recommendations.append(
                "Overall keyword quality is low. Consider refining keyword generation strategy."
            )
        
        return recommendations
    
    def _generate_learning_report(self, episode_id: str = None):
        """Generate a report on learning progress."""
        report = {
            'episode_id': episode_id,
            'timestamp': datetime.utcnow().isoformat(),
            'keywords_tracked': len(self.learned_weights),
            'average_learned_weight': sum(self.learned_weights.values()) / len(self.learned_weights) if self.learned_weights else 0,
            'high_performers': len([w for w in self.learned_weights.values() if w >= self.HIGH_PERFORMER_THRESHOLD]),
            'low_performers': len([w for w in self.learned_weights.values() if w <= self.LOW_PERFORMER_THRESHOLD])
        }
        
        # Get API waste report
        waste_report = self.tracker.get_api_waste_report()
        report['api_efficiency'] = waste_report['summary']['efficiency_percentage']
        report['api_calls_wasted'] = waste_report['summary']['api_calls_wasted']
        
        logger.info(
            f"Learning Report: {report['keywords_tracked']} keywords, "
            f"{report['api_efficiency']:.1f}% efficiency, "
            f"{report['api_calls_wasted']} wasted calls"
        )
        
        return report
    
    def apply_negative_feedback(self, keywords: List[str], penalty_factor: float = 0.2):
        """
        Apply negative feedback to keywords when a draft is rejected.
        This reduces the weight of the associated keywords.
        
        Args:
            keywords: List of keywords to penalize
            penalty_factor: How much to reduce the weight (0-1, default 0.2 = 20% reduction)
        """
        logger.info(f"Applying negative feedback to {len(keywords)} keywords with penalty factor {penalty_factor}")
        
        for keyword in keywords:
            # Get current weight or use exploration weight if not found
            current_weight = self.learned_weights.get(keyword, self.EXPLORATION_WEIGHT)
            
            # Apply penalty (reduce weight by penalty_factor)
            new_weight = max(self.MIN_WEIGHT, current_weight * (1 - penalty_factor))
            
            # Store the new weight
            self.learned_weights[keyword] = new_weight
            
            # Update timestamp
            self.redis.set(
                self.last_update_key.format(keyword=keyword),
                datetime.utcnow().isoformat()
            )
            
            logger.debug(f"Reduced weight for '{keyword}': {current_weight:.3f} → {new_weight:.3f}")
        
        # Save to persistent storage
        if keywords:
            self._save_learned_weights()
            logger.info(f"Applied negative feedback to {len(keywords)} keywords")
    
    def reset_learning(self, keyword: str = None):
        """
        Reset learned weights for a specific keyword or all keywords.
        
        Args:
            keyword: Specific keyword to reset, or None for all
        """
        if keyword:
            if keyword in self.learned_weights:
                del self.learned_weights[keyword]
                self.redis.delete(self.last_update_key.format(keyword=keyword))
                logger.info(f"Reset learned weight for '{keyword}'")
        else:
            self.learned_weights = {}
            # Clear all Redis keys
            for key in self.redis.scan_iter(match="keywords:learned:*"):
                self.redis.delete(key)
            logger.info("Reset all learned keyword weights")
        
        self._save_learned_weights()