#!/usr/bin/env python3
"""
Fixed Claude Pipeline Bridge - Ensures proper environment for subprocess execution
This version preserves the PATH environment variable to ensure Node.js and Claude CLI work
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


def ensure_environment():
    """
    Ensure the environment has proper PATH for Node.js and Claude CLI.
    """
    # Get current PATH
    current_path = os.environ.get('PATH', '')

    # Add critical directories if not already present
    required_paths = [
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
        os.path.expanduser('~/.nvm/versions/node/v18.17.0/bin'),  # Node via nvm
        os.path.expanduser('~/.nvm/versions/node/v20.10.0/bin'),  # Alternative Node
        os.path.expanduser('~/.claude/local'),  # Claude CLI for current user
        '/home/debian/.claude/local',  # Claude CLI for debian user
    ]

    path_parts = current_path.split(':')
    for req_path in required_paths:
        if req_path not in path_parts and os.path.exists(req_path):
            path_parts.insert(0, req_path)

    # Update PATH
    new_path = ':'.join(path_parts)
    os.environ['PATH'] = new_path

    # Set other critical environment variables
    os.environ['CLAUDE_CLI_PATH'] = '/home/debian/.claude/local/claude'
    os.environ['NODE_PATH'] = '/usr/lib/node_modules'
    os.environ['PYTHONUNBUFFERED'] = '1'  # For real-time output

    logger.info(f"Environment PATH configured: {new_path}")

    # Verify Node.js and Claude CLI are available
    try:
        node_result = subprocess.run(['which', 'node'], capture_output=True, text=True)
        logger.info(f"Node.js found at: {node_result.stdout.strip()}")
    except:
        logger.warning("Node.js not found in PATH")

    try:
        claude_result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
        logger.info(f"Claude CLI found at: {claude_result.stdout.strip()}")
    except:
        logger.warning("Claude CLI not found in PATH")

    return new_path


def run_claude_pipeline(episode_id: str, stages: str, transcript_path: str = None,
                        video_url: str = None, debug: bool = True):
    """
    Run the orchestrator.py with proper environment setup.

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
        # Ensure proper environment first
        configured_path = ensure_environment()

        # Get project root and orchestrator path
        project_root = Path(__file__).parent.parent.parent
        orchestrator_path = project_root / "claude-pipeline" / "orchestrator.py"

        if not orchestrator_path.exists():
            raise FileNotFoundError(f"Orchestrator not found at {orchestrator_path}")

        # Build command
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

        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"With PATH: {configured_path}")

        # Create environment dict with our fixed PATH
        env = os.environ.copy()
        env['PATH'] = configured_path

        # Run the orchestrator with fixed environment
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            env=env,  # Pass the fixed environment
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
            'command': ' '.join(cmd),
            'path': configured_path
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
        description="Fixed Claude Pipeline Runner with proper environment"
    )

    parser.add_argument('--episode-id', required=True, help='Episode ID')
    parser.add_argument('--stages', default='summarize',
                       help='Comma-separated stages')
    parser.add_argument('--transcript', required=True, help='Path to transcript file')
    parser.add_argument('--video-url', help='YouTube video URL')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    # Run the pipeline with fixed environment
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
        print(f"PATH: {result.get('path', 'N/A')}")
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