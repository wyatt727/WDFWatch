#!/usr/bin/env python3
"""
ULTRA SIMPLE Claude Pipeline Bridge - Just saves transcript and runs orchestrator.py
No complexity, no stdin, just saves the transcript to a file and runs the exact CLI command.
"""

import sys
import os
import subprocess
import json
import argparse
from pathlib import Path
import tempfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_claude_pipeline(episode_id: str, stages: str, transcript_path: str = None, 
                        video_url: str = None, debug: bool = True):
    """
    Run the orchestrator.py with EXACT CLI arguments.
    
    Args:
        episode_id: Episode identifier (e.g., "episode_12345")
        stages: Comma-separated stages to run (e.g., "summarize")
        transcript_path: Path to transcript file
        video_url: Optional YouTube URL for the episode
        debug: Enable debug output
    
    Returns:
        Dict with success status and output
    """
    try:
        # Get project root and orchestrator path
        project_root = Path(__file__).parent.parent.parent
        orchestrator_path = project_root / "claude-pipeline" / "orchestrator.py"
        
        if not orchestrator_path.exists():
            raise FileNotFoundError(f"Orchestrator not found at {orchestrator_path}")
        
        # Build the EXACT command that works from CLI
        cmd = [
            sys.executable, 
            str(orchestrator_path),
            '--episode-id', episode_id,
            '--stages', stages
        ]
        
        # Add transcript path if provided
        if transcript_path and Path(transcript_path).exists():
            cmd.extend(['--transcript', transcript_path])
        else:
            # Default to transcripts/latest.txt
            default_transcript = project_root / "transcripts" / "latest.txt"
            if default_transcript.exists():
                cmd.extend(['--transcript', str(default_transcript)])
            else:
                raise FileNotFoundError("No transcript file found")
        
        # Add video URL if provided
        if video_url:
            cmd.extend(['--video-url', video_url])
        
        # Add debug flag
        if debug:
            cmd.append('-d')
        
        # Add tweets file if it exists (for testing)
        tweets_file = project_root / "transcripts" / "tweets.json"
        if tweets_file.exists() and 'classify' in stages:
            cmd.extend(['--tweets', str(tweets_file)])
        
        logger.info(f"Running EXACT command: {' '.join(cmd)}")
        
        # Run the orchestrator EXACTLY as we would from CLI
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,  # Prevent any stdin reading
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'command': ' '.join(cmd)
        }
        
    except subprocess.TimeoutExpired:
        logger.error("Orchestrator timed out after 30 minutes")
        return {
            'success': False,
            'error': "Pipeline timed out after 30 minutes"
        }
    except Exception as e:
        logger.error(f"Failed to run orchestrator: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """Command-line interface for testing."""
    parser = argparse.ArgumentParser(
        description="ULTRA SIMPLE Claude Pipeline Runner"
    )
    
    parser.add_argument('--episode-id', required=True, help='Episode ID')
    parser.add_argument('--stages', default='summarize', 
                       help='Comma-separated stages')
    parser.add_argument('--transcript', required=True, help='Path to transcript file')
    parser.add_argument('--video-url', help='YouTube video URL')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Run the pipeline with exact file path
    result = run_claude_pipeline(
        episode_id=args.episode_id,
        stages=args.stages,
        transcript_path=args.transcript,
        video_url=args.video_url,
        debug=args.debug
    )
    
    if result['success']:
        print(f"✓ Pipeline completed successfully")
        print(f"Command: {result.get('command', 'N/A')}")
        if args.debug:
            print("\nOutput:")
            print(result['stdout'])
    else:
        print(f"✗ Pipeline failed")
        print(f"Error: {result.get('error', 'Unknown error')}")
        if result.get('stderr'):
            print(f"\nError output:")
            print(result['stderr'])
        sys.exit(1)


if __name__ == "__main__":
    main()