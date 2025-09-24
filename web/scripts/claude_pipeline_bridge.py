#!/usr/bin/env python3
"""
Claude Pipeline Bridge - Integrates the unified claude-pipeline with the web dashboard.
This module handles:
- Episode directory management
- Claude pipeline orchestration via orchestrator.py subprocess calls
- Context file synchronization
- Cost tracking and metrics
"""

import sys
import os
import json
import subprocess
import logging
import argparse
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime
from decimal import Decimal

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.scripts.web_bridge import WebUIBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudePipelineBridge(WebUIBridge):
    """
    Bridge between unified Claude pipeline and web dashboard.
    Uses subprocess calls to orchestrator.py instead of direct imports.
    """
    
    def __init__(self, episode_id: int = None):
        """Initialize the Claude pipeline bridge."""
        super().__init__()
        self.episode_id = episode_id
        
        # Set up paths
        self.project_root = Path(__file__).parent.parent.parent
        self.orchestrator_path = self.project_root / "claude-pipeline" / "orchestrator.py"
        # Claude pipeline uses its own episodes directory
        self.episodes_dir = self.project_root / "claude-pipeline" / "episodes"
        
        # Ensure directories exist
        self.episodes_dir.mkdir(exist_ok=True, parents=True)
        
        # Load configuration from database
        self.load_llm_configuration()
        self.load_stage_configuration()
        
        logger.info(f"Claude Pipeline Bridge initialized for episode {episode_id}")
        logger.info(f"Orchestrator path: {self.orchestrator_path}")
        logger.info(f"Episodes directory: {self.episodes_dir}")
    
    def load_llm_configuration(self):
        """Load user-defined LLM model configuration from database."""
        try:
            # Query database for LLM model settings
            settings_query = "SELECT value FROM settings WHERE key = %s"
            result = None
            
            if hasattr(self, 'connection') and self.connection:
                from psycopg2.extras import RealDictCursor
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(settings_query, ('llm_models',))
                    result = cursor.fetchone()
            
            if result and result.get('value'):
                llm_config = result['value']
                logger.info(f"Loaded LLM configuration from database: {llm_config}")
                
                # Set environment variables for orchestrator
                for task, model in llm_config.items():
                    env_var = f"WDF_LLM_MODEL_{task.upper()}"
                    os.environ[env_var] = model
                    logger.debug(f"Set {env_var} = {model}")
                
                # Also set WDF_WEB_MODE to ensure database-first configuration
                os.environ['WDF_WEB_MODE'] = 'true'
                
            else:
                logger.info("No LLM configuration found in database, using defaults")
                
        except Exception as e:
            logger.warning(f"Failed to load LLM configuration from database: {e}")
            logger.info("Falling back to environment variables or defaults")
    
    def load_stage_configuration(self):
        """Load pipeline stage enable/disable configuration from database."""
        try:
            # Query database for stage configuration
            settings_query = "SELECT value FROM settings WHERE key = %s"
            result = None
            
            if hasattr(self, 'connection') and self.connection:
                from psycopg2.extras import RealDictCursor
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(settings_query, ('pipeline_stages',))
                    result = cursor.fetchone()
            
            if result and result.get('value'):
                stage_config = result['value']
                logger.info(f"Loaded stage configuration from database: {stage_config}")
                
                # Set environment variables for orchestrator stage checking
                for stage, config in stage_config.items():
                    if isinstance(config, dict) and 'enabled' in config:
                        env_var = f"WDF_STAGE_{stage.upper()}_ENABLED"
                        os.environ[env_var] = 'true' if config['enabled'] else 'false'
                        logger.debug(f"Set {env_var} = {config['enabled']}")
                
                # Store stage config for local use
                self.stage_config = stage_config
                
            else:
                logger.info("No stage configuration found in database, using defaults")
                # Use default stage configuration for Claude pipeline
                self.stage_config = {
                    'summarization': {'enabled': True, 'required': True},
                    'scraping': {'enabled': True, 'required': False},
                    'classification': {'enabled': True, 'required': True},
                    'response': {'enabled': True, 'required': False},
                    'moderation': {'enabled': False, 'required': False}
                }
                
        except Exception as e:
            logger.warning(f"Failed to load stage configuration from database: {e}")
            logger.info("Using default stage configuration")
            self.stage_config = {
                'summarization': {'enabled': True, 'required': True},
                'scraping': {'enabled': True, 'required': False},
                'classification': {'enabled': True, 'required': True},
                'response': {'enabled': True, 'required': False},
                'moderation': {'enabled': False, 'required': False}
            }

    def get_episode_info(self, episode_id: int) -> Dict[str, Any]:
        """Get episode information from database."""
        try:
            if hasattr(self, 'connection') and self.connection:
                from psycopg2.extras import RealDictCursor
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, title, claude_episode_dir, video_url
                        FROM podcast_episodes 
                        WHERE id = %s
                    """, (episode_id,))
                    return cursor.fetchone()
        except Exception as e:
            logger.error(f"Failed to get episode info: {e}")
            return None

    def fix_episode_permissions(self, episode_dir: str):
        """Fix permissions for episode directory before orchestrator execution."""
        try:
            episode_path = self.episodes_dir / episode_dir
            logger.info(f"Fixing permissions for episode directory: {episode_path}")

            # Fix permissions using the container-based approach
            import subprocess

            # Use the approach that works from the container
            permission_commands = [
                ['chown', '-R', 'debian:nodejs', str(episode_path)],
                ['chmod', '-R', 'g+w', str(episode_path)]
            ]

            for cmd in permission_commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        logger.warning(f"Permission command failed (non-critical): {' '.join(cmd)} - {result.stderr}")
                except Exception as e:
                    logger.warning(f"Permission fix failed (non-critical): {e}")

            logger.info(f"Permission fix completed for {episode_path}")

        except Exception as e:
            logger.warning(f"Could not fix permissions for {episode_dir} (non-critical): {e}")

    def run_orchestrator(self, stage: str = 'full', episode_id: str = None, force: bool = False) -> Dict[str, Any]:
        """
        Run the unified pipeline orchestrator for a specific stage.

        Args:
            stage: Stage to run ('summarize', 'classify', 'respond', 'moderate', 'full')
            episode_id: Episode identifier
            force: Force reprocessing even if outputs exist

        Returns:
            Dict with orchestrator results and metadata
        """
        try:
            # Check if episode_dir was provided directly (bypasses database)
            if hasattr(self, 'episode_dir_override') and self.episode_dir_override:
                episode_dir = self.episode_dir_override
                transcript_path = self.episodes_dir / episode_dir / "transcript.txt"
                # Try to load video URL from file
                video_url_file = self.episodes_dir / episode_dir / "video_url.txt"
                if video_url_file.exists():
                    video_url = video_url_file.read_text().strip()
                else:
                    video_url = None
                logger.info(f"Using provided episode directory: {episode_dir}")
            # Otherwise try database lookup
            elif self.episode_id:
                episode_info = self.get_episode_info(self.episode_id)
                if not episode_info:
                    # Database lookup failed - we need the episode directory name
                    # The Web UI should have passed it via --episode-dir
                    raise Exception(f"Episode {self.episode_id} not found in database and no --episode-dir provided. Cannot determine episode directory name.")
                else:
                    # Determine episode directory from database
                    episode_dir = episode_info.get('claude_episode_dir')
                    if episode_dir:
                        # Claude pipeline episodes are in claude-pipeline/episodes/
                        transcript_path = self.episodes_dir / episode_dir / "transcript.txt"
                    else:
                        # Fallback to legacy location
                        transcript_path = self.project_root / "transcripts" / "latest.txt"
                    
                    video_url = episode_info.get('video_url')
            else:
                # Fallback to default transcript location
                transcript_path = self.project_root / "transcripts" / "latest.txt"
                video_url = None
            
            # Build orchestrator command - use venv Python if available
            venv_python = self.project_root / "venv" / "bin" / "python3"
            python_executable = str(venv_python) if venv_python.exists() else sys.executable

            cmd = [
                python_executable,
                str(self.orchestrator_path),
                '--transcript', str(transcript_path)
            ]
            
            # Use the episode directory name as the episode identifier
            if episode_dir:
                # The claude_episode_dir from database is like "claudetest5" 
                # Pass it directly as the episode ID to the orchestrator
                cmd.extend(['--episode-id', episode_dir])
            else:
                # If no episode directory, we shouldn't proceed
                raise Exception("Episode directory not found")
            
            if video_url:
                cmd.extend(['--video-url', video_url])
            
            # Add stage-specific arguments (use --stages which works for single or multiple)
            cmd.extend(['--stages', stage])
            
            # Set up environment for orchestrator with fixed PATH for Node.js and Claude CLI
            env = os.environ.copy()

            # Ensure PATH includes Node.js and Claude CLI
            current_path = env.get('PATH', '')
            required_paths = [
                '/usr/bin',  # Node.js is here
                '/usr/local/bin',
                '/bin',
                os.path.expanduser('~/.claude/local'),  # Claude CLI
                '/home/debian/.claude/local',
            ]

            path_parts = current_path.split(':')
            for req_path in required_paths:
                if req_path not in path_parts and os.path.exists(req_path):
                    path_parts.insert(0, req_path)

            env.update({
                'PATH': ':'.join(path_parts),
                'WDF_WEB_MODE': 'true',
                'WDF_EPISODE_ID': str(self.episode_id) if self.episode_id else '',
                'PYTHONPATH': str(self.project_root),
                'NODE_PATH': '/usr/lib/node_modules',
                'CLAUDE_CLI_PATH': '/home/debian/.claude/local/claude',
                'PYTHONUNBUFFERED': '1'
            })
            
            logger.info(f"Running orchestrator command: {' '.join(cmd)}")

            # Run orchestrator with explicit stdin handling
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                env=env,
                stdin=subprocess.DEVNULL,  # Prevent any stdin reading
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("Orchestrator completed successfully")
                
                # Try to parse results if available
                try:
                    # Look for results file
                    results_pattern = f"pipeline_results_*.json"
                    results_files = list(self.project_root.glob(results_pattern))
                    if results_files:
                        latest_results = max(results_files, key=lambda x: x.stat().st_mtime)
                        with open(latest_results, 'r') as f:
                            orchestrator_results = json.load(f)
                    else:
                        orchestrator_results = {}
                except Exception as e:
                    logger.warning(f"Could not parse orchestrator results: {e}")
                    orchestrator_results = {}
                
                return {
                    'success': True,
                    'stage': stage,
                    'episode_id': episode_id,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'results': orchestrator_results
                }
            else:
                logger.error(f"Orchestrator failed with return code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                
                return {
                    'success': False,
                    'stage': stage,
                    'episode_id': episode_id,
                    'error': f"Orchestrator failed with return code {result.returncode}",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Orchestrator timed out after 30 minutes")
            return {
                'success': False,
                'stage': stage,
                'episode_id': episode_id,
                'error': "Orchestrator timed out after 30 minutes"
            }
        except Exception as e:
            logger.error(f"Failed to run orchestrator: {e}")
            return {
                'success': False,
                'stage': stage,
                'episode_id': episode_id,
                'error': str(e)
            }

    def run_stage(self, stage: str, force: bool = False) -> Dict[str, Any]:
        """
        Run a specific pipeline stage.
        
        Args:
            stage: Stage to run ('summarize', 'classify', 'respond', 'moderate', 'full')
            force: Force reprocessing even if outputs exist
            
        Returns:
            Dict with stage results
        """
        logger.info(f"Running Claude pipeline stage: {stage}")
        
        # Update pipeline status in database
        self.emit_sse_event({
            'type': 'pipeline_stage_started',
            'episodeId': str(self.episode_id) if self.episode_id else '0',
            'stage': stage,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get episode info from database to get the episode directory name
        episode_dir_name = None
        if self.episode_id:
            episode_info = self.get_episode_info(self.episode_id)
            if episode_info:
                episode_dir_name = episode_info.get('claude_episode_dir')
        
        # Run orchestrator using the episode directory name as ID
        result = self.run_orchestrator(
            stage=stage,
            episode_id=episode_dir_name,
            force=force
        )
        
        # If response stage completed successfully, sync responses to database
        if result['success'] and stage in ['respond', 'response', 'full']:
            try:
                # Check if responses.json exists in episode directory
                if episode_dir_name:
                    responses_file = self.episodes_dir / episode_dir_name / "responses.json"
                    if responses_file.exists():
                        logger.info(f"Syncing responses from {responses_file} to database")
                        
                        # Import the sync function
                        from web_bridge import sync_responses_to_database
                        
                        # Sync responses to database as drafts
                        draft_count = sync_responses_to_database(
                            str(responses_file),
                            episode_dir_name
                        )
                        
                        if draft_count > 0:
                            logger.info(f"Successfully synced {draft_count} responses as drafts")
                            result['drafts_created'] = draft_count
                        else:
                            logger.warning("No drafts were created from responses")
                    else:
                        logger.warning(f"Responses file not found: {responses_file}")
            except Exception as e:
                logger.error(f"Failed to sync responses to database: {e}")
                # Don't fail the whole stage, just log the error
                result['sync_error'] = str(e)
        
        # Emit completion event
        event_type = 'pipeline_stage_completed' if result['success'] else 'pipeline_stage_error'
        self.emit_sse_event({
            'type': event_type,
            'episodeId': str(self.episode_id) if self.episode_id else '0',
            'stage': stage,
            'success': result['success'],
            'error': result.get('error'),
            'drafts_created': result.get('drafts_created', 0),
            'timestamp': datetime.now().isoformat()
        })
        
        return result


def main():
    """Command-line interface for the Claude pipeline bridge."""
    parser = argparse.ArgumentParser(description="Claude Pipeline Bridge")
    
    parser.add_argument('--episode-id', type=int, help='Episode ID')
    parser.add_argument('--episode-dir', help='Episode directory name (bypasses database lookup)')
    parser.add_argument('--stage', '--stages', default='full', 
                       choices=['summarize', 'scraping', 'classify', 'respond', 'moderate', 'full'],
                       help='Pipeline stage to run')
    parser.add_argument('--force', action='store_true', help='Force reprocessing')
    
    args = parser.parse_args()
    
    # Initialize bridge
    bridge = ClaudePipelineBridge(episode_id=args.episode_id)
    
    # Set episode directory override if provided
    if args.episode_dir:
        bridge.episode_dir_override = args.episode_dir
    
    # Run specified stage
    result = bridge.run_stage(args.stage, force=args.force)
    
    if result['success']:
        print(f"✓ Stage '{args.stage}' completed successfully")
        if result.get('results'):
            print(json.dumps(result['results'], indent=2))
    else:
        print(f"✗ Stage '{args.stage}' failed: {result.get('error')}")
        if result.get('stderr'):
            print(f"Error output: {result['stderr']}")
        sys.exit(1)


if __name__ == "__main__":
    main()