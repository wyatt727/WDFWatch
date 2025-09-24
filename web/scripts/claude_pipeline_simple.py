#!/usr/bin/env python3
"""
Simplified Claude Pipeline Bridge - Just runs the CLI orchestrator command
No database queries, no complex logic - just subprocess call to orchestrator.py
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


def run_claude_pipeline(episode_id: str, stages: str, transcript_text: str = None, 
                        video_url: str = None, debug: bool = True):
    """
    Run the Claude pipeline orchestrator with the exact same CLI arguments that work.
    
    Args:
        episode_id: Episode identifier (e.g., "episode_12345")
        stages: Comma-separated stages to run (e.g., "summarize", "summarize,classify,respond")
        transcript_text: Optional transcript text (will be saved to temp file)
        video_url: Optional YouTube URL for the episode
        debug: Enable debug output
    
    Returns:
        Dict with success status and output
    """
    transcript_file_to_delete = None
    try:
        # Get project root and orchestrator path
        project_root = Path(__file__).parent.parent.parent
        orchestrator_path = project_root / "claude-pipeline" / "orchestrator.py"
        
        if not orchestrator_path.exists():
            raise FileNotFoundError(f"Orchestrator not found at {orchestrator_path}")
        
        # Build the command - exactly like the CLI
        cmd = [sys.executable, str(orchestrator_path)]
        
        # Add episode ID
        cmd.extend(['--episode-id', episode_id])
        
        # Add stages
        cmd.extend(['--stages', stages])
        
        # Handle transcript
        if transcript_text:
            # Save transcript to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(transcript_text)
                transcript_file = f.name
                transcript_file_to_delete = transcript_file
            cmd.extend(['--transcript', transcript_file])
        else:
            # Check if stdin has data (when called from Web UI)
            if not sys.stdin.isatty():
                stdin_text = sys.stdin.read()
                if stdin_text:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(stdin_text)
                        transcript_file = f.name
                        transcript_file_to_delete = transcript_file
                    cmd.extend(['--transcript', transcript_file])
                else:
                    # Use default transcript location
                    transcript_file = project_root / "transcripts" / "latest.txt"
                    if transcript_file.exists():
                        cmd.extend(['--transcript', str(transcript_file)])
            else:
                # Use default transcript location
                transcript_file = project_root / "transcripts" / "latest.txt"
                if transcript_file.exists():
                    cmd.extend(['--transcript', str(transcript_file)])
        
        # Add video URL if provided
        if video_url:
            cmd.extend(['--video-url', video_url])
        
        # Add debug flag
        if debug:
            cmd.append('-d')
        
        # Add tweets file if it exists (for testing)
        tweets_file = project_root / "transcripts" / "tweets.json"
        if tweets_file.exists():
            cmd.extend(['--tweets', str(tweets_file)])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Run the orchestrator exactly as we would from CLI
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,  # Prevent any stdin reading
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        # Clean up temp transcript file if created
        if transcript_file_to_delete:
            try:
                os.unlink(transcript_file_to_delete)
            except:
                pass
        
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
        description="Simplified Claude Pipeline Runner - Just runs the orchestrator CLI"
    )
    
    parser.add_argument('--episode-id', required=True, help='Episode ID')
    parser.add_argument('--stages', default='summarize', 
                       help='Comma-separated stages (e.g., summarize,classify,respond)')
    parser.add_argument('--transcript', help='Path to transcript file')
    parser.add_argument('--video-url', help='YouTube video URL')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Read transcript if file provided
    transcript_text = None
    if args.transcript:
        with open(args.transcript, 'r') as f:
            transcript_text = f.read()
    
    # Run the pipeline
    result = run_claude_pipeline(
        episode_id=args.episode_id,
        stages=args.stages,
        transcript_text=transcript_text,
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