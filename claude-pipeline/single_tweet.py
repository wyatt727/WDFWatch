#!/usr/bin/env python3
"""
Claude Single Tweet Response Generator
Generates responses for individual tweets with or without episode context.

This module allows Claude to respond to specific tweets without requiring
a full episode pipeline run. It can work with:
- Just a tweet (uses general podcast knowledge)
- Tweet + episode context (uses specific episode information)
- Tweet + custom context (uses provided context)

Related files:
- /claude-pipeline/stages/respond.py (Full response generation)
- /src/wdf/tasks/single_tweet_response.py (Legacy single tweet handler)
"""

import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaudeSingleTweetResponder:
    """Generate Claude responses for individual tweets"""
    
    def __init__(self, claude_interface=None):
        """
        Initialize the single tweet responder.
        
        Args:
            claude_interface: Optional ClaudeInterface instance
        """
        if claude_interface:
            self.claude = claude_interface
        else:
            # Import here to avoid circular dependencies
            from claude_pipeline.core import ClaudeInterface
            self.claude = ClaudeInterface()
        
        # Path to specialized CLAUDE.md for responses
        self.responder_claude_md = Path(__file__).parent / "specialized" / "responder" / "CLAUDE.md"
        
        # Ensure the specialized CLAUDE.md exists
        if not self.responder_claude_md.exists():
            # Fall back to main CLAUDE.md
            self.responder_claude_md = Path(__file__).parent / "CLAUDE.md"
            logger.warning(f"Using main CLAUDE.md as responder file not found")
    
    
    def respond_to_tweet(
        self,
        tweet_text: str,
        tweet_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        episode_context_path: Optional[str] = None,
        custom_context: Optional[str] = None,
        video_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a Claude response for a single tweet.
        
        Args:
            tweet_text: The tweet content to respond to
            tweet_id: Optional tweet ID for tracking
            episode_id: Optional episode ID for context
            episode_context_path: Optional path to EPISODE_CONTEXT.md file
            custom_context: Optional custom context from user
            video_url: Optional video URL to include
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Set up context files for Claude
            context_files = [str(self.responder_claude_md)]
            
            # Add episode context if available
            if episode_context_path and Path(episode_context_path).exists():
                context_files.append(episode_context_path)
                logger.info(f"Using episode context from {episode_context_path}")
            
            # Set current context for Claude interface
            if episode_context_path:
                self.claude.current_episode_context = Path(episode_context_path)
            
            # Build the prompt
            prompt = f"""TWEET TO RESPOND TO:
{tweet_text}

{f"VIDEO URL TO INCLUDE: {video_url}" if video_url else ""}
{f"ADDITIONAL CONTEXT: {custom_context}" if custom_context else ""}

Generate a response following the guidelines in your context. Output ONLY the response text:"""

            # Call Claude with respond mode
            response = self.claude.generate(
                prompt=prompt,
                mode="respond",
                temperature=0.7,
                max_tokens=100
            )
            
            # Clean and validate response
            response_text = response.strip()
            
            # Remove any quotes if Claude wrapped it
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            # Validate character count
            if len(response_text) > 280:
                # Truncate if too long
                response_text = response_text[:277] + "..."
                logger.warning(f"Response truncated from {len(response)} to 280 characters")
            
            # Calculate approximate token usage for cost tracking
            input_tokens = len(prompt) // 4  # Rough estimate
            output_tokens = len(response_text) // 4
            
            result = {
                "success": True,
                "response": response_text,
                "character_count": len(response_text),
                "tweet_id": tweet_id,
                "episode_id": episode_id,
                "context_type": "episode" if episode_context_path else "custom" if custom_context else "general",
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Generated response: {len(response_text)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return {
                "success": False,
                "error": str(e),
                "tweet_id": tweet_id
            }
    
    def respond_to_url(self, tweet_url: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response for a tweet URL.
        
        Args:
            tweet_url: Twitter/X URL
            **kwargs: Additional arguments for respond_to_tweet
            
        Returns:
            Response dictionary
        """
        # Parse tweet ID from URL
        pattern = r'(?:twitter\.com|x\.com)/(?:#!\/)?(\w+)/status(?:es)?/(\d+)'
        match = re.search(pattern, tweet_url, re.IGNORECASE)
        
        if not match:
            return {
                "success": False,
                "error": f"Invalid tweet URL: {tweet_url}"
            }
        
        username = match.group(1)
        tweet_id = match.group(2)
        
        # Note: In a real implementation, we would fetch the tweet text
        # For now, we'll require the text to be provided
        if 'tweet_text' not in kwargs:
            return {
                "success": False,
                "error": "Tweet text must be provided (fetching not implemented for safety)"
            }
        
        return self.respond_to_tweet(tweet_id=tweet_id, **kwargs)
    
    def batch_respond(
        self,
        tweets: list[Dict[str, str]],
        episode_context_path: Optional[str] = None,
        video_url: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Generate responses for multiple tweets.
        
        Args:
            tweets: List of tweet dictionaries with 'id' and 'text'
            episode_context_path: Optional path to EPISODE_CONTEXT.md
            video_url: Optional video URL to include
            
        Returns:
            List of response dictionaries
        """
        responses = []
        
        for tweet in tweets:
            response = self.respond_to_tweet(
                tweet_text=tweet.get('text', ''),
                tweet_id=tweet.get('id'),
                episode_context_path=episode_context_path,
                video_url=video_url
            )
            responses.append(response)
            
            # Add small delay to avoid rate limiting
            import time
            time.sleep(0.5)
        
        return responses


def main():
    """CLI interface for single tweet responses"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Claude response for a single tweet')
    parser.add_argument('tweet_text', help='The tweet text to respond to')
    parser.add_argument('--tweet-id', help='Tweet ID for tracking')
    parser.add_argument('--episode-id', help='Episode ID for context')
    parser.add_argument('--episode-context-file', help='Path to EPISODE_CONTEXT.md file')
    parser.add_argument('--custom-context', help='Custom context string')
    parser.add_argument('--video-url', help='Video URL to include in response')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Create responder and generate response
    responder = ClaudeSingleTweetResponder()
    result = responder.respond_to_tweet(
        tweet_text=args.tweet_text,
        tweet_id=args.tweet_id,
        episode_id=args.episode_id,
        episode_context_path=args.episode_context_file,
        custom_context=args.custom_context,
        video_url=args.video_url
    )
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result['success']:
            print(f"\nResponse ({result['character_count']} chars):")
            print(result['response'])
            print(f"\nContext type: {result['context_type']}")
            print(f"Tokens used: {result['tokens']['input']} input, {result['tokens']['output']} output")
        else:
            print(f"Error: {result['error']}")


if __name__ == "__main__":
    main()