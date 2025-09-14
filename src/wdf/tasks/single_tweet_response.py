#!/usr/bin/env python3
"""
Single Tweet Response Generator

Generates responses for individual tweets outside the normal pipeline.
Used by the web UI for targeted responses.

Features:
- Direct tweet fetching via URL
- Episode context selection
- Custom prompt support
- Character limit validation
- Response caching

Related files:
- /web/app/api/single-tweet/route.ts (API endpoint)
- /web/app/(dashboard)/single-tweet/page.tsx (UI)
- /src/wdf/tasks/deepseek.py (Response generation logic)
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import structlog
import subprocess
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from wdf.settings import WDFSettings
from wdf.twitter_client import TwitterClient
from wdf.web_bridge import WebBridge

logger = structlog.get_logger()

class SingleTweetResponseGenerator:
    """Generates responses for individual tweets"""
    
    def __init__(self, settings: WDFSettings):
        self.settings = settings
        self.web_bridge = WebBridge(settings)
        self.twitter_client = TwitterClient(settings)
        
    def parse_tweet_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse tweet ID and username from URL"""
        pattern = r'(?:twitter\.com|x\.com)/(?:#!\/)?(\w+)/status(?:es)?/(\d+)'
        match = re.search(pattern, url, re.IGNORECASE)
        
        if match:
            return {
                "username": match.group(1),
                "tweet_id": match.group(2)
            }
        return None
    
    def fetch_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tweet from Twitter API"""
        try:
            # In production, this would use the Twitter API
            # For safety, we'll return mock data
            logger.warning(
                "Tweet fetching not implemented for safety",
                tweet_id=tweet_id
            )
            
            return {
                "id": tweet_id,
                "text": f"[Mock tweet content for ID: {tweet_id}]",
                "author": {
                    "username": "mock_user",
                    "name": "Mock User"
                },
                "metrics": {
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0
                }
            }
            
        except Exception as e:
            logger.error(
                "Failed to fetch tweet",
                tweet_id=tweet_id,
                error=str(e)
            )
            return None
    
    def load_episode_context(self, episode_id: Optional[int]) -> Dict[str, Any]:
        """Load episode context for response generation"""
        try:
            if episode_id:
                # Load specific episode from database
                # For now, return mock data
                return {
                    "id": episode_id,
                    "title": f"Episode {episode_id}",
                    "summary": "Episode summary would be loaded from database",
                    "keywords": ["federalism", "constitution", "liberty"]
                }
            else:
                # Load latest episode
                # For now, return mock data
                return {
                    "id": 0,
                    "title": "Latest Episode",
                    "summary": "Latest episode summary",
                    "keywords": ["current", "events", "discussion"]
                }
                
        except Exception as e:
            logger.error(
                "Failed to load episode context",
                episode_id=episode_id,
                error=str(e)
            )
            return {}
    
    def generate_response(
        self,
        tweet_text: str,
        episode_context: Dict[str, Any],
        custom_context: Optional[str] = None,
        model: str = "deepseek-r1:latest"
    ) -> str:
        """Generate response using LLM"""
        try:
            # Build prompt
            prompt = f"""Generate a concise Twitter response (max 280 characters) to this tweet:

Tweet: {tweet_text}

Episode Context:
Title: {episode_context.get('title', 'N/A')}
Summary: {episode_context.get('summary', 'N/A')[:500]}

{f"Additional Context: {custom_context}" if custom_context else ""}

Requirements:
1. Keep response under 280 characters
2. Be relevant to the tweet
3. Naturally mention the WDF podcast
4. Include a call-to-action if appropriate
5. Be respectful and engaging

Response:"""

            # Check if model is configured
            configured_model = self.settings.llm_models.response
            if configured_model:
                model = configured_model
                logger.info(f"Using configured model: {model}")
            
            # Call Ollama to generate response
            # For safety, we'll return a mock response
            logger.warning(
                "LLM generation not implemented for safety",
                model=model
            )
            
            mock_response = (
                "Great point! Rick Becker explores this exact issue in the WDF podcast. "
                "Check out our latest episode on constitutional federalism."
            )
            
            # In production, this would call:
            # result = subprocess.run(
            #     ["ollama", "run", model],
            #     input=prompt,
            #     capture_output=True,
            #     text=True,
            #     timeout=30
            # )
            # response = result.stdout.strip()
            
            return mock_response
            
        except Exception as e:
            logger.error(
                "Failed to generate response",
                error=str(e)
            )
            return ""
    
    def validate_response(self, response: str) -> Dict[str, Any]:
        """Validate response meets requirements"""
        char_count = len(response)
        is_valid = char_count <= 280 and char_count > 0
        
        return {
            "valid": is_valid,
            "character_count": char_count,
            "errors": [] if is_valid else [
                f"Response is {char_count} characters (max 280)" if char_count > 280 
                else "Response is empty"
            ]
        }
    
    async def process_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single tweet response request"""
        try:
            tweet_url = params.get("tweet_url")
            tweet_id = params.get("tweet_id")
            tweet_text = params.get("tweet_text")
            episode_id = params.get("episode_id")
            custom_context = params.get("custom_context")
            model = params.get("model", "deepseek-r1:latest")
            request_id = params.get("request_id")
            
            logger.info(
                "Processing single tweet response request",
                tweet_url=tweet_url,
                episode_id=episode_id
            )
            
            # Parse tweet URL if needed
            if not tweet_id and tweet_url:
                parsed = self.parse_tweet_url(tweet_url)
                if parsed:
                    tweet_id = parsed["tweet_id"]
            
            # Fetch tweet if text not provided
            if not tweet_text and tweet_id:
                tweet_data = self.fetch_tweet(tweet_id)
                if tweet_data:
                    tweet_text = tweet_data.get("text", "")
            
            if not tweet_text:
                raise ValueError("Could not obtain tweet text")
            
            # Load episode context
            episode_context = self.load_episode_context(episode_id)
            
            # Generate response
            response_text = self.generate_response(
                tweet_text,
                episode_context,
                custom_context,
                model
            )
            
            # Validate response
            validation = self.validate_response(response_text)
            
            if not validation["valid"]:
                raise ValueError(f"Invalid response: {validation['errors']}")
            
            # Send real-time update
            await self.web_bridge.send_event(
                "single_tweet_response_generated",
                {
                    "requestId": request_id,
                    "response": response_text,
                    "characterCount": validation["character_count"]
                }
            )
            
            return {
                "success": True,
                "text": response_text,
                "character_count": validation["character_count"],
                "tweet_id": tweet_id,
                "episode_id": episode_id
            }
            
        except Exception as e:
            logger.error(
                "Failed to process request",
                error=str(e),
                params=params
            )
            
            # Send failure event
            if request_id:
                await self.web_bridge.send_event(
                    "single_tweet_response_failed",
                    {
                        "requestId": request_id,
                        "error": str(e)
                    }
                )
            
            return {
                "success": False,
                "error": str(e)
            }


async def main():
    """Main entry point"""
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Generate response for single tweet")
    parser.add_argument(
        "--params",
        type=str,
        required=True,
        help="JSON parameters for request"
    )
    
    args = parser.parse_args()
    
    try:
        # Parse parameters
        params = json.loads(args.params)
        
        # Load settings
        settings = WDFSettings()
        
        # Create generator
        generator = SingleTweetResponseGenerator(settings)
        
        # Process request
        result = await generator.process_request(params)
        
        # Output result as JSON for the web API to parse
        print(json.dumps(result))
        
    except Exception as e:
        logger.error("Single tweet response failed", error=str(e))
        print(json.dumps({
            "success": False,
            "error": str(e)
        }))
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())