#!/usr/bin/env python3
"""
Test version of data migration script that validates JSON structure
without requiring actual database connection
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import argparse

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataValidator:
    """Validates migration data without database connection"""
    
    def __init__(self):
        """Initialize validator"""
        self.errors = []
        self.warnings = []
        self.stats = {
            "episodes": 0,
            "tweets": 0,
            "keywords": 0,
            "classifications": 0,
            "drafts": 0,
            "published": 0,
            "runs": 0
        }
        
    def validate_episode_data(self, transcript_dir: Path) -> bool:
        """Validate episode data from transcript files"""
        logger.info(f"Validating episode data from {transcript_dir}")
        valid = True
        
        # Check podcast overview
        overview_path = transcript_dir / "podcast_overview.txt"
        if overview_path.exists():
            logger.info("✓ Found podcast_overview.txt")
        else:
            self.warnings.append("No podcast_overview.txt found")
            
        # Check summary
        summary_path = transcript_dir / "summary.md"
        if summary_path.exists():
            logger.info("✓ Found summary.md")
            self.stats["episodes"] += 1
        else:
            self.warnings.append("No summary.md found")
            
        # Check keywords
        keywords_path = transcript_dir / "keywords.json"
        if keywords_path.exists():
            try:
                with open(keywords_path) as f:
                    keywords = json.load(f)
                    if isinstance(keywords, list):
                        self.stats["keywords"] = len(keywords)
                        logger.info(f"✓ Found {len(keywords)} keywords")
                    else:
                        self.errors.append("keywords.json is not a list")
                        valid = False
            except json.JSONDecodeError as e:
                self.errors.append(f"Invalid JSON in keywords.json: {e}")
                valid = False
        else:
            self.warnings.append("No keywords.json found")
            
        return valid
        
    def validate_tweets(self, tweets_path: Path) -> Dict[str, Any]:
        """Validate tweets from JSON file"""
        logger.info(f"Validating tweets from {tweets_path}")
        tweet_mapping = {}
        
        if not tweets_path.exists():
            self.warnings.append(f"Tweets file not found: {tweets_path}")
            return tweet_mapping
            
        try:
            with open(tweets_path) as f:
                tweets = json.load(f)
                
            if not isinstance(tweets, list):
                self.errors.append(f"{tweets_path}: Expected list, got {type(tweets).__name__}")
                return tweet_mapping
                
            for i, tweet in enumerate(tweets):
                # Validate required fields
                tweet_id = tweet.get("id", tweet.get("twitter_id", ""))
                if not tweet_id:
                    self.errors.append(f"{tweets_path}: Tweet {i} missing id")
                    continue
                    
                if not tweet.get("text", tweet.get("full_text", "")):
                    self.errors.append(f"{tweets_path}: Tweet {tweet_id} missing text")
                    
                if not tweet.get("user", tweet.get("author_handle", "")):
                    self.errors.append(f"{tweets_path}: Tweet {tweet_id} missing user")
                    
                tweet_mapping[tweet_id] = tweet
                
            self.stats["tweets"] += len(tweet_mapping)
            logger.info(f"✓ Validated {len(tweet_mapping)} tweets")
            
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {tweets_path}: {e}")
            
        return tweet_mapping
        
    def validate_classifications(self, classified_path: Path, tweet_mapping: Dict[str, Any]):
        """Validate tweet classifications"""
        logger.info(f"Validating classifications from {classified_path}")
        
        if not classified_path.exists():
            self.warnings.append(f"Classifications file not found: {classified_path}")
            return
            
        try:
            with open(classified_path) as f:
                classifications = json.load(f)
                
            if not isinstance(classifications, list):
                self.errors.append(f"{classified_path}: Expected list")
                return
                
            for item in classifications:
                tweet_id = item.get("id", item.get("twitter_id", ""))
                if not tweet_id:
                    self.errors.append(f"{classified_path}: Classification missing tweet id")
                    continue
                    
                if tweet_id not in tweet_mapping:
                    self.warnings.append(f"{classified_path}: Tweet {tweet_id} not found in tweets")
                    
                classification = item.get("classification", "")
                if classification not in ["RELEVANT", "SKIP"]:
                    self.errors.append(f"{classified_path}: Invalid classification '{classification}' for tweet {tweet_id}")
                    
            self.stats["classifications"] += len(classifications)
            logger.info(f"✓ Validated {len(classifications)} classifications")
            
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {classified_path}: {e}")
            
    def validate_responses(self, responses_path: Path, tweet_mapping: Dict[str, Any]):
        """Validate draft responses"""
        logger.info(f"Validating responses from {responses_path}")
        
        if not responses_path.exists():
            self.warnings.append(f"Responses file not found: {responses_path}")
            return
            
        try:
            with open(responses_path) as f:
                responses = json.load(f)
                
            if not isinstance(responses, list):
                self.errors.append(f"{responses_path}: Expected list")
                return
                
            for response in responses:
                tweet_id = response.get("id", response.get("twitter_id", ""))
                if not tweet_id:
                    self.errors.append(f"{responses_path}: Response missing tweet id")
                    continue
                    
                if tweet_id not in tweet_mapping:
                    self.warnings.append(f"{responses_path}: Tweet {tweet_id} not found in tweets")
                    
                if not response.get("response", response.get("text", "")):
                    self.errors.append(f"{responses_path}: Response for tweet {tweet_id} missing text")
                    
                # Check response length
                response_text = response.get("response", response.get("text", ""))
                if len(response_text) > 280:
                    self.warnings.append(f"{responses_path}: Response for tweet {tweet_id} exceeds 280 chars ({len(response_text)})")
                    
            self.stats["drafts"] += len(responses)
            logger.info(f"✓ Validated {len(responses)} responses")
            
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {responses_path}: {e}")
            
    def validate_published(self, published_path: Path, tweet_mapping: Dict[str, Any]):
        """Validate published responses"""
        logger.info(f"Validating published from {published_path}")
        
        if not published_path.exists():
            logger.info("No published.json found (this is normal)")
            return
            
        try:
            with open(published_path) as f:
                published = json.load(f)
                
            if not isinstance(published, list):
                self.errors.append(f"{published_path}: Expected list")
                return
                
            for item in published:
                tweet_id = item.get("id", item.get("twitter_id", ""))
                if not tweet_id:
                    self.errors.append(f"{published_path}: Published item missing tweet id")
                    continue
                    
                if tweet_id not in tweet_mapping:
                    self.warnings.append(f"{published_path}: Tweet {tweet_id} not found in tweets")
                    
            self.stats["published"] += len(published)
            logger.info(f"✓ Validated {len(published)} published items")
            
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {published_path}: {e}")
            
    def validate_artefacts(self, artefacts_dir: Path):
        """Validate all run artefacts"""
        logger.info(f"Validating artefacts from {artefacts_dir}")
        
        if not artefacts_dir.exists():
            logger.info("No artefacts directory found")
            return
            
        # Process each timestamped run directory
        for run_dir in sorted(artefacts_dir.iterdir()):
            if not run_dir.is_dir():
                continue
                
            run_id = run_dir.name
            logger.info(f"\nValidating run: {run_id}")
            self.stats["runs"] += 1
            
            # Validate data from this run
            tweet_mapping = self.validate_tweets(run_dir / "tweets.json")
            self.validate_classifications(run_dir / "classified.json", tweet_mapping)
            self.validate_responses(run_dir / "responses.json", tweet_mapping)
            
    def validate_all(self, base_dir: Path):
        """Validate all data"""
        logger.info(f"Starting validation from {base_dir}")
        logger.info("="*60)
        
        transcripts_dir = base_dir / "transcripts"
        artefacts_dir = base_dir / "artefacts"
        
        # Validate current episode data
        if transcripts_dir.exists():
            self.validate_episode_data(transcripts_dir)
            
            # Validate current tweets
            tweet_mapping = self.validate_tweets(transcripts_dir / "tweets.json")
            self.validate_classifications(transcripts_dir / "classified.json", tweet_mapping)
            self.validate_responses(transcripts_dir / "responses.json", tweet_mapping)
            self.validate_published(transcripts_dir / "published.json", tweet_mapping)
        
        # Validate historical artefacts
        self.validate_artefacts(artefacts_dir)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("VALIDATION SUMMARY")
        logger.info("="*60)
        
        logger.info("\n📊 Statistics:")
        for key, value in self.stats.items():
            logger.info(f"  {key.capitalize()}: {value}")
            
        if self.warnings:
            logger.info(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings[:5]:  # Show first 5
                logger.info(f"  - {warning}")
            if len(self.warnings) > 5:
                logger.info(f"  ... and {len(self.warnings) - 5} more")
                
        if self.errors:
            logger.info(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors[:5]:  # Show first 5
                logger.info(f"  - {error}")
            if len(self.errors) > 5:
                logger.info(f"  ... and {len(self.errors) - 5} more")
        else:
            logger.info("\n✅ No errors found!")
            
        logger.info("\n" + "="*60)
        
        return len(self.errors) == 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate WDFWatch data for migration")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent.parent / "test_data",
        help="Base directory containing transcripts and artefacts"
    )
    
    args = parser.parse_args()
    
    validator = DataValidator()
    success = validator.validate_all(args.base_dir)
    
    if success:
        logger.info("\n✅ Data validation passed! Ready for migration.")
        sys.exit(0)
    else:
        logger.error("\n❌ Data validation failed. Please fix errors before migration.")
        sys.exit(1)
            

if __name__ == "__main__":
    main()