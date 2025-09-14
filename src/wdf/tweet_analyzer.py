"""
Tweet Analysis Utilities

Analyzes enriched tweet data for trust signals, bot detection, and influence scoring.
Uses the comprehensive data collected via "one-pass enriched fetch" strategy.

Integrates with: twitter_api_v2.py, classify.py
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class TweetAnalyzer:
    """
    Analyzes enriched tweet data for classification signals.
    
    Features:
    - Bot detection from source and user patterns
    - Influence scoring from user metrics
    - Context extraction from Twitter's AI annotations
    - Trust scoring for prioritization
    """
    
    # Known bot/automation sources
    BOT_SOURCES = [
        'IFTTT',
        'Zapier',
        'Buffer',
        'Hootsuite',
        'TweetDeck',
        'SocialOomph',
        'dlvr.it',
        'twittbot.net',
        'Bot',
        'API'
    ]
    
    # Human/mobile sources (higher trust)
    HUMAN_SOURCES = [
        'Twitter for iPhone',
        'Twitter for Android', 
        'Twitter Web App',
        'Twitter for iPad',
        'Twitter for Mac'
    ]
    
    def analyze_tweet(self, tweet: Dict) -> Dict:
        """
        Perform comprehensive analysis on enriched tweet data.
        
        Args:
            tweet: Enriched tweet dictionary with all fields
            
        Returns:
            Analysis results with scores and signals
        """
        analysis = {
            'bot_probability': self._calculate_bot_probability(tweet),
            'influence_score': self._calculate_influence_score(tweet),
            'trust_score': self._calculate_trust_score(tweet),
            'engagement_quality': self._analyze_engagement_quality(tweet),
            'context_topics': self._extract_context_topics(tweet),
            'conversation_signals': self._analyze_conversation(tweet),
            'content_signals': self._analyze_content(tweet)
        }
        
        # Overall relevance boost based on signals
        analysis['relevance_boost'] = self._calculate_relevance_boost(analysis)
        
        return analysis
    
    def _calculate_bot_probability(self, tweet: Dict) -> float:
        """
        Calculate probability that tweet is from a bot account.
        
        Signals:
        - Source application
        - Account age vs follower ratio
        - Tweet frequency
        - Username patterns
        """
        score = 0.0
        signals = []
        
        # Check source application
        source = tweet.get('source', '')
        if any(bot in source for bot in self.BOT_SOURCES):
            score += 0.4
            signals.append(f"bot_source:{source}")
        elif source in self.HUMAN_SOURCES:
            score -= 0.2
            signals.append(f"human_source:{source}")
        
        # Check account age
        user_created = tweet.get('user_created_at')
        if user_created:
            try:
                created_date = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
                account_age_days = (datetime.now(created_date.tzinfo) - created_date).days
                
                # New account with high activity is suspicious
                if account_age_days < 30:
                    score += 0.3
                    signals.append("new_account")
                elif account_age_days > 365:
                    score -= 0.1
                    signals.append("established_account")
                    
            except Exception as e:
                logger.debug(f"Failed to parse user creation date: {e}")
        
        # Check username patterns (numbers, underscores)
        username = tweet.get('user', '').replace('@', '')
        if re.search(r'\d{4,}', username):  # 4+ consecutive digits
            score += 0.2
            signals.append("numeric_username")
        
        # Check follower/following ratio
        user_metrics = tweet.get('user_metrics', {})
        followers = user_metrics.get('followers_count', 0)
        following = user_metrics.get('following_count', 0)
        
        if followers > 0 and following > 0:
            ratio = followers / following
            if ratio < 0.1:  # Following way more than followers
                score += 0.2
                signals.append("low_follower_ratio")
            elif ratio > 10:  # Many followers, few following
                score -= 0.1
                signals.append("high_follower_ratio")
        
        # Check if protected account (less likely to be bot)
        if tweet.get('user_protected', False):
            score -= 0.2
            signals.append("protected_account")
        
        # Normalize to 0-1 range
        bot_probability = max(0.0, min(1.0, score))
        
        logger.debug(f"Bot probability for @{username}: {bot_probability:.2f} (signals: {signals})")
        return bot_probability
    
    def _calculate_influence_score(self, tweet: Dict) -> float:
        """
        Calculate user influence score based on metrics.
        
        Higher influence = more important to engage with.
        """
        user_metrics = tweet.get('user_metrics', {})
        
        # Get follower count (main influence metric)
        followers = user_metrics.get('followers_count', 0)
        
        # Logarithmic scale for followers (diminishing returns)
        if followers > 0:
            import math
            # log10(1) = 0, log10(1000) = 3, log10(1M) = 6
            follower_score = min(1.0, math.log10(followers + 1) / 6)
        else:
            follower_score = 0.0
        
        # Verified accounts get a boost
        if tweet.get('user_verified', False):
            follower_score = min(1.0, follower_score + 0.3)
        
        # Engagement rate (likes/followers) indicates active audience
        likes = tweet.get('likes', 0)
        if followers > 100 and likes > 0:
            engagement_rate = likes / followers
            if engagement_rate > 0.01:  # >1% engagement is good
                follower_score = min(1.0, follower_score + 0.1)
        
        return follower_score
    
    def _calculate_trust_score(self, tweet: Dict) -> float:
        """
        Calculate overall trust score for prioritization.
        
        Combines bot probability, influence, and content signals.
        """
        # Start with inverse of bot probability
        bot_prob = self._calculate_bot_probability(tweet)
        trust = 1.0 - bot_prob
        
        # Boost for verified accounts
        if tweet.get('user_verified', False):
            trust = min(1.0, trust + 0.2)
        
        # Boost for established accounts
        user_metrics = tweet.get('user_metrics', {})
        tweet_count = user_metrics.get('tweet_count', 0)
        if tweet_count > 1000:
            trust = min(1.0, trust + 0.1)
        
        # Penalty for possibly sensitive content
        if tweet.get('possibly_sensitive', False):
            trust = max(0.0, trust - 0.2)
        
        # Boost for English (since we filtered for it)
        if tweet.get('lang') == 'en':
            trust = min(1.0, trust + 0.05)
        
        return trust
    
    def _analyze_engagement_quality(self, tweet: Dict) -> Dict:
        """
        Analyze engagement patterns for quality signals.
        """
        metrics = tweet.get('metrics', {})
        likes = metrics.get('like_count', 0)
        retweets = metrics.get('retweet_count', 0)
        replies = metrics.get('reply_count', 0)
        quotes = metrics.get('quote_count', 0)
        
        total_engagement = likes + retweets + replies + quotes
        
        quality = {
            'total_engagement': total_engagement,
            'engagement_type': 'none',
            'viral_potential': False,
            'discussion_value': False
        }
        
        if total_engagement == 0:
            return quality
        
        # Determine primary engagement type
        if replies > likes:
            quality['engagement_type'] = 'discussion'
            quality['discussion_value'] = True
        elif retweets > likes:
            quality['engagement_type'] = 'amplification'
            quality['viral_potential'] = retweets > 10
        else:
            quality['engagement_type'] = 'approval'
        
        # High quote count indicates thought-provoking content
        if quotes > 5:
            quality['discussion_value'] = True
        
        return quality
    
    def _extract_context_topics(self, tweet: Dict) -> List[str]:
        """
        Extract topics from Twitter's context annotations.
        
        These are AI-detected topics that Twitter assigns.
        """
        topics = []
        context_annotations = tweet.get('context_annotations', [])
        
        for annotation in context_annotations:
            domain = annotation.get('domain', {})
            entity = annotation.get('entity', {})
            
            # Add domain name (category)
            if domain.get('name'):
                topics.append(f"domain:{domain['name']}")
            
            # Add entity name (specific topic)
            if entity.get('name'):
                topics.append(f"entity:{entity['name']}")
        
        return topics
    
    def _analyze_conversation(self, tweet: Dict) -> Dict:
        """
        Analyze conversation context and threading.
        """
        signals = {
            'is_reply': bool(tweet.get('in_reply_to_user_id')),
            'is_quote': False,
            'is_retweet': False,
            'has_thread': tweet.get('conversation_id') == tweet.get('id'),
            'reply_settings': tweet.get('reply_settings', 'everyone')
        }
        
        # Check referenced tweets
        for ref in tweet.get('referenced_tweets', []):
            ref_type = ref.get('type')
            if ref_type == 'quoted':
                signals['is_quote'] = True
            elif ref_type == 'retweeted':
                signals['is_retweet'] = True
        
        return signals
    
    def _analyze_content(self, tweet: Dict) -> Dict:
        """
        Analyze tweet content for relevant signals.
        """
        text = tweet.get('text', '')
        entities = tweet.get('entities', {})
        
        signals = {
            'has_links': bool(entities.get('urls')),
            'has_media': bool(tweet.get('attachments', {}).get('media_keys')),
            'has_mentions': bool(entities.get('mentions')),
            'has_hashtags': bool(entities.get('hashtags')),
            'text_length': len(text),
            'is_thread_start': '🧵' in text or '1/' in text or 'Thread:' in text.upper()
        }
        
        # Check media types if present
        if tweet.get('media'):
            media_types = [m.get('type') for m in tweet['media']]
            signals['media_types'] = list(set(media_types))
        
        return signals
    
    def _calculate_relevance_boost(self, analysis: Dict) -> float:
        """
        Calculate relevance boost based on all signals.
        
        This can be added to classification scores.
        """
        boost = 0.0
        
        # High influence users get a boost
        boost += analysis['influence_score'] * 0.2
        
        # High trust users get a boost
        boost += analysis['trust_score'] * 0.1
        
        # Discussion-generating content gets a boost
        if analysis['engagement_quality']['discussion_value']:
            boost += 0.15
        
        # Viral content gets a boost
        if analysis['engagement_quality']['viral_potential']:
            boost += 0.1
        
        # Penalize likely bots
        boost -= analysis['bot_probability'] * 0.3
        
        return max(-0.5, min(0.5, boost))  # Cap between -0.5 and +0.5
    
    def get_priority_score(self, tweet: Dict) -> float:
        """
        Get overall priority score for response generation.
        
        Higher score = respond to this tweet first.
        """
        analysis = self.analyze_tweet(tweet)
        
        # Combine influence, trust, and engagement
        priority = (
            analysis['influence_score'] * 0.4 +
            analysis['trust_score'] * 0.3 +
            min(1.0, analysis['engagement_quality']['total_engagement'] / 100) * 0.3
        )
        
        # Apply bot penalty
        priority *= (1.0 - analysis['bot_probability'] * 0.5)
        
        return priority