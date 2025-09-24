#!/usr/bin/env python3
"""
Master Pipeline Orchestrator - Runs the complete unified Claude pipeline
Each episode gets its own directory with CLAUDE.md as the memory
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    project_root_env = Path(__file__).parent.parent / '.env'
    if project_root_env.exists():
        load_dotenv(project_root_env)
        print(f"[ORCHESTRATOR] Loaded environment variables from {project_root_env}")
except ImportError:
    print("[ORCHESTRATOR] Warning: python-dotenv not available, skipping .env loading")

# Ensure Claude CLI is in PATH (critical for Web UI execution)
# Add the Claude CLI location to PATH if not already present
claude_path = '/home/debian/.claude/local'
if claude_path not in os.environ.get('PATH', ''):
    os.environ['PATH'] = f"{claude_path}:{os.environ.get('PATH', '')}"
    print(f"[ORCHESTRATOR] Added {claude_path} to PATH")

# Debug: Log the current PATH to verify
import subprocess
import sys
print(f"[ORCHESTRATOR] PATH at startup: {os.environ.get('PATH', '')}")
try:
    result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
    print(f"[ORCHESTRATOR] which claude: {result.stdout.strip()}")
except Exception as e:
    print(f"[ORCHESTRATOR] Failed to check claude location: {e}")

# Add src/wdf to Python path for scraping module imports
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
    print(f"[ORCHESTRATOR] Added {src_path} to Python path")

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Core components
from core import UnifiedInterface, EpisodeManager
from stages import Summarizer, Classifier, ResponseGenerator, QualityModerator

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()

class UnifiedClaudePipeline:
    """
    Master orchestrator for the unified Claude pipeline.
    Manages episode directories with CLAUDE.md as memory.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the unified pipeline.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Initialize components
        console.print("[bold cyan]Initializing Unified Claude Pipeline[/bold cyan]")
        
        # Load stage configuration
        self.stage_config = self._load_stage_configuration()
        
        self.claude = UnifiedInterface(config)
        # Use claude-pipeline/episodes directory for episode storage
        episodes_dir = Path(__file__).parent / "episodes"
        self.episode_mgr = EpisodeManager(episodes_dir=str(episodes_dir))
        
        self.summarizer = Summarizer(self.claude)
        self.classifier = Classifier(self.claude)
        self.responder = ResponseGenerator(self.claude)
        self.moderator = QualityModerator(self.claude)
        
        console.print("[green]✓[/green] Pipeline initialized")
        self._display_stage_configuration()
        
        # Validate stage configuration
        validation = self._validate_stage_configuration()
        self._display_stage_validation(validation)
    
    def run_episode(self,
                   transcript_path: str,
                   episode_id: str = None,
                   video_url: str = None,
                   skip_scraping: bool = False,
                   skip_moderation: bool = False,
                   tweets_file: str = None) -> Dict:
        """
        Run complete pipeline for an episode.
        
        Args:
            transcript_path: Path to transcript file
            episode_id: Optional episode ID
            video_url: Optional YouTube URL
            skip_scraping: Skip tweet scraping (use cached)
            skip_moderation: Skip human moderation
            
        Returns:
            Complete pipeline results
        """
        start_time = time.time()
        
        # Load transcript
        transcript_path = Path(transcript_path)
        if not transcript_path.exists():
            raise FileNotFoundError(f"Transcript not found: {transcript_path}")
        
        transcript = transcript_path.read_text()
        
        # Load podcast overview
        overview_path = transcript_path.parent / "podcast_overview.txt"
        if overview_path.exists():
            podcast_overview = overview_path.read_text()
        else:
            podcast_overview = self._get_default_overview()
        
        # Display episode info
        console.print(Panel.fit(
            f"[bold]Processing Episode[/bold]\n"
            f"Transcript: {transcript_path.name}\n"
            f"Length: {len(transcript)} characters\n"
            f"Video: {video_url or 'Not provided'}",
            title="Episode Information"
        ))
        
        results = {
            'episode_id': episode_id,
            'stages': {},
            'stats': {},
            'start_time': datetime.now().isoformat()
        }
        
        # =====================
        # STAGE 1: SUMMARIZATION & MEMORY CREATION
        # =====================
        if self._is_stage_enabled('summarization'):
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Stage 1: Summarization & Memory Creation", total=None)
                
                summary_result = self.summarizer.summarize(
                    transcript=transcript,
                    podcast_overview=podcast_overview,
                    episode_id=episode_id,
                    video_url=video_url
                )
                
                episode_id = summary_result['episode_id']
                results['episode_id'] = episode_id
                results['episode_dir'] = summary_result.get('episode_dir')
                results['stages']['summarization'] = summary_result
                
                progress.update(task, completed=100)
            
            console.print(f"[green]✓[/green] Summary generated for episode {episode_id}")
            console.print(f"[green]✓[/green] Episode CLAUDE.md created with full context")
            
            # Display summary stats
            self._display_summary_stats(summary_result)
        else:
            console.print("[yellow]Summarization stage disabled - skipping[/yellow]")
            results['stages']['summarization'] = {'skipped': True}
        
        # =====================
        # STAGE 2: TWEET SCRAPING
        # =====================
        if self._is_stage_enabled('scraping'):
            if not skip_scraping:
                tweets = self._scrape_tweets(summary_result.get('keywords', []), episode_id, tweets_file)
            else:
                tweets = self._load_cached_tweets(episode_id)
            
            # Sync tweets to database if in web mode
            if tweets and os.getenv("WDF_WEB_MODE") == "true":
                self._sync_tweets_to_database(tweets, episode_id)
            
            results['stages']['scraping'] = {
                'tweet_count': len(tweets),
                'skipped': skip_scraping
            }
            
            console.print(f"[green]✓[/green] Loaded {len(tweets)} tweets")
        else:
            console.print("[yellow]Scraping stage disabled - using empty tweet list[/yellow]")
            tweets = []
            results['stages']['scraping'] = {'skipped': True, 'tweet_count': 0}
        
        # =====================
        # STAGE 3: CLASSIFICATION (NO FEW-SHOTS!)
        # =====================
        if self._is_stage_enabled('classification') and tweets:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Stage 3: Tweet Classification", total=None)
                
                classified = self.classifier.classify(tweets, episode_id)
                
                progress.update(task, completed=100)
            
            # Filter relevant tweets
            relevant_tweets = [t for t in classified if t.get('classification') == 'RELEVANT']
            
            results['stages']['classification'] = {
                'total_tweets': len(classified),
                'relevant': len(relevant_tweets),
                'skip': len(classified) - len(relevant_tweets),
                'relevant_percentage': round(len(relevant_tweets) / len(classified) * 100, 1) if classified else 0
            }
            
            console.print(f"[green]✓[/green] Classification complete (no few-shots needed!)")
            self._display_classification_stats(results['stages']['classification'])
            
            # Save classified tweets to episode directory
            episode_dir = self.episode_mgr.get_episode_dir(episode_id)
            if episode_dir:
                with open(episode_dir / "classified.json", 'w') as f:
                    json.dump(classified, f, indent=2)
        else:
            if not self._is_stage_enabled('classification'):
                console.print("[yellow]Classification stage disabled - treating all tweets as relevant[/yellow]")
                relevant_tweets = tweets
                classified = [{'text': t.get('text', ''), 'classification': 'RELEVANT'} for t in tweets]
            else:
                console.print("[yellow]No tweets to classify[/yellow]")
                relevant_tweets = []
                classified = []
                
            results['stages']['classification'] = {
                'total_tweets': len(classified),
                'relevant': len(relevant_tweets),
                'skip': 0,
                'relevant_percentage': 100 if classified else 0,
                'skipped': not self._is_stage_enabled('classification')
            }
        
        # =====================
        # STAGE 4: RESPONSE GENERATION
        # =====================
        if self._is_stage_enabled('response') and relevant_tweets:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Stage 4: Response Generation", total=None)
                
                responses = self.responder.generate_responses(relevant_tweets, episode_id)  # Process all relevant tweets
                
                progress.update(task, completed=100)
            
            results['stages']['response_generation'] = {
                'responses_generated': len(responses)
            }
            
            console.print(f"[green]✓[/green] Generated {len(responses)} responses")
        else:
            if not self._is_stage_enabled('response'):
                console.print("[yellow]Response generation stage disabled - skipping[/yellow]")
            else:
                console.print("[yellow]No relevant tweets for response generation[/yellow]")
            responses = []
            results['stages']['response_generation'] = {
                'responses_generated': 0,
                'skipped': not self._is_stage_enabled('response')
            }
        
        # =====================
        # STAGE 5: QUALITY MODERATION
        # =====================
        if self._is_stage_enabled('moderation') and responses:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Stage 5: Quality Moderation", total=None)
                
                moderated = self.moderator.moderate_responses(responses, episode_id)
                
                progress.update(task, completed=100)
            
            # Get quality report
            quality_report = self.moderator.get_quality_report(moderated)
            results['stages']['moderation'] = quality_report
            
            console.print(f"[green]✓[/green] Quality moderation complete")
            self._display_quality_report(quality_report)
            
            # Filter approved responses
            approved_responses = [r for r in moderated if r.get('quality_approved')]
        else:
            if not self._is_stage_enabled('moderation'):
                console.print("[yellow]Quality moderation stage disabled - auto-approving all responses[/yellow]")
                approved_responses = responses
                quality_report = {
                    'total': len(responses),
                    'approved': len(responses),
                    'rejected': 0,
                    'approval_rate': 100 if responses else 0,
                    'skipped': True
                }
            else:
                console.print("[yellow]No responses to moderate[/yellow]")
                approved_responses = []
                quality_report = {
                    'total': 0,
                    'approved': 0,
                    'rejected': 0,
                    'approval_rate': 0,
                    'skipped': False
                }
            
            results['stages']['moderation'] = quality_report
        
        # =====================
        # STAGE 6: HUMAN REVIEW (Optional)
        # =====================
        if not skip_moderation and approved_responses:
            console.print("\n[bold yellow]Human review required[/bold yellow]")
            console.print(f"Please review {len(approved_responses)} responses")
            # This would normally launch the moderation UI
            final_responses = approved_responses
        else:
            final_responses = approved_responses
        
        # Save final responses
        if episode_dir:
            with open(episode_dir / "published.json", 'w') as f:
                json.dump(final_responses, f, indent=2)
        
        # =====================
        # FINAL REPORT
        # =====================
        elapsed_time = time.time() - start_time
        results['stats'] = {
            'total_time_seconds': round(elapsed_time, 2),
            'total_time_minutes': round(elapsed_time / 60, 2),
            'tweets_processed': len(tweets),
            'responses_generated': len(responses),
            'responses_approved': len(final_responses),
            'approval_rate': round(len(final_responses) / len(responses) * 100, 1) if responses else 0
        }
        
        # Display final report
        self._display_final_report(results)
        
        # Display cost report
        cost_report = self.claude.get_cost_report()
        self._display_cost_report(cost_report)
        
        return results
    
    def run_individual_stage(self,
                            stage: str,
                            transcript_path: str,
                            episode_id: str = None,
                            video_url: str = None) -> Dict:
        """
        Run a single pipeline stage.
        
        Args:
            stage: Stage to run ('summarize', 'classify', 'respond', 'moderate')
            transcript_path: Path to transcript file
            episode_id: Optional episode ID
            video_url: Optional YouTube URL
            
        Returns:
            Stage execution results
        """
        start_time = time.time()
        
        console.print(Panel.fit(
            f"[bold]Running Individual Stage: {stage.title()}[/bold]\n"
            f"Episode ID: {episode_id or 'Auto-generated'}\n"
            f"Transcript: {Path(transcript_path).name}",
            title="Stage Execution"
        ))
        
        # Load transcript
        transcript_path = Path(transcript_path)
        if not transcript_path.exists():
            raise FileNotFoundError(f"Transcript not found: {transcript_path}")
        
        transcript = transcript_path.read_text()
        
        # Load podcast overview
        overview_path = transcript_path.parent / "podcast_overview.txt"
        if overview_path.exists():
            podcast_overview = overview_path.read_text()
        else:
            podcast_overview = self._get_default_overview()
        
        results = {
            'stage': stage,
            'episode_id': episode_id,
            'success': False,
            'start_time': datetime.now().isoformat(),
            'stats': {}
        }
        
        try:
            # Stage-specific execution
            if stage == 'summarize':
                stage_result = self._run_summarize_stage(transcript, podcast_overview, episode_id, video_url)
            elif stage == 'scraping':
                stage_result = self._run_scraping_stage(episode_id)
            elif stage == 'classify':
                stage_result = self._run_classify_stage(episode_id)
            elif stage == 'respond':
                stage_result = self._run_respond_stage(episode_id)
            elif stage == 'moderate':
                stage_result = self._run_moderate_stage(episode_id)
            else:
                raise ValueError(f"Unknown stage: {stage}")
            
            results.update(stage_result)
            results['success'] = True
            
            # Calculate timing
            elapsed_time = time.time() - start_time
            results['stats'] = {
                'total_time_seconds': round(elapsed_time, 2),
                'total_time_minutes': round(elapsed_time / 60, 2)
            }
            
            console.print(f"[green]✓[/green] Stage '{stage}' completed successfully in {elapsed_time:.2f}s")
            
        except Exception as e:
            results['error'] = str(e)
            results['success'] = False
            console.print(f"[red]✗[/red] Stage '{stage}' failed: {e}")
            logger.error(f"Stage {stage} failed: {e}", exc_info=True)
        
        return results
    
    def _run_summarize_stage(self, transcript: str, podcast_overview: str, episode_id: str = None, video_url: str = None) -> Dict:
        """Execute summarization stage."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Summarizing transcript and generating context", total=None)
            
            summary_result = self.summarizer.summarize(
                transcript=transcript,
                podcast_overview=podcast_overview,
                episode_id=episode_id,
                video_url=video_url
            )
            
            progress.update(task, completed=100)
        
        # Display summary stats
        self._display_summary_stats(summary_result)
        
        return {
            'episode_id': summary_result['episode_id'],
            'episode_dir': summary_result.get('episode_dir'),
            'summary': summary_result.get('summary', ''),
            'keywords': summary_result.get('keywords', []),
            'video_url': summary_result.get('video_url')
        }

    def _run_scraping_stage(self, episode_id: str) -> Dict:
        """Execute tweet scraping stage."""
        if not episode_id:
            raise ValueError("Episode ID required for scraping stage")

        # Get episode directory and load keywords
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if not episode_dir:
            raise ValueError(f"Episode directory not found for episode {episode_id}")

        keywords_file = episode_dir / "keywords.json"
        if not keywords_file.exists():
            raise ValueError(f"Keywords file not found: {keywords_file}")

        # Load keywords from file
        with open(keywords_file, 'r') as f:
            keyword_dicts = json.load(f)

        # Extract keyword strings from the dictionary format
        keywords = [kw.get('keyword', kw) if isinstance(kw, dict) else kw for kw in keyword_dicts]

        if not keywords:
            console.print("[yellow]No keywords found for scraping[/yellow]")
            return {'tweets_scraped': 0}

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Scraping tweets for {len(keywords)} keywords", total=None)

            # Call the real scraping method
            tweets = self._scrape_tweets_real(keywords, episode_id)

            progress.update(task, completed=100)

        # If no tweets returned from subprocess, try to copy from episode file manager
        if not tweets or len(tweets) == 0:
            project_root = Path(__file__).parent.parent
            episode_pattern = f"*{episode_id}*"
            episode_dirs = list(project_root.glob(f"episodes/{episode_pattern}"))

            if episode_dirs:
                # Use the most recent episode directory
                latest_episode_dir = max(episode_dirs, key=lambda p: p.stat().st_mtime)
                source_file = latest_episode_dir / "outputs" / "tweets.json"

                if source_file.exists():
                    with open(source_file) as f:
                        tweets = json.load(f)
                    console.print(f"[dim]Copied {len(tweets)} tweets from {source_file}[/dim]")

        # Save tweets to episode directory
        tweets_file = episode_dir / "tweets.json"
        with open(tweets_file, 'w') as f:
            json.dump(tweets, f, indent=2)

        console.print(f"[green]✓[/green] Scraped {len(tweets)} tweets")
        console.print(f"[dim]Saved tweets to {tweets_file}[/dim]")

        return {
            'tweets_scraped': len(tweets),
            'keywords_used': len(keywords),
            'tweets_file': str(tweets_file)
        }

    def _run_classify_stage(self, episode_id: str) -> Dict:
        """Execute classification stage."""
        if not episode_id:
            raise ValueError("Episode ID required for classification stage")
        
        # Load tweets from episode directory or database
        tweets = self._load_tweets_for_episode(episode_id)
        if not tweets:
            console.print("[yellow]No tweets found for classification[/yellow]")
            return {'tweets_classified': 0, 'relevant_count': 0}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Classifying {len(tweets)} tweets", total=None)
            
            classified = self.classifier.classify(tweets, episode_id)
            
            progress.update(task, completed=100)
        
        # Filter relevant tweets
        relevant_tweets = [t for t in classified if t.get('classification') == 'RELEVANT']
        
        # Save classified tweets to episode directory
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            classified_file = episode_dir / "classified.json"
            with open(classified_file, 'w') as f:
                json.dump(classified, f, indent=2)
            console.print(f"[dim]Saved classified tweets to {classified_file}[/dim]")
            
            # Debug: Show some sample classifications
            if logger.isEnabledFor(logging.DEBUG):
                console.print("\n[dim]Sample Classifications (first 5):[/dim]")
                for i, tweet in enumerate(classified[:5], 1):
                    text_preview = tweet.get('text', '')[:80] + "..."
                    score = tweet.get('relevance_score', 0)
                    classification = tweet.get('classification', 'UNKNOWN')
                    reason = tweet.get('classification_reason', 'No reason')
                    console.print(f"  {i}. [{classification}] (score: {score:.2f})")
                    console.print(f"     Text: {text_preview}")
                    console.print(f"     Reason: {reason[:100]}...")
        
        result = {
            'tweets_classified': len(classified),
            'relevant_count': len(relevant_tweets),
            'skip_count': len(classified) - len(relevant_tweets),
            'relevant_percentage': round(len(relevant_tweets) / len(classified) * 100, 1) if classified else 0
        }
        
        console.print(f"[green]✓[/green] Classified {len(classified)} tweets, {len(relevant_tweets)} relevant")
        
        return result
    
    def _run_respond_stage(self, episode_id: str) -> Dict:
        """Execute response generation stage."""
        if not episode_id:
            raise ValueError("Episode ID required for response stage")
        
        # Load relevant tweets from previous stage
        relevant_tweets = self._load_relevant_tweets_for_episode(episode_id)
        if not relevant_tweets:
            console.print("[yellow]No relevant tweets found for response generation[/yellow]")
            return {'responses_generated': 0}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Generating responses for {len(relevant_tweets)} tweets", total=None)
            
            responses = self.responder.generate_responses(relevant_tweets, episode_id)  # Process all relevant tweets
            
            progress.update(task, completed=100)
        
        console.print(f"[green]✓[/green] Generated {len(responses)} responses")
        
        # Debug: Show sample responses
        if logger.isEnabledFor(logging.DEBUG) and responses:
            console.print("\n[dim]Sample Responses (first 3):[/dim]")
            for i, tweet in enumerate(responses[:3], 1):
                text_preview = tweet.get('text', '')[:60] + "..."
                response = tweet.get('response', 'No response')
                length = tweet.get('response_length', 0)
                console.print(f"  {i}. Tweet: {text_preview}")
                console.print(f"     Response ({length} chars): {response}")
                console.print()
        
        return {'responses_generated': len(responses)}
    
    def _run_moderate_stage(self, episode_id: str) -> Dict:
        """Execute moderation stage."""
        if not episode_id:
            raise ValueError("Episode ID required for moderation stage")
        
        # Load pending responses
        responses = self._load_responses_for_episode(episode_id)
        if not responses:
            console.print("[yellow]No responses found for moderation[/yellow]")
            return {'responses_moderated': 0, 'approved': 0}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Moderating {len(responses)} responses", total=None)
            
            moderated = self.moderator.moderate_responses(responses, episode_id)
            
            progress.update(task, completed=100)
        
        # Get quality report
        quality_report = self.moderator.get_quality_report(moderated)
        console.print(f"[green]✓[/green] Moderated {len(moderated)} responses")
        self._display_quality_report(quality_report)
        
        return quality_report
    
    def _load_tweets_for_episode(self, episode_id: str) -> List[Dict]:
        """Load tweets for classification."""
        # Try episode directory first
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            tweets_file = episode_dir / "tweets.json"
            if tweets_file.exists():
                with open(tweets_file) as f:
                    return json.load(f)
        
        # Try database integration if in web mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            try:
                import sys
                project_root = Path(__file__).parent.parent
                sys.path.insert(0, str(project_root))
                
                from web.scripts.web_bridge import get_bridge
                bridge = get_bridge()
                tweets = bridge.get_unclassified_tweets(int(episode_id))
                # Convert database format to pipeline format
                return [{
                    'id': str(tweet['id']),
                    'text': tweet['full_text'],
                    'user': tweet['author_handle'],
                    'created_at': tweet.get('created_at', ''),
                    'twitter_id': tweet['twitter_id']
                } for tweet in tweets]
            except Exception as e:
                logger.debug(f"Failed to load tweets from database: {e}")
        
        # Fallback to mock tweets
        return self._scrape_tweets([], episode_id)
    
    def _load_relevant_tweets_for_episode(self, episode_id: str) -> List[Dict]:
        """Load relevant tweets for response generation."""
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            classified_file = episode_dir / "classified.json"
            if classified_file.exists():
                with open(classified_file) as f:
                    classified = json.load(f)
                    return [t for t in classified if t.get('classification') == 'RELEVANT']
        
        # Try database integration if in web mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            try:
                import sys
                project_root = Path(__file__).parent.parent
                sys.path.insert(0, str(project_root))
                
                from web.scripts.web_bridge import get_bridge
                bridge = get_bridge()
                # This would need to be implemented in web_bridge
                # For now, return empty list - could load relevant tweets from database
                pass
            except Exception as e:
                logger.debug(f"Failed to load relevant tweets from database: {e}")
        
        return []
    
    def _load_responses_for_episode(self, episode_id: str) -> List[Dict]:
        """Load responses for moderation."""
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            responses_file = episode_dir / "responses.json"
            if responses_file.exists():
                with open(responses_file) as f:
                    return json.load(f)
        
        return []
    
    def _scrape_tweets(self, keywords: List[str], episode_id: str, tweets_file: str = None) -> List[Dict]:
        """Scrape tweets using the real Twitter API via scrape.py module or load from file."""
        # Check if a specific tweets file was provided (legacy compatibility)
        if tweets_file:
            tweets_path = Path(tweets_file)
            if tweets_path.exists():
                console.print(f"[cyan]Loading tweets from {tweets_path}[/cyan]")
                with open(tweets_path) as f:
                    tweets = json.load(f)
                    console.print(f"[green]Loaded {len(tweets)} tweets from {tweets_path.name}[/green]")
                    return tweets
            else:
                console.print(f"[red]ERROR: Tweets file not found: {tweets_path}[/red]")
                return []

        # Check if real Twitter scraping is enabled and configured
        if self._is_real_scraping_enabled():
            console.print("[bold blue]Real Twitter scraping enabled - using scrape.py module[/bold blue]")
            return self._scrape_tweets_real(keywords, episode_id)

        # Fall back to file-based loading
        console.print("[yellow]Real scraping disabled - falling back to file-based tweets[/yellow]")

        # Try episode directory first
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            tweets_file = episode_dir / "tweets.json"
            if tweets_file.exists():
                console.print(f"[cyan]Loading tweets from episode: {tweets_file}[/cyan]")
                with open(tweets_file) as f:
                    tweets = json.load(f)
                    console.print(f"[green]Loaded {len(tweets)} tweets from episode[/green]")
                    return tweets

        # Try to load from transcripts/tweets.json (default test data)
        transcripts_tweets = project_root / "transcripts" / "tweets.json"
        if transcripts_tweets.exists():
            console.print(f"[cyan]Loading tweets from transcripts/tweets.json[/cyan]")
            with open(transcripts_tweets) as f:
                tweets = json.load(f)
                console.print(f"[green]Loaded {len(tweets)} tweets from transcripts[/green]")
                return tweets

        # No tweets found
        console.print("[red]ERROR: No tweets file found![/red]")
        console.print("[yellow]To enable real scraping: Set API keys and WDF_NO_AUTO_SCRAPE=false[/yellow]")
        console.print("[yellow]To generate sample tweets for testing, run: python scripts/generate_sample_tweets.py[/yellow]")

        return []

    def _scrape_tweets_real(self, keywords: List[str], episode_id: str) -> List[Dict]:
        """Scrape tweets using the real scrape.py module via subprocess."""
        try:
            # Get episode directory and save keywords
            episode_dir = self.episode_mgr.get_episode_dir(episode_id)
            if not episode_dir:
                logger.error(f"Episode directory not found for episode {episode_id}")
                return []

            # Save keywords for the scrape module
            keywords_file = episode_dir / "keywords.json"
            keyword_dicts = [{"keyword": kw, "weight": 1.0} for kw in keywords]
            with open(keywords_file, 'w') as f:
                json.dump(keyword_dicts, f, indent=2)

            console.print(f"[dim]Saved {len(keywords)} keywords to {keywords_file}[/dim]")

            # Build command to run scrape.py
            python_cmd = sys.executable
            cmd = [
                python_cmd, '-m', 'src.wdf.tasks.scrape',
                '--episode-id', episode_id,
                '--manual-trigger',  # Enable API calls
                '--count', '100'     # Default count
            ]

            # Set up environment for subprocess - include all necessary credentials
            env = os.environ.copy()

            # Get project root for PYTHONPATH
            project_root = Path(__file__).parent.parent

            # Core WDF configuration
            env.update({
                'WDF_WEB_MODE': 'true',
                'WDF_EPISODE_ID': episode_id,
                'WDF_NO_AUTO_SCRAPE': 'false',  # Allow scraping in subprocess
                'PYTHONPATH': str(project_root),
                'PYTHONUNBUFFERED': '1'  # For real-time output
            })

            # Twitter API credentials - pass through all possible variants
            twitter_env_vars = [
                'API_KEY', 'CLIENT_ID', 'TWITTER_API_KEY',
                'API_KEY_SECRET', 'CLIENT_SECRET', 'TWITTER_API_SECRET',
                'ACCESS_TOKEN', 'TWITTER_TOKEN', 'TWITTER_ACCESS_TOKEN',
                'TWITTER_ACCESS_TOKEN_SECRET', 'TWITTER_BEARER_TOKEN',
                'WDFWATCH_ACCESS_TOKEN'  # Most important for OAuth 2.0
            ]

            missing_credentials = []
            for var in twitter_env_vars:
                if var in os.environ:
                    env[var] = os.environ[var]
                elif var == 'WDFWATCH_ACCESS_TOKEN':
                    # This is the critical OAuth token
                    missing_credentials.append(var)

            # Database connection for web_bridge integration
            if 'DATABASE_URL' in os.environ:
                env['DATABASE_URL'] = os.environ['DATABASE_URL']

            # Additional optional variables for configuration
            optional_vars = ['WDF_BYPASS_QUOTA_CHECK', 'WDF_GENERATE_SAMPLES', 'REDIS_URL']
            for var in optional_vars:
                if var in os.environ:
                    env[var] = os.environ[var]

            # Log credential status
            if missing_credentials:
                console.print(f"[yellow]Warning: Missing critical credentials: {missing_credentials}[/yellow]")
                logger.warning(f"Missing Twitter credentials: {missing_credentials}")

            # Check for essential credentials
            has_wdfwatch = 'WDFWATCH_ACCESS_TOKEN' in env
            has_basic_api = 'API_KEY' in env and 'API_KEY_SECRET' in env

            if not (has_wdfwatch or has_basic_api):
                console.print("[red]Error: No valid Twitter API credentials found[/red]")
                console.print("[red]Need either WDFWATCH_ACCESS_TOKEN or API_KEY+API_KEY_SECRET[/red]")
                return []

            console.print(f"[dim]Running scraping command: {' '.join(cmd)}[/dim]")
            if has_wdfwatch:
                console.print("[dim]✓ Using WDFWATCH_ACCESS_TOKEN (OAuth 2.0)[/dim]")
            elif has_basic_api:
                console.print("[dim]✓ Using API_KEY+API_KEY_SECRET[/dim]")

            # Run the scraping task with timeout
            result = subprocess.run(
                cmd,
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                console.print(f"[green]Scraping completed successfully[/green]")
                logger.info(f"Scraping subprocess completed. Output length: {len(result.stdout)} chars")

                # Log any important output from the scrape process
                if result.stdout:
                    # Look for key information in stdout
                    stdout_lines = result.stdout.strip().split('\n')
                    for line in stdout_lines[-10:]:  # Last 10 lines
                        if any(keyword in line.lower() for keyword in ['scraped', 'found', 'saved', 'error', 'warning']):
                            console.print(f"[dim]Scrape: {line.strip()}[/dim]")

                # Find and copy tweets from episode file manager location to expected location
                project_root = Path(__file__).parent.parent
                episode_pattern = f"*{episode_id}*"
                episode_dirs = list(project_root.glob(f"episodes/{episode_pattern}"))

                tweets_found = []
                source_file = None

                if episode_dirs:
                    # Use the most recent episode directory
                    latest_episode_dir = max(episode_dirs, key=lambda p: p.stat().st_mtime)
                    source_file = latest_episode_dir / "outputs" / "tweets.json"

                    if source_file.exists():
                        with open(source_file) as f:
                            tweets_found = json.load(f)
                        console.print(f"[dim]Found {len(tweets_found)} tweets in {source_file}[/dim]")

                        # Copy tweets to orchestrator's expected location
                        target_file = episode_dir / "tweets.json"
                        with open(target_file, 'w') as f:
                            json.dump(tweets_found, f, indent=2)
                        console.print(f"[green]Copied tweets to {target_file}[/green]")
                    else:
                        console.print(f"[yellow]Warning: No tweets file found at {source_file}[/yellow]")

                if tweets_found:
                    console.print(f"[green]Loaded {len(tweets_found)} scraped tweets[/green]")
                    return tweets_found
                else:
                    console.print("[yellow]Warning: No tweets were scraped or found[/yellow]")
                    console.print("[yellow]Scraping may have failed or returned no results[/yellow]")
                    return []
            else:
                console.print(f"[red]Scraping failed with return code {result.returncode}[/red]")

                # Enhanced error reporting
                if result.stderr:
                    stderr_lines = result.stderr.strip().split('\n')
                    console.print(f"[red]Error details:[/red]")
                    for line in stderr_lines[:5]:  # First 5 lines of error
                        if line.strip():
                            console.print(f"[red]  {line.strip()}[/red]")

                if result.stdout:
                    # Check if there are helpful messages in stdout
                    stdout_lines = result.stdout.strip().split('\n')
                    for line in stdout_lines:
                        if any(keyword in line.lower() for keyword in ['error', 'failed', 'quota', 'rate limit']):
                            console.print(f"[red]  {line.strip()}[/red]")

                logger.error(
                    f"Scraping subprocess failed with return code {result.returncode}. "
                    f"Episode: {episode_id}, Keywords: {len(keywords)}. "
                    f"STDERR: {result.stderr[:1000] if result.stderr else 'None'}. "
                    f"STDOUT: {result.stdout[:1000] if result.stdout else 'None'}"
                )
                return []

        except subprocess.TimeoutExpired:
            console.print("[red]Scraping timed out after 5 minutes[/red]")
            console.print("[red]This may indicate API rate limiting or network issues[/red]")
            logger.error(f"Scraping subprocess timed out after 300 seconds for episode {episode_id}")
            return []
        except FileNotFoundError as e:
            console.print(f"[red]Scraping module not found: {e}[/red]")
            console.print("[red]Ensure src.wdf.tasks.scrape is available in PYTHONPATH[/red]")
            logger.error(f"Scraping module not found: {e}", exc_info=True)
            return []
        except Exception as e:
            console.print(f"[red]Scraping failed: {e}[/red]")
            logger.error(f"Scraping subprocess error for episode {episode_id}: {e}", exc_info=True)
            return []

    def _load_cached_tweets(self, episode_id: str) -> List[Dict]:
        """Load cached tweets from episode directory."""
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        if episode_dir:
            tweets_file = episode_dir / "tweets.json"
            if tweets_file.exists():
                with open(tweets_file) as f:
                    return json.load(f)
        
        # Fall back to mock tweets
        return self._scrape_tweets([], episode_id)
    
    def _sync_tweets_to_database(self, tweets: List[Dict], episode_id: str):
        """Sync loaded tweets to database if web bridge is available."""
        try:
            import sys
            project_root = Path(__file__).parent.parent
            sys.path.insert(0, str(project_root / "web" / "scripts"))
            
            from web_bridge import WebUIBridge
            bridge = WebUIBridge()
            
            # First need to ensure tweets are associated with the episode
            # Get the episode's database ID
            episode_dir = self.episode_mgr.get_episode_dir(episode_id)
            
            with bridge.connection.cursor() as cursor:
                # Find the episode in database
                cursor.execute("""
                    SELECT id FROM podcast_episodes 
                    WHERE claude_episode_dir = %s OR episode_dir = %s
                """, (episode_id, episode_id))
                result = cursor.fetchone()
                
                if result:
                    db_episode_id = result[0]
                    
                    # Insert tweets if they don't exist
                    for tweet in tweets:
                        cursor.execute("""
                            INSERT INTO tweets (
                                twitter_id, author_handle, full_text, text_preview,
                                created_at, updated_at, status, episode_id
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (twitter_id) 
                            DO UPDATE SET 
                                episode_id = EXCLUDED.episode_id,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            tweet.get('id', tweet.get('twitter_id')),
                            tweet.get('user', '@unknown'),
                            tweet.get('text', ''),
                            tweet.get('text', '')[:280],
                            tweet.get('created_at', datetime.now()),
                            datetime.now(),  # updated_at
                            'unclassified',
                            db_episode_id
                        ))
                    
                    bridge.connection.commit()
                    logger.info(f"Synced {len(tweets)} tweets to database for episode {episode_id} (DB ID: {db_episode_id})")
                    console.print(f"[dim]Synced {len(tweets)} tweets to database[/dim]")
                else:
                    logger.warning(f"Episode {episode_id} not found in database - cannot sync tweets")
            
            bridge.close()
            
        except ImportError:
            logger.debug("WebUIBridge not available - running in file-only mode")
        except Exception as e:
            logger.warning(f"Failed to sync tweets to database: {e}")
            # Continue anyway - don't fail the pipeline
    
    def _get_default_overview(self) -> str:
        """Get default podcast overview."""
        return """The War, Divorce, or Federalism podcast explores America's political future 
        in the context of growing division. Host Rick Becker examines whether the nation 
        will face civil conflict, undergo peaceful separation, or embrace true federalism 
        as a solution to preserve both liberty and unity."""
    
    def _display_summary_stats(self, summary_result: Dict):
        """Display summary statistics."""
        table = Table(title="Summary Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Episode ID", summary_result['episode_id'])
        table.add_row("Keywords", str(len(summary_result.get('keywords', []))))
        table.add_row("Context File", "CLAUDE.md created")
        table.add_row("Video URL", "✓" if summary_result.get('video_url') else "✗")
        
        console.print(table)
    
    def _display_classification_stats(self, stats: Dict):
        """Display classification statistics."""
        table = Table(title="Classification Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Tweets", str(stats['total_tweets']))
        table.add_row("Relevant", f"{stats['relevant']} ({stats['relevant_percentage']}%)")
        table.add_row("Skip", str(stats['skip']))
        table.add_row("Method", "Claude Direct (No Few-Shots)")
        
        console.print(table)
    
    def _display_quality_report(self, report: Dict):
        """Display quality moderation report."""
        table = Table(title="Quality Moderation Report")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Responses", str(report['total']))
        table.add_row("Approved", str(report['approved']))
        table.add_row("Rejected", str(report['rejected']))
        table.add_row("Approval Rate", f"{report['approval_rate']}%")
        
        if report.get('average_scores'):
            for score_type, value in report['average_scores'].items():
                table.add_row(f"Avg {score_type.title()}", f"{value:.1f}/10")
        
        console.print(table)
    
    def _display_final_report(self, results: Dict):
        """Display final pipeline report."""
        console.print("\n" + "="*60)
        console.print("[bold green]PIPELINE COMPLETE[/bold green]")
        console.print("="*60)
        
        table = Table(title="Final Report")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        stats = results['stats']
        table.add_row("Episode ID", results['episode_id'])
        table.add_row("Episode Directory", results.get('episode_dir', 'N/A'))
        table.add_row("Total Time", f"{stats['total_time_minutes']} minutes")
        table.add_row("Tweets Processed", str(stats['tweets_processed']))
        table.add_row("Responses Generated", str(stats['responses_generated']))
        table.add_row("Responses Approved", str(stats['responses_approved']))
        table.add_row("Final Approval Rate", f"{stats['approval_rate']}%")
        
        console.print(table)
    
    def _display_cost_report(self, report: Dict):
        """Display cost report."""
        if not report:
            return
        
        table = Table(title="API Cost Report")
        table.add_column("Mode", style="cyan")
        table.add_column("Cost", style="yellow")
        
        for mode, cost in report.get('by_mode', {}).items():
            table.add_row(mode.title(), f"${cost:.2f}")
        
        table.add_row("Total", f"${report.get('total_cost', 0):.2f}", style="bold")
        
        console.print(table)

    def _load_stage_configuration(self) -> Dict:
        """
        Load pipeline stage configuration from environment variables.
        Falls back to defaults if no configuration is found.
        """
        default_config = {
            'summarization': {'enabled': True, 'required': False},  # Can run independently
            'fewshot': {'enabled': False, 'required': False},  # Not needed for Claude pipeline
            'scraping': {'enabled': True, 'required': False},  # Can be skipped if using cached tweets
            'classification': {'enabled': True, 'required': False},  # Can be run independently
            'response': {'enabled': True, 'required': False},
            'moderation': {'enabled': False, 'required': False}  # Optional quality check
        }
        
        # Check environment variables for stage overrides
        stage_config = default_config.copy()
        for stage in stage_config.keys():
            env_var = f"WDF_STAGE_{stage.upper()}_ENABLED"
            if env_var in os.environ:
                enabled = os.environ[env_var].lower() == 'true'
                stage_config[stage]['enabled'] = enabled
                logger.debug(f"Stage {stage} enabled from environment: {enabled}")
        
        return stage_config

    def _display_stage_configuration(self):
        """Display current stage configuration."""
        table = Table(title="Pipeline Stage Configuration")
        table.add_column("Stage", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Required", style="dim")
        
        for stage, config in self.stage_config.items():
            status = "[green]Enabled[/green]" if config['enabled'] else "[red]Disabled[/red]"
            required = "Yes" if config['required'] else "No"
            stage_name = stage.replace('_', ' ').title()
            table.add_row(stage_name, status, required)
        
        console.print(table)

    def _is_stage_enabled(self, stage_name: str) -> bool:
        """Check if a pipeline stage is enabled."""
        return self.stage_config.get(stage_name, {}).get('enabled', True)

    def _is_real_scraping_enabled(self) -> bool:
        """Check if real Twitter scraping is enabled and properly configured."""
        # Check for API keys (WDFwatch tokens preferred)
        has_api_keys = bool(
            os.getenv("WDFWATCH_ACCESS_TOKEN") or
            os.getenv("API_KEY") or
            os.getenv("CLIENT_ID")
        )

        # Check if scraping stage is enabled
        scraping_enabled = self._is_stage_enabled('scraping')

        # Check safety flag (WDF_NO_AUTO_SCRAPE should be false to allow scraping)
        auto_scrape_allowed = os.getenv("WDF_NO_AUTO_SCRAPE", "false").lower() != "true"

        # Log the configuration status
        logger.info(
            f"Scraping configuration check: has_api_keys={has_api_keys}, "
            f"scraping_enabled={scraping_enabled}, auto_scrape_allowed={auto_scrape_allowed}, "
            f"can_scrape={has_api_keys and scraping_enabled and auto_scrape_allowed}"
        )

        return has_api_keys and scraping_enabled and auto_scrape_allowed

    def _validate_stage_configuration(self) -> Dict:
        """
        Validate stage configuration for dependencies and required stages.
        
        Returns:
            Dict with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        # Check required stages
        for stage, config in self.stage_config.items():
            if config.get('required', False) and not config.get('enabled', True):
                errors.append(f"Required stage '{stage}' cannot be disabled")
        
        # Check stage dependencies
        if self._is_stage_enabled('response') and not self._is_stage_enabled('classification'):
            warnings.append("Response generation is enabled but classification is disabled. This may result in responses to irrelevant tweets.")
        
        if self._is_stage_enabled('moderation') and not self._is_stage_enabled('response'):
            errors.append("Moderation requires response generation to be enabled.")
        
        if self._is_stage_enabled('classification') and not self._is_stage_enabled('scraping'):
            warnings.append("Classification is enabled but scraping is disabled. No tweets will be available to classify.")
        
        if self._is_stage_enabled('response') and not self._is_stage_enabled('scraping'):
            warnings.append("Response generation is enabled but scraping is disabled. No tweets will be available for responses.")
        
        return {'errors': errors, 'warnings': warnings}

    def _display_stage_validation(self, validation: Dict):
        """Display stage validation results."""
        if validation['errors']:
            console.print("[bold red]Stage Configuration Errors:[/bold red]")
            for error in validation['errors']:
                console.print(f"  [red]✗[/red] {error}")
            console.print("[red]Pipeline cannot run with configuration errors![/red]")
            
        if validation['warnings']:
            console.print("[bold yellow]Stage Configuration Warnings:[/bold yellow]")
            for warning in validation['warnings']:
                console.print(f"  [yellow]⚠[/yellow] {warning}")
        
        if not validation['errors'] and not validation['warnings']:
            console.print("[green]✓[/green] Stage configuration is valid")


def main():
    """Main entry point for the orchestrator."""
    import argparse
    import os
    import subprocess
    import threading
    import time

    # Heartbeat logger to track if process is alive
    def heartbeat():
        counter = 0
        while True:
            counter += 1
            print(f"[ORCHESTRATOR HEARTBEAT] Still alive - {counter * 5}s elapsed", flush=True)
            time.sleep(5)

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    print(f"[ORCHESTRATOR] Started at {time.time()}", flush=True)

    # Debug: Check PATH when started
    print(f"[ORCHESTRATOR] PATH at startup: {os.environ.get('PATH', 'NOT SET')}", flush=True)
    try:
        which_result = subprocess.run(['which', 'claude'], capture_output=True, text=True, timeout=2)
        print(f"[ORCHESTRATOR] which claude: {which_result.stdout.strip()}", flush=True)
    except:
        print("[ORCHESTRATOR] Could not find claude in PATH", flush=True)

    parser = argparse.ArgumentParser(
        description="Run the unified Claude pipeline for WDFWatch"
    )
    
    parser.add_argument(
        '--transcript', '-t',
        default="transcripts/latest.txt",
        help="Path to transcript file"
    )
    parser.add_argument(
        '--episode-id', '-e',
        help="Episode identifier"
    )
    parser.add_argument(
        '--video-url', '-v',
        help="YouTube video URL"
    )
    parser.add_argument(
        '--skip-scraping',
        action='store_true',
        help="Skip tweet scraping, use cached"
    )
    parser.add_argument(
        '--skip-moderation',
        action='store_true',
        help="Skip human moderation"
    )
    parser.add_argument(
        '--stage', '-s',
        choices=['summarize', 'classify', 'respond', 'moderate', 'full'],
        help="Run a specific pipeline stage (deprecated, use --stages)"
    )
    parser.add_argument(
        '--stages',
        help="Comma-separated list of stages to run (e.g., 'summarize,classify,respond'). Options: summarize, classify, respond, moderate, or 'all' for full pipeline"
    )
    parser.add_argument(
        '--tweets',
        help="Path to tweets JSON file to use for classification (defaults to transcripts/tweets.json)"
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help="Enable debug output to see detailed classifications and responses"
    )
    
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Handle stage configuration
    stages_to_run = []
    
    # Check for --stages (new flexible approach)
    if args.stages:
        if args.stages.lower() == 'all':
            stages_to_run = ['summarize', 'classify', 'respond', 'moderate']
        else:
            stages_to_run = [s.strip().lower() for s in args.stages.split(',')]
    # Backward compatibility with --stage
    elif args.stage:
        if args.stage == 'full':
            stages_to_run = ['summarize', 'classify', 'respond']  # Note: moderate not included by default
        else:
            stages_to_run = [args.stage]
    # Default: run main stages except moderation
    else:
        stages_to_run = ['summarize', 'classify', 'respond']
    
    # Configure stages based on what should run
    stage_mappings = {
        'summarize': 'summarization',
        'scraping': 'scraping',
        'classify': 'classification',
        'respond': 'response',
        'moderate': 'moderation'
    }
    
    # Set environment variables for all stages
    for stage_key in ['summarization', 'fewshot', 'scraping', 'classification', 'response', 'moderation']:
        env_var = f"WDF_STAGE_{stage_key.upper()}_ENABLED"
        
        # Check if this stage should be enabled
        should_enable = False
        
        # Direct stage mapping
        for stage in stages_to_run:
            if stage_key == stage_mappings.get(stage):
                should_enable = True
                break
        
        # Handle dependencies
        # Scraping is needed for classification and response
        if stage_key == 'scraping' and ('classify' in stages_to_run or 'respond' in stages_to_run):
            should_enable = True
        
        # Classification is needed for response  
        if stage_key == 'classification' and 'respond' in stages_to_run:
            should_enable = True
        
        os.environ[env_var] = 'true' if should_enable else 'false'
    
    # Initialize pipeline
    pipeline = UnifiedClaudePipeline()
    
    # If episode is specified, use its transcript instead of default
    transcript_path = args.transcript
    if args.episode_id:
        # Check if episode directory exists and has a transcript
        episode_dir = Path("episodes") / args.episode_id
        episode_transcript = episode_dir / "transcript.txt"
        if episode_transcript.exists():
            transcript_path = str(episode_transcript)
            console.print(f"[cyan]Using transcript from episode: {transcript_path}[/cyan]")
        else:
            console.print(f"[yellow]Warning: No transcript found in {episode_dir}, using default: {transcript_path}[/yellow]")
    
    # Run pipeline based on selected stages
    print(f"[ORCHESTRATOR] About to run pipeline stages: {stages_to_run}", flush=True)
    print(f"[ORCHESTRATOR] Execution starting at {time.time()}", flush=True)

    # If multiple stages or full pipeline, use run_episode
    if len(stages_to_run) > 1 or (args.stage == 'full' and not args.stages):
        print(f"[ORCHESTRATOR] Running multiple stages via run_episode", flush=True)
        results = pipeline.run_episode(
            transcript_path=transcript_path,
            episode_id=args.episode_id,
            video_url=args.video_url,
            skip_scraping=args.skip_scraping,
            skip_moderation=args.skip_moderation or 'moderate' not in stages_to_run,
            tweets_file=args.tweets
        )
    # If single stage, use run_individual_stage for compatibility
    elif len(stages_to_run) == 1:
        print(f"[ORCHESTRATOR] Running single stage: {stages_to_run[0]}", flush=True)
        results = pipeline.run_individual_stage(
            stage=stages_to_run[0],
            transcript_path=transcript_path,
            episode_id=args.episode_id,
            video_url=args.video_url
        )
    else:
        console.print("[red]Error: No stages specified to run[/red]")
        return

    print(f"[ORCHESTRATOR] Pipeline execution completed at {time.time()}", flush=True)
    
    # Save results to episode directory (not pipeline root)
    if 'episode_dir' in results:
        episode_dir = Path(results['episode_dir'])
        results_file = episode_dir / "pipeline_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]Results saved to {results_file}[/green]")
    else:
        # Fallback to pipeline root for non-episode operations
        results_file = Path(f"pipeline_results_{results.get('episode_id', 'unknown')}.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]Results saved to {results_file}[/green]")


if __name__ == "__main__":
    main()