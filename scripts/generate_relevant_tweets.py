#!/usr/bin/env python3
"""
Generate tweets relevant to specific keywords for testing
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict

def generate_keyword_tweets(keywords: List[str], count: int = 100) -> List[Dict]:
    """Generate sample tweets containing the specified keywords"""

    # Templates that will include the actual keywords
    TEMPLATES = [
        "The concept of {keyword} is gaining traction as states push back against federal overreach.",
        "Interesting discussion about {keyword} on the WDF podcast. Worth considering as an option.",
        "{keyword} might be extreme, but the federal government's power grab is forcing states to consider it.",
        "Why is {keyword} even being discussed? Because DC won't respect state sovereignty.",
        "The founding fathers gave us federalism to avoid {keyword}, but here we are.",
        "{keyword} shouldn't be necessary if we actually followed the 10th Amendment.",
        "Rick Becker's take on {keyword} really made me think about peaceful solutions.",
        "States considering {keyword} shows how broken our federal system has become.",
        "Before {keyword}, maybe we should try actual federalism for once?",
        "{keyword} is what happens when one size fits all policies ignore local needs.",
        "The fact that {keyword} is trending shows people are fed up with federal overreach.",
        "Is {keyword} really the answer? Or should we restore constitutional boundaries?",
        "Those discussing {keyword} have valid concerns about federal tyranny.",
        "{keyword} conversations highlight the importance of state sovereignty.",
        "Not advocating for {keyword}, but I understand why some states are discussing it.",
    ]

    tweets = []
    now = datetime.now()

    for i in range(count):
        # Pick a random keyword and template
        keyword = random.choice(keywords)
        template = random.choice(TEMPLATES)
        text = template.format(keyword=keyword)

        # Generate realistic metadata
        tweet_id = f"t{random.randint(1000000000000000000, 9999999999999999999)}"
        hours_ago = random.randint(1, 168)  # Up to 7 days old
        created_at = now - timedelta(hours=hours_ago)
        username = f"@{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789_', k=random.randint(5, 15)))}"

        tweet = {
            "id": tweet_id,
            "text": text,
            "user": username,
            "created_at": created_at.isoformat() + "Z",
            "matched_keyword": keyword,  # Important for filtering
            "metrics": {
                "like_count": random.randint(0, 100),
                "retweet_count": random.randint(0, 20),
                "reply_count": random.randint(0, 10)
            }
        }
        tweets.append(tweet)

    return tweets

if __name__ == "__main__":
    # Test with "national divorce"
    import sys
    keywords = sys.argv[1:] if len(sys.argv) > 1 else ["national divorce"]
    tweets = generate_keyword_tweets(keywords, 20)
    print(json.dumps(tweets, indent=2))