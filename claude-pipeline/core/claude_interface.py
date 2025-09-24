#!/usr/bin/env python3
"""
Unified Claude Interface - Single point of interaction with Claude CLI
Handles all modes, caching, cost tracking, and episode contexts
"""

import hashlib
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class ClaudeInterface:
    """
    Unified interface for all Claude operations.
    Uses episode-specific CLAUDE.md files for context.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize Claude interface.
        
        Args:
            config: Configuration dictionary with API settings
        """
        self.config = config or {}
        self.pipeline_dir = Path(__file__).parent.parent
        self.claude_cli = "claude"  # Assumes claude is in PATH
        
        # Model mapping for Claude CLI (same as claude_adapter.py)
        self.model_mapping = {
            'claude': 'sonnet',  # Default to sonnet (Claude 4 Sonnet)
            'sonnet': 'sonnet',  # Claude 4 Sonnet
            'haiku': 'haiku',   # Claude 4 Haiku
            'opus': 'opus',     # Claude 4 Opus
            'claude-3-haiku': 'haiku',
            'claude-3-sonnet': 'sonnet',
            'claude-3-opus': 'opus',
            'claude-3.5-sonnet': 'sonnet',
            'claude-3.5-haiku': 'haiku',
        }
        
        # Get default model from environment or config
        self.default_model = self._get_default_model()
        
        # Import dependent components
        from .cache import ResponseCache
        from .cost_tracker import CostTracker
        
        self.cache = ResponseCache()
        self.cost_tracker = CostTracker()
        
        # Track current episode context - hybrid approach
        self.current_episode_id = None
        self.current_episode_context = None  # Path to EPISODE_CONTEXT.md
        
        logger.info(f"Claude interface initialized with default model: {self.default_model}")
    
    def _get_default_model(self) -> str:
        """
        Get the default Claude model from environment, config, or use fallback.
        
        Returns:
            CLI model name (sonnet, haiku, opus)
        """
        import os
        
        # Check environment variables for model preference
        env_models = [
            'WDF_LLM_MODEL_SUMMARIZATION',  # Primary fallback
            'WDF_LLM_MODEL_CLASSIFICATION', 
            'WDF_LLM_MODEL_RESPONSE',
            'WDF_LLM_MODEL_MODERATION'
        ]
        
        for env_var in env_models:
            if env_var in os.environ:
                model_name = os.environ[env_var]
                # Map to CLI model name
                cli_model = self.model_mapping.get(model_name, 'sonnet')
                logger.debug(f"Using model from {env_var}: {model_name} -> {cli_model}")
                return cli_model
        
        # Check config
        default_from_config = self.config.get('default_model', 'claude')
        cli_model = self.model_mapping.get(default_from_config, 'sonnet')
        
        logger.debug(f"Using default model from config: {default_from_config} -> {cli_model}")
        return cli_model
    
    def set_episode_context(self, episode_id: str):
        """
        Set the episode context to use for operations.
        
        Args:
            episode_id: Episode ID to load context for
        """
        from .episode_manager import EpisodeManager
        
        self.current_episode_id = episode_id
        episode_mgr = EpisodeManager()
        episode_dir = episode_mgr.get_episode_dir(episode_id)
        
        if episode_dir and (episode_dir / "summary.md").exists():
            # Use comprehensive summary.md as episode context
            self.current_episode_context = (episode_dir / "summary.md").resolve()
            logger.info(f"Using episode context: {self.current_episode_context}")
        else:
            logger.warning(f"No episode summary for {episode_id}")
            self.current_episode_context = None
    
    def call(self,
             prompt: str,
             mode: str = "default",
             episode_id: str = None,
             use_cache: bool = True,
             temperature: float = None) -> str:
        """
        Unified Claude calling with episode context, caching, and cost tracking.
        
        Args:
            prompt: The prompt to send to Claude
            mode: Operation mode (summarize, classify, respond, moderate)
            episode_id: Episode ID for context (uses current if not specified)
            use_cache: Whether to use cached responses
            temperature: Optional temperature setting
            
        Returns:
            Claude's response
        """
        # Set episode context if provided
        if episode_id and episode_id != self.current_episode_id:
            self.set_episode_context(episode_id)
        
        # Check cache first
        if use_cache:
            cached = self.cache.get(prompt, mode)
            if cached:
                logger.info(f"Cache hit for {mode} operation")
                return cached
        
        # Prepare prompt with mode instructions
        full_prompt = self._prepare_prompt(prompt, mode)
        
        # Call Claude CLI with mode for specialized context
        start_time = time.time()
        response = self._call_claude_cli(full_prompt, mode, temperature)
        elapsed = time.time() - start_time
        
        logger.info(f"Claude {mode} call took {elapsed:.2f}s")
        
        # Track costs
        self.cost_tracker.track(full_prompt, response, mode)
        
        # Cache response
        if use_cache:
            self.cache.store(prompt, response, mode)
        
        return response
    
    def _prepare_prompt(self, prompt: str, mode: str) -> str:
        """
        Prepare prompt with mode-specific instructions.
        
        Args:
            prompt: Base prompt
            mode: Operation mode
            
        Returns:
            Full prompt with mode context
        """
        mode_prefixes = {
            'summarize': "MODE: SUMMARIZE\n\n",
            'classify': "MODE: CLASSIFY\n\n",
            'respond': "MODE: RESPOND\n\n",
            'moderate': "MODE: MODERATE\n\n"
        }
        
        prefix = mode_prefixes.get(mode, "")
        return f"{prefix}{prompt}"
    
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
    
    def _call_claude_cli(self, prompt: str, mode: str = "default", temperature: float = None) -> str:
        """
        Call Claude CLI with hybrid context: specialized CLAUDE.md + episode context.
        
        Args:
            prompt: The prompt to send
            mode: Operation mode to determine specialized CLAUDE.md
            temperature: Optional temperature
            
        Returns:
            Claude's response
        """
        try:
            # Write prompt to temp file to avoid shell escaping
            temp_prompt = self.pipeline_dir / ".temp_prompt.txt"
            temp_prompt.write_text(prompt)
            
            # Build command with hybrid context approach
            cmd = [
                self.claude_cli,
                "--model", self.default_model,
                "--print"
            ]
            
            # Add specialized CLAUDE.md based on mode
            specialized_context = self._get_specialized_context_file(mode)
            if specialized_context and specialized_context.exists():
                cmd.append(f"@{specialized_context}")
                logger.debug(f"Using specialized context: {specialized_context}")
            else:
                # Fallback to master CLAUDE.md
                master_context = self.pipeline_dir / "CLAUDE.md"
                cmd.append(f"@{master_context}")
                logger.debug(f"Using master context: {master_context}")
            
            # Add episode context if available
            if self.current_episode_context and self.current_episode_context.exists():
                cmd.append(f"@{self.current_episode_context}")
                logger.debug(f"Using episode context: {self.current_episode_context}")
            
            # Add prompt
            cmd.append(f"@{temp_prompt}")
            
            # Add temperature if specified
            if temperature is not None:
                cmd.extend(["--temperature", str(temperature)])
            
            logger.debug(f"Claude CLI command: {' '.join(cmd)}")
            
            # Execute
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,  # Prevent any stdin reading
                capture_output=True,
                text=True,
                cwd=self.pipeline_dir,
                timeout=120  # 2 minute timeout
            )
            
            # Clean up temp file
            temp_prompt.unlink(missing_ok=True)
            
            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return ""
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            logger.error("Claude call timed out")
            return ""
        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return ""
    
    def batch_classify(self, tweets: List[str], episode_id: str = None) -> List[float]:
        """
        Classify multiple tweets in batches.
        
        Args:
            tweets: List of tweet texts
            episode_id: Episode ID for context
            
        Returns:
            List of relevance scores
        """
        if episode_id:
            self.set_episode_context(episode_id)
        
        batch_size = 20
        all_scores = []
        
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i+batch_size]
            
            # Format tweets for classification
            tweet_list = '\n'.join([f"{j+1}. {tweet}" for j, tweet in enumerate(batch)])
            prompt = f"""Score each tweet from 0.00 to 1.00 based on relevance.
Output one score per line, in order, with no other text.

TWEETS:
{tweet_list}

SCORES (one per line):"""
            
            # Get scores
            response = self.call(prompt, mode='classify', episode_id=episode_id)
            
            # Parse scores
            scores = []
            for line in response.strip().split('\n'):
                try:
                    score = float(line.strip())
                    scores.append(max(0.0, min(1.0, score)))
                except ValueError:
                    scores.append(0.0)
            
            # Ensure correct number of scores
            while len(scores) < len(batch):
                scores.append(0.0)
            
            all_scores.extend(scores[:len(batch)])
        
        return all_scores
    
    def generate_response(self, tweet: str, episode_id: str = None) -> str:
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
        
        prompt = f"""Generate a <200 character response to promote the WDF Podcast.
Connect the tweet to episode themes and include the video URL.

TWEET TO RESPOND TO:
{tweet}

RESPONSE:"""
        
        response = self.call(prompt, mode='respond', episode_id=episode_id)
        
        # Validate response
        if len(response) > 200:
            # Try to truncate intelligently
            if '...' in response:
                response = response[:response.rfind('...')+3]
            else:
                response = response[:197] + "..."
        
        return response
    
    def moderate_response(self, response: str, tweet: str, episode_id: str = None) -> Dict:
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
        
        evaluation = self.call(prompt, mode='moderate', episode_id=episode_id)
        
        # Parse evaluation
        result = self._parse_moderation(evaluation)
        result['response'] = response
        result['tweet'] = tweet
        
        return result
    
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