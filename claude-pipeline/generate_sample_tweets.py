#!/usr/bin/env python3
"""
Standalone sample tweet generator for episodes
No external dependencies - uses only Python standard library
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

def generate_tweets_for_keywords(keywords, count=20):
    """Generate sample tweets based on keywords"""

    templates = [
        "The concept of {kw} is gaining traction as states push back against federal overreach.",
        "Interesting discussion about {kw} on the WDF podcast. Worth considering.",
        "{kw} might be extreme, but federal power grabs are forcing states to consider it.",
        "Why is {kw} being discussed? Because DC won't respect state sovereignty.",
        "The founders gave us federalism to avoid {kw}, but here we are.",
        "{kw} shouldn't be necessary if we followed the 10th Amendment.",
        "Rick Becker's take on {kw} made me think about peaceful solutions.",
        "States considering {kw} shows how broken our federal system has become.",
        "Before {kw}, maybe we should try actual federalism?",
        "{kw} discussions highlight the importance of state sovereignty.",
        "The federal government's overreach in {kw} context is concerning. States need autonomy.",
        "Just listened to WDF discussion on {kw}. Really made me think about federalism.",
        "Why does Washington think they know better about {kw}?",
        "State sovereignty is crucial when it comes to {kw}. One size doesn't fit all.",
        "The Supreme Court's stance on {kw} shows why we need stronger state rights.",
        "Interesting point about {kw} and the 10th Amendment. More people should understand this.",
        "{kw} should be decided at the state level, not by federal bureaucrats.",
        "The founding fathers would be appalled at federal control over {kw} discussions.",
        "My state knows better than DC how to handle {kw}. #Federalism",
        "Rick Becker's take on {kw} and constitutional limits really resonated with me.",
    ]

    tweets = []
    now = datetime.now()

    for i in range(count):
        keyword = random.choice(keywords)
        template = random.choice(templates)
        tweet_text = template.format(kw=keyword)

        # Generate realistic tweet metadata
        hours_ago = random.randint(1, 72)
        created_at = now - timedelta(hours=hours_ago)

        tweet = {
            "id": f"sample_{i}_{int(now.timestamp())}",
            "text": tweet_text,
            "user": f"@user{random.randint(100, 999)}",
            "created_at": created_at.isoformat() + "Z",
            "matched_keyword": keyword,
            "metrics": {
                "like_count": random.randint(5, 100),
                "retweet_count": random.randint(0, 20),
                "reply_count": random.randint(0, 10)
            }
        }
        tweets.append(tweet)

    return tweets

def main():
    # Get episode ID from command line or environment
    episode_id = None
    if len(sys.argv) > 1:
        episode_id = sys.argv[1]
    elif 'WDF_EPISODE_ID' in os.environ:
        episode_id = os.environ['WDF_EPISODE_ID']

    if not episode_id:
        print("Error: No episode ID provided", file=sys.stderr)
        sys.exit(1)

    # Find episode directory
    project_root = Path(__file__).parent.parent
    episode_dir = project_root / "claude-pipeline" / "episodes" / episode_id

    if not episode_dir.exists():
        print(f"Error: Episode directory not found: {episode_dir}", file=sys.stderr)
        sys.exit(1)

    # Load keywords
    keywords_file = episode_dir / "keywords.json"
    if not keywords_file.exists():
        print(f"Error: Keywords file not found: {keywords_file}", file=sys.stderr)
        sys.exit(1)

    with open(keywords_file) as f:
        keywords_data = json.load(f)

    # Extract keyword strings
    keywords = []
    for kw in keywords_data:
        if isinstance(kw, dict):
            keywords.append(kw.get('keyword', str(kw)))
        else:
            keywords.append(str(kw))

    print(f"Generating sample tweets for keywords: {', '.join(keywords)}")

    # Generate tweets
    tweets = generate_tweets_for_keywords(keywords, count=20)

    # Save tweets
    tweets_file = episode_dir / "tweets.json"
    with open(tweets_file, 'w') as f:
        json.dump(tweets, f, indent=2)

    print(f"Generated {len(tweets)} sample tweets and saved to {tweets_file}")
    return 0

if __name__ == "__main__":
    import os
    sys.exit(main())