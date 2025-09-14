#!/usr/bin/env python3
"""
Test script to verify response syncing from Claude pipeline to database
This ensures drafts appear in the review page after response generation
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_response_sync():
    """Test syncing responses from file to database"""
    
    # Import the sync function
    from web_bridge import sync_responses_to_database, get_bridge
    
    print("Testing response sync to database...")
    
    # Find a sample responses.json file
    episodes_dir = Path(__file__).parent.parent.parent / "claude-pipeline" / "episodes"
    
    # Look for any episode with responses.json
    response_files = list(episodes_dir.glob("*/responses.json"))
    
    if not response_files:
        print("❌ No responses.json files found in claude-pipeline/episodes/")
        print("   Please run the response stage for an episode first")
        return False
    
    # Use the most recent responses file
    response_file = max(response_files, key=lambda x: x.stat().st_mtime)
    episode_dir = response_file.parent.name
    
    print(f"✓ Found responses file: {response_file}")
    print(f"  Episode directory: {episode_dir}")
    
    # Load and check the responses
    with open(response_file, 'r') as f:
        responses = json.load(f)
    
    valid_responses = [r for r in responses if r.get('response') and '[Skipped' not in r.get('response', '')]
    print(f"  Total responses: {len(responses)}")
    print(f"  Valid responses: {len(valid_responses)}")
    
    if not valid_responses:
        print("❌ No valid responses to sync")
        return False
    
    # Test database connection
    try:
        bridge = get_bridge()
        with bridge.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM tweets")
            tweet_count = cursor.fetchone()[0]
            print(f"✓ Database connection successful")
            print(f"  Total tweets in database: {tweet_count}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Count existing pending drafts
    try:
        with bridge.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM draft_replies WHERE status = 'pending'")
            before_count = cursor.fetchone()[0]
            print(f"  Pending drafts before sync: {before_count}")
    except Exception as e:
        print(f"⚠️  Could not count existing drafts: {e}")
        before_count = 0
    
    # Perform the sync
    print("\n🔄 Syncing responses to database...")
    try:
        created_count = sync_responses_to_database(str(response_file), episode_dir)
        
        if created_count > 0:
            print(f"✅ Successfully synced {created_count} responses as drafts!")
            
            # Count drafts after sync
            with bridge.connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM draft_replies WHERE status = 'pending'")
                after_count = cursor.fetchone()[0]
                print(f"  Pending drafts after sync: {after_count}")
                
                # Show sample draft
                cursor.execute("""
                    SELECT dr.id, dr.text, t.twitter_id, t.author_handle
                    FROM draft_replies dr
                    JOIN tweets t ON dr.tweet_id = t.id
                    WHERE dr.status = 'pending'
                    ORDER BY dr.created_at DESC
                    LIMIT 1
                """)
                sample = cursor.fetchone()
                if sample:
                    print(f"\n  Sample draft created:")
                    print(f"    Draft ID: {sample[0]}")
                    print(f"    Tweet: @{sample[3]} (ID: {sample[2]})")
                    print(f"    Response: {sample[1][:100]}...")
            
            print("\n✅ Drafts should now appear in the review page at /review")
            return True
        else:
            print("⚠️  No drafts were created")
            print("   This could mean:")
            print("   - Tweets in responses.json don't exist in database")
            print("   - All responses are empty or skipped")
            print("   - Drafts already exist for these tweets")
            return False
            
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set web mode environment variable
    os.environ["WDF_WEB_MODE"] = "true"
    
    success = test_response_sync()
    sys.exit(0 if success else 1)