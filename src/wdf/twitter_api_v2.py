"""
Twitter API v2 Implementation

Real Twitter API v2 implementation with optimized search and quota management.

Integrates with: keyword_optimizer.py, quota_manager.py
"""

import logging
import time
from typing import List, Dict, Optional, Set
import requests
from requests_oauthlib import OAuth1Session
import os

from .quota_manager import QuotaManager
from .keyword_tracker import KeywordTracker
from .twitter_query_builder import TwitterQueryBuilder
from .search_boundaries import SearchBoundaryManager

logger = logging.getLogger(__name__)


class TwitterAPIv2:
    """
    Twitter API v2 client with optimized keyword search.
    
    Features:
    - OAuth 1.0a authentication
    - Optimized batch searching
    - Automatic rate limiting
    - Quota management
    - Duplicate detection
    """
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, api_key: str = None, api_secret: str = None, 
                 access_token: str = None, access_token_secret: str = None,
                 scraping_settings: Dict = None):
        """
        Initialize Twitter API v2 client.
        
        Args:
            api_key: Twitter API key (consumer key)
            api_secret: Twitter API secret (consumer secret)
            access_token: Twitter access token
            access_token_secret: Twitter access token secret
        """
        # CRITICAL SAFETY: Check for and reject WDF_Show tokens
        if os.getenv("ACCESS_TOKEN") or os.getenv("TWITTER_TOKEN"):
            logger.warning("⚠️  WDF_Show tokens detected in environment - ignoring them")
        
        # Get credentials - PRIORITIZE WDFWATCH tokens
        self.api_key = api_key or os.getenv("API_KEY") or os.getenv("CLIENT_ID")
        self.api_secret = api_secret or os.getenv("API_KEY_SECRET") or os.getenv("CLIENT_SECRET")
        
        # CRITICAL: Use WDFWATCH_ACCESS_TOKEN for OAuth 2.0 with auto-refresh
        try:
            from .token_manager import get_wdfwatch_token
            wdfwatch_token = get_wdfwatch_token()  # This handles refresh automatically
            self.access_token = access_token or wdfwatch_token
            self.access_token_secret = access_token_secret or ""  # Not needed for OAuth 2.0
            logger.info("✅ Using WDFWATCH_ACCESS_TOKEN (OAuth 2.0 with auto-refresh)")
        except Exception as e:
            # Fallback to environment variable without auto-refresh
            wdfwatch_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
            if wdfwatch_token:
                self.access_token = access_token or wdfwatch_token
                self.access_token_secret = access_token_secret or ""
                logger.info("✅ Using WDFWATCH_ACCESS_TOKEN (OAuth 2.0)")
            else:
                logger.error("⚠️  WDFWATCH_ACCESS_TOKEN not found!")
                logger.error("⚠️  TwitterAPIv2 should use WDFwatch tokens for safety")
                # Only use these if explicitly passed in (for backward compatibility)
                self.access_token = access_token or ""
                self.access_token_secret = access_token_secret or ""
                wdfwatch_token = None
        
        # Validate credentials
        if not all([self.api_key, self.api_secret, self.access_token]):
            raise ValueError("Twitter API credentials not configured")
        
        # Create OAuth session
        if wdfwatch_token:
            # OAuth 2.0 Bearer Token session for WDFwatch
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            })
            logger.info("Using OAuth 2.0 Bearer Token authentication")
        else:
            # OAuth 1.0a session (legacy, should avoid)
            self.session = OAuth1Session(
                self.api_key,
                client_secret=self.api_secret,
                resource_owner_key=self.access_token,
                resource_owner_secret=self.access_token_secret
            )
            logger.warning("Using OAuth 1.0a (legacy) - consider using WDFWATCH tokens")
        
        # Initialize quota manager, keyword tracker, and query builder
        self.quota_manager = QuotaManager()
        self.keyword_tracker = KeywordTracker()
        self.query_builder = TwitterQueryBuilder()
        self.boundary_manager = SearchBoundaryManager()
        
        # Store scraping settings
        self.scraping_settings = scraping_settings or {}
        
        # Track tweets and keyword effectiveness
        self.session_tweets: Set[str] = set()
        self.keyword_effectiveness: Dict[str, Dict] = {}
        
    def search_tweets_optimized(self, keywords: List[Dict[str, float]], 
                               max_tweets: int = 300,
                               min_relevance: float = 0.5,
                               days_back: int = None) -> List[Dict]:
        """
        Search tweets with individual keyword searches for effectiveness tracking.
        
        CONSERVATIVE APPROACH:
        - Sort keywords by weight (highest priority first)
        - Search each keyword individually (NO batching)
        - Default to settings or 10 results per keyword
        - Track which keywords produce results
        - Respect monthly quota (10,000 reads/month)
        - STOP when max_tweets total is reached (across all keywords)
        
        Args:
            keywords: List of keyword dicts with 'keyword' and 'weight'
            max_tweets: TOTAL maximum tweets to return across ALL keywords (default 300)
            min_relevance: DEPRECATED - classification handles this
            days_back: Number of days to search back
            
        Returns:
            List of tweet dictionaries with keyword tracking
            
        Example:
            With max_tweets=100, max_results_per_keyword=10, and 30 keywords:
            - Will search keywords in order
            - Stop after ~10 keywords when 100 total tweets collected
            - Later keywords won't be searched if limit already reached
        """
        logger.info(f"Starting individual keyword search for {len(keywords)} keywords")
        
        # Update settings
        settings = self.scraping_settings.copy()
        if days_back is not None:
            settings['daysBack'] = days_back
        
        # Get max results per keyword from settings (default: 10, NOT 100!)
        # This can be configured in settings but defaults to conservative value
        max_results_per_keyword = settings.get('maxResultsPerKeyword', 10)
        
        # Calculate total API reads required
        total_reads_needed = len(keywords) * max_results_per_keyword
        
        # Check quota before starting (unless bypassed for manual trigger)
        bypass_quota = os.getenv("WDF_BYPASS_QUOTA_CHECK", "false").lower() == "true"
        if not bypass_quota:
            quota_ok, reason = self.quota_manager.check_quota_available(
                required_calls=len(keywords)  # Number of search requests
            )
            if not quota_ok:
                logger.error(f"Cannot proceed with search: {reason}")
                return []
        else:
            logger.warning("Bypassing quota check for manual trigger")
        
        # Log quota status
        remaining = self.quota_manager.get_remaining_quota()
        logger.info(
            f"Quota status: {remaining}/{self.quota_manager.MONTHLY_READ_LIMIT} monthly reads remaining. "
            f"Will use {total_reads_needed} reads for this search."
        )
        
        # Warn if this search will use significant quota
        quota_percentage = (total_reads_needed / remaining) * 100 if remaining > 0 else 100
        if quota_percentage > 20:
            logger.warning(
                f"⚠️ This search will use {quota_percentage:.1f}% of remaining monthly quota! "
                f"Consider reducing max_results_per_keyword or number of keywords."
            )
        
        all_tweets = []
        tweets_by_id = {}  # For deduplication
        
        # Sort keywords by weight (highest first) to prioritize important searches
        sorted_keywords = sorted(keywords, key=lambda k: k.get('weight', 0), reverse=True)
        logger.info(f"Keywords sorted by weight - searching highest weight first")
        
        # Track effectiveness per keyword
        for kw_dict in sorted_keywords:
            keyword = kw_dict['keyword']
            weight = kw_dict.get('weight', 1.0)
            
            # Initialize effectiveness tracking
            self.keyword_effectiveness[keyword] = {
                'weight': weight,
                'tweets_found': 0,
                'unique_tweets': 0,
                'search_query': None
            }
        
        # Search each keyword individually (in weight order)
        for i, kw_dict in enumerate(sorted_keywords, 1):
            keyword = kw_dict['keyword']
            weight = kw_dict.get('weight', 1.0)
            
            # Build query for this specific keyword
            # Add quotes for multi-word keywords
            if ' ' in keyword:
                keyword_query = f'"{keyword}"'
            else:
                keyword_query = keyword

            # Add standard filters
            # CRITICAL: Also exclude tweets FROM WDF accounts (prevent self-replies)
            query = f"{keyword_query} -from:wdf_show -from:wdfshow -from:wdf_watch -from:wdfwatch -is:retweet lang:en"
            
            # Get optimized search parameters using boundaries
            boundary_params = self.boundary_manager.get_search_params(
                keyword=keyword,
                max_results=max_results_per_keyword,
                search_window_days=settings.get('daysBack', 7)
            )
            
            logger.info(
                f"Searching keyword {i}/{len(sorted_keywords)}: '{keyword}' "
                f"(weight: {weight:.2f}, priority: #{i}, max_results: {max_results_per_keyword}, "
                f"search_type: {boundary_params['search_type']})"
            )
            
            # Check rate limit before each search
            self.quota_manager.wait_if_rate_limited()
            
            # Execute search with configured max_results and boundary params
            try:
                tweets = []
                
                # Always do a simple search with the full quota - no splitting
                # This avoids the min_results=10 API requirement issues
                tweets = self._search_single_query(
                    query,
                    max_results=max_results_per_keyword,
                        settings=settings,
                        since_id=boundary_params.get('since_id'),
                        until_id=boundary_params.get('until_id')
                    )
                
                # Track effectiveness
                self.keyword_effectiveness[keyword]['search_query'] = query
                self.keyword_effectiveness[keyword]['tweets_found'] = len(tweets)
                
                # Update search boundaries for this keyword
                if tweets:
                    self.boundary_manager.update_boundaries(
                        keyword=keyword,
                        tweets=tweets,
                        search_window_days=settings.get('daysBack', 7)
                    )
                
                # Process tweets
                unique_count = 0
                for tweet in tweets:
                    tweet_id = tweet['id']
                    
                    # Track if this is a new unique tweet
                    if tweet_id not in tweets_by_id:
                        unique_count += 1
                        tweet['matched_keyword'] = keyword  # Track which keyword found this
                        tweet['keyword_weight'] = weight
                        tweets_by_id[tweet_id] = tweet
                    else:
                        # Tweet already found by another keyword
                        # Add this keyword to the matched list
                        if 'additional_keywords' not in tweets_by_id[tweet_id]:
                            tweets_by_id[tweet_id]['additional_keywords'] = []
                        tweets_by_id[tweet_id]['additional_keywords'].append(keyword)
                
                self.keyword_effectiveness[keyword]['unique_tweets'] = unique_count
                
                # Log keyword performance
                if len(tweets) == 0:
                    logger.warning(f"  No tweets found for '{keyword}'")
                else:
                    logger.info(
                        f"  Found {len(tweets)} tweets ({unique_count} unique) for '{keyword}'"
                    )
                
                # Record API usage
                self.quota_manager.record_api_call(
                    endpoint="search",
                    success=True
                )
                
                # Stop if we have enough tweets (TOTAL across all keywords)
                if len(tweets_by_id) >= max_tweets:
                    logger.info(
                        f"Reached max_tweets TOTAL limit ({max_tweets}), "
                        f"stopping search at keyword {i}/{len(sorted_keywords)} ('{keyword}'). "
                        f"Remaining {len(sorted_keywords) - i} lower-weight keywords will NOT be searched."
                    )
                    break
                    
            except Exception as e:
                logger.error(f"Error searching for '{keyword}': {e}")
                self.quota_manager.record_api_call(
                    endpoint="search",
                    success=False
                )
                continue
        
        # Convert to list and limit to max_tweets
        all_tweets = list(tweets_by_id.values())[:max_tweets]
        
        # Log effectiveness summary
        logger.info("\n📊 Keyword Effectiveness Summary:")
        logger.info(f"{'Keyword':<30} {'Found':<10} {'Unique':<10} {'Weight':<10}")
        logger.info("-" * 60)
        
        for keyword, stats in sorted(
            self.keyword_effectiveness.items(), 
            key=lambda x: x[1]['unique_tweets'], 
            reverse=True
        ):
            logger.info(
                f"{keyword:<30} {stats['tweets_found']:<10} "
                f"{stats['unique_tweets']:<10} {stats['weight']:<10.2f}"
            )
        
        # Log overall statistics
        total_searches = len([k for k in self.keyword_effectiveness if self.keyword_effectiveness[k]['tweets_found'] > 0])
        logger.info(
            f"\nSearch complete: {len(all_tweets)} unique tweets from {total_searches}/{len(keywords)} keywords. "
            f"API calls made: {len(sorted_keywords)}. "
            f"Classification will determine relevance."
        )
        
        # Log boundary savings estimate
        savings = self.boundary_manager.estimate_savings()
        if savings['keywords_tracked'] > 0:
            logger.info(
                f"\n💰 Boundary Savings: ~{savings['estimated_duplicates_avoided']} duplicate tweets avoided "
                f"({savings['percentage_of_monthly_quota_saved']:.2f}% of monthly quota saved). "
                f"Tracking {savings['keywords_tracked']} keywords."
            )
        
        # Update session tracking
        self.session_tweets.update(t['id'] for t in all_tweets)
        
        return all_tweets
    
    def _search_single_query(self, query: str, max_results: int = 10, settings: Dict = None,
                            since_id: str = None, until_id: str = None) -> List[Dict]:
        """
        Execute a single Twitter search query.
        
        Args:
            query: The search query string (with operators)
            max_results: Maximum results to fetch (default 10, max 100)
            settings: Scraping settings for time range
            since_id: Only return tweets newer than this ID (checkpoint)
            until_id: Only return tweets older than this ID (checkpoint)
            
        Returns:
            List of tweet dictionaries
        """
        endpoint = f"{self.BASE_URL}/tweets/search/recent"
        
        # Build base parameters with COMPREHENSIVE field collection
        # Following "One-pass enriched fetch" strategy from API conservation guide
        params = {
            'query': query,
            'max_results': min(100, max(10, max_results)),  # Twitter API v2 requires 10-100
            # Get ALL valuable tweet fields in one request - INCLUDING TEXT for full content
            'tweet.fields': (
                'text,created_at,author_id,public_metrics,conversation_id,'
                'lang,source,possibly_sensitive,reply_settings,'
                'context_annotations,entities,referenced_tweets,'
                'in_reply_to_user_id,geo'
            ),
            # Get ALL valuable user fields for influence/trust signals
            'user.fields': (
                'username,name,verified,public_metrics,created_at,'
                'description,location,profile_image_url,protected'
            ),
            # Expand to get referenced content and media
            'expansions': (
                'author_id,referenced_tweets.id,referenced_tweets.id.author_id,'
                'attachments.media_keys,entities.mentions.username,'
                'in_reply_to_user_id,geo.place_id'
            ),
            # Get media details if present
            'media.fields': 'type,url,duration_ms,height,width,preview_image_url,alt_text',
            # Get place details if geo-tagged
            'place.fields': 'country,country_code,full_name,geo,place_type'
        }
        
        # Add checkpoint parameters (these take precedence over time range)
        if since_id:
            params['since_id'] = since_id
            logger.debug(f"Using since_id={since_id} (only newer tweets)")
        if until_id:
            params['until_id'] = until_id
            logger.debug(f"Using until_id={until_id} (only older tweets)")
            
        # Add time range parameters from settings (only if no ID boundaries)
        if settings and not (since_id or until_id):
            time_params = self.query_builder.build_search_params(settings)
            params.update(time_params)
        
        all_tweets = []
        next_token = None
        pages_fetched = 0
        max_pages = (max_results + 99) // 100  # Calculate pages needed
        
        while pages_fetched < max_pages:
            if next_token:
                params['pagination_token'] = next_token
            
            try:
                # Make API request
                response = self.session.get(endpoint, params=params, timeout=30)
                
                # Record API call
                self.quota_manager.record_api_call(
                    endpoint="search",
                    success=response.status_code == 200
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract all includes for comprehensive data
                    tweets = data.get('data', [])
                    includes = data.get('includes', {})
                    users = {u['id']: u for u in includes.get('users', [])}
                    media = {m['media_key']: m for m in includes.get('media', [])}
                    places = {p['id']: p for p in includes.get('places', [])}
                    ref_tweets = {t['id']: t for t in includes.get('tweets', [])}
                    
                    # Process tweets with ALL available data
                    for tweet in tweets:
                        author = users.get(tweet['author_id'], {})

                        # Extract full text, handling retweets properly
                        full_text = self._extract_full_text(tweet, ref_tweets, users)

                        # Build comprehensive tweet object
                        formatted_tweet = {
                            # Core fields
                            'id': tweet['id'],
                            'text': full_text,
                            'created_at': tweet.get('created_at'),
                            
                            # User info with trust signals
                            'user': f"@{author.get('username', 'unknown')}",
                            'user_name': author.get('name'),
                            'user_verified': author.get('verified', False),
                            'user_created_at': author.get('created_at'),
                            'user_description': author.get('description'),
                            'user_location': author.get('location'),
                            'user_metrics': author.get('public_metrics', {}),
                            'user_protected': author.get('protected', False),
                            
                            # Tweet metadata for bot detection
                            'lang': tweet.get('lang'),
                            'source': tweet.get('source'),  # App used to post
                            'possibly_sensitive': tweet.get('possibly_sensitive', False),
                            'reply_settings': tweet.get('reply_settings'),
                            
                            # Engagement metrics
                            'metrics': tweet.get('public_metrics', {}),
                            'likes': tweet.get('public_metrics', {}).get('like_count', 0),
                            'retweets': tweet.get('public_metrics', {}).get('retweet_count', 0),
                            'replies': tweet.get('public_metrics', {}).get('reply_count', 0),
                            'quotes': tweet.get('public_metrics', {}).get('quote_count', 0),
                            
                            # Conversation context
                            'conversation_id': tweet.get('conversation_id'),
                            'in_reply_to_user_id': tweet.get('in_reply_to_user_id'),
                            
                            # AI-detected topics from Twitter
                            'context_annotations': tweet.get('context_annotations', []),
                            
                            # Entities (mentions, hashtags, urls)
                            'entities': tweet.get('entities', {}),
                            
                            # Referenced tweets (quotes, replies)
                            'referenced_tweets': tweet.get('referenced_tweets', []),
                            
                            # Media attachments
                            'attachments': tweet.get('attachments', {}),
                            
                            # Geo data if available
                            'geo': tweet.get('geo', {})
                        }
                        
                        # Add expanded referenced tweet data if available
                        if formatted_tweet['referenced_tweets']:
                            for ref in formatted_tweet['referenced_tweets']:
                                ref_id = ref.get('id')
                                if ref_id in ref_tweets:
                                    ref['tweet_data'] = {
                                        'text': ref_tweets[ref_id].get('text'),
                                        'author_id': ref_tweets[ref_id].get('author_id')
                                    }
                        
                        # Add media details if present
                        if 'media_keys' in formatted_tweet.get('attachments', {}):
                            formatted_tweet['media'] = [
                                media.get(key, {}) for key in formatted_tweet['attachments']['media_keys']
                            ]
                        
                        # Add place details if geo-tagged
                        if 'place_id' in formatted_tweet.get('geo', {}):
                            place_id = formatted_tweet['geo']['place_id']
                            if place_id in places:
                                formatted_tweet['place'] = places[place_id]
                        
                        all_tweets.append(formatted_tweet)
                    
                    # Check for next page
                    next_token = data.get('meta', {}).get('next_token')
                    if not next_token:
                        break
                        
                    pages_fetched += 1
                    
                elif response.status_code == 429:
                    # Rate limited
                    reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 60))
                    wait_time = max(1, reset_time - time.time())
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    
                elif response.status_code == 400:
                    # Bad request - check for specific error types
                    try:
                        error_data = response.json()
                        errors = error_data.get('errors', [])
                        for error in errors:
                            if 'since_id' in error.get('parameters', {}):
                                logger.warning(f"Invalid since_id parameter - skipping checkpoint and using time-based search")
                                # Retry without since_id parameter
                                if 'since_id' in params:
                                    del params['since_id']
                                    continue
                            elif 'max_results' in error.get('parameters', {}):
                                logger.warning(f"Invalid max_results parameter - using minimum valid value")
                                params['max_results'] = 10
                                continue
                        # If we get here, it's a different 400 error
                        logger.error(f"Bad request: {response.status_code} - {response.text}")
                        break
                    except Exception:
                        logger.error(f"Search failed: {response.status_code} - {response.text}")
                        break
                else:
                    logger.error(f"Search failed: {response.status_code} - {response.text}")
                    break
                    
            except Exception as e:
                logger.error(f"Search error: {e}")
                self.quota_manager.record_api_call(endpoint="search", success=False)
                break
        
        return all_tweets
    
    def _find_matched_keywords(self, text: str, keywords: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Find which keywords match the tweet text.
        
        Args:
            text: Tweet text
            keywords: List of keyword dictionaries
            
        Returns:
            List of matched keyword dictionaries
        """
        text_lower = text.lower()
        matched = []
        
        for kw_dict in keywords:
            keyword = kw_dict['keyword'].lower()
            
            # Check for match (exact or word-level)
            if keyword in text_lower:
                matched.append(kw_dict)
            elif any(word in text_lower for word in keyword.split()):
                matched.append(kw_dict)
        
        return matched

    def _extract_full_text(self, tweet, ref_tweets, users):
        """
        Extract full text from a tweet, handling retweets properly.

        For retweets, Twitter API v2 only provides truncated text by default.
        This method reconstructs the full text using referenced_tweets data.

        Args:
            tweet: The main tweet object
            ref_tweets: Dictionary of referenced tweet data from includes
            users: Dictionary of user data from includes

        Returns:
            str: Full text of the tweet (original or reconstructed)
        """
        original_text = tweet.get('text', '')

        # Check if this is a retweet
        referenced_tweets = tweet.get('referenced_tweets', [])
        if not referenced_tweets:
            return original_text

        # Look for retweeted content
        for ref in referenced_tweets:
            if ref.get('type') == 'retweeted':
                ref_id = ref.get('id')
                if ref_id and ref_id in ref_tweets:
                    ref_tweet = ref_tweets[ref_id]
                    ref_text = ref_tweet.get('text', '')
                    ref_author_id = ref_tweet.get('author_id')

                    # Get the original author's username
                    ref_author = users.get(ref_author_id, {})
                    ref_username = ref_author.get('username', 'unknown')

                    # Reconstruct the full retweet text
                    if ref_text:
                        full_retweet_text = f"RT @{ref_username}: {ref_text}"
                        logger.debug(f"Reconstructed retweet: {len(original_text)} → {len(full_retweet_text)} chars")
                        return full_retweet_text

        # For quoted tweets or other types, return original text
        return original_text

    def search_keyword_deep(self, keyword: str, max_results: int = 100,
                           days_back: int = 7, next_token: str = None,
                           exclude_replies: bool = False,
                           exclude_retweets: bool = False,
                           min_likes: int = 0,
                           min_retweets: int = 0) -> Dict:
        """
        Deep search for a single keyword with pagination support.

        This method is designed for focused scraping where we want many tweets
        for a specific keyword rather than spreading across multiple keywords.

        Args:
            keyword: The keyword to search for
            max_results: Number of tweets to return in this batch (10-100)
            days_back: Number of days to search back
            next_token: Pagination token for continuing a search
            exclude_replies: Whether to exclude replies
            exclude_retweets: Whether to exclude retweets
            min_likes: Minimum number of likes
            min_retweets: Minimum number of retweets

        Returns:
            Dict with 'data' (tweets), 'meta' (including next_token)
        """
        logger.info(f"Deep search for keyword: '{keyword}'", max_results=max_results)

        # Build query with filters
        query_parts = []

        # Add keyword (quote if multi-word)
        if ' ' in keyword:
            query_parts.append(f'"{keyword}"')
        else:
            query_parts.append(keyword)

        # CRITICAL: Exclude tweets FROM WDF accounts (but still get mentions of them)
        # This prevents self-replies and circular engagement
        query_parts.append('-from:wdf_show')
        query_parts.append('-from:wdfshow')
        query_parts.append('-from:wdf_watch')
        query_parts.append('-from:wdfwatch')

        # Add filters
        if exclude_retweets:
            query_parts.append('-is:retweet')
        if exclude_replies:
            query_parts.append('-is:reply')
        if min_likes > 0:
            query_parts.append(f'min_faves:{min_likes}')
        if min_retweets > 0:
            query_parts.append(f'min_retweets:{min_retweets}')

        # Always add language filter
        query_parts.append('lang:en')

        query = ' '.join(query_parts)
        logger.debug(f"Built query: {query}")

        # API endpoint
        endpoint = f"{self.BASE_URL}/tweets/search/recent"

        # Build parameters with comprehensive fields
        params = {
            'query': query,
            'max_results': min(100, max(10, max_results)),
            # Comprehensive tweet fields
            'tweet.fields': (
                'text,created_at,author_id,public_metrics,conversation_id,'
                'lang,source,possibly_sensitive,reply_settings,'
                'context_annotations,entities,referenced_tweets,'
                'in_reply_to_user_id,geo'
            ),
            # User fields for influence metrics
            'user.fields': (
                'username,name,verified,public_metrics,created_at,'
                'description,location,profile_image_url,protected'
            ),
            # Expansions for complete data
            'expansions': (
                'author_id,referenced_tweets.id,referenced_tweets.id.author_id,'
                'attachments.media_keys,entities.mentions.username,'
                'in_reply_to_user_id,geo.place_id'
            ),
            'media.fields': 'type,url,duration_ms,height,width,preview_image_url,alt_text',
            'place.fields': 'country,country_code,full_name,geo,place_type'
        }

        # Add pagination token if provided
        if next_token:
            params['pagination_token'] = next_token
            logger.debug("Continuing paginated search", next_token=next_token[:20])

        # Add time range
        if days_back and not next_token:  # Only on first request
            from datetime import datetime, timedelta
            start_time = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            params['start_time'] = start_time

        try:
            # Make API request
            response = self.session.get(endpoint, params=params, timeout=30)

            # Record API call for quota tracking
            self.quota_manager.record_api_call(
                endpoint="search",
                success=response.status_code == 200
            )

            if response.status_code == 200:
                data = response.json()

                # Process and enrich tweet data
                tweets = data.get('data', [])
                includes = data.get('includes', {})
                users = {u['id']: u for u in includes.get('users', [])}
                media_items = {m['media_key']: m for m in includes.get('media', [])}
                places = {p['id']: p for p in includes.get('places', [])}
                ref_tweets = {t['id']: t for t in includes.get('tweets', [])}

                # Enrich each tweet with user and additional data
                enriched_tweets = []
                for tweet in tweets:
                    author = users.get(tweet['author_id'], {})

                    # Extract full text, handling retweets properly
                    full_text = self._extract_full_text(tweet, ref_tweets, users)

                    # Build comprehensive tweet object
                    enriched_tweet = {
                        'id': tweet['id'],
                        'text': full_text,
                        'created_at': tweet.get('created_at'),
                        'author_id': tweet.get('author_id'),
                        'conversation_id': tweet.get('conversation_id'),
                        'lang': tweet.get('lang'),
                        'source': tweet.get('source'),
                        'possibly_sensitive': tweet.get('possibly_sensitive', False),
                        'reply_settings': tweet.get('reply_settings'),

                        # Metrics
                        'public_metrics': tweet.get('public_metrics', {}),
                        'retweet_count': tweet.get('public_metrics', {}).get('retweet_count', 0),
                        'reply_count': tweet.get('public_metrics', {}).get('reply_count', 0),
                        'like_count': tweet.get('public_metrics', {}).get('like_count', 0),
                        'quote_count': tweet.get('public_metrics', {}).get('quote_count', 0),

                        # Author information
                        'user': {
                            'id': author.get('id'),
                            'username': author.get('username'),
                            'name': author.get('name'),
                            'verified': author.get('verified', False),
                            'created_at': author.get('created_at'),
                            'description': author.get('description'),
                            'location': author.get('location'),
                            'profile_image_url': author.get('profile_image_url'),
                            'protected': author.get('protected', False),
                            'public_metrics': author.get('public_metrics', {})
                        },

                        # Additional metadata
                        'entities': tweet.get('entities', {}),
                        'context_annotations': tweet.get('context_annotations', []),
                        'referenced_tweets': tweet.get('referenced_tweets', []),
                        'in_reply_to_user_id': tweet.get('in_reply_to_user_id'),
                        'geo': tweet.get('geo'),
                        'attachments': tweet.get('attachments', {}),

                        # Add keyword tracking
                        'matched_keyword': keyword,
                        'search_query': query,
                        'focused_search': True
                    }

                    # Add media details if present
                    if 'media_keys' in enriched_tweet.get('attachments', {}):
                        enriched_tweet['media'] = [
                            media_items.get(key, {})
                            for key in enriched_tweet['attachments']['media_keys']
                        ]

                    # Add place details if geo-tagged
                    if enriched_tweet.get('geo') and 'place_id' in enriched_tweet['geo']:
                        place_id = enriched_tweet['geo']['place_id']
                        if place_id in places:
                            enriched_tweet['place'] = places[place_id]

                    # Add referenced tweet data
                    if enriched_tweet['referenced_tweets']:
                        for ref in enriched_tweet['referenced_tweets']:
                            ref_id = ref.get('id')
                            if ref_id in ref_tweets:
                                ref['tweet_data'] = {
                                    'text': ref_tweets[ref_id].get('text'),
                                    'author_id': ref_tweets[ref_id].get('author_id')
                                }

                    enriched_tweets.append(enriched_tweet)

                # Return enriched data with pagination info
                result = {
                    'data': enriched_tweets,
                    'meta': data.get('meta', {})
                }

                logger.info(
                    f"Deep search returned {len(enriched_tweets)} tweets",
                    has_next=bool(data.get('meta', {}).get('next_token'))
                )

                return result

            elif response.status_code == 429:
                # Rate limited
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 60))
                wait_time = max(1, reset_time - time.time())
                logger.warning(f"Rate limited, please wait {wait_time}s")
                raise Exception(f"Rate limited - wait {wait_time}s")

            else:
                logger.error(f"Search failed: {response.status_code} - {response.text}")
                raise Exception(f"Search failed with status {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during deep search: {e}")
            self.quota_manager.record_api_call(endpoint="search", success=False)
            raise

    def get_tweet_by_id(self, tweet_id: str) -> Optional[Dict]:
        """
        Fetch a single tweet by ID.
        
        Args:
            tweet_id: The tweet ID
            
        Returns:
            Tweet dictionary or None
        """
        endpoint = f"{self.BASE_URL}/tweets/{tweet_id}"
        
        params = {
            'tweet.fields': 'text,created_at,author_id,public_metrics,conversation_id,referenced_tweets',
            'user.fields': 'username,name,verified',
            'expansions': 'author_id,referenced_tweets.id,referenced_tweets.id.author_id'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=30)
            
            # Record API call
            self.quota_manager.record_api_call(
                endpoint="tweet_lookup",
                success=response.status_code == 200
            )
            
            if response.status_code == 200:
                data = response.json()
                tweet = data.get('data')
                includes = data.get('includes', {})
                users = {u['id']: u for u in includes.get('users', [])}
                ref_tweets = {t['id']: t for t in includes.get('tweets', [])}

                if tweet:
                    author = users.get(tweet['author_id'], {})

                    # Extract full text, handling retweets properly
                    full_text = self._extract_full_text(tweet, ref_tweets, users)

                    return {
                        'id': tweet['id'],
                        'text': full_text,
                        'created_at': tweet.get('created_at'),
                        'user': f"@{author.get('username', 'unknown')}",
                        'user_name': author.get('name'),
                        'metrics': tweet.get('public_metrics', {}),
                        'conversation_id': tweet.get('conversation_id')
                    }
                    
        except Exception as e:
            logger.error(f"Failed to fetch tweet {tweet_id}: {e}")
            self.quota_manager.record_api_call(endpoint="tweet_lookup", success=False)
            
        return None
    
    def reply_to_tweet(self, tweet_id: str, text: str) -> bool:
        """
        Reply to a tweet - WITH SAFETY CHECKS.
        
        Args:
            tweet_id: Tweet to reply to
            text: Reply text
            
        Returns:
            True if successful
        """
        # CRITICAL: Verify account before posting
        if not hasattr(self, '_account_verified'):
            user_response = self.session.get(f"{self.BASE_URL}/users/me", timeout=30)
            if user_response.status_code == 200:
                user_data = user_response.json()
                username = user_data.get('data', {}).get('username', 'unknown')
                if username.lower() == 'wdf_show':
                    logger.error("🚨 CRITICAL: Attempting to post from WDF_Show account!")
                    logger.error("ABORTING - This is the managing account, not WDFwatch!")
                    return False
                elif username.lower() in ['wdfwatch', 'wdf_watch']:
                    logger.info(f"✅ Verified: Posting as @{username} (automated account)")
                else:
                    logger.warning(f"⚠️  Posting as @{username}")
                self._account_verified = True
        
        endpoint = f"{self.BASE_URL}/tweets"
        
        payload = {
            'text': text,
            'reply': {
                'in_reply_to_tweet_id': tweet_id
            }
        }
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=30)
            
            # Record API call
            self.quota_manager.record_api_call(
                endpoint="tweet_create",
                success=response.status_code == 201
            )
            
            if response.status_code == 201:
                logger.info(f"Successfully replied to tweet {tweet_id}")
                return True
            else:
                logger.error(f"Failed to reply: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Reply error: {e}")
            self.quota_manager.record_api_call(endpoint="tweet_create", success=False)
            
        return False