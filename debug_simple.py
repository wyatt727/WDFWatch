#!/usr/bin/env python3

import os
import json
from pathlib import Path

def test_path_resolution():
    print("=== Testing Path Resolution ===")

    # Test the exact scenario from scrape.py
    episode_id = "keyword_national_divorce"
    print(f"Episode ID: {episode_id}")

    # Find the episode directory
    claude_episodes_dir = Path(os.getcwd()) / "claude-pipeline" / "episodes"
    print(f"Looking for episodes in: {claude_episodes_dir}")

    # Check if the episode directory exists
    episode_dir = claude_episodes_dir / episode_id
    print(f"Episode directory: {episode_dir}")
    print(f"Episode directory exists: {episode_dir.exists()}")

    if episode_dir.exists():
        # Test the file configuration for Claude pipeline
        files = {
            'tweets': 'tweets.json',
            'keywords': 'keywords.json',
            'classified': 'classified.json'
        }

        for key, relative_path in files.items():
            full_path = episode_dir / relative_path
            print(f"File '{key}': {full_path} (exists: {full_path.exists()})")

        # Test writing a file
        test_content = [{"test": "data"}]
        tweets_path = episode_dir / 'tweets.json'
        print(f"\nWriting test data to: {tweets_path}")

        try:
            with open(tweets_path, 'w') as f:
                json.dump(test_content, f, indent=2)
            print(f"Successfully wrote to: {tweets_path}")
            print(f"File exists after write: {tweets_path.exists()}")
            print(f"File size: {tweets_path.stat().st_size} bytes")
        except Exception as e:
            print(f"Error writing file: {e}")

if __name__ == "__main__":
    test_path_resolution()