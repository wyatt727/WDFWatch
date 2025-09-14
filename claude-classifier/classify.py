#!/usr/bin/env python3
"""
Claude-based tweet classification without few-shots.
Directly classifies tweets using Claude's reasoning capabilities.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import argparse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path configuration
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
CLAUDE_MD = SCRIPT_DIR / "CLAUDE.md"
EPISODE_CONTEXT_FILE = SCRIPT_DIR / "EPISODE_CONTEXT.md"

class ClaudeClassifier:
    """Direct tweet classification using Claude's reasoning."""
    
    def __init__(self, episode_id: str = None):
        """Initialize classifier with optional episode context."""
        self.episode_id = episode_id
        self.episode_context = ""
        
        # Verify CLAUDE.md exists
        if not CLAUDE_MD.exists():
            raise FileNotFoundError(f"CLAUDE.md not found at {CLAUDE_MD}")
        
        # Load episode context if available
        self.load_episode_context()
    
    def load_episode_context(self):
        """Load episode-specific context from summary if available."""
        if self.episode_id and EPISODE_CONTEXT_FILE.exists():
            self.episode_context = EPISODE_CONTEXT_FILE.read_text()
            logger.info(f"Loaded episode context for {self.episode_id}")
        elif self.episode_id:
            # Try to extract from existing summary
            self.extract_episode_context()
    
    def extract_episode_context(self):
        """Extract key points from episode summary for classification."""
        summary_path = PARENT_DIR / "transcripts" / "summary.md"
        if not summary_path.exists():
            logger.warning("No summary found for episode context")
            return
        
        summary = summary_path.read_text()
        
        # Extract key sections for classification context
        context_parts = ["# Current Episode Context\n"]
        
        # Extract guest info
        if "guest" in summary.lower():
            lines = summary.split('\n')
            for i, line in enumerate(lines):
                if "guest" in line.lower() and i < len(lines) - 1:
                    context_parts.append(f"## Guest: {lines[i+1].strip()}\n")
                    break
        
        # Extract main topics (first few key points)
        context_parts.append("\n## Main Topics:\n")
        key_topics = []
        for line in summary.split('\n'):
            if line.strip() and not line.startswith('#'):
                # Look for substantive content lines
                if any(word in line.lower() for word in 
                       ['discusses', 'explains', 'argues', 'proposes', 'explores']):
                    key_topics.append(f"- {line.strip()}")
                    if len(key_topics) >= 5:
                        break
        context_parts.extend(key_topics)
        
        # Extract keywords if available
        keywords_path = PARENT_DIR / "transcripts" / "keywords.json"
        if keywords_path.exists():
            keywords = json.loads(keywords_path.read_text())
            context_parts.append(f"\n## Keywords: {', '.join(keywords[:10])}\n")
        
        self.episode_context = '\n'.join(context_parts)
        
        # Save for future use
        EPISODE_CONTEXT_FILE.write_text(self.episode_context)
        logger.info(f"Extracted episode context ({len(self.episode_context)} chars)")
    
    def classify_tweet(self, tweet_text: str, with_reasoning: bool = False) -> Dict:
        """
        Classify a single tweet using Claude.
        
        Args:
            tweet_text: The tweet to classify
            with_reasoning: Include reasoning explanation
            
        Returns:
            Dict with score and optionally reasoning
        """
        # Build prompt
        if with_reasoning:
            prompt = f"""Based on the podcast context and classification criteria, score this tweet's relevance and explain why.

Tweet: {tweet_text}

Format your response as:
SCORE: [0.00-1.00]
REASON: [One sentence explanation]"""
        else:
            prompt = f"""Based on the podcast context and classification criteria, score this tweet's relevance from 0.00 to 1.00.

Tweet: {tweet_text}

Output only the numerical score:"""
        
        # Add episode context if available
        if self.episode_context:
            prompt = f"{self.episode_context}\n\n{prompt}"
        
        # Call Claude
        result = self._call_claude(prompt)
        
        # Parse result
        if with_reasoning:
            return self._parse_score_and_reason(result)
        else:
            try:
                score = float(result.strip())
                return {"score": score, "classification": "RELEVANT" if score >= 0.70 else "SKIP"}
            except ValueError:
                logger.error(f"Failed to parse score: {result}")
                return {"score": 0.0, "classification": "SKIP", "error": "Parse error"}
    
    def classify_batch(self, tweets: List[str], batch_size: int = 20) -> List[Dict]:
        """
        Classify multiple tweets efficiently in batches.
        
        Args:
            tweets: List of tweet texts
            batch_size: Number of tweets per Claude call
            
        Returns:
            List of classification results
        """
        results = []
        total_batches = (len(tweets) + batch_size - 1) // batch_size
        
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i+batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} tweets)")
            
            # Build batch prompt
            tweet_list = '\n'.join([f"{j+1}. {tweet}" for j, tweet in enumerate(batch)])
            prompt = f"""Score each tweet from 0.00 to 1.00 based on relevance to the WDF podcast.
Output one score per line, in order, with no other text.

TWEETS:
{tweet_list}

SCORES (one per line):"""
            
            # Add episode context if available
            if self.episode_context:
                prompt = f"{self.episode_context}\n\n{prompt}"
            
            # Call Claude
            response = self._call_claude(prompt)
            
            # Parse scores
            scores = self._parse_batch_scores(response, len(batch))
            
            # Create results
            for tweet, score in zip(batch, scores):
                results.append({
                    "text": tweet,
                    "score": score,
                    "classification": "RELEVANT" if score >= 0.70 else "SKIP"
                })
        
        return results
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI with the given prompt."""
        try:
            # Write prompt to temp file to avoid shell escaping issues
            temp_prompt = SCRIPT_DIR / ".temp_prompt.txt"
            temp_prompt.write_text(prompt)
            
            # Build command
            cmd = [
                "claude",
                "--model", "sonnet",
                "--print",
                f"@{CLAUDE_MD}",
                f"@{temp_prompt}"
            ]
            
            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=SCRIPT_DIR
            )
            
            # Clean up temp file
            temp_prompt.unlink(missing_ok=True)
            
            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return "0.00"  # Default to not relevant on error
            
            return result.stdout.strip()
            
        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return "0.00"
    
    def _parse_score_and_reason(self, response: str) -> Dict:
        """Parse score and reasoning from Claude response."""
        try:
            lines = response.strip().split('\n')
            score_line = next((l for l in lines if l.startswith("SCORE:")), None)
            reason_line = next((l for l in lines if l.startswith("REASON:")), None)
            
            if score_line:
                score = float(score_line.replace("SCORE:", "").strip())
            else:
                score = 0.0
            
            reason = reason_line.replace("REASON:", "").strip() if reason_line else ""
            
            return {
                "score": score,
                "classification": "RELEVANT" if score >= 0.70 else "SKIP",
                "reason": reason
            }
        except Exception as e:
            logger.error(f"Error parsing score and reason: {e}")
            return {"score": 0.0, "classification": "SKIP", "error": str(e)}
    
    def _parse_batch_scores(self, response: str, expected_count: int) -> List[float]:
        """Parse batch scores from Claude response."""
        scores = []
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line:
                try:
                    score = float(line)
                    scores.append(max(0.0, min(1.0, score)))  # Clamp to [0, 1]
                except ValueError:
                    logger.warning(f"Skipping invalid score: {line}")
        
        # Ensure we have the right number of scores
        while len(scores) < expected_count:
            logger.warning(f"Missing score, adding default 0.0")
            scores.append(0.0)
        
        return scores[:expected_count]


def process_file(input_file: Path, output_file: Path, 
                 episode_id: str = None, with_reasoning: bool = False,
                 batch_size: int = 20) -> Dict:
    """
    Process tweets from file and save classifications.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file
        episode_id: Optional episode ID for context
        with_reasoning: Include reasoning for each classification
        batch_size: Number of tweets per batch
        
    Returns:
        Statistics about the classification
    """
    # Load tweets
    logger.info(f"Loading tweets from {input_file}")
    with open(input_file) as f:
        data = json.load(f)
    
    # Handle different input formats
    if isinstance(data, list):
        tweets = data
    elif isinstance(data, dict) and 'tweets' in data:
        tweets = data['tweets']
    else:
        raise ValueError("Invalid input format")
    
    # Initialize classifier
    classifier = ClaudeClassifier(episode_id)
    
    # Extract tweet texts
    tweet_texts = []
    for tweet in tweets:
        if isinstance(tweet, str):
            tweet_texts.append(tweet)
        elif isinstance(tweet, dict):
            tweet_texts.append(tweet.get('text', tweet.get('full_text', '')))
    
    # Classify tweets
    logger.info(f"Classifying {len(tweet_texts)} tweets")
    
    if with_reasoning:
        # Process individually for reasoning
        results = []
        for i, text in enumerate(tweet_texts):
            logger.info(f"Classifying tweet {i+1}/{len(tweet_texts)}")
            result = classifier.classify_tweet(text, with_reasoning=True)
            result['text'] = text
            results.append(result)
    else:
        # Batch process for efficiency
        results = classifier.classify_batch(tweet_texts, batch_size)
    
    # Add classifications back to original tweets
    for i, tweet in enumerate(tweets):
        if isinstance(tweet, dict):
            tweet['relevance_score'] = results[i]['score']
            tweet['classification'] = results[i]['classification']
            if 'reason' in results[i]:
                tweet['classification_reason'] = results[i]['reason']
        else:
            # Convert to dict format
            tweets[i] = {
                'text': tweet,
                'relevance_score': results[i]['score'],
                'classification': results[i]['classification']
            }
            if 'reason' in results[i]:
                tweets[i]['classification_reason'] = results[i]['reason']
    
    # Calculate statistics
    relevant_count = sum(1 for r in results if r['classification'] == 'RELEVANT')
    skip_count = len(results) - relevant_count
    avg_score = sum(r['score'] for r in results) / len(results) if results else 0
    
    stats = {
        'total_tweets': len(results),
        'relevant': relevant_count,
        'skip': skip_count,
        'average_score': round(avg_score, 3),
        'relevant_percentage': round(relevant_count / len(results) * 100, 1) if results else 0
    }
    
    # Save output
    output_data = {
        'episode_id': episode_id,
        'classification_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'stats': stats,
        'tweets': tweets
    }
    
    logger.info(f"Saving results to {output_file}")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Print summary
    logger.info(f"Classification complete:")
    logger.info(f"  Total tweets: {stats['total_tweets']}")
    logger.info(f"  Relevant: {stats['relevant']} ({stats['relevant_percentage']}%)")
    logger.info(f"  Skip: {stats['skip']}")
    logger.info(f"  Average score: {stats['average_score']}")
    
    return stats


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Classify tweets using Claude without few-shots"
    )
    
    # Mode selection
    parser.add_argument(
        'mode', 
        choices=['single', 'batch', 'file'],
        help="Classification mode"
    )
    
    # Input options
    parser.add_argument(
        '--tweet', '-t',
        help="Tweet text to classify (single mode)"
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        help="Input JSON file (file mode)"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help="Output JSON file (file mode)"
    )
    
    # Options
    parser.add_argument(
        '--episode-id', '-e',
        help="Episode ID for context"
    )
    parser.add_argument(
        '--with-reasoning', '-r',
        action='store_true',
        help="Include reasoning for each classification"
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=20,
        help="Batch size for processing (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Initialize classifier
    classifier = ClaudeClassifier(args.episode_id)
    
    if args.mode == 'single':
        if not args.tweet:
            parser.error("Single mode requires --tweet")
        
        result = classifier.classify_tweet(args.tweet, args.with_reasoning)
        print(json.dumps(result, indent=2))
    
    elif args.mode == 'batch':
        # Read tweets from stdin
        tweets = []
        print("Enter tweets (one per line, empty line to finish):")
        while True:
            line = input().strip()
            if not line:
                break
            tweets.append(line)
        
        if tweets:
            results = classifier.classify_batch(tweets, args.batch_size)
            print(json.dumps(results, indent=2))
    
    elif args.mode == 'file':
        if not args.input or not args.output:
            parser.error("File mode requires --input and --output")
        
        stats = process_file(
            args.input, 
            args.output,
            args.episode_id,
            args.with_reasoning,
            args.batch_size
        )


if __name__ == "__main__":
    main()