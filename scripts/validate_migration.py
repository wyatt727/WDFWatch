#!/usr/bin/env python3
"""
Validation script to ensure data consistency between files and database
Compares counts and key data points after migration
Interacts with: JSON files in transcripts/, PostgreSQL database
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationValidator:
    """Validates data consistency after migration"""
    
    def __init__(self, db_url: str):
        """Initialize with database connection"""
        self.db_url = db_url
        self.conn = None
        self.cursor = None
        self.errors = []
        self.warnings = []
        
    def __enter__(self):
        """Connect to database"""
        self.conn = psycopg2.connect(self.db_url)
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection"""
        if self.conn:
            self.cursor.close()
            self.conn.close()
            
    def validate_tweet_counts(self, transcripts_dir: Path) -> bool:
        """Validate tweet counts match between files and database"""
        logger.info("Validating tweet counts...")
        
        # Count tweets in JSON files
        json_count = 0
        tweets_path = transcripts_dir / "tweets.json"
        if tweets_path.exists():
            with open(tweets_path) as f:
                tweets = json.load(f)
                json_count = len(tweets)
                
        # Count tweets in database
        self.cursor.execute("SELECT COUNT(*) as count FROM tweets")
        db_count = self.cursor.fetchone()["count"]
        
        if json_count != db_count:
            self.errors.append(
                f"Tweet count mismatch: JSON has {json_count}, DB has {db_count}"
            )
            return False
            
        logger.info(f"✓ Tweet counts match: {json_count}")
        return True
        
    def validate_classifications(self, transcripts_dir: Path) -> bool:
        """Validate classification data consistency"""
        logger.info("Validating classifications...")
        
        classified_path = transcripts_dir / "classified.json"
        if not classified_path.exists():
            logger.warning("No classified.json found to validate")
            return True
            
        with open(classified_path) as f:
            classifications = json.load(f)
            
        # Group by classification
        json_counts = defaultdict(int)
        for item in classifications:
            classification = item.get("classification", "UNKNOWN")
            json_counts[classification] += 1
            
        # Get database counts
        self.cursor.execute("""
            SELECT 
                CASE 
                    WHEN status = 'relevant' THEN 'RELEVANT'
                    WHEN status = 'skipped' THEN 'SKIP'
                    ELSE 'UNCLASSIFIED'
                END as classification,
                COUNT(*) as count
            FROM tweets
            WHERE status IN ('relevant', 'skipped')
            GROUP BY status
        """)
        
        db_counts = defaultdict(int)
        for row in self.cursor.fetchall():
            db_counts[row["classification"]] = row["count"]
            
        # Compare counts
        all_classifications = set(json_counts.keys()) | set(db_counts.keys())
        for classification in all_classifications:
            json_val = json_counts.get(classification, 0)
            db_val = db_counts.get(classification, 0)
            
            if json_val != db_val:
                self.errors.append(
                    f"Classification count mismatch for {classification}: "
                    f"JSON has {json_val}, DB has {db_val}"
                )
                
        logger.info(f"✓ Validated {len(classifications)} classifications")
        return len(self.errors) == 0
        
    def validate_drafts(self, transcripts_dir: Path) -> bool:
        """Validate draft responses consistency"""
        logger.info("Validating draft responses...")
        
        responses_path = transcripts_dir / "responses.json"
        if not responses_path.exists():
            logger.warning("No responses.json found to validate")
            return True
            
        with open(responses_path) as f:
            responses = json.load(f)
            
        # Check each response exists in database
        missing_drafts = []
        for response in responses:
            twitter_id = response.get("id", response.get("twitter_id", ""))
            response_text = response.get("response", response.get("text", ""))
            
            self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM draft_replies dr
                JOIN tweets t ON dr.tweet_id = t.id
                WHERE t.twitter_id = %s
                AND dr.text = %s
            """, (twitter_id, response_text))
            
            count = self.cursor.fetchone()["count"]
            if count == 0:
                missing_drafts.append(twitter_id)
                
        if missing_drafts:
            self.errors.append(
                f"Missing drafts in database for tweets: {missing_drafts[:5]}..."
            )
            
        logger.info(f"✓ Validated {len(responses)} draft responses")
        return len(missing_drafts) == 0
        
    def validate_published(self, transcripts_dir: Path) -> bool:
        """Validate published responses"""
        logger.info("Validating published responses...")
        
        published_path = transcripts_dir / "published.json"
        if not published_path.exists():
            logger.warning("No published.json found to validate")
            return True
            
        with open(published_path) as f:
            published = json.load(f)
            
        # Check each published tweet has correct status
        mismatched_status = []
        for item in published:
            twitter_id = item.get("id", item.get("twitter_id", ""))
            
            self.cursor.execute("""
                SELECT status
                FROM tweets
                WHERE twitter_id = %s
            """, (twitter_id,))
            
            result = self.cursor.fetchone()
            if not result:
                self.errors.append(f"Published tweet {twitter_id} not found in database")
            elif result["status"] != "posted":
                mismatched_status.append(twitter_id)
                
        if mismatched_status:
            self.warnings.append(
                f"Status mismatch for published tweets: {mismatched_status[:5]}..."
            )
            
        logger.info(f"✓ Validated {len(published)} published responses")
        return True
        
    def validate_data_integrity(self) -> bool:
        """Validate database integrity constraints"""
        logger.info("Validating data integrity...")
        
        # Check for orphaned drafts
        self.cursor.execute("""
            SELECT COUNT(*) as count
            FROM draft_replies dr
            LEFT JOIN tweets t ON dr.tweet_id = t.id
            WHERE t.id IS NULL
        """)
        orphaned_drafts = self.cursor.fetchone()["count"]
        if orphaned_drafts > 0:
            self.errors.append(f"Found {orphaned_drafts} orphaned drafts")
            
        # Check for tweets without text
        self.cursor.execute("""
            SELECT COUNT(*) as count
            FROM tweets
            WHERE full_text IS NULL OR full_text = ''
        """)
        empty_tweets = self.cursor.fetchone()["count"]
        if empty_tweets > 0:
            self.errors.append(f"Found {empty_tweets} tweets without text")
            
        # Check for invalid status values
        self.cursor.execute("""
            SELECT DISTINCT status
            FROM tweets
            WHERE status NOT IN ('unclassified', 'relevant', 'skipped', 'drafted', 'posted')
        """)
        invalid_statuses = [row["status"] for row in self.cursor.fetchall()]
        if invalid_statuses:
            self.errors.append(f"Found invalid tweet statuses: {invalid_statuses}")
            
        logger.info("✓ Data integrity checks completed")
        return len(self.errors) == 0
        
    def generate_summary_report(self) -> Dict:
        """Generate summary statistics from database"""
        logger.info("Generating summary report...")
        
        report = {}
        
        # Tweet statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT author_handle) as unique_authors,
                COUNT(*) FILTER (WHERE status = 'relevant') as relevant,
                COUNT(*) FILTER (WHERE status = 'skipped') as skipped,
                COUNT(*) FILTER (WHERE status = 'posted') as posted
            FROM tweets
        """)
        report["tweets"] = dict(self.cursor.fetchone())
        
        # Draft statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                COUNT(DISTINCT model_name) as models_used
            FROM draft_replies
        """)
        report["drafts"] = dict(self.cursor.fetchone())
        
        # Episode statistics
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'keywords_ready') as with_keywords
            FROM podcast_episodes
        """)
        report["episodes"] = dict(self.cursor.fetchone())
        
        return report
        
    def validate_all(self, base_dir: Path) -> bool:
        """Run all validation checks"""
        logger.info(f"Starting validation for {base_dir}")
        
        transcripts_dir = base_dir / "transcripts"
        
        # Run validations
        validations = [
            self.validate_tweet_counts(transcripts_dir),
            self.validate_classifications(transcripts_dir),
            self.validate_drafts(transcripts_dir),
            self.validate_published(transcripts_dir),
            self.validate_data_integrity()
        ]
        
        # Generate report
        report = self.generate_summary_report()
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("VALIDATION SUMMARY")
        logger.info("="*60)
        
        if self.errors:
            logger.error(f"Found {len(self.errors)} errors:")
            for error in self.errors:
                logger.error(f"  ❌ {error}")
                
        if self.warnings:
            logger.warning(f"Found {len(self.warnings)} warnings:")
            for warning in self.warnings:
                logger.warning(f"  ⚠️  {warning}")
                
        logger.info("\nDatabase Statistics:")
        logger.info(f"  Episodes: {report['episodes']['total']}")
        logger.info(f"  Tweets: {report['tweets']['total']} "
                   f"(relevant: {report['tweets']['relevant']}, "
                   f"posted: {report['tweets']['posted']})")
        logger.info(f"  Drafts: {report['drafts']['total']} "
                   f"(pending: {report['drafts']['pending']})")
        
        success = all(validations) and len(self.errors) == 0
        
        if success:
            logger.info("\n✅ All validations passed!")
        else:
            logger.error("\n❌ Validation failed!")
            
        return success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate WDFWatch data migration")
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
    
    args = parser.parse_args()
    
    try:
        with MigrationValidator(args.db_url) as validator:
            success = validator.validate_all(args.base_dir)
            sys.exit(0 if success else 1)
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)
        

if __name__ == "__main__":
    main()