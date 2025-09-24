#!/usr/bin/env python3
"""
Tweet data cleaner - removes unnecessary fields for classification
"""

from typing import Dict, List

def clean_tweet(tweet: Dict) -> Dict:
    """
    Extract only essential fields from a tweet for classification.
    
    Args:
        tweet: Raw tweet dictionary with all fields
        
    Returns:
        Cleaned tweet with only essential fields
    """
    # Essential fields for classification
    essential = {
        'id': tweet.get('id', ''),
        'text': tweet.get('text', tweet.get('full_text', '')),
        'user': tweet.get('user', tweet.get('author_handle', 'unknown')),
        'created_at': tweet.get('created_at', ''),
    }
    
    # Add metrics if available (for context)
    if 'metrics' in tweet:
        essential['likes'] = tweet['metrics'].get('like_count', 0)
        essential['retweets'] = tweet['metrics'].get('retweet_count', 0)
    elif 'likes' in tweet:
        essential['likes'] = tweet.get('likes', 0)
        essential['retweets'] = tweet.get('retweets', 0)
    
    return essential

def clean_tweets(tweets: List[Dict]) -> List[Dict]:
    """
    Clean a list of tweets.
    
    Args:
        tweets: List of raw tweet dictionaries
        
    Returns:
        List of cleaned tweets
    """
    return [clean_tweet(tweet) for tweet in tweets]