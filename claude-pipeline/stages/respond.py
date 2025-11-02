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

# Try to import web_bridge for database sync - TRY MULTIPLE PATHS
HAS_WEB_BRIDGE = False
sync_responses_to_database = None

# Try different import paths for web_bridge
import_attempts = []

# Method 1: Try importing from current directory (symlink in claude-pipeline)
try:
    from web_bridge import sync_responses_to_database as sync_func
    sync_responses_to_database = sync_func
    HAS_WEB_BRIDGE = True
    import_attempts.append(("claude-pipeline local", "SUCCESS"))
except ImportError as e:
    import_attempts.append(("claude-pipeline local", f"FAILED: {e}"))

# Method 2: Try importing from web/scripts if first method failed
if not HAS_WEB_BRIDGE:
    try:
        import sys
        from pathlib import Path
        web_scripts_path = Path(__file__).parent.parent.parent / "web" / "scripts"
        if str(web_scripts_path) not in sys.path:
            sys.path.insert(0, str(web_scripts_path))
        from web_bridge import sync_responses_to_database as sync_func
        sync_responses_to_database = sync_func
        HAS_WEB_BRIDGE = True
        import_attempts.append(("web/scripts direct", "SUCCESS"))
    except ImportError as e:
        import_attempts.append(("web/scripts direct", f"FAILED: {e}"))

# If all imports failed, create stub function but LOG LOUDLY
if not HAS_WEB_BRIDGE:
    logger = logging.getLogger(__name__)
    logger.error(
        f"❌ WEB BRIDGE IMPORT FAILED - Database sync will NOT work! "
        f"Attempts: {import_attempts}, CWD: {os.getcwd()}, "
        f"WEB_MODE: {os.getenv('WDF_WEB_MODE')}"
    )

    def sync_responses_to_database(responses_file, episode_dir):
        """Stub function when web_bridge is not available"""
        logger = logging.getLogger(__name__)
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            logger.error(
                f"❌ CRITICAL: sync_responses_to_database called but web_bridge not imported! "
                f"Responses NOT synced to database! File: {responses_file}"
            )
        return 0
else:
    logger = logging.getLogger(__name__)
    logger.info(
        f"✅ Web bridge imported successfully for response sync. "
        f"Method: {import_attempts[-1][0] if import_attempts else 'unknown'}"
    )

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
        batch_size = 15  # Optimized batch size - reliable completion within timeout while minimizing API calls
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
            
            # Sync responses to database if web bridge is available - CRITICAL FIX
            # Auto-enable web mode if episode_id looks like a database-backed episode (keyword_* or episode_*)
            web_mode = os.getenv("WDF_WEB_MODE", "false").lower() == "true"
            is_database_episode = episode_id and (episode_id.startswith("keyword_") or episode_id.startswith("episode_"))

            if HAS_WEB_BRIDGE and (web_mode or is_database_episode):
                if not web_mode and is_database_episode:
                    logger.info(f"🔄 Auto-enabling web mode for database episode: {episode_id}")
                try:
                    logger.info(f"🔄 Attempting to sync {len(all_responses)} responses to database for episode {episode_id}")
                    draft_count = sync_responses_to_database(
                        responses_file=str(responses_file),
                        episode_dir=episode_id
                    )
                    if draft_count > 0:
                        logger.info(f"✅ Successfully synced {draft_count} responses as drafts to database")
                    else:
                        logger.warning("⚠️ No responses were synced to database (possibly no tweets in DB or all tweets already have drafts)")
                except Exception as e:
                    logger.error(f"❌ FAILED to sync responses to database: {e}")
                    # Continue anyway - don't fail the whole pipeline
            elif not HAS_WEB_BRIDGE and (web_mode or is_database_episode):
                logger.error(
                    f"❌ CRITICAL: Web bridge NOT imported, {len(all_responses)} responses NOT synced to database! "
                    f"Episode: {episode_id}, WDF_WEB_MODE: {web_mode}, Is Database Episode: {is_database_episode}"
                )
        
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
        # THINK HARD is used for individual responses to maximize quality
        prompt = f"""THINK HARD and craft the most engaging response possible. You are the WDF Podcast Tweet Response Generator. Your ONLY function is to generate tweet responses that promote the podcast.

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
                logger.info(f"Using video URL from file: {video_url}")

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

        # Initialize response_text to capture partial responses even on error
        response_text = ""
        responses = []

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

            # Log the prompt for debugging
            logger.debug(f"Sending prompt to Claude (first 500 chars): {prompt[:500]}...")
            logger.info(f"Prompt length: {len(prompt)} characters, requesting {len(tweets)} responses")

            # Call Claude
            response_text = self.claude.call(
                prompt=prompt,
                mode='respond',
                episode_id=episode_id,
                use_cache=False  # Don't cache batch responses
            )

            # Log the raw response for debugging
            logger.debug(f"Raw response from Claude (first 500 chars): {response_text[:500]}...")
            logger.info(f"Response length: {len(response_text)} characters")

            # Check if response is an error
            if response_text.startswith('[ERROR:'):
                logger.error(f"Claude returned an error: {response_text}")
                # Don't raise immediately - try to parse what we got

        except Exception as e:
            logger.error(f"Error calling Claude for batch responses: {e}", exc_info=True)
            # Don't give up yet - try to parse whatever we got

        # Always try to parse responses, even if there was an error
        if response_text and not response_text.startswith('[ERROR:'):
            try:
                # Parse responses
                responses = response_text.strip().split('---')

                # Clean up responses (remove empty ones from bad splits)
                responses = [r.strip() for r in responses if r.strip()]

                # Log the counts for debugging
                logger.info(f"Parsed {len(responses)} responses from Claude output for {len(tweets)} tweets")

            except Exception as parse_error:
                logger.error(f"Error parsing responses: {parse_error}")
                responses = []
        else:
            logger.warning("No valid response text to parse")
            responses = []

        # Map parsed responses to tweets and only regenerate truly missing ones
        for idx, tweet in enumerate(tweets):
            if idx < len(responses) and responses[idx]:
                response = responses[idx]
                # Validate but don't delete if too long
                tweet_text = tweet.get('text', tweet.get('full_text', ''))
                response = self._validate_response(response, tweet_text, episode_id)
                tweet['response'] = response
                tweet['response_length'] = len(response)
                tweet['response_method'] = 'claude_batch'
                logger.debug(f"Tweet {idx+1}: Got batch response ({len(response)} chars)")
            else:
                # Only regenerate this specific tweet
                logger.warning(f"Missing response for tweet #{idx+1}: {tweet.get('text', '')[:50]}...")
                try:
                    logger.info(f"Generating individual response for tweet {idx+1}")
                    response = self.generate_single_response(
                        tweet.get('text', tweet.get('full_text', '')),
                        episode_id
                    )
                    tweet['response'] = response
                    tweet['response_length'] = len(response)
                    tweet['response_method'] = 'claude_single_fallback'
                    logger.info(f"Successfully generated individual response: {len(response)} chars")
                except Exception as fallback_error:
                    logger.error(f"Individual generation also failed: {fallback_error}")
                    tweet['response'] = ""
                    tweet['response_length'] = 0
                    tweet['response_method'] = 'no_response'

        return tweets