#!/usr/bin/env python3
"""
Claude Classification Task - Pipeline integration for direct Claude classification.
Replaces few-shot generation and classification with direct Claude reasoning.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List
import logging

# Add claude-classifier to path
CLAUDE_CLASSIFIER_DIR = Path(__file__).parent.parent.parent.parent / "claude-classifier"
sys.path.insert(0, str(CLAUDE_CLASSIFIER_DIR))

from classify import ClaudeClassifier
from episode_memory import EpisodeMemory

# Conditional imports for web bridge
try:
    from src.wdf.web_bridge import WebBridge
    web_bridge = WebBridge()
except ImportError:
    web_bridge = None

logger = logging.getLogger(__name__)

def run(
    run_id: str = None,
    episode_id: str = None,
    use_memory: bool = True,
    batch_size: int = 20
) -> Path:
    """
    Run Claude classification task as part of the pipeline.
    
    This replaces BOTH:
    1. Few-shot generation (fewshot.py)
    2. Tweet classification (classify.py)
    
    Args:
        run_id: Unique run identifier
        episode_id: Episode identifier for memory
        use_memory: Whether to use episode memory for context
        batch_size: Number of tweets per Claude call
        
    Returns:
        Path to classified tweets file
    """
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    logger.info(f"Starting Claude classification for run {run_id}")
    
    # Set up paths
    base_dir = Path(__file__).parent.parent.parent.parent
    transcripts_dir = base_dir / "transcripts"
    artefacts_dir = base_dir / "artefacts" / run_id
    artefacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Input and output files
    tweets_file = transcripts_dir / "tweets.json"
    classified_file = transcripts_dir / "classified.json"
    artefact_classified = artefacts_dir / "classified.json"
    
    # Check for input
    if not tweets_file.exists():
        logger.error(f"No tweets file found at {tweets_file}")
        return classified_file
    
    # Load tweets
    with open(tweets_file) as f:
        tweets_data = json.load(f)
    
    if isinstance(tweets_data, dict):
        tweets = tweets_data.get('tweets', [])
    else:
        tweets = tweets_data
    
    logger.info(f"Loaded {len(tweets)} tweets for classification")
    
    # Initialize episode memory if requested
    memory = None
    if use_memory:
        if not episode_id:
            # Generate episode ID from transcript
            transcript_path = transcripts_dir / "latest.txt"
            if transcript_path.exists():
                import hashlib
                content = transcript_path.read_text()
                episode_id = hashlib.md5(content.encode()).hexdigest()[:8]
            else:
                episode_id = run_id
        
        memory = EpisodeMemory(episode_id)
        
        # Check if memory exists from summarization
        if 'summarization' in memory.memory.get('stages_completed', []):
            logger.info(f"Using existing episode memory for {episode_id}")
            # Write context file for classifier
            context_file = CLAUDE_CLASSIFIER_DIR / "EPISODE_CONTEXT.md"
            context_file.write_text(f"""# Current Episode Context

{memory.get_classification_context()}

## Classification Focus
Focus on tweets that relate to the themes and controversies discussed in this specific episode.
Give higher scores to tweets that directly engage with the guest's arguments or proposed solutions.
""")
        else:
            logger.warning("No episode memory found, classifying without episode context")
            # Still try to extract from summary if available
            _extract_minimal_context(transcripts_dir)
    
    # Initialize Claude classifier
    classifier = ClaudeClassifier(episode_id)
    
    # Extract tweet texts
    tweet_texts = []
    for tweet in tweets:
        if isinstance(tweet, dict):
            text = tweet.get('text', tweet.get('full_text', ''))
        else:
            text = str(tweet)
        tweet_texts.append(text)
    
    # Classify tweets in batches
    logger.info(f"Classifying {len(tweet_texts)} tweets with Claude (batch size: {batch_size})")
    
    if web_bridge:
        web_bridge.send_event({
            'type': 'classification_started',
            'run_id': run_id,
            'episode_id': episode_id,
            'tweet_count': len(tweet_texts),
            'using_memory': use_memory
        })
    
    start_time = time.time()
    results = classifier.classify_batch(tweet_texts, batch_size)
    elapsed_time = time.time() - start_time
    
    # Merge results back into tweet objects
    for i, tweet in enumerate(tweets):
        if i < len(results):
            result = results[i]
            if isinstance(tweet, dict):
                tweet['relevance_score'] = result['score']
                tweet['classification'] = result['classification']
                tweet['classification_method'] = 'claude_direct'
            else:
                # Convert to dict
                tweets[i] = {
                    'text': tweet,
                    'relevance_score': result['score'],
                    'classification': result['classification'],
                    'classification_method': 'claude_direct'
                }
    
    # Calculate statistics
    relevant_tweets = [t for t in tweets if t.get('classification') == 'RELEVANT']
    skip_tweets = [t for t in tweets if t.get('classification') == 'SKIP']
    avg_score = sum(t.get('relevance_score', 0) for t in tweets) / len(tweets) if tweets else 0
    
    stats = {
        'total_tweets': len(tweets),
        'relevant': len(relevant_tweets),
        'skip': len(skip_tweets),
        'average_score': round(avg_score, 3),
        'relevant_percentage': round(len(relevant_tweets) / len(tweets) * 100, 1) if tweets else 0,
        'classification_time_seconds': round(elapsed_time, 2),
        'tweets_per_second': round(len(tweets) / elapsed_time, 2) if elapsed_time > 0 else 0,
        'method': 'claude_direct',
        'used_memory': use_memory,
        'episode_id': episode_id
    }
    
    # Prepare output
    output = {
        'run_id': run_id,
        'episode_id': episode_id,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'stats': stats,
        'tweets': tweets
    }
    
    # Save to both locations
    with open(classified_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    with open(artefact_classified, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Update web UI if available
    if web_bridge:
        web_bridge.send_event({
            'type': 'classification_complete',
            'run_id': run_id,
            'episode_id': episode_id,
            'stats': stats
        })
        
        # Update tweet classifications in database
        for tweet in relevant_tweets[:10]:  # Update top 10 relevant tweets
            web_bridge.update_tweet_classification(
                tweet_id=tweet.get('id'),
                score=tweet.get('relevance_score'),
                classification=tweet.get('classification')
            )
    
    # Mark stage complete in memory
    if memory:
        memory.mark_stage_complete('classification')
    
    # Log summary
    logger.info("=" * 60)
    logger.info("CLAUDE CLASSIFICATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total tweets: {stats['total_tweets']}")
    logger.info(f"Relevant: {stats['relevant']} ({stats['relevant_percentage']}%)")
    logger.info(f"Skip: {stats['skip']}")
    logger.info(f"Average score: {stats['average_score']}")
    logger.info(f"Time: {stats['classification_time_seconds']}s")
    logger.info(f"Speed: {stats['tweets_per_second']} tweets/sec")
    logger.info("=" * 60)
    
    if stats['relevant'] == 0:
        logger.warning("No relevant tweets found! Check classification criteria.")
    elif stats['relevant_percentage'] < 5:
        logger.warning(f"Very low relevance rate ({stats['relevant_percentage']}%). Consider adjusting criteria.")
    elif stats['relevant_percentage'] > 50:
        logger.warning(f"Very high relevance rate ({stats['relevant_percentage']}%). May be too permissive.")
    
    return classified_file


def _extract_minimal_context(transcripts_dir: Path):
    """Extract minimal context from existing files if no memory exists."""
    context_parts = []
    
    # Try to get summary
    summary_file = transcripts_dir / "summary.md"
    if summary_file.exists():
        summary = summary_file.read_text()
        # Extract first paragraph
        lines = summary.split('\n')
        for line in lines[:10]:
            if line.strip() and not line.startswith('#'):
                context_parts.append(line.strip())
                break
    
    # Try to get keywords
    keywords_file = transcripts_dir / "keywords.json"
    if keywords_file.exists():
        keywords = json.loads(keywords_file.read_text())
        context_parts.append(f"Keywords: {', '.join(keywords[:10])}")
    
    if context_parts:
        context_file = CLAUDE_CLASSIFIER_DIR / "EPISODE_CONTEXT.md"
        context_file.write_text(f"""# Episode Context (Minimal)

{chr(10).join(context_parts)}

Note: Full episode memory not available. Using minimal context from existing files.
""")


def compare_with_fewshot(run_id: str = None) -> Dict:
    """
    Compare Claude direct classification with few-shot classification.
    Useful for validation and tuning.
    """
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    base_dir = Path(__file__).parent.parent.parent.parent
    
    # Run comparison script
    compare_script = CLAUDE_CLASSIFIER_DIR / "compare.py"
    if compare_script.exists():
        cmd = [
            sys.executable,
            str(compare_script),
            "--input", str(base_dir / "transcripts" / "tweets.json"),
            "--output", str(base_dir / "artefacts" / run_id / "classification_comparison.json")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Load and return comparison results
            comparison_file = base_dir / "artefacts" / run_id / "classification_comparison.json"
            if comparison_file.exists():
                with open(comparison_file) as f:
                    return json.load(f)
    
    return {}


# CLI usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude classification task")
    parser.add_argument("--run-id", help="Run identifier")
    parser.add_argument("--episode-id", help="Episode identifier")
    parser.add_argument("--no-memory", action="store_true", help="Don't use episode memory")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size")
    parser.add_argument("--compare", action="store_true", help="Compare with few-shot")
    
    args = parser.parse_args()
    
    if args.compare:
        results = compare_with_fewshot(args.run_id)
        print(json.dumps(results, indent=2))
    else:
        output_file = run(
            run_id=args.run_id,
            episode_id=args.episode_id,
            use_memory=not args.no_memory,
            batch_size=args.batch_size
        )
        print(f"Classification complete: {output_file}")