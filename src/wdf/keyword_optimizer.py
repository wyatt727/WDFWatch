"""
Keyword Search Optimization Module

Simple keyword batching for efficient Twitter API usage.
Focuses on combining keywords into mega-queries rather than volume testing.

Integrates with: twitter_client.py, scrape.py, twitter_api_v2.py
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class KeywordOptimizer:
    """
    Simple keyword batching for Twitter API efficiency.
    
    Features:
    - Weight-based prioritization
    - Query batching with OR operators
    - Duplicate detection
    - API call estimation
    - No volume testing (let classification handle relevance)
    """
    
    # Twitter API v2 query limits
    MAX_QUERY_LENGTH = 512  # characters
    MAX_OR_OPERATORS = 25   # max OR conditions per query
    
    def __init__(self, quota_remaining: int = 10000):
        """
        Initialize the optimizer.
        
        Args:
            quota_remaining: Current remaining API quota
        """
        self.quota_remaining = quota_remaining
        self.seen_tweet_ids: Set[str] = set()
    
    def prioritize_keywords(self, keywords: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Sort keywords by weight (highest first) for prioritized searching.
        
        Args:
            keywords: List of dicts with 'keyword' and 'weight' keys
            
        Returns:
            Sorted list of keywords by weight descending
        """
        return sorted(keywords, key=lambda k: k.get('weight', 0), reverse=True)
    
    def group_similar_keywords(self, keywords: List[Dict[str, float]]) -> List[List[Dict[str, float]]]:
        """
        Group semantically similar keywords to search together.
        This reduces redundant searches for related terms.
        
        Args:
            keywords: List of keyword dicts
            
        Returns:
            List of keyword groups
        """
        groups = []
        used = set()
        
        for kw in keywords:
            if kw['keyword'] in used:
                continue
                
            # Start a new group with this keyword
            group = [kw]
            used.add(kw['keyword'])
            
            # Find similar keywords (simple heuristic: shared words)
            kw_words = set(kw['keyword'].lower().split())
            for other in keywords:
                if other['keyword'] in used:
                    continue
                    
                other_words = set(other['keyword'].lower().split())
                
                # If keywords share words, group them
                if kw_words & other_words:
                    group.append(other)
                    used.add(other['keyword'])
                    
            groups.append(group)
            
        logger.info(f"Grouped {len(keywords)} keywords into {len(groups)} search groups")
        return groups
    
    def build_or_queries(self, keyword_groups: List[List[Dict[str, float]]]) -> List[str]:
        """
        Build optimized OR queries for Twitter API v2.
        
        Args:
            keyword_groups: Groups of related keywords
            
        Returns:
            List of optimized query strings
        """
        queries = []
        
        for group in keyword_groups:
            # Sort group by weight
            group = sorted(group, key=lambda k: k.get('weight', 0), reverse=True)
            
            current_query_parts = []
            current_length = 0
            
            for kw in group:
                keyword = kw['keyword']
                
                # Quote multi-word keywords
                if ' ' in keyword:
                    keyword = f'"{keyword}"'
                
                # Check if adding this keyword would exceed limits
                keyword_length = len(keyword) + 4  # Include " OR " separator
                
                if current_query_parts and (
                    current_length + keyword_length > self.MAX_QUERY_LENGTH or
                    len(current_query_parts) >= self.MAX_OR_OPERATORS
                ):
                    # Save current query and start new one
                    queries.append(' OR '.join(current_query_parts))
                    current_query_parts = [keyword]
                    current_length = len(keyword)
                else:
                    current_query_parts.append(keyword)
                    current_length += keyword_length
            
            # Add remaining query
            if current_query_parts:
                queries.append(' OR '.join(current_query_parts))
        
        logger.info(f"Built {len(queries)} optimized queries from {len(keyword_groups)} groups")
        return queries
    
    def estimate_api_calls(self, queries: List[str], tweets_per_query: int = 100) -> Dict[str, int]:
        """
        Estimate API call cost before executing searches.
        
        Args:
            queries: List of search queries
            tweets_per_query: Max tweets to fetch per query
            
        Returns:
            Dictionary with estimation details
        """
        # Twitter API v2 rate limits
        # Standard v2: 180 searches per 15 min = ~500/day
        # Each search counts as 1 read
        
        total_calls = len(queries)
        
        # Estimate based on pagination (100 tweets per page)
        pages_per_query = (tweets_per_query + 99) // 100
        total_reads = total_calls * pages_per_query
        
        estimate = {
            'total_queries': total_calls,
            'reads_per_query': pages_per_query,
            'total_reads': total_reads,
            'percentage_of_quota': (total_reads / self.quota_remaining) * 100 if self.quota_remaining > 0 else 100,
            'will_exceed_quota': total_reads > self.quota_remaining
        }
        
        logger.warning(f"API Call Estimate: {total_reads} reads ({estimate['percentage_of_quota']:.1f}% of remaining quota)")
        
        return estimate
    
    
    def progressive_search_strategy(self, keywords: List[Dict[str, float]], 
                                   target_tweets: int = 100,
                                   min_relevance_score: float = 0.7) -> Dict[str, any]:
        """
        Progressive search that stops when enough relevant tweets are found.
        
        Args:
            keywords: List of keyword dicts with weights
            target_tweets: Target number of relevant tweets
            min_relevance_score: Minimum score to consider tweet relevant
            
        Returns:
            Search strategy with phases
        """
        # Prioritize by weight
        prioritized = self.prioritize_keywords(keywords)
        
        # Split into tiers based on weight
        tier1 = [k for k in prioritized if k.get('weight', 0) >= 0.8]  # High priority
        tier2 = [k for k in prioritized if 0.5 <= k.get('weight', 0) < 0.8]  # Medium
        tier3 = [k for k in prioritized if k.get('weight', 0) < 0.5]  # Low
        
        strategy = {
            'phases': [],
            'total_keywords': len(keywords),
            'estimated_api_calls': 0
        }
        
        # Phase 1: Search high-weight keywords first
        if tier1:
            groups = self.group_similar_keywords(tier1)
            queries = self.build_or_queries(groups)
            strategy['phases'].append({
                'name': 'High Priority',
                'keywords': len(tier1),
                'queries': queries,
                'weight_range': '0.8-1.0'
            })
            strategy['estimated_api_calls'] += len(queries)
        
        # Phase 2: Medium weight (only if needed)
        if tier2:
            groups = self.group_similar_keywords(tier2)
            queries = self.build_or_queries(groups)
            strategy['phases'].append({
                'name': 'Medium Priority',
                'keywords': len(tier2),
                'queries': queries,
                'weight_range': '0.5-0.8',
                'conditional': True  # Only run if phase 1 doesn't yield enough
            })
            strategy['estimated_api_calls'] += len(queries)
        
        # Phase 3: Low weight (rarely needed)
        if tier3:
            groups = self.group_similar_keywords(tier3[:10])  # Limit low-weight keywords
            queries = self.build_or_queries(groups)
            strategy['phases'].append({
                'name': 'Low Priority (Limited)',
                'keywords': min(10, len(tier3)),
                'queries': queries,
                'weight_range': '<0.5',
                'conditional': True
            })
            strategy['estimated_api_calls'] += len(queries)
        
        return strategy
    
    def deduplicate_tweets(self, tweets: List[Dict], new_tweet_ids: Set[str]) -> List[Dict]:
        """
        Remove duplicate tweets across multiple searches.
        
        Args:
            tweets: List of tweet dictionaries
            new_tweet_ids: Set of tweet IDs from current search
            
        Returns:
            Deduplicated list of tweets
        """
        unique_tweets = []
        
        for tweet in tweets:
            tweet_id = tweet.get('id')
            if tweet_id and tweet_id not in self.seen_tweet_ids:
                unique_tweets.append(tweet)
                self.seen_tweet_ids.add(tweet_id)
        
        duplicate_count = len(tweets) - len(unique_tweets)
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count} duplicate tweets")
            
        return unique_tweets
    
    def calculate_relevance_score(self, tweet_text: str, matched_keywords: List[Dict[str, float]]) -> float:
        """
        Calculate relevance score based on keyword matches and weights.
        
        Args:
            tweet_text: The tweet text
            matched_keywords: Keywords that matched this tweet
            
        Returns:
            Relevance score between 0 and 1
        """
        if not matched_keywords:
            return 0.0
            
        text_lower = tweet_text.lower()
        total_weight = 0
        match_count = 0
        
        for kw_dict in matched_keywords:
            keyword = kw_dict['keyword'].lower()
            weight = kw_dict.get('weight', 1.0)
            
            # Check for exact match
            if keyword in text_lower:
                total_weight += weight
                match_count += 1
            # Check for partial word match
            elif any(word in text_lower for word in keyword.split()):
                total_weight += weight * 0.5  # Partial match gets half weight
                match_count += 0.5
        
        # Score based on weighted matches and match density
        if match_count > 0:
            weight_score = total_weight / len(matched_keywords)
            density_score = min(1.0, match_count / 3)  # Bonus for multiple matches
            return (weight_score * 0.7) + (density_score * 0.3)
        
        return 0.0
    
    def optimize_search_plan(self, keywords: List[Dict[str, float]], 
                            quota_limit: Optional[int] = None) -> Dict[str, any]:
        """
        Create an optimized search plan that respects quota limits.
        
        Args:
            keywords: List of keyword dictionaries
            quota_limit: Maximum API calls to use (defaults to 10% of remaining)
            
        Returns:
            Optimized search plan
        """
        if quota_limit is None:
            # Use at most 10% of remaining quota per search
            quota_limit = max(1, self.quota_remaining // 10)
        
        # Get progressive strategy
        strategy = self.progressive_search_strategy(keywords)
        
        # Estimate costs
        estimate = self.estimate_api_calls(
            [q for phase in strategy['phases'] for q in phase.get('queries', [])]
        )
        
        # Adjust if over quota
        if estimate['total_reads'] > quota_limit:
            logger.warning(f"Search would use {estimate['total_reads']} reads, limiting to {quota_limit}")
            
            # Trim phases to fit quota
            adjusted_phases = []
            reads_used = 0
            
            for phase in strategy['phases']:
                phase_reads = len(phase.get('queries', []))
                if reads_used + phase_reads <= quota_limit:
                    adjusted_phases.append(phase)
                    reads_used += phase_reads
                else:
                    # Partial phase - take what we can
                    remaining = quota_limit - reads_used
                    if remaining > 0:
                        phase['queries'] = phase['queries'][:remaining]
                        phase['adjusted'] = True
                        adjusted_phases.append(phase)
                    break
                    
            strategy['phases'] = adjusted_phases
            strategy['quota_limited'] = True
            
        plan = {
            'strategy': strategy,
            'estimate': estimate,
            'quota_limit': quota_limit,
            'recommendations': self._get_recommendations(keywords, estimate)
        }
        
        return plan
    
    def _get_recommendations(self, keywords: List[Dict[str, float]], estimate: Dict) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Check if too many low-weight keywords
        low_weight = [k for k in keywords if k.get('weight', 0) < 0.3]
        if len(low_weight) > len(keywords) * 0.5:
            recommendations.append(
                f"Consider removing {len(low_weight)} low-weight keywords (weight < 0.3) to save API calls"
            )
        
        # Check for potential duplicates
        keyword_texts = [k['keyword'].lower() for k in keywords]
        if len(keyword_texts) != len(set(keyword_texts)):
            recommendations.append("Remove duplicate keywords to avoid redundant searches")
        
        # Suggest grouping if many similar keywords
        single_words = [k for k in keywords if ' ' not in k['keyword']]
        if len(single_words) > 20:
            recommendations.append(
                "Consider combining related single-word keywords into phrase searches"
            )
        
        # Warn about quota usage
        if estimate['percentage_of_quota'] > 5:
            recommendations.append(
                f"This search will use {estimate['percentage_of_quota']:.1f}% of remaining quota. "
                "Consider more selective keywords or lower tweet count."
            )
        
        return recommendations