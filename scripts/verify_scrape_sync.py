#!/usr/bin/env python3
"""
Verification script to confirm tweets from tweets.json are syncing to database.
Run this AFTER a scrape operation to verify Fix #7 is working correctly.

Usage: python3 scripts/verify_scrape_sync.py [episode_id]
"""

import json
import sys
import psycopg2
from pathlib import Path
from datetime import datetime

def main():
    episode_id = sys.argv[1] if len(sys.argv) > 1 else "65"

    # Read DATABASE_URL from .env.local
    env_file = Path('web/.env.local')
    db_url = None
    if env_file.exists():
        for line in env_file.read_text().split('\n'):
            if line.startswith('DATABASE_URL='):
                db_url = line.split('=', 1)[1].strip('"').split('?')[0]
                break

    if not db_url:
        print('❌ DATABASE_URL not found in web/.env.local')
        sys.exit(1)

    # Read tweets.json for the episode
    episode_dir = Path(f'claude-pipeline/episodes/keyword_national_divorce')
    tweets_file = episode_dir / 'tweets.json'

    if not tweets_file.exists():
        print(f'❌ tweets.json not found at {tweets_file}')
        sys.exit(1)

    with open(tweets_file, 'r') as f:
        tweets = json.load(f)

    if not tweets:
        print('⚠️  tweets.json is empty')
        sys.exit(0)

    # Get date range from tweets.json
    dates = set()
    sample_ids = []
    for tweet in tweets[:5]:  # Sample first 5
        created_at = tweet.get('created_at', '')
        if created_at:
            date = created_at.split('T')[0]
            dates.add(date)
        if tweet.get('id'):
            sample_ids.append(str(tweet['id']))

    min_date = min(dates)
    max_date = max(dates)

    print(f'\n📄 tweets.json Analysis:')
    print(f'   Total tweets: {len(tweets)}')
    print(f'   Date range: {min_date} to {max_date}')
    print(f'   Sample IDs: {", ".join(sample_ids[:3])}')

    # Check database
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Check if sample tweets are in database
        cursor.execute('''
            SELECT COUNT(*)
            FROM tweets
            WHERE episode_id = %s
            AND twitter_id = ANY(%s)
        ''', (episode_id, sample_ids))

        matched = cursor.fetchone()[0]

        # Get database stats for date range
        cursor.execute('''
            SELECT COUNT(*)
            FROM tweets
            WHERE episode_id = %s
            AND created_at >= %s
            AND created_at < %s::date + interval '1 day'
        ''', (episode_id, min_date, max_date))

        date_range_count = cursor.fetchone()[0]

        print(f'\n🗄️  Database Check (episode {episode_id}):')
        print(f'   Tweets from {min_date}-{max_date}: {date_range_count}')
        print(f'   Sample IDs matched: {matched}/{len(sample_ids)}')

        # Verify sync worked
        if matched == len(sample_ids):
            print(f'\n✅ SUCCESS: All sample tweets synced to database!')
            print(f'   Fix #7 is working correctly!')
        elif matched > 0:
            print(f'\n⚠️  PARTIAL SYNC: {matched}/{len(sample_ids)} sample tweets found')
            print(f'   Some tweets may have been filtered as duplicates')
        else:
            print(f'\n❌ SYNC FAILED: No sample tweets found in database')
            print(f'   Check logs for WDF_CURRENT_EPISODE_ID errors')

            # Check for non-numeric episode ID errors
            cursor.execute('''
                SELECT twitter_id, created_at
                FROM tweets
                WHERE episode_id = %s
                ORDER BY scraped_at DESC
                LIMIT 3
            ''', (episode_id,))

            print(f'\n   Most recent tweets in DB:')
            for row in cursor.fetchall():
                print(f'     {row[1]}: {row[0]}')

        cursor.close()
        conn.close()

    except Exception as e:
        print(f'\n❌ Database Error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
