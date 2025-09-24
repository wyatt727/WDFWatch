#!/usr/bin/env python3
"""
Import all tweets.json and responses.json files from episode directories into PostgreSQL database.
Tweets are imported with proper episode associations.
Responses are imported as approved drafts (not in review queue).
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import sys
from pathlib import Path

# Database connection
DB_URL = "postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch"

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DB_URL)

def get_episode_mapping():
    """Get mapping of episode_dir to episode_id from database"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, episode_dir FROM podcast_episodes")
            episodes = cur.fetchall()

    # Create mapping
    mapping = {}
    for episode in episodes:
        if episode['episode_dir']:
            mapping[episode['episode_dir']] = episode['id']

    print(f"Found {len(mapping)} episodes in database:")
    for episode_dir, episode_id in mapping.items():
        print(f"  {episode_id}: {episode_dir}")

    return mapping

def import_tweets_for_episode(episode_dir, episode_id, tweets_file):
    """Import tweets from tweets.json file for a specific episode"""
    print(f"\nImporting tweets for episode {episode_id} ({episode_dir})...")

    try:
        with open(tweets_file, 'r') as f:
            tweets_data = json.load(f)
    except Exception as e:
        print(f"  ERROR: Could not read {tweets_file}: {e}")
        return 0

    if not tweets_data:
        print(f"  No tweets found in {tweets_file}")
        return 0

    imported_count = 0
    skipped_count = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for tweet_data in tweets_data:
                try:
                    # Extract tweet information
                    twitter_id = str(tweet_data.get('id'))
                    author_handle = tweet_data.get('author_username', '')
                    author_name = tweet_data.get('author_name', '')
                    full_text = tweet_data.get('text', '')
                    text_preview = full_text[:280] if full_text else ''

                    # Get created_at timestamp
                    created_at_str = tweet_data.get('created_at')
                    if created_at_str:
                        # Parse Twitter's ISO format
                        scraped_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        scraped_at = datetime.now()

                    # Check if tweet already exists
                    cur.execute("SELECT id FROM tweets WHERE twitter_id = %s", (twitter_id,))
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                    # Insert tweet
                    cur.execute("""
                        INSERT INTO tweets (
                            twitter_id, author_handle, author_name, full_text, text_preview,
                            status, episode_id, scraped_at, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                        )
                    """, (
                        twitter_id, author_handle, author_name, full_text, text_preview,
                        'scraped', episode_id, scraped_at
                    ))

                    imported_count += 1

                except Exception as e:
                    print(f"  ERROR importing tweet {tweet_data.get('id', 'unknown')}: {e}")
                    continue

    print(f"  Imported: {imported_count} tweets, Skipped: {skipped_count} duplicates")
    return imported_count

def import_responses_for_episode(episode_dir, episode_id, responses_file):
    """Import responses from responses.json file as approved drafts"""
    print(f"\nImporting responses for episode {episode_id} ({episode_dir})...")

    try:
        with open(responses_file, 'r') as f:
            responses_data = json.load(f)
    except Exception as e:
        print(f"  ERROR: Could not read {responses_file}: {e}")
        return 0

    if not responses_data:
        print(f"  No responses found in {responses_file}")
        return 0

    imported_count = 0
    skipped_count = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for response_data in responses_data:
                try:
                    # Get the original tweet's twitter_id to find tweet_id in database
                    original_twitter_id = str(response_data.get('id'))
                    response_text = response_data.get('response', '')
                    model_name = response_data.get('model', 'unknown')

                    if not response_text:
                        continue

                    # Find the tweet_id in our database
                    cur.execute("SELECT id FROM tweets WHERE twitter_id = %s", (original_twitter_id,))
                    tweet_result = cur.fetchone()

                    if not tweet_result:
                        print(f"  Warning: Could not find tweet {original_twitter_id} in database")
                        continue

                    tweet_id = tweet_result[0]

                    # Check if draft already exists for this tweet
                    cur.execute("SELECT id FROM draft_replies WHERE tweet_id = %s", (tweet_id,))
                    if cur.fetchone():
                        skipped_count += 1
                        continue

                    # Insert as approved draft (not in review queue)
                    cur.execute("""
                        INSERT INTO draft_replies (
                            tweet_id, model_name, text, status, character_count,
                            approved_by, approved_at, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW()
                        )
                    """, (
                        tweet_id, model_name, response_text, 'approved',
                        len(response_text), 'system'
                    ))

                    imported_count += 1

                except Exception as e:
                    print(f"  ERROR importing response for tweet {response_data.get('id', 'unknown')}: {e}")
                    continue

    print(f"  Imported: {imported_count} responses, Skipped: {skipped_count} duplicates")
    return imported_count

def main():
    print("Starting import of episode data from file system to database...")

    # Get episode mapping
    episode_mapping = get_episode_mapping()

    # Find all episode directories with data files
    episodes_dir = Path("claude-pipeline/episodes")

    total_tweets = 0
    total_responses = 0

    for episode_dir in episodes_dir.iterdir():
        if not episode_dir.is_dir():
            continue

        episode_name = episode_dir.name

        # Skip if episode not in database
        if episode_name not in episode_mapping:
            print(f"\nSkipping {episode_name} (not found in database)")
            continue

        episode_id = episode_mapping[episode_name]

        # Import tweets if they exist
        tweets_file = episode_dir / "tweets.json"
        if tweets_file.exists():
            count = import_tweets_for_episode(episode_name, episode_id, tweets_file)
            total_tweets += count

        # Import responses if they exist
        responses_file = episode_dir / "responses.json"
        if responses_file.exists():
            count = import_responses_for_episode(episode_name, episode_id, responses_file)
            total_responses += count

    print(f"\n=== IMPORT COMPLETE ===")
    print(f"Total tweets imported: {total_tweets}")
    print(f"Total responses imported: {total_responses}")

    # Show final counts
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tweets")
            tweet_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM draft_replies WHERE status = 'approved'")
            approved_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM draft_replies WHERE status = 'pending'")
            pending_count = cur.fetchone()[0]

    print(f"\nDatabase totals:")
    print(f"  Total tweets: {tweet_count}")
    print(f"  Approved responses: {approved_count}")
    print(f"  Pending responses: {pending_count}")

if __name__ == "__main__":
    main()