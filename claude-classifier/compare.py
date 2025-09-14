#!/usr/bin/env python3
"""
Compare Claude direct classification with few-shot based classification.
Validates accuracy, consistency, and cost differences.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
import argparse
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the Claude classifier
from classify import ClaudeClassifier

class ClassificationComparator:
    """Compare different classification methods."""
    
    def __init__(self, episode_id: str = None):
        """Initialize comparator with episode context."""
        self.episode_id = episode_id
        self.parent_dir = Path(__file__).parent.parent
        self.claude_classifier = ClaudeClassifier(episode_id)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'episode_id': episode_id,
            'comparisons': [],
            'statistics': {}
        }
    
    def run_fewshot_classification(self, tweets: List[str]) -> List[Dict]:
        """
        Run the existing few-shot based classification.
        Uses the current pipeline's classifier.
        """
        logger.info("Running few-shot classification...")
        
        # First, generate few-shots if they don't exist
        fewshots_path = self.parent_dir / "transcripts" / "fewshots.json"
        if not fewshots_path.exists():
            logger.info("Generating few-shot examples...")
            self._generate_fewshots()
        
        # Load few-shots
        with open(fewshots_path) as f:
            fewshots = json.load(f)
        
        # Run classification using existing classifier
        results = []
        classifier_script = self.parent_dir / "tweet_classifier.py"
        
        if classifier_script.exists():
            # Write tweets to temp file
            temp_input = self.parent_dir / ".temp_tweets.txt"
            temp_input.write_text('\n'.join(tweets))
            
            # Run classifier
            cmd = [
                sys.executable,
                str(classifier_script),
                "--input-file", str(temp_input),
                "--summary-file", str(self.parent_dir / "transcripts" / "summary.md"),
                "--workers", "1"  # Single thread for consistency
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.parent_dir
                )
                
                # Parse output (classifier prints JSON)
                if result.returncode == 0:
                    output_lines = result.stdout.strip().split('\n')
                    for line in output_lines:
                        if line.startswith('{'):
                            try:
                                data = json.loads(line)
                                results.append(data)
                            except:
                                pass
                
                # Clean up
                temp_input.unlink(missing_ok=True)
                
            except Exception as e:
                logger.error(f"Error running few-shot classification: {e}")
        else:
            logger.warning("tweet_classifier.py not found, using mock data")
            # Mock results for testing
            import random
            for tweet in tweets:
                results.append({
                    'text': tweet,
                    'relevance_score': random.uniform(0, 1),
                    'classification': 'RELEVANT' if random.random() > 0.5 else 'SKIP'
                })
        
        return results
    
    def run_claude_classification(self, tweets: List[str]) -> List[Dict]:
        """Run Claude direct classification."""
        logger.info("Running Claude direct classification...")
        return self.claude_classifier.classify_batch(tweets, batch_size=20)
    
    def _generate_fewshots(self):
        """Generate few-shot examples using existing pipeline."""
        fewshot_script = self.parent_dir / "src" / "wdf" / "tasks" / "fewshot.py"
        if fewshot_script.exists():
            cmd = [sys.executable, str(fewshot_script), "--run-id", "comparison"]
            subprocess.run(cmd, cwd=self.parent_dir)
        else:
            # Create mock few-shots for testing
            mock_fewshots = [
                ["State sovereignty is crucial for liberty", "RELEVANT"],
                ["Just made dinner", "SKIP"],
                ["Federal overreach is destroying America", "RELEVANT"],
                ["Check out my new NFT", "SKIP"]
            ]
            fewshots_path = self.parent_dir / "transcripts" / "fewshots.json"
            fewshots_path.write_text(json.dumps(mock_fewshots, indent=2))
    
    def compare_classifications(self, tweets: List[str]) -> Dict:
        """
        Compare both classification methods on the same tweets.
        
        Args:
            tweets: List of tweet texts to classify
            
        Returns:
            Detailed comparison results
        """
        # Run both classifiers
        start_fewshot = time.time()
        fewshot_results = self.run_fewshot_classification(tweets)
        fewshot_time = time.time() - start_fewshot
        
        start_claude = time.time()
        claude_results = self.claude_classifier.classify_batch(tweets)
        claude_time = time.time() - start_claude
        
        # Analyze differences
        comparisons = []
        score_diffs = []
        agreement_count = 0
        
        for i, tweet in enumerate(tweets):
            fewshot = fewshot_results[i] if i < len(fewshot_results) else {'relevance_score': 0, 'classification': 'SKIP'}
            claude = claude_results[i] if i < len(claude_results) else {'score': 0, 'classification': 'SKIP'}
            
            # Calculate difference
            fewshot_score = fewshot.get('relevance_score', 0)
            claude_score = claude.get('score', 0)
            score_diff = abs(fewshot_score - claude_score)
            score_diffs.append(score_diff)
            
            # Check agreement
            agrees = fewshot.get('classification') == claude.get('classification')
            if agrees:
                agreement_count += 1
            
            comparison = {
                'tweet': tweet[:100] + '...' if len(tweet) > 100 else tweet,
                'fewshot_score': round(fewshot_score, 3),
                'claude_score': round(claude_score, 3),
                'score_difference': round(score_diff, 3),
                'fewshot_class': fewshot.get('classification'),
                'claude_class': claude.get('classification'),
                'agreement': agrees
            }
            comparisons.append(comparison)
        
        # Calculate statistics
        stats = {
            'total_tweets': len(tweets),
            'agreement_rate': round(agreement_count / len(tweets) * 100, 1) if tweets else 0,
            'average_score_difference': round(sum(score_diffs) / len(score_diffs), 3) if score_diffs else 0,
            'max_score_difference': round(max(score_diffs), 3) if score_diffs else 0,
            'fewshot_time_seconds': round(fewshot_time, 2),
            'claude_time_seconds': round(claude_time, 2),
            'speed_ratio': round(fewshot_time / claude_time, 2) if claude_time > 0 else 0,
            'fewshot_relevant_count': sum(1 for r in fewshot_results if r.get('classification') == 'RELEVANT'),
            'claude_relevant_count': sum(1 for r in claude_results if r.get('classification') == 'RELEVANT')
        }
        
        # Cost analysis
        stats['cost_analysis'] = {
            'fewshot_generation': 0.05,  # One-time cost per episode
            'fewshot_classification': 0.00,  # Local Gemma
            'claude_classification': round(len(tweets) * 0.001, 3),  # ~$0.001 per tweet
            'cost_difference': round(len(tweets) * 0.001 - 0.05, 3)
        }
        
        # Store results
        self.results['comparisons'] = comparisons
        self.results['statistics'] = stats
        
        return self.results
    
    def print_report(self):
        """Print a formatted comparison report."""
        stats = self.results['statistics']
        
        print("\n" + "="*60)
        print("CLASSIFICATION COMPARISON REPORT")
        print("="*60)
        
        print(f"\nEpisode ID: {self.results['episode_id'] or 'None'}")
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Total Tweets: {stats['total_tweets']}")
        
        print("\n--- ACCURACY METRICS ---")
        print(f"Agreement Rate: {stats['agreement_rate']}%")
        print(f"Average Score Difference: {stats['average_score_difference']}")
        print(f"Max Score Difference: {stats['max_score_difference']}")
        print(f"Few-shot Relevant: {stats['fewshot_relevant_count']}")
        print(f"Claude Relevant: {stats['claude_relevant_count']}")
        
        print("\n--- PERFORMANCE METRICS ---")
        print(f"Few-shot Time: {stats['fewshot_time_seconds']}s")
        print(f"Claude Time: {stats['claude_time_seconds']}s")
        print(f"Speed Ratio: {stats['speed_ratio']}x")
        
        print("\n--- COST ANALYSIS ---")
        cost = stats['cost_analysis']
        print(f"Few-shot Generation: ${cost['fewshot_generation']}")
        print(f"Few-shot Classification: ${cost['fewshot_classification']}")
        print(f"Claude Classification: ${cost['claude_classification']}")
        print(f"Cost Difference: ${cost['cost_difference']}")
        
        print("\n--- DISAGREEMENTS ---")
        disagreements = [c for c in self.results['comparisons'] if not c['agreement']]
        if disagreements:
            print(f"Found {len(disagreements)} disagreements:")
            for i, comp in enumerate(disagreements[:5]):  # Show first 5
                print(f"\n{i+1}. Tweet: {comp['tweet']}")
                print(f"   Few-shot: {comp['fewshot_score']} ({comp['fewshot_class']})")
                print(f"   Claude: {comp['claude_score']} ({comp['claude_class']})")
        else:
            print("Perfect agreement!")
        
        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)
        
        if stats['agreement_rate'] > 80:
            print("✅ HIGH AGREEMENT: Claude classification is ready for production")
        elif stats['agreement_rate'] > 60:
            print("⚠️ MODERATE AGREEMENT: Further tuning recommended")
        else:
            print("❌ LOW AGREEMENT: Investigate discrepancies before deployment")
        
        if stats['speed_ratio'] > 2:
            print(f"⚡ Few-shot is {stats['speed_ratio']}x faster but requires generation overhead")
        else:
            print(f"🚀 Claude is competitive on speed without generation overhead")
        
        print("\n")
    
    def save_report(self, output_path: Path):
        """Save detailed comparison report to file."""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Report saved to {output_path}")


def load_sample_tweets() -> List[str]:
    """Load sample tweets for testing."""
    samples = [
        "The federal government has completely overstepped its constitutional boundaries. Time for states to push back!",
        "Just finished my morning coffee ☕",
        "State sovereignty isn't just a concept, it's our last hope against tyranny",
        "Anyone know a good pizza place in Austin?",
        "The 10th Amendment has been ignored for too long. States need to reclaim their rights.",
        "Watching the game tonight! Go team!",
        "Federal mandates are destroying small businesses. Let states decide their own policies.",
        "My cat is being adorable right now 😺",
        "If we don't embrace federalism soon, we're headed for civil conflict",
        "Check out my new NFT collection! Link in bio",
        "The founding fathers would be appalled at federal overreach",
        "Recipe for chocolate chip cookies: First, preheat oven to 350°F...",
        "State nullification is a legitimate constitutional remedy",
        "Weather is perfect today for a bike ride!",
        "Time for a national divorce? Maybe peaceful separation is the answer.",
    ]
    return samples


def main():
    """Main entry point for comparison script."""
    parser = argparse.ArgumentParser(
        description="Compare Claude classification with few-shot classification"
    )
    
    parser.add_argument(
        '--input', '-i',
        type=Path,
        help="Input file with tweets (JSON)"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help="Output file for detailed report (JSON)"
    )
    parser.add_argument(
        '--episode-id', '-e',
        help="Episode ID for context"
    )
    parser.add_argument(
        '--use-samples', '-s',
        action='store_true',
        help="Use built-in sample tweets for testing"
    )
    
    args = parser.parse_args()
    
    # Load tweets
    if args.use_samples:
        tweets = load_sample_tweets()
        logger.info(f"Using {len(tweets)} sample tweets")
    elif args.input:
        with open(args.input) as f:
            data = json.load(f)
            if isinstance(data, list):
                tweets = [t if isinstance(t, str) else t.get('text', '') for t in data]
            else:
                tweets = [t.get('text', '') for t in data.get('tweets', [])]
        logger.info(f"Loaded {len(tweets)} tweets from {args.input}")
    else:
        print("Enter tweets to compare (one per line, empty line to finish):")
        tweets = []
        while True:
            line = input().strip()
            if not line:
                break
            tweets.append(line)
    
    if not tweets:
        logger.error("No tweets to classify")
        return
    
    # Run comparison
    comparator = ClassificationComparator(args.episode_id)
    results = comparator.compare_classifications(tweets)
    
    # Print report
    comparator.print_report()
    
    # Save detailed report if requested
    if args.output:
        comparator.save_report(args.output)


if __name__ == "__main__":
    main()