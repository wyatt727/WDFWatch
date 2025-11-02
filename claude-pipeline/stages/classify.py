#!/usr/bin/env python3
"""
Classification stage - Direct tweet classification without few-shots
"""

import logging
import asyncio
import os
import sys
from typing import List, Dict
from pathlib import Path

# Add web scripts to path for web_bridge if available
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "web" / "scripts"))

from core import UnifiedInterface, BatchProcessor
from core.tweet_cleaner import clean_tweets

# Try to import web_bridge for database sync
HAS_WEB_BRIDGE = False
try:
    from web_bridge import WebUIBridge
    HAS_WEB_BRIDGE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.debug("WebUIBridge not available - running in file-only mode")

logger = logging.getLogger(__name__)

class Classifier:
    """
    Classifies tweets using episode context, no few-shots needed.
    """
    
    def __init__(self, claude: UnifiedInterface):
        """
        Initialize classifier.
        
        Args:
            claude: Unified interface instance
        """
        self.claude = claude
        self.batch_processor = BatchProcessor(batch_size=20)
        logger.info("Classifier initialized")
    
    def classify(self, tweets: List[Dict], episode_id: str, with_reasoning: bool = True) -> List[Dict]:
        """
        Classify tweets based on episode relevance.
        
        Args:
            tweets: List of tweet dictionaries
            episode_id: Episode ID for context
            with_reasoning: If True, include reasoning for each classification
            
        Returns:
            Tweets with classification scores and reasoning
        """
        if not tweets:
            return []
        
        logger.info(f"Classifying {len(tweets)} tweets for episode {episode_id} (with_reasoning={with_reasoning})")
        
        # Clean tweets to remove unnecessary fields
        cleaned_tweets = clean_tweets(tweets)
        logger.info(f"Cleaned tweets from avg {sum(len(str(t)) for t in tweets)/len(tweets):.0f} to {sum(len(str(t)) for t in cleaned_tweets)/len(cleaned_tweets):.0f} chars each")
        
        # Save cleaned tweets to episode directory for reference
        from pathlib import Path
        import json
        from core.episode_manager import EpisodeManager
        
        # Use EpisodeManager to get the correct episode directory
        episodes_dir = Path(__file__).parent.parent / "episodes"
        manager = EpisodeManager(episodes_dir=str(episodes_dir))
        episode_dir = manager.get_episode_dir(episode_id)
        
        if episode_dir:
            tweets_clean_path = episode_dir / "tweets_clean.json"
            with open(tweets_clean_path, 'w') as f:
                json.dump(cleaned_tweets, f, indent=2)
            logger.info(f"Saved cleaned tweets to {tweets_clean_path}")
        
        # Set episode context
        self.claude.set_episode_context(episode_id)
        
        # Batch classify using Claude with cleaned tweets (handle async method)
        try:
            results = asyncio.run(self.claude.batch_classify(cleaned_tweets, episode_id, with_reasoning=with_reasoning))
        except RuntimeError:
            # If already in an event loop, create a new thread
            import concurrent.futures
            import threading
            
            def run_async():
                return asyncio.run(self.claude.batch_classify(cleaned_tweets, episode_id, with_reasoning=with_reasoning))
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async)
                results = future.result()
        
        # Merge results back into ORIGINAL tweet objects (not cleaned ones)
        for i, tweet in enumerate(tweets):
            if i < len(results):
                result = results[i]
                
                if with_reasoning and isinstance(result, dict):
                    score = result.get('score', 0.0)
                    reason = result.get('reason', '')
                else:
                    score = result if isinstance(result, (int, float)) else 0.0
                    reason = ''
                
                if isinstance(tweet, dict):
                    tweet['relevance_score'] = score
                    tweet['classification'] = 'RELEVANT' if score >= 0.70 else 'SKIP'
                    tweet['classification_method'] = 'claude_direct'
                    if with_reasoning:
                        tweet['classification_reason'] = reason
                else:
                    # Convert to dict
                    tweets[i] = {
                        'text': tweet,
                        'relevance_score': score,
                        'classification': 'RELEVANT' if score >= 0.70 else 'SKIP',
                        'classification_method': 'claude_direct'
                    }
                    if with_reasoning:
                        tweets[i]['classification_reason'] = reason
        
        # Log statistics
        relevant = sum(1 for t in tweets if t.get('classification') == 'RELEVANT')
        skip = len(tweets) - relevant
        avg_score = sum(t.get('relevance_score', 0) for t in tweets) / len(tweets)
        
        logger.info(f"Classification complete:")
        logger.info(f"  Relevant: {relevant} ({relevant/len(tweets)*100:.1f}%)")
        logger.info(f"  Skip: {skip}")
        logger.info(f"  Average score: {avg_score:.3f}")
        
        # Sync classifications to database if web bridge is available
        if HAS_WEB_BRIDGE and os.getenv("WDF_WEB_MODE") == "true":
            try:
                bridge = WebUIBridge()
                bridge.notify_tweets_classified(tweets)
                bridge.close()
                logger.info(f"Synced {len(tweets)} tweet classifications to database")
            except Exception as e:
                logger.warning(f"Failed to sync classifications to database: {e}")
                # Continue anyway - don't fail the whole pipeline
        
        return tweets
    
    def classify_single(self, tweet_text: str, episode_id: str) -> Dict:
        """
        Classify a single tweet.
        
        Args:
            tweet_text: Tweet text to classify
            episode_id: Episode ID for context
            
        Returns:
            Classification result
        """
        # Set episode context
        self.claude.set_episode_context(episode_id)
        
        prompt = f"""Score this tweet's relevance from 0.00 to 1.00 based on episode themes (if available) or general WDF Podcast themes.
Output only the numerical score.

TWEET:
{tweet_text}

SCORE:"""
        
        response = self.claude.call(
            prompt=prompt,
            mode='classify',
            episode_id=episode_id
        )
        
        try:
            score = float(response.strip())
        except ValueError:
            logger.error(f"Failed to parse score: {response}")
            score = 0.0
        
        return {
            'text': tweet_text,
            'relevance_score': score,
            'classification': 'RELEVANT' if score >= 0.70 else 'SKIP'
        }