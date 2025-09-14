#!/usr/bin/env python3
"""
Data migration script to move from file-based storage to PostgreSQL
Migrates tweets, classifications, responses, and published data
Interacts with: JSON files in transcripts/ and artefacts/, PostgreSQL database
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import psycopg2
from psycopg2.extras import Json
import argparse

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataMigrator:
    """Handles migration from JSON files to PostgreSQL"""
    
    def __init__(self, db_url: str):
        """Initialize with database connection"""
        self.db_url = db_url
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        """Connect to database"""
        self.conn = psycopg2.connect(self.db_url)
        self.cursor = self.conn.cursor()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.cursor.close()
            self.conn.close()
            
    def migrate_episode_data(self, transcript_dir: Path) -> Optional[int]:
        """Migrate episode data from transcript files"""
        logger.info(f"Migrating episode data from {transcript_dir}")
        
        # Read podcast overview if exists
        overview_path = transcript_dir / "podcast_overview.txt"
        overview_text = ""
        if overview_path.exists():
            overview_text = overview_path.read_text()
            
        # Read summary if exists  
        summary_path = transcript_dir / "summary.md"
        summary_text = ""
        if summary_path.exists():
            summary_text = summary_path.read_text()
            
        # Read keywords if exists
        keywords_path = transcript_dir / "keywords.json"
        keywords = []
        if keywords_path.exists():
            with open(keywords_path) as f:
                keywords = json.load(f)
                
        # Insert episode
        self.cursor.execute("""
            INSERT INTO podcast_episodes (title, summary_text, keywords, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            f"Episode from {datetime.now().strftime('%Y-%m-%d')}",
            summary_text or overview_text,
            Json(keywords),
            "keywords_ready" if keywords else "summarized" if summary_text else "no_transcript"
        ))
        
        episode_id = self.cursor.fetchone()[0]
        logger.info(f"Created episode with ID: {episode_id}")
        
        # Insert keywords into keywords table
        for keyword in keywords:
            if isinstance(keyword, str):
                keyword_text = keyword
                weight = 1.0
            else:
                keyword_text = keyword.get("text", keyword.get("keyword", ""))
                weight = keyword.get("weight", 1.0)
                
            if keyword_text:
                self.cursor.execute("""
                    INSERT INTO keywords (episode_id, keyword, weight)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (episode_id, keyword) DO UPDATE
                    SET weight = EXCLUDED.weight
                """, (episode_id, keyword_text, weight))
                
        return episode_id
        
    def migrate_tweets(self, tweets_path: Path, episode_id: Optional[int] = None) -> Dict[str, int]:
        """Migrate tweets from JSON file, returns mapping of twitter_id to db id"""
        logger.info(f"Migrating tweets from {tweets_path}")
        
        if not tweets_path.exists():
            logger.warning(f"Tweets file not found: {tweets_path}")
            return {}
            
        with open(tweets_path) as f:
            tweets = json.load(f)
            
        tweet_mapping = {}
        
        for tweet in tweets:
            # Handle different tweet formats
            twitter_id = tweet.get("id", tweet.get("twitter_id", ""))
            text = tweet.get("text", tweet.get("full_text", ""))
            user = tweet.get("user", tweet.get("author_handle", ""))
            
            # Extract user handle
            if isinstance(user, dict):
                author_handle = user.get("screen_name", "")
                author_name = user.get("name", "")
            else:
                author_handle = user.strip("@") if user else ""
                author_name = ""
                
            # Get metrics if available
            metrics = {}
            if "favorite_count" in tweet:
                metrics["likes"] = tweet["favorite_count"]
            if "retweet_count" in tweet:
                metrics["retweets"] = tweet["retweet_count"]
                
            # Check for classification
            status = "unclassified"
            relevance_score = None
            if "classification" in tweet:
                status = "relevant" if tweet["classification"] == "RELEVANT" else "skipped"
            if "relevance_score" in tweet:
                relevance_score = float(tweet["relevance_score"])
                
            # Insert tweet
            self.cursor.execute("""
                INSERT INTO tweets (
                    twitter_id, author_handle, author_name, full_text, text_preview,
                    relevance_score, status, metrics, scraped_at, episode_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (twitter_id) DO UPDATE
                SET status = EXCLUDED.status,
                    relevance_score = COALESCE(EXCLUDED.relevance_score, tweets.relevance_score)
                RETURNING id
            """, (
                twitter_id,
                author_handle,
                author_name,
                text,
                text[:280] if text else "",
                relevance_score,
                status,
                Json(metrics) if metrics else None,
                datetime.fromisoformat(tweet.get("created_at", datetime.now().isoformat())),
                episode_id
            ))
            
            db_id = self.cursor.fetchone()[0]
            tweet_mapping[twitter_id] = db_id
            
        logger.info(f"Migrated {len(tweet_mapping)} tweets")
        return tweet_mapping
        
    def migrate_classifications(self, classified_path: Path, tweet_mapping: Dict[str, int]):
        """Update tweet classifications from classified.json"""
        logger.info(f"Migrating classifications from {classified_path}")
        
        if not classified_path.exists():
            logger.warning(f"Classifications file not found: {classified_path}")
            return
            
        with open(classified_path) as f:
            classifications = json.load(f)
            
        for item in classifications:
            twitter_id = item.get("id", item.get("twitter_id", ""))
            if twitter_id not in tweet_mapping:
                logger.warning(f"Tweet {twitter_id} not found in mapping")
                continue
                
            db_id = tweet_mapping[twitter_id]
            classification = item.get("classification", "")
            rationale = item.get("rationale", item.get("reason", ""))
            
            status = "relevant" if classification == "RELEVANT" else "skipped"
            
            self.cursor.execute("""
                UPDATE tweets
                SET status = %s, classification_rationale = %s
                WHERE id = %s
            """, (status, rationale, db_id))
            
        logger.info(f"Updated {len(classifications)} classifications")
        
    def migrate_responses(self, responses_path: Path, tweet_mapping: Dict[str, int]):
        """Migrate draft responses from responses.json"""
        logger.info(f"Migrating responses from {responses_path}")
        
        if not responses_path.exists():
            logger.warning(f"Responses file not found: {responses_path}")
            return
            
        with open(responses_path) as f:
            responses = json.load(f)
            
        for response in responses:
            twitter_id = response.get("id", response.get("twitter_id", ""))
            if twitter_id not in tweet_mapping:
                logger.warning(f"Tweet {twitter_id} not found in mapping")
                continue
                
            db_id = tweet_mapping[twitter_id]
            
            # Insert draft
            self.cursor.execute("""
                INSERT INTO draft_replies (
                    tweet_id, model_name, text, character_count, status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                db_id,
                response.get("model", "deepseek-r1:latest"),
                response.get("response", response.get("text", "")),
                response.get("response_length", len(response.get("response", ""))),
                "pending",
                datetime.now()
            ))
            
        logger.info(f"Migrated {len(responses)} draft responses")
        
    def migrate_published(self, published_path: Path, tweet_mapping: Dict[str, int]):
        """Migrate published responses from published.json"""
        logger.info(f"Migrating published responses from {published_path}")
        
        if not published_path.exists():
            logger.warning(f"Published file not found: {published_path}")
            return
            
        with open(published_path) as f:
            published = json.load(f)
            
        for item in published:
            twitter_id = item.get("id", item.get("twitter_id", ""))
            if twitter_id not in tweet_mapping:
                logger.warning(f"Tweet {twitter_id} not found in mapping")
                continue
                
            db_id = tweet_mapping[twitter_id]
            
            # Update tweet status
            self.cursor.execute("""
                UPDATE tweets SET status = 'posted' WHERE id = %s
            """, (db_id,))
            
            # Update draft status if we can find it
            final_text = item.get("final_response", item.get("response", ""))
            self.cursor.execute("""
                UPDATE draft_replies 
                SET status = 'approved',
                    approved_at = %s,
                    posted_at = %s
                WHERE tweet_id = %s 
                AND text = %s
            """, (
                datetime.now(),
                datetime.now(),
                db_id,
                final_text
            ))
            
        logger.info(f"Migrated {len(published)} published responses")
        
    def migrate_artefacts(self, artefacts_dir: Path, episode_id: Optional[int] = None):
        """Migrate all run artefacts from timestamped directories"""
        logger.info(f"Migrating artefacts from {artefacts_dir}")
        
        if not artefacts_dir.exists():
            logger.warning(f"Artefacts directory not found: {artefacts_dir}")
            return
            
        # Process each timestamped run directory
        for run_dir in sorted(artefacts_dir.iterdir()):
            if not run_dir.is_dir():
                continue
                
            run_id = run_dir.name
            logger.info(f"Processing run: {run_id}")
            
            # Create pipeline run record
            self.cursor.execute("""
                INSERT INTO pipeline_runs (run_id, episode_id, stage, status, artifacts_path)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
            """, (run_id, episode_id, "complete", "completed", str(run_dir)))
            
            # Migrate data from this run
            tweet_mapping = self.migrate_tweets(run_dir / "tweets.json", episode_id)
            self.migrate_classifications(run_dir / "classified.json", tweet_mapping)
            self.migrate_responses(run_dir / "responses.json", tweet_mapping)
            
    def migrate_all(self, base_dir: Path):
        """Migrate all data from file system to database"""
        logger.info(f"Starting full migration from {base_dir}")
        
        transcripts_dir = base_dir / "transcripts"
        artefacts_dir = base_dir / "artefacts"
        
        # Migrate current episode data
        episode_id = None
        if transcripts_dir.exists():
            episode_id = self.migrate_episode_data(transcripts_dir)
            
            # Migrate current tweets
            tweet_mapping = self.migrate_tweets(transcripts_dir / "tweets.json", episode_id)
            self.migrate_classifications(transcripts_dir / "classified.json", tweet_mapping)
            self.migrate_responses(transcripts_dir / "responses.json", tweet_mapping) 
            self.migrate_published(transcripts_dir / "published.json", tweet_mapping)
        
        # Migrate historical artefacts
        self.migrate_artefacts(artefacts_dir, episode_id)
        
        logger.info("Migration completed successfully")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Migrate WDFWatch data to PostgreSQL")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch"),
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Base directory containing transcripts and artefacts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without committing changes"
    )
    
    args = parser.parse_args()
    
    try:
        with DataMigrator(args.db_url) as migrator:
            migrator.migrate_all(args.base_dir)
            
            if args.dry_run:
                logger.info("Dry run completed - rolling back changes")
                raise Exception("Dry run - rolling back")
                
    except Exception as e:
        if not args.dry_run or "Dry run" not in str(e):
            logger.error(f"Migration failed: {e}")
            sys.exit(1)
        else:
            logger.info("Dry run completed successfully")
            

if __name__ == "__main__":
    main()