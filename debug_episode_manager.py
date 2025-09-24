#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/debian/Tools/WDFWatch/src')

from wdf.episode_files import get_episode_file_manager

def debug_file_manager():
    print("=== Testing EpisodeFileManager ===")

    # Test with keyword_national_divorce episode
    episode_id = "keyword_national_divorce"
    print(f"Creating file manager for episode: {episode_id}")

    try:
        file_manager = get_episode_file_manager(episode_id)
        print(f"File manager created successfully")
        print(f"Episode ID: {file_manager.episode_id}")
        print(f"Episode dir: {file_manager.episode_dir}")
        print(f"Base path: {file_manager.base_path}")
        print(f"Pipeline type: {file_manager.pipeline_type}")
        print(f"File config files: {file_manager.file_config.files}")

        # Test get_output_path for tweets
        print("\n=== Testing get_output_path('tweets') ===")
        tweets_path = file_manager.get_output_path('tweets')
        print(f"Tweets path: {tweets_path}")
        print(f"Tweets path type: {type(tweets_path)}")
        print(f"Tweets path str: '{str(tweets_path)}'")
        print(f"Tweets path exists: {tweets_path.exists()}")

    except Exception as e:
        print(f"Error creating file manager: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_file_manager()