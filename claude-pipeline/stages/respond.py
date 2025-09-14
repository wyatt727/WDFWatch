#!/usr/bin/env python3
"""
Response generation stage - Creates engaging tweet responses using episode context
"""

import logging
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add web scripts to path for web_bridge if available
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "web" / "scripts"))

from core import UnifiedInterface, BatchProcessor
from core.episode_manager import EpisodeManager

# Try to import web_bridge for database sync
HAS_WEB_BRIDGE = False
try:
    from web_bridge import sync_responses_to_database
    HAS_WEB_BRIDGE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.debug("WebUIBridge not available - running in file-only mode")

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """
    Generates tweet responses using episode-specific CLAUDE.md context.
    """
    
    def __init__(self, claude: UnifiedInterface):
        """
        Initialize response generator.
        
        Args:
            claude: Claude interface instance
        """
        self.claude = claude
        self.batch_processor = BatchProcessor(max_workers=3)
        # Use same episodes directory as orchestrator
        from pathlib import Path
        episodes_dir = Path(__file__).parent.parent / "episodes"
        self.episode_mgr = EpisodeManager(episodes_dir=str(episodes_dir))
        logger.info("Response generator initialized")
    
    def generate_responses(self, tweets: List[Dict], episode_id: str) -> List[Dict]:
        """
        Generate responses for relevant tweets using batch mode.
        
        Args:
            tweets: List of relevant tweet dictionaries
            episode_id: Episode ID for context
            
        Returns:
            Tweets with generated responses
        """
        if not tweets:
            return []
        
        logger.info(f"Generating responses for {len(tweets)} tweets using episode {episode_id}")
        
        # Set episode context - this loads summary.md which has everything including video URL
        self.claude.set_episode_context(episode_id)
        
        # Get episode directory for saving output
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        
        # Process in batches to avoid context limits while maintaining efficiency
        batch_size = 20  # Balance between context quality and processing speed
        all_responses = []
        
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} tweets")
            batch_responses = self.batch_generate_responses(batch, episode_id)
            all_responses.extend(batch_responses)
        
        # Save responses to episode directory
        if episode_dir:
            responses_file = episode_dir / "responses.json"
            with open(responses_file, 'w') as f:
                json.dump(all_responses, f, indent=2)
            logger.info(f"Saved {len(all_responses)} responses to {responses_file}")
            
            # Sync responses to database if web bridge is available
            if HAS_WEB_BRIDGE and os.getenv("WDF_WEB_MODE") == "true":
                try:
                    draft_count = sync_responses_to_database(
                        responses_file=str(responses_file),
                        episode_dir=episode_id
                    )
                    if draft_count > 0:
                        logger.info(f"Successfully synced {draft_count} responses as drafts to database")
                    else:
                        logger.warning("No responses were synced to database")
                except Exception as e:
                    logger.warning(f"Failed to sync responses to database: {e}")
                    # Continue anyway - don't fail the whole pipeline
        
        return all_responses
    
    def generate_single_response(self, tweet_text: str, episode_id: str) -> str:
        """
        Generate a single tweet response.
        
        Args:
            tweet_text: Tweet to respond to
            episode_id: Episode ID for context
            
        Returns:
            Response text (under 250 chars)
        """
        # Embed instructions directly in prompt
        prompt = f"""You are the WDF Podcast Tweet Response Generator. Your ONLY function is to generate tweet responses that promote the podcast.

CRITICAL RULES:
- Output ONLY the tweet response - nothing else
- Maximum 240 characters
- NEVER use emojis
- NEVER explain what you're doing
- Include the URL/handle naturally

TWEET TO RESPOND TO:
{tweet_text}

Generate a response:"""
        
        response = self.claude.call(
            prompt=prompt,
            mode='respond',
            episode_id=episode_id
        )
        
        # Validate and clean response
        response = self._validate_response(response)
        
        return response
    
    def _validate_response(self, response: str, tweet_text: str = None, episode_id: str = None) -> str:
        """
        Validate and clean response. Regenerate if too long.
        
        Args:
            response: Generated response
            tweet_text: Original tweet text for regeneration if needed
            episode_id: Episode ID for regeneration if needed
            
        Returns:
            Validated response (always under 250 chars)
        """
        # Remove any instruction text
        if "Here's" in response or "I would" in response:
            # Extract just the response
            lines = response.split('\n')
            for line in lines:
                if line and not any(word in line for word in ['Here', 'I would', 'Response:']):
                    response = line
                    break
        
        # Remove emojis if any slipped through
        import re
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        response = emoji_pattern.sub('', response).strip()
        
        # Check length but DON'T delete - let Draft Review handle it
        if len(response) > 250:
            logger.warning(f"Response is {len(response)} chars (over 250 limit) - keeping for Draft Review")
            # Keep the response - the Draft Review UI will show it's too long
            # User can edit it there
        
        return response
    
    def batch_generate_responses(self, tweets: List[Dict], episode_id: str) -> List[Dict]:
        """
        Generate responses for all tweets in a single batch call.
        
        Args:
            tweets: List of tweets
            episode_id: Episode ID
            
        Returns:
            Tweets with responses
        """
        if not tweets:
            return tweets
            
        # Get the video URL from the episode directory
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        video_url = None
        if episode_dir:
            video_url_file = episode_dir / "video_url.txt"
            if video_url_file.exists():
                video_url = video_url_file.read_text().strip()
        
        # If no video_url.txt file, fall back to default
        if not video_url:
            video_url = "https://youtube.com/wdf-latest"
            logger.warning(f"No video URL found for episode {episode_id}, using default")
        
        # Format tweets for the prompt with all context - no filtering
        tweet_texts = []
        for tweet in tweets:
            text = tweet.get('text', tweet.get('full_text', ''))
            reason = tweet.get('classification_reason', '')
            user = tweet.get('user', 'unknown')
            
            # Include user and classification reason for better context
            tweet_entry = f"@{user}: {text}"
            if reason:
                tweet_entry += f"\n[WHY RELEVANT: {reason}]"
            tweet_texts.append(tweet_entry)
        
        # Create structured prompt with tweets directly embedded
        tweets_formatted = '\n---\n'.join(tweet_texts)
        
        try:
            # Pass tweets directly in the prompt with embedded instructions
            prompt = f"""You are the WDF Podcast Tweet Response Generator. Your ONLY function is to generate tweet responses that promote the podcast.

CRITICAL RULES:
- You ONLY output tweet responses - nothing else
- Maximum 240 characters per response
- NEVER use emojis
- NEVER explain what you're doing
- Include the provided URL/handle in each response
- For multiple tweets, separate responses with ---

URL/HANDLE TO INCLUDE: {video_url}

TWEETS TO RESPOND TO:
{tweets_formatted}

Generate exactly {len(tweets)} responses separated by ---:"""
            
            # Call Claude
            response_text = self.claude.call(
                prompt=prompt,
                mode='respond',
                episode_id=episode_id,
                use_cache=False  # Don't cache batch responses
            )
            
            # Parse responses
            responses = response_text.strip().split('---')
            
            # Clean up responses (remove empty ones from bad splits)
            responses = [r.strip() for r in responses if r.strip()]
            
            # Log the counts for debugging
            logger.info(f"Received {len(responses)} responses for {len(tweets)} tweets")
            
            # Directly map responses to tweets in order
            for idx, tweet in enumerate(tweets):
                if idx < len(responses):
                    response = responses[idx]
                    # Validate but don't delete if too long
                    tweet_text = tweet.get('text', tweet.get('full_text', ''))
                    response = self._validate_response(response, tweet_text, episode_id)
                    tweet['response'] = response
                    tweet['response_length'] = len(response)
                    tweet['response_method'] = 'claude_batch'
                else:
                    logger.warning(f"Missing response for tweet #{idx+1}: {tweet.get('text', '')[:50]}...")
                    tweet['response'] = ""
                    tweet['response_length'] = 0
                    tweet['response_method'] = 'no_response'
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error generating batch responses: {e}")
            # Fall back to individual processing if batch fails
            for tweet in tweets:
                if tweet.get('response') is None:
                    try:
                        response = self.generate_single_response(
                            tweet.get('text', tweet.get('full_text', '')),
                            episode_id
                        )
                        tweet['response'] = response
                        tweet['response_length'] = len(response)
                        tweet['response_method'] = 'claude_single'
                    except Exception as e:
                        logger.error(f"Failed to generate response for tweet: {e}")
                        tweet['response'] = ""
                        tweet['response_length'] = 0
                        tweet['response_method'] = 'error'
            return tweets