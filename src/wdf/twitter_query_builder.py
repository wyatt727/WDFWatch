"""
Twitter Query Builder Module

Builds optimized Twitter API v2 search queries with proper operators
and filters based on configured settings.

Integrates with: twitter_api_v2.py, scraping settings
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TwitterQueryBuilder:
    """
    Builds Twitter API v2 search queries with proper operators.
    
    Twitter API v2 query operators:
    - min_faves:X - Minimum likes (NOT min_likes!)
    - min_retweets:X - Minimum retweets
    - min_replies:X - Minimum replies
    - -is:reply - Exclude replies
    - -is:retweet - Exclude retweets
    - lang:XX - Language filter
    - from:username - From specific user
    - to:username - To specific user
    """
    
    def build_search_query(self, keywords: List[str], settings: Dict) -> str:
        """
        Build a Twitter API v2 search query with all filters.
        
        Args:
            keywords: List of keywords to search for
            settings: Scraping settings dict with filters
            
        Returns:
            Optimized query string with operators (max 512 chars)
        """
        # Start with keywords (OR logic)
        if not keywords:
            raise ValueError("At least one keyword is required")
        
        # Prepare filters that apply to all queries
        filter_parts = []
        
        # Add engagement filters
        min_likes = settings.get('minLikes', 0)
        if min_likes > 0:
            filter_parts.append(f"min_faves:{min_likes}")
            
        min_retweets = settings.get('minRetweets', 0)
        if min_retweets > 0:
            filter_parts.append(f"min_retweets:{min_retweets}")
            
        min_replies = settings.get('minReplies', 0)
        if min_replies > 0:
            filter_parts.append(f"min_replies:{min_replies}")
        
        # Add exclusion filters
        if settings.get('excludeReplies', False):
            filter_parts.append("-is:reply")
            
        if settings.get('excludeRetweets', False):
            filter_parts.append("-is:retweet")
        
        # Add language filter
        language = settings.get('language')
        if language and language != 'all':
            filter_parts.append(f"lang:{language}")
        
        # Calculate space needed for filters
        filters_str = " ".join(filter_parts) if filter_parts else ""
        filters_length = len(filters_str) + (1 if filters_str else 0)  # +1 for space
        
        # Maximum length for keywords part (512 - filters - safety margin)
        max_keyword_length = 512 - filters_length - 10  # 10 char safety margin
        
        # Process keywords - quote multi-word keywords
        processed_keywords = []
        for keyword in keywords[:25]:  # Max 25 OR operators
            # Quote multi-word keywords
            if ' ' in keyword:
                processed_keywords.append(f'"{keyword}"')
            else:
                processed_keywords.append(keyword)
        
        # Build keyword query with length enforcement
        if len(processed_keywords) > 1:
            # Try to fit as many keywords as possible
            keyword_query = ""
            included_keywords = []
            
            for kw in processed_keywords:
                test_query = " OR ".join(included_keywords + [kw])
                if len(test_query) <= max_keyword_length:
                    included_keywords.append(kw)
                else:
                    logger.warning(f"Excluding keyword '{kw}' to stay within 512 char limit")
                    break
            
            if included_keywords:
                keyword_query = "(" + " OR ".join(included_keywords) + ")"
            else:
                # If even one keyword is too long, truncate it
                keyword_query = processed_keywords[0][:max_keyword_length]
        else:
            keyword_query = processed_keywords[0]
            if len(keyword_query) > max_keyword_length:
                keyword_query = keyword_query[:max_keyword_length]
        
        # Combine keywords and filters
        query_parts = [keyword_query]
        if filters_str:
            query_parts.append(filters_str)
        
        query = " ".join(query_parts)
        
        # Final length check and truncation
        if len(query) > 512:
            logger.warning(f"Query still exceeds 512 chars ({len(query)}), truncating")
            query = query[:512]
        
        logger.info(f"Built query ({len(query)} chars): {query[:100]}...")
        return query
    
    def build_search_params(self, settings: Dict) -> Dict:
        """
        Build API parameters for search endpoint.
        
        Args:
            settings: Scraping settings dict
            
        Returns:
            Dict of API parameters
        """
        params = {}
        
        # Add time range based on days_back
        days_back = settings.get('daysBack', 7)
        if days_back > 0:
            # Calculate start time
            start_time = datetime.utcnow() - timedelta(days=days_back)
            params['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            logger.info(f"Set search window: last {days_back} days (from {params['start_time']})")
        
        # Request public_metrics to verify engagement thresholds
        params['tweet.fields'] = 'created_at,author_id,public_metrics,conversation_id'
        params['user.fields'] = 'username,name,verified'
        params['expansions'] = 'author_id'
        
        return params
    
    def build_or_queries_with_filters(self, keyword_groups: List[List[str]], settings: Dict) -> List[str]:
        """
        Build multiple OR queries with filters for batch searching.
        
        Args:
            keyword_groups: Groups of keywords for OR queries
            settings: Scraping settings dict
            
        Returns:
            List of query strings with filters
        """
        queries = []
        
        for group in keyword_groups:
            # Build OR query for this group
            if len(group) > 1:
                keyword_part = "(" + " OR ".join(group) + ")"
            else:
                keyword_part = group[0]
            
            # Add filters (these apply to all queries)
            query_parts = [keyword_part]
            
            # Add engagement filters
            min_likes = settings.get('minLikes', 0)
            if min_likes > 0:
                query_parts.append(f"min_faves:{min_likes}")
                
            min_retweets = settings.get('minRetweets', 0)
            if min_retweets > 0:
                query_parts.append(f"min_retweets:{min_retweets}")
                
            min_replies = settings.get('minReplies', 0)
            if min_replies > 0:
                query_parts.append(f"min_replies:{min_replies}")
            
            # Add exclusion filters
            if settings.get('excludeReplies', False):
                query_parts.append("-is:reply")
                
            if settings.get('excludeRetweets', False):
                query_parts.append("-is:retweet")
            
            # Add language filter
            language = settings.get('language')
            if language and language != 'all':
                query_parts.append(f"lang:{language}")
            
            query = " ".join(query_parts)
            
            # Check length
            if len(query) <= 512:
                queries.append(query)
            else:
                logger.warning(f"Query too long ({len(query)} chars), splitting group")
                # Fall back to individual keywords with filters
                for keyword in group:
                    simple_query = f"{keyword} " + " ".join(query_parts[1:])
                    if len(simple_query) <= 512:
                        queries.append(simple_query)
        
        return queries
    
    def validate_settings(self, settings: Dict) -> List[str]:
        """
        Validate scraping settings and return warnings.
        
        Args:
            settings: Scraping settings dict
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check engagement thresholds
        min_likes = settings.get('minLikes', 0)
        min_retweets = settings.get('minRetweets', 0)
        min_replies = settings.get('minReplies', 0)
        
        if min_likes < 0:
            warnings.append(f"Invalid minLikes ({min_likes}): must be >= 0")
        elif min_likes > 100:
            warnings.append(f"High minLikes ({min_likes}) may severely limit results")
            
        if min_retweets < 0:
            warnings.append(f"Invalid minRetweets ({min_retweets}): must be >= 0")
        elif min_retweets > 50:
            warnings.append(f"High minRetweets ({min_retweets}) may severely limit results")
            
        if min_replies < 0:
            warnings.append(f"Invalid minReplies ({min_replies}): must be >= 0")
        elif min_replies > 20:
            warnings.append(f"High minReplies ({min_replies}) may severely limit results")
        
        # Check for conflicting settings
        if settings.get('excludeReplies') and min_replies > 0:
            warnings.append("excludeReplies conflicts with minReplies setting")
        
        # Check days back
        days_back = settings.get('daysBack', 7)
        if days_back < 0:
            warnings.append(f"Invalid days_back ({days_back}): must be >= 0")
        elif days_back == 0:
            warnings.append("days_back = 0 will only search today's tweets")
        elif days_back > 7:
            warnings.append(f"days_back > 7 requires Academic access for full archive search")
        elif days_back > 30:
            warnings.append(f"days_back = {days_back} is very large, consider reducing")
        
        # Check max tweets
        max_tweets = settings.get('maxTweets', 100)
        if max_tweets > 500:
            warnings.append(f"High maxTweets ({max_tweets}) will consume significant API credits")
        elif max_tweets < 1:
            warnings.append(f"Invalid maxTweets ({max_tweets}): must be >= 1")
        
        return warnings