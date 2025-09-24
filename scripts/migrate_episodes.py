#!/usr/bin/env python3
"""
Migration script for existing episodes
Moves legacy files from transcripts/ to episode-specific directories

Usage:
    python scripts/migrate_episodes.py                      # Interactive mode
    python scripts/migrate_episodes.py --episode-id 123     # Migrate specific episode
    python scripts/migrate_episodes.py --all                # Migrate all episodes from database
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.episode_files import EpisodeFileManager, EPISODES_BASE_DIR
from src.wdf.settings import get_settings


def get_legacy_files() -> Dict[str, Path]:
    """Get mapping of legacy file keys to paths"""
    settings = get_settings()
    transcript_dir = Path(settings.transcript_dir)
    
    return {
        'transcript': transcript_dir / 'latest.txt',
        'overview': transcript_dir / 'podcast_overview.txt',
        'video_url': transcript_dir / 'VIDEO_URL.txt',
        'summary': transcript_dir / 'summary.md',
        'keywords': transcript_dir / 'keywords.json',
        'fewshots': transcript_dir / 'fewshots.json',
        'tweets': transcript_dir / 'tweets.json',
        'classified': transcript_dir / 'classified.json',
        'responses': transcript_dir / 'responses.json',
        'published': transcript_dir / 'published.json'
    }


def check_legacy_files() -> Dict[str, bool]:
    """Check which legacy files exist"""
    legacy_files = get_legacy_files()
    return {key: path.exists() for key, path in legacy_files.items()}


def migrate_episode(episode_id: str, episode_title: Optional[str] = None, dry_run: bool = False) -> bool:
    """
    Migrate files for a specific episode
    
    Args:
        episode_id: Episode ID
        episode_title: Optional episode title for directory naming
        dry_run: If True, only show what would be done
        
    Returns:
        True if migration successful
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating episode {episode_id}...")
    
    # Create episode file manager
    timestamp = datetime.now().strftime('%Y%m%d')
    if episode_title:
        # Sanitize title for directory name
        safe_title = "-".join(episode_title.lower().split()[:5])
        safe_title = "".join(c for c in safe_title if c.isalnum() or c == '-')
        episode_dir = f"{timestamp}-ep{episode_id}-{safe_title}"
    else:
        episode_dir = f"{timestamp}-ep{episode_id}"
    
    fm = EpisodeFileManager(episode_id, episode_dir)
    
    if not dry_run:
        print(f"Created episode directory: {fm.episode_dir}")
    else:
        print(f"Would create episode directory: {fm.episode_dir}")
    
    # Get legacy files
    legacy_files = get_legacy_files()
    migrated_count = 0
    
    for key, legacy_path in legacy_files.items():
        if legacy_path.exists():
            # Determine target path
            if key in ['transcript', 'overview', 'video_url']:
                target_path = fm.get_input_path(key)
            else:
                target_path = fm.get_output_path(key)
            
            if not dry_run:
                # Create parent directory
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(legacy_path, target_path)
                print(f"  ✓ Copied {key}: {legacy_path} → {target_path}")
            else:
                print(f"  Would copy {key}: {legacy_path} → {target_path}")
            
            migrated_count += 1
        else:
            print(f"  ⊗ Skipped {key}: file not found")
    
    print(f"\n{'Would migrate' if dry_run else 'Migrated'} {migrated_count} files")
    
    # Update episode in database if in web mode
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true" and not dry_run:
        try:
            # Try to update episode with file config
            from web.scripts.web_bridge import update_episode_file_config
            
            file_config = {
                'episodeDir': fm.episode_dir,
                'files': fm.file_config.files
            }
            
            update_episode_file_config(episode_id, file_config)
            print(f"✓ Updated episode in database with file configuration")
        except Exception as e:
            print(f"⚠ Could not update database: {e}")
    
    return True


def get_episodes_from_database() -> List[Dict]:
    """Get all episodes from database"""
    try:
        # Import web bridge
        sys.path.insert(0, str(Path(__file__).parent.parent / "web" / "scripts"))
        from web_bridge import get_all_episodes
        
        episodes = get_all_episodes()
        return episodes if episodes else []
    except Exception as e:
        print(f"Error loading episodes from database: {e}")
        return []


def interactive_mode():
    """Interactive migration mode"""
    print("Episode Migration Tool")
    print("=" * 50)
    
    # Check legacy files
    legacy_status = check_legacy_files()
    print("\nLegacy files found:")
    for key, exists in legacy_status.items():
        print(f"  {key}: {'✓' if exists else '✗'}")
    
    if not any(legacy_status.values()):
        print("\nNo legacy files found to migrate.")
        return
    
    # Get episodes from database if available
    episodes = []
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        episodes = get_episodes_from_database()
        if episodes:
            print(f"\nFound {len(episodes)} episodes in database:")
            for i, ep in enumerate(episodes, 1):
                print(f"  {i}. Episode {ep['id']}: {ep['title']}")
    
    # Ask user what to do
    print("\nOptions:")
    print("  1. Migrate to a new episode")
    print("  2. Migrate to an existing episode")
    print("  3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        # Create new episode
        episode_id = input("Enter episode ID: ").strip()
        episode_title = input("Enter episode title (optional): ").strip()
        
        # Confirm
        print(f"\nWill migrate legacy files to episode {episode_id}")
        if episode_title:
            print(f"Title: {episode_title}")
        
        confirm = input("\nProceed? (y/N): ").strip().lower()
        if confirm == 'y':
            migrate_episode(episode_id, episode_title)
        else:
            print("Migration cancelled.")
    
    elif choice == "2" and episodes:
        # Select existing episode
        ep_num = input(f"\nSelect episode (1-{len(episodes)}): ").strip()
        try:
            idx = int(ep_num) - 1
            if 0 <= idx < len(episodes):
                ep = episodes[idx]
                
                print(f"\nWill migrate legacy files to episode {ep['id']}: {ep['title']}")
                confirm = input("\nProceed? (y/N): ").strip().lower()
                
                if confirm == 'y':
                    migrate_episode(ep['id'], ep['title'])
                else:
                    print("Migration cancelled.")
            else:
                print("Invalid episode number.")
        except ValueError:
            print("Invalid input.")
    
    else:
        print("Exiting.")


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy files to episode-based structure")
    parser.add_argument("--episode-id", type=str, help="Episode ID to migrate to")
    parser.add_argument("--episode-title", type=str, help="Episode title for directory naming")
    parser.add_argument("--all", action="store_true", help="Migrate all episodes from database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually doing it")
    
    args = parser.parse_args()
    
    if args.all:
        # Migrate all episodes
        if os.getenv("WDF_WEB_MODE", "false").lower() != "true":
            print("Error: --all requires WDF_WEB_MODE=true")
            sys.exit(1)
        
        episodes = get_episodes_from_database()
        if not episodes:
            print("No episodes found in database.")
            sys.exit(1)
        
        print(f"Found {len(episodes)} episodes to migrate")
        
        for ep in episodes:
            # Check if already has episode directory
            if ep.get('episodeDir'):
                print(f"\nSkipping episode {ep['id']}: already has episode directory")
                continue
            
            migrate_episode(ep['id'], ep['title'], dry_run=args.dry_run)
    
    elif args.episode_id:
        # Migrate specific episode
        migrate_episode(args.episode_id, args.episode_title, dry_run=args.dry_run)
    
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()