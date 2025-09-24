#!/usr/bin/env python3
"""
Unified Interface - Single point of interaction with any LLM provider
Handles all modes, caching, cost tracking, and episode contexts using flexible model selection
"""

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Union
from datetime import datetime

from .model_factory import ModelFactory
from .context_adapter import ContextAdapter
from .model_interface import ModelInterface, ModelResponse, ModelException

logger = logging.getLogger(__name__)

class UnifiedInterface:
    """
    Unified interface for all LLM operations supporting multiple providers.
    Uses episode-specific CLAUDE.md files for context and flexible model selection.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize unified interface.
        
        Args:
            config: Configuration dictionary with API settings
        """
        self.config = config or {}
        self.pipeline_dir = Path(__file__).parent.parent
        
        # Initialize factory and adapters
        self.model_factory = ModelFactory()
        self.context_adapter = ContextAdapter()
        
        # Import dependent components
        from .cache import ResponseCache
        from .cost_tracker import CostTracker
        
        self.cache = ResponseCache()
        self.cost_tracker = CostTracker()
        
        # Track current episode context - hybrid approach
        self.current_episode_id = None
        self.current_episode_context = None  # Path to EPISODE_CONTEXT.md
        
        logger.info("Unified interface initialized with flexible model support")
    
    def set_episode_context(self, episode_id: str):
        """
        Set the episode context to use for operations.
        
        Args:
            episode_id: Episode ID to load context for
        """
        from .episode_manager import EpisodeManager
        
        self.current_episode_id = episode_id
        # Use the same episodes directory as orchestrator
        episodes_dir = self.pipeline_dir / "episodes"
        episode_mgr = EpisodeManager(episodes_dir=str(episodes_dir))
        episode_dir = episode_mgr.get_episode_dir(episode_id)
        
        if episode_dir and (episode_dir / "summary.md").exists():
            # Use comprehensive summary.md as episode context
            self.current_episode_context = (episode_dir / "summary.md").resolve()
            logger.info(f"Using episode context: {self.current_episode_context}")
        else:
            logger.warning(f"No episode summary for {episode_id}")
            self.current_episode_context = None
    
    async def call_async(self,
                        prompt: str,
                        mode: str = "default",
                        episode_id: str = None,
                        use_cache: bool = True,
                        temperature: float = None,
                        model_override: str = None) -> str:
        """
        Async unified LLM calling with episode context, caching, and cost tracking.
        
        Args:
            prompt: The prompt to send to the model
            mode: Operation mode (summarize, classify, respond, moderate)
            episode_id: Episode ID for context (uses current if not specified)
            use_cache: Whether to use cached responses
            temperature: Optional temperature setting
            model_override: Optional specific model to use instead of configured one
            
        Returns:
            Model's response
        """
        # Set episode context if provided
        if episode_id and episode_id != self.current_episode_id:
            self.set_episode_context(episode_id)
        
        # Check cache first
        cache_key = f"{prompt}_{mode}_{episode_id or 'default'}"
        if use_cache:
            cached = self.cache.get(cache_key, mode)
            if cached:
                logger.info(f"Cache hit for {mode} operation")
                return cached
        
        try:
            # Get appropriate model for this task
            if model_override:
                model = self.model_factory.create_model(model_override)
            else:
                model = self.model_factory.create_model_for_task(mode, check_enabled=True)
            
            # If model is None, the stage is disabled
            if model is None:
                logger.info(f"Stage {mode} is disabled, skipping execution")
                return f"[Stage {mode} disabled]"
            
            # Prepare context for this model
            context_content = self._get_context_content(mode)
            adapted_context = self.context_adapter.adapt_context_for_model(
                context_content=context_content,
                model_name=model.model_name,
                provider=model.config.provider,
                mode=mode,
                max_context_length=model.get_context_limit()
            )
            
            # Override temperature if specified
            if temperature is not None:
                model.config.temperature = temperature
            
            # Call the model
            start_time = time.time()
            response = await model.generate(prompt, adapted_context, mode)
            elapsed = time.time() - start_time
            
            logger.info(f"{model.model_name} {mode} call took {elapsed:.2f}s")
            
            # Track costs
            self.cost_tracker.track_response(response)
            
            # Cache response
            if use_cache:
                self.cache.store(cache_key, response.content, mode)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise ModelException(f"Failed to call model for {mode}: {e}")
    
    def call(self,
             prompt: str,
             mode: str = "default",
             episode_id: str = None,
             use_cache: bool = True,
             temperature: float = None,
             model_override: str = None) -> str:
        """
        Synchronous wrapper for async call method.
        Maintains backward compatibility with existing stage classes.
        """
        try:
            # Try to get the current event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
                logger.debug(f"Event loop running: {loop.is_running()}")
            except RuntimeError:
                # No event loop exists, create one
                logger.debug("No event loop found, using asyncio.run")
                return asyncio.run(
                    self.call_async(prompt, mode, episode_id, use_cache, temperature, model_override)
                )
            
            if loop.is_running():
                # If we're already in an event loop, create a new thread
                logger.debug("Running in thread due to existing event loop")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.call_async(prompt, mode, episode_id, use_cache, temperature, model_override)
                    )
                    return future.result()
            else:
                logger.debug("Running with run_until_complete")
                return loop.run_until_complete(
                    self.call_async(prompt, mode, episode_id, use_cache, temperature, model_override)
                )
        except Exception as e:
            logger.error(f"Synchronous call failed: {e}", exc_info=True)
            # Return an error response that clearly indicates failure
            # This prevents "Execution error" from being treated as valid content
            return f"[ERROR: {str(e)}]"
    
    def _get_context_content(self, mode: str) -> str:
        """
        Get combined context content for the current mode and episode.
        
        Args:
            mode: Operation mode
            
        Returns:
            Combined context content
        """
        context_files = []
        
        # Add specialized CLAUDE.md based on mode
        specialized_context = self._get_specialized_context_file(mode)
        if specialized_context and specialized_context.exists():
            context_files.append(str(specialized_context))
            logger.debug(f"Using specialized context: {specialized_context}")
        else:
            # Fallback to master CLAUDE.md
            master_context = self.pipeline_dir / "CLAUDE.md"
            if master_context.exists():
                context_files.append(str(master_context))
                logger.debug(f"Using master context: {master_context}")
        
        # Add episode context if available
        if self.current_episode_context and self.current_episode_context.exists():
            context_files.append(str(self.current_episode_context))
            logger.debug(f"Using episode context: {self.current_episode_context}")
        
        # Load and combine all context files
        return self.context_adapter.load_context_from_files(context_files, mode)
    
    def _get_specialized_context_file(self, mode: str) -> Optional[Path]:
        """
        Get the specialized CLAUDE.md file for a given mode.
        
        Args:
            mode: Operation mode (summarize, classify, respond, moderate)
            
        Returns:
            Path to specialized CLAUDE.md or None if not found
        """
        mode_to_dir = {
            'summarize': 'summarizer',
            'classify': 'classifier', 
            'respond': 'responder',
            'moderate': 'moderator'
        }
        
        if mode not in mode_to_dir:
            return None
        
        # Look for specialized directory inside pipeline dir
        specialized_dir = self.pipeline_dir / "specialized" / mode_to_dir[mode]
        specialized_file = specialized_dir / "CLAUDE.md"
        
        return specialized_file if specialized_file.exists() else None
    
    async def batch_classify(self, tweets: List[Union[str, Dict]], episode_id: str = None, with_reasoning: bool = False) -> List[Union[float, Dict]]:
        """
        Classify multiple tweets in batches.
        
        Args:
            tweets: List of tweet texts or tweet dictionaries (cleaned)
            episode_id: Episode ID for context
            with_reasoning: If True, return both scores and reasoning
            
        Returns:
            List of relevance scores (or dicts with score and reason if with_reasoning=True)
        """
        if episode_id:
            self.set_episode_context(episode_id)
        
        try:
            
            # Process tweets in smaller batches to avoid overwhelming Claude
            all_results = []
            
            # Save cleaned tweets to file for Claude CLI to reference
            import json
            import tempfile
            
            # Convert tweets to proper format if needed
            tweet_data = []
            for tweet in tweets:
                if isinstance(tweet, dict):
                    # Already a dict, use it
                    tweet_data.append(tweet)
                else:
                    # Just text, create minimal dict
                    tweet_data.append({"text": str(tweet)})
            
            # Save to episode directory if available, otherwise use temp file in working directory
            tweets_file = None
            if episode_id:
                from .episode_manager import EpisodeManager
                episodes_dir = self.pipeline_dir / "episodes"
                manager = EpisodeManager(episodes_dir=str(episodes_dir))
                episode_dir = manager.get_episode_dir(episode_id)
                
                if episode_dir:
                    tweets_file = episode_dir / "tweets_clean.json"
                    with open(tweets_file, 'w') as f:
                        json.dump(tweet_data, f, indent=2)
                    logger.info(f"Saved cleaned tweets to {tweets_file}")
            
            # If no episode directory, create a temp file in current working directory
            if not tweets_file:
                import time
                tweets_file = Path(f"temp_tweets_classify_{int(time.time())}.json")
                with open(tweets_file, 'w') as f:
                    json.dump(tweet_data, f, indent=2)
                logger.info(f"Saved cleaned tweets to temporary file {tweets_file}")
            
            # Process tweets in batches like the response stage (batch_size = 15)
            BATCH_SIZE = 15  # Use same batch size as response stage for reliability
            logger.info(f"Processing {len(tweet_data)} tweets in batches of {BATCH_SIZE}")

            for batch_start in range(0, len(tweet_data), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(tweet_data))
                batch_tweets = tweet_data[batch_start:batch_end]
                batch_num = (batch_start // BATCH_SIZE) + 1
                total_batches = (len(tweet_data) + BATCH_SIZE - 1) // BATCH_SIZE

                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_tweets)} tweets)")

                # Build prompt for this batch using same approach as response stage
                if with_reasoning:
                    # Build tweet list using response stage format - direct embedding
                    tweet_texts = []
                    for tweet in batch_tweets:
                        tweet_text = tweet.get('text', str(tweet))
                        tweet_texts.append(tweet_text)

                    # Join tweets with clear separators like response stage does
                    tweets_formatted = '\n---\n'.join(tweet_texts)

                    # Simple prompt structure like response stage - no complex instructions
                    prompt = f"""You are the WDF Podcast Tweet Classifier. Score each tweet from 0.00 to 1.00 for relevance to WDF podcast themes (federalism, state sovereignty, constitutional issues).

CRITICAL RULES:
- ULTRATHINK about every single individual tweet provided
- Pay attention to the specific people mentioned in each tweet:
  * Political figures (governors, senators, representatives)
  * Supreme Court justices and federal judges
  * Federal agency officials and bureaucrats
  * State officials and constitutional sheriffs
  * Historical figures relevant to federalism
- Consider HOW each person's actions/positions relate to WDF themes
- Come up with a UNIQUE classification reason for each tweet
- Analyze each tweet's specific content, context, people mentioned, and potential WDF connections
- Output ONLY the classifications - nothing else
- Each classification must have exactly 2 lines:
  SCORE: 0.XX
  REASON: one sentence explaining relevance and response angle
- For multiple tweets, separate classifications with ---
- NEVER explain what you're doing

TWEETS TO CLASSIFY:
{tweets_formatted}

ULTRATHINK and generate exactly {len(batch_tweets)} classifications (each with UNIQUE SCORE and REASON lines) separated by ---:"""
                else:
                    # Build tweet list for scoring only
                    tweet_list = ""
                    for i, tweet in enumerate(batch_tweets):
                        tweet_text = tweet.get('text', str(tweet))
                        tweet_list += f"{i+1}. {tweet_text}\n"

                    prompt = f"""THINK HARD and score each tweet from 0.00 to 1.00 for relevance to WDF podcast (federalism, state sovereignty, constitutional issues). Output ONLY numerical scores, one per line:

TWEETS:
{tweet_list.strip()}

SCORES (one per line):"""

                # Use the same high-level call method as response stage instead of model.generate
                try:
                    response_text = self.call(
                        prompt=prompt,
                        mode='classify',
                        episode_id=episode_id,
                        use_cache=False
                    )
                    # Create response object to match expected format
                    class Response:
                        def __init__(self, content):
                            self.content = content

                    response = Response(response_text)
                except Exception as e:
                    logger.error(f"Batch {batch_num} classification call failed: {e}")
                    # Create empty response to trigger fallback
                    response = Response("")

                # Log the raw response for debugging
                logger.info(f"Batch {batch_num} response length: {len(response.content)} chars")
                if with_reasoning and len(batch_tweets) <= 5:  # Only log details for small batches
                    logger.debug(f"Batch {batch_num} response (first 500 chars): {response.content[:500]}")

                # Parse response for this batch
                batch_results = []

                if with_reasoning:
                    # Parse score and reason pairs using simple approach like response stage
                    entries = response.content.strip().split('---')
                    # Clean up responses (remove empty ones from bad splits) - same as response stage
                    entries = [entry.strip() for entry in entries if entry.strip()]

                    logger.info(f"Batch {batch_num}: Parsed {len(entries)} classifications from Claude output for {len(batch_tweets)} tweets")

                    for i, entry in enumerate(entries):
                        score = 0.0
                        reason = "Failed to parse"

                        # Simple parsing - just look for SCORE: and REASON: lines
                        for line in entry.split('\n'):
                            line = line.strip()
                            if line.startswith('SCORE:'):
                                try:
                                    score_str = line.replace('SCORE:', '').strip()
                                    score = float(score_str)
                                    score = max(0.0, min(1.0, score))
                                except ValueError:
                                    score = 0.0
                            elif line.startswith('REASON:'):
                                reason = line.replace('REASON:', '').strip()

                        batch_results.append({'score': score, 'reason': reason})

                    logger.info(f"Batch {batch_num}: Parsed {len(batch_results)} results for {len(batch_tweets)} tweets")

                    # Ensure correct number of results for this batch
                    if len(batch_results) < len(batch_tweets):
                        logger.warning(f"Batch {batch_num}: Only parsed {len(batch_results)} results but have {len(batch_tweets)} tweets")
                        logger.warning(f"Batch {batch_num}: Filling missing results with default values")
                        while len(batch_results) < len(batch_tweets):
                            batch_results.append({'score': 0.0, 'reason': 'Failed to parse - insufficient results from model'})
                    elif len(batch_results) > len(batch_tweets):
                        logger.warning(f"Batch {batch_num}: Parsed {len(batch_results)} results but only have {len(batch_tweets)} tweets, truncating")
                        batch_results = batch_results[:len(batch_tweets)]

                else:
                    # Parse scores only (one per line)
                    lines = response.content.strip().split('\n')
                    logger.debug(f"Batch {batch_num}: Parsing {len(lines)} lines for scores")

                    for i, line in enumerate(lines):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            score = float(line)
                            batch_results.append(max(0.0, min(1.0, score)))
                            if i < 3 and len(batch_tweets) <= 5:  # Log first few for debugging
                                logger.debug(f"Batch {batch_num} Line {i+1}: '{line}' -> {score}")
                        except ValueError as e:
                            logger.warning(f"Batch {batch_num}: Failed to parse score from line {i+1}: '{line}' - {e}")
                            batch_results.append(0.0)

                    logger.info(f"Batch {batch_num}: Parsed {len(batch_results)} scores for {len(batch_tweets)} tweets")

                    # Ensure correct number of scores for this batch
                    if len(batch_results) < len(batch_tweets):
                        logger.warning(f"Batch {batch_num}: Only parsed {len(batch_results)} scores but have {len(batch_tweets)} tweets")
                        logger.warning(f"Batch {batch_num}: Filling missing scores with 0.0")
                        while len(batch_results) < len(batch_tweets):
                            batch_results.append(0.0)
                    elif len(batch_results) > len(batch_tweets):
                        logger.warning(f"Batch {batch_num}: Parsed {len(batch_results)} scores but only have {len(batch_tweets)} tweets, truncating")
                        batch_results = batch_results[:len(batch_tweets)]

                # Add this batch's results to the overall results
                all_results.extend(batch_results)

            # Final validation
            logger.info(f"Processed all batches: {len(all_results)} total results for {len(tweets)} tweets")

            if len(all_results) != len(tweets):
                logger.warning(f"Mismatch: {len(all_results)} results for {len(tweets)} tweets")
                # Ensure we have exactly the right number of results
                if len(all_results) < len(tweets):
                    logger.warning("Padding with default values")
                    if with_reasoning:
                        while len(all_results) < len(tweets):
                            all_results.append({'score': 0.0, 'reason': 'Failed to parse - insufficient results from model'})
                    else:
                        while len(all_results) < len(tweets):
                            all_results.append(0.0)
                elif len(all_results) > len(tweets):
                    logger.warning("Truncating excess results")
                    all_results = all_results[:len(tweets)]
            
            # Clean up temporary file
            try:
                tweets_file.unlink()
            except:
                pass
            
            return all_results
            
        except Exception as e:
            logger.error(f"Batch classification failed: {e}")
            return [0.0] * len(tweets)
    
    async def generate_response(self, tweet: str, episode_id: str = None) -> str:
        """
        Generate a response to a tweet.
        
        Args:
            tweet: Tweet text to respond to
            episode_id: Episode ID for context
            
        Returns:
            Response text
        """
        if episode_id:
            self.set_episode_context(episode_id)
        
        try:
            # Get response generation model
            model = self.model_factory.create_model_for_task('response', check_enabled=True)
            
            # If response generation is disabled, return empty string
            if model is None:
                logger.info("Response generation stage is disabled, returning empty response")
                return ""
            
            # Prepare context
            context_content = self._get_context_content('respond')
            adapted_context = self.context_adapter.adapt_context_for_model(
                context_content=context_content,
                model_name=model.model_name,
                provider=model.config.provider,
                mode='respond',
                max_context_length=model.get_context_limit()
            )
            
            prompt = f"""Generate a <200 character response to promote the WDF Podcast.
Connect the tweet to episode themes, craft an engaging hook, and include the video URL.

TWEET TO RESPOND TO:
{tweet}

RESPONSE:"""
            
            response = await model.generate(prompt, adapted_context, 'respond')
            
            # Track costs
            self.cost_tracker.track_response(response)
            
            response_text = response.content.strip()
            
            # Validate response length
            if len(response_text) > 200:
                # Try to truncate intelligently
                if '...' in response_text:
                    response_text = response_text[:response_text.rfind('...')+3]
                else:
                    response_text = response_text[:197] + "..."
            
            return response_text
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return ""
    
    async def moderate_response(self, response: str, tweet: str, episode_id: str = None) -> Dict:
        """
        Evaluate response quality.
        
        Args:
            response: Generated response
            tweet: Original tweet
            episode_id: Episode ID for context
            
        Returns:
            Moderation result with scores and feedback
        """
        if episode_id:
            self.set_episode_context(episode_id)
        
        try:
            # Get moderation model
            model = self.model_factory.create_model_for_task('moderation', check_enabled=True)
            
            # If moderation is disabled, return basic approval
            if model is None:
                logger.info("Moderation stage is disabled, returning auto-approval")
                return {
                    'relevance': 5,
                    'engagement': 5,
                    'connection': 5,
                    'tone': 5,
                    'char_count': len(response),
                    'url_included': 'http' in response.lower(),
                    'no_emojis': True,
                    'approved': True,
                    'feedback': 'Auto-approved (moderation disabled)',
                    'response': response,
                    'tweet': tweet,
                    'overall_score': 5.0
                }
            
            # Prepare context
            context_content = self._get_context_content('moderate')
            adapted_context = self.context_adapter.adapt_context_for_model(
                context_content=context_content,
                model_name=model.model_name,
                provider=model.config.provider,
                mode='moderate',
                max_context_length=model.get_context_limit()
            )
            
            prompt = f"""Evaluate this response for quality and appropriateness.

ORIGINAL TWEET:
{tweet}

GENERATED RESPONSE:
{response}

Evaluate on these criteria (0-10 each):
1. Relevance to tweet
2. Engagement potential
3. Episode connection
4. Tone appropriateness

Also check:
- Character count (must be <200)
- URL included (required)
- No emojis (required)

OUTPUT FORMAT:
RELEVANCE: [0-10]
ENGAGEMENT: [0-10]
CONNECTION: [0-10]
TONE: [0-10]
CHAR_COUNT: [actual count]
URL_INCLUDED: [YES/NO]
NO_EMOJIS: [YES/NO]
OVERALL: [APPROVE/REJECT]
FEEDBACK: [One line of feedback if rejected]"""
            
            model_response = await model.generate(prompt, adapted_context, 'moderate')
            
            # Track costs
            self.cost_tracker.track_response(model_response)
            
            # Parse evaluation
            result = self._parse_moderation(model_response.content)
            result['response'] = response
            result['tweet'] = tweet
            
            return result
            
        except Exception as e:
            logger.error(f"Moderation failed: {e}")
            return {
                'relevance': 0,
                'engagement': 0,
                'connection': 0,
                'tone': 0,
                'char_count': len(response),
                'url_included': False,
                'no_emojis': True,
                'approved': False,
                'feedback': f"Moderation error: {e}",
                'response': response,
                'tweet': tweet,
                'overall_score': 0
            }
    
    def _parse_moderation(self, evaluation: str) -> Dict:
        """Parse moderation evaluation into structured result."""
        result = {
            'relevance': 0,
            'engagement': 0,
            'connection': 0,
            'tone': 0,
            'char_count': 0,
            'url_included': False,
            'no_emojis': True,
            'approved': False,
            'feedback': ''
        }
        
        lines = evaluation.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                try:
                    if key == 'relevance':
                        result['relevance'] = float(value)
                    elif key == 'engagement':
                        result['engagement'] = float(value)
                    elif key == 'connection':
                        result['connection'] = float(value)
                    elif key == 'tone':
                        result['tone'] = float(value)
                    elif key == 'char_count':
                        result['char_count'] = int(value)
                    elif key == 'url_included':
                        result['url_included'] = value.upper() == 'YES'
                    elif key == 'no_emojis':
                        result['no_emojis'] = value.upper() == 'YES'
                    elif key == 'overall':
                        result['approved'] = value.upper() == 'APPROVE'
                    elif key == 'feedback':
                        result['feedback'] = value
                except (ValueError, AttributeError):
                    logger.debug(f"Failed to parse moderation field {key}: {value}")
        
        # Calculate overall score
        result['overall_score'] = (
            result['relevance'] + 
            result['engagement'] + 
            result['connection'] + 
            result['tone']
        ) / 4.0
        
        return result
    
    def get_cost_report(self) -> Dict:
        """Get cost tracking report."""
        return self.cost_tracker.get_report()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def get_available_models(self) -> Dict[str, bool]:
        """Get list of available models and their status."""
        return self.model_factory.get_available_models()
    
    def validate_model_for_task(self, task_type: str) -> bool:
        """
        Validate that the configured model for a task is available.
        
        Args:
            task_type: Task type to validate
            
        Returns:
            True if model is available and working
        """
        try:
            model = self.model_factory.create_model_for_task(task_type)
            return model.validate_availability()
        except Exception as e:
            logger.debug(f"Model validation failed for {task_type}: {e}")
            return False


# Backward compatibility alias
ClaudeInterface = UnifiedInterface