#!/usr/bin/env python3
"""
Claude Tweet Classifier Wrapper

This script provides a wrapper around tweet classification using Claude,
allowing it to be used instead of Ollama/Gemma when configured.

It maintains compatibility with the existing classifier by:
1. Reading the same input files
2. Producing the same output format
3. Supporting the same command-line options

Usage:
    python scripts/claude_classifier.py --input-file tweets.txt --summary-file summary.md
    
This can be called from tweet_classifier.py when Claude is selected.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import logging

# Get Claude command builder
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.wdf.claude_config import build_claude_command

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def load_few_shot_examples() -> List[Tuple[str, str]]:
    """Load few-shot examples from JSON file"""
    fewshots_path = Path("transcripts/fewshots.json")
    if fewshots_path.exists():
        with open(fewshots_path, 'r') as f:
            examples = json.load(f)
            # Convert to tuples of (tweet, label)
            return [(ex[0], ex[1]) for ex in examples[:5]]  # Use only 5 examples
    return []

def build_classification_prompt(tweet: str, summary: str, examples: List[Tuple[str, str]]) -> str:
    """Build the Claude classification prompt"""
    prompt = f"""You are an expert at scoring tweet relevancy for the "War, Divorce, or Federalism" podcast.

Based on the podcast summary and few-shot examples, score this tweet's relevance from 0.00 to 1.00.

SCORING GUIDELINES:
- 0.85-1.00: Highly relevant - directly discusses podcast themes
- 0.70-0.84: Relevant - relates to topic, good for engagement  
- 0.30-0.69: Somewhat relevant - tangentially related
- 0.00-0.29: Not relevant - unrelated to podcast

PODCAST SUMMARY:
{summary[:1000]}  # Limit summary length

FEW-SHOT EXAMPLES:
"""
    
    for tweet_ex, label in examples:
        score = "0.85" if label == "RELEVANT" else "0.15"
        prompt += f"Tweet: {tweet_ex}\nScore: {score}\n\n"
    
    prompt += f"""TWEET TO CLASSIFY:
{tweet}

Reply with ONLY a decimal number between 0.00 and 1.00 (e.g., 0.85, 0.42, 1.00).
Do not include any other text or explanation."""
    
    return prompt

def classify_tweet_with_claude(tweet: str, summary: str, examples: List[Tuple[str, str]]) -> float:
    """Classify a single tweet using Claude"""
    prompt = build_classification_prompt(tweet, summary, examples)
    
    try:
        # Call Claude CLI with optimized no-MCP config
        result = subprocess.run(
            build_claude_command(prompt),
            capture_output=True,
            text=True,
            timeout=10  # Should complete in ~7 seconds with no-MCP config
        )
        
        if result.returncode != 0:
            logger.error(f"Claude CLI failed: {result.stderr}")
            return 0.50  # Default middle score on error
        
        # Parse the score from response
        response = result.stdout.strip()
        
        # Try to extract just the number
        import re
        numbers = re.findall(r'\d+\.\d+', response)
        if numbers:
            score = float(numbers[0])
            return max(0.0, min(1.0, score))  # Clamp to valid range
        
        logger.warning(f"Could not parse score from: {response}")
        return 0.50
        
    except subprocess.TimeoutExpired:
        logger.error("Claude request timed out")
        return 0.50
    except Exception as e:
        logger.error(f"Error calling Claude: {e}")
        return 0.50

def classify_tweets_batch(tweets: List[str], summary: str, examples: List[Tuple[str, str]]) -> List[float]:
    """Classify multiple tweets"""
    scores = []
    total = len(tweets)
    
    for i, tweet in enumerate(tweets, 1):
        logger.info(f"Classifying tweet {i}/{total}")
        score = classify_tweet_with_claude(tweet, summary, examples)
        scores.append(score)
        
    return scores

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Classify tweets using Claude")
    parser.add_argument("--input-file", type=str, required=True, help="Input file with tweets")
    parser.add_argument("--summary-file", type=str, help="Podcast summary file")
    parser.add_argument("--output-file", type=str, help="Output file for results")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (ignored for Claude)")
    
    args = parser.parse_args()
    
    # Load tweets
    tweets = []
    with open(args.input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                tweets.append(line)
    
    if not tweets:
        logger.error("No tweets found in input file")
        sys.exit(1)
    
    # Load summary if provided
    summary = ""
    if args.summary_file and Path(args.summary_file).exists():
        with open(args.summary_file, 'r') as f:
            summary = f.read()
    
    # Load few-shot examples
    examples = load_few_shot_examples()
    
    logger.info(f"Classifying {len(tweets)} tweets with Claude")
    
    # Classify tweets
    scores = classify_tweets_batch(tweets, summary, examples)
    
    # Prepare results
    results = []
    for tweet, score in zip(tweets, scores):
        classification = "RELEVANT" if score >= 0.70 else "SKIP"
        results.append({
            "text": tweet,
            "relevance_score": score,
            "classification": classification
        })
    
    # Output results
    if args.output_file:
        with open(args.output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output_file}")
    else:
        # Print to stdout
        for result in results:
            print(f"{result['relevance_score']:.2f}\t{result['classification']}\t{result['text']}")
    
    # Summary statistics
    relevant = sum(1 for r in results if r['classification'] == 'RELEVANT')
    logger.info(f"Classification complete: {relevant}/{len(results)} relevant")

if __name__ == "__main__":
    main()