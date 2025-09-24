#!/usr/bin/env python3
"""
Generate Sample Tweets for Pipeline Testing

Creates a sample tweets.json file with mock data for testing the pipeline
without making actual Twitter API calls.

Usage:
    python scripts/generate_sample_tweets.py
    python scripts/generate_sample_tweets.py --count 50
    python scripts/generate_sample_tweets.py --relevant-ratio 0.3
"""

import json
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict


# Sample tweet templates
RELEVANT_TEMPLATES = [
    "The federal government's overreach in {topic} is concerning. States should have more autonomy.",
    "Just listened to the WDF podcast discussion on {topic}. Really made me think about federalism.",
    "Why does Washington think they know better than local governments about {topic}?",
    "State sovereignty is crucial when it comes to {topic}. One size doesn't fit all.",
    "The Supreme Court's ruling on {topic} shows why we need stronger state rights.",
    "Interesting point about {topic} and the 10th Amendment. More people should understand this.",
    "{topic} should be decided at the state level, not by federal bureaucrats.",
    "The founding fathers would be appalled at federal control over {topic}.",
    "My state knows better than DC how to handle {topic}. #Federalism",
    "Rick Becker's take on {topic} and constitutional limits really resonated with me.",
]

IRRELEVANT_TEMPLATES = [
    "Just made the best {food} for dinner! Recipe in comments.",
    "Can't believe my team lost again. {sport} season is pain.",
    "New {product} just dropped! Who's copping?",
    "Weather is {weather} today. Perfect for {activity}.",
    "Watching {show} and I'm obsessed. No spoilers please!",
    "{celebrity} just posted and I can't even...",
    "My {pet} is being so cute right now! 😍",
    "Coffee tastes better on {day}s, change my mind.",
    "Why is {technology} so complicated? I just want it to work!",
    "Best {music} album of the year, hands down.",
]

# Topics for relevant tweets
TOPICS = [
    "healthcare", "education", "gun rights", "marijuana legalization",
    "immigration", "environmental policy", "taxation", "law enforcement",
    "election laws", "COVID mandates", "energy policy", "infrastructure"
]

# Random data for irrelevant tweets
FOODS = ["pizza", "tacos", "sushi", "pasta", "burgers", "salad"]
SPORTS = ["football", "basketball", "baseball", "soccer", "hockey"]
PRODUCTS = ["iPhone", "PlayStation", "sneakers", "laptop", "headphones"]
WEATHER = ["sunny", "rainy", "cloudy", "snowy", "windy"]
ACTIVITIES = ["hiking", "reading", "gaming", "sleeping", "shopping"]
SHOWS = ["The Last of Us", "Succession", "Ted Lasso", "Stranger Things"]
CELEBRITIES = ["Taylor Swift", "Drake", "LeBron", "Beyonce", "Elon Musk"]
PETS = ["cat", "dog", "hamster", "bird", "fish"]
DAYS = ["Monday", "Friday", "Sunday", "Tuesday", "Saturday"]
TECHNOLOGY = ["WiFi", "Bluetooth", "my printer", "Windows", "this app"]
MUSIC = ["pop", "rock", "hip-hop", "country", "jazz"]


def generate_tweet(tweet_id: str, is_relevant: bool, created_at: datetime) -> Dict:
    """Generate a single mock tweet"""
    if is_relevant:
        template = random.choice(RELEVANT_TEMPLATES)
        text = template.format(topic=random.choice(TOPICS))
        # Relevant tweets tend to get more engagement
        likes = random.randint(5, 500)
        retweets = random.randint(2, 200)
        replies = random.randint(1, 50)
    else:
        template = random.choice(IRRELEVANT_TEMPLATES)
        replacements = {
            "food": random.choice(FOODS),
            "sport": random.choice(SPORTS),
            "product": random.choice(PRODUCTS),
            "weather": random.choice(WEATHER),
            "activity": random.choice(ACTIVITIES),
            "show": random.choice(SHOWS),
            "celebrity": random.choice(CELEBRITIES),
            "pet": random.choice(PETS),
            "day": random.choice(DAYS),
            "technology": random.choice(TECHNOLOGY),
            "music": random.choice(MUSIC),
        }
        # Replace all placeholders
        text = template
        for key, value in replacements.items():
            text = text.replace(f"{{{key}}}", value)
        
        # Irrelevant tweets have lower engagement
        likes = random.randint(0, 50)
        retweets = random.randint(0, 10)
        replies = random.randint(0, 5)
    
    # Generate random username
    username = f"@{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789_', k=random.randint(5, 15)))}"
    
    return {
        "id": tweet_id,
        "text": text,
        "user": username,
        "created_at": created_at.isoformat() + "Z",
        "metrics": {
            "like_count": likes,
            "retweet_count": retweets,
            "reply_count": replies
        },
        "author_id": f"user_{random.randint(1000000, 9999999)}",
        "conversation_id": tweet_id,
        "lang": "en",
        "possibly_sensitive": False,
        "reply_settings": "everyone",
        "source": "Twitter Web App"
    }


def generate_sample_tweets(count: int = 20, relevant_ratio: float = 0.25) -> List[Dict]:
    """Generate a list of sample tweets"""
    tweets = []
    now = datetime.now()
    
    for i in range(count):
        # Generate tweet ID
        tweet_id = f"{random.randint(1000000000000000000, 9999999999999999999)}"
        
        # Determine if relevant based on ratio
        is_relevant = random.random() < relevant_ratio
        
        # Generate timestamp (tweets from last 7 days)
        hours_ago = random.randint(1, 168)  # Up to 7 days
        created_at = now - timedelta(hours=hours_ago)
        
        tweet = generate_tweet(tweet_id, is_relevant, created_at)
        tweets.append(tweet)
    
    # Sort by created_at (newest first)
    tweets.sort(key=lambda x: x["created_at"], reverse=True)
    
    return tweets


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate sample tweets for testing")
    parser.add_argument("--count", type=int, default=20, help="Number of tweets to generate")
    parser.add_argument("--relevant-ratio", type=float, default=0.25, 
                       help="Ratio of relevant tweets (0.0-1.0)")
    parser.add_argument("--output", type=str, default="transcripts/tweets.json",
                       help="Output file path")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not 0 <= args.relevant_ratio <= 1:
        print("Error: relevant-ratio must be between 0.0 and 1.0")
        return 1
    
    # Generate tweets
    print(f"Generating {args.count} sample tweets...")
    print(f"Relevant ratio: {args.relevant_ratio:.0%}")
    
    tweets = generate_sample_tweets(args.count, args.relevant_ratio)
    
    # Count relevant tweets
    relevant_count = sum(1 for t in tweets 
                        if any(keyword in t["text"].lower() 
                              for keyword in ["federal", "state", "sovereignty", "10th amendment"]))
    
    # Write to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(tweets, f, indent=2)
    
    print(f"\n✅ Generated {len(tweets)} tweets")
    print(f"📊 Approximately {relevant_count} relevant tweets")
    print(f"💾 Saved to: {output_path}")
    print("\nSample tweets:")
    for tweet in tweets[:3]:
        print(f"  - {tweet['user']}: {tweet['text'][:60]}...")
    
    return 0


if __name__ == "__main__":
    exit(main())