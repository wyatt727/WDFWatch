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
            # Get classification model
            model = self.model_factory.create_model_for_task('classification', check_enabled=True)
            
            # If classification is disabled, return default scores
            if model is None:
                logger.info("Classification stage is disabled, returning default scores")
                return [0.0] * len(tweets)
            
            # Prepare context
            context_content = self._get_context_content('classify')
            adapted_context = self.context_adapter.adapt_context_for_model(
                context_content=context_content,
                model_name=model.model_name,
                provider=model.config.provider,
                mode='classify',
                max_context_length=model.get_context_limit()
            )
            
            # Process all tweets in one batch for efficiency
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
            
            # Build prompt with @ reference (Claude CLI supports this)
            # The specialized CLAUDE.md already has all the instructions
            if with_reasoning:
                prompt = f"""Using the Reasoning Mode format, classify these tweets:

@{tweets_file.resolve()}

Output ONLY the scores and reasons in the exact format specified."""
            else:
                prompt = f"""Using the Batch Mode format, classify these tweets:

@{tweets_file.resolve()}

Output ONLY one score per line, nothing else."""
            
            # Get response
            response = await model.generate(prompt, adapted_context, 'classify')
            
            # Log the raw response for debugging
            logger.info(f"Classification response length: {len(response.content)} chars")
            if with_reasoning:
                logger.debug(f"Raw classification response (first 500 chars): {response.content[:500]}")
            
            # Parse response based on mode
            if with_reasoning:
                # Parse score and reason pairs
                results = []
                
                # First try to split by --- separator
                entries = response.content.strip().split('---')
                logger.debug(f"Found {len(entries)} entries when split by ---")
                
                for i, entry in enumerate(entries):
                    entry = entry.strip()
                    if not entry:
                        continue
                    
                    score = 0.0
                    reason = "Failed to parse"
                    
                    # Log each entry for debugging
                    if len(entries) < 5:  # Only log details for small batches
                        logger.debug(f"Entry {i+1}: {entry[:200]}..." if len(entry) > 200 else f"Entry {i+1}: {entry}")
                    
                    for line in entry.split('\n'):
                        line = line.strip()
                        if line.startswith('SCORE:'):
                            try:
                                score_str = line.replace('SCORE:', '').strip()
                                score = float(score_str)
                                score = max(0.0, min(1.0, score))
                                logger.debug(f"Parsed score: {score}")
                            except ValueError as e:
                                logger.warning(f"Failed to parse score from '{line}': {e}")
                                score = 0.0
                        elif line.startswith('REASON:'):
                            reason = line.replace('REASON:', '').strip()
                            if reason:
                                logger.debug(f"Parsed reason: {reason[:50]}...")
                        elif 'score' in line.lower() and ':' in line:
                            # Try alternative format like "Score: 0.85"
                            try:
                                parts = line.split(':', 1)
                                score = float(parts[1].strip())
                                score = max(0.0, min(1.0, score))
                                logger.debug(f"Parsed score from alternative format: {score}")
                            except:
                                pass
                    
                    results.append({'score': score, 'reason': reason})
                
                logger.info(f"Parsed {len(results)} classification results with reasoning")
                
                # Ensure correct number of results
                if len(results) < len(tweets):
                    logger.warning(f"Only parsed {len(results)} results but have {len(tweets)} tweets")
                    logger.warning("Filling missing results with default values")
                    while len(results) < len(tweets):
                        results.append({'score': 0.0, 'reason': 'Failed to parse - insufficient results from model'})
                elif len(results) > len(tweets):
                    logger.warning(f"Parsed {len(results)} results but only have {len(tweets)} tweets, truncating")
                
                all_results = results[:len(tweets)]
            else:
                # Parse scores only (one per line)
                scores = []
                lines = response.content.strip().split('\n')
                logger.debug(f"Parsing {len(lines)} lines for scores")
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        score = float(line)
                        scores.append(max(0.0, min(1.0, score)))
                        if i < 3:  # Log first few for debugging
                            logger.debug(f"Line {i+1}: '{line}' -> {score}")
                    except ValueError as e:
                        logger.warning(f"Failed to parse score from line {i+1}: '{line}' - {e}")
                        scores.append(0.0)
                
                logger.info(f"Parsed {len(scores)} classification scores")
                
                # Ensure correct number of scores
                if len(scores) < len(tweets):
                    logger.warning(f"Only parsed {len(scores)} scores but have {len(tweets)} tweets")
                    logger.warning("Filling missing scores with 0.0")
                    while len(scores) < len(tweets):
                        scores.append(0.0)
                elif len(scores) > len(tweets):
                    logger.warning(f"Parsed {len(scores)} scores but only have {len(tweets)} tweets, truncating")
                
                all_results = scores[:len(tweets)]
            
            # Track costs
            self.cost_tracker.track_response(response)
            
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
Connect the tweet to episode themes and include the video URL.

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