#!/Users/pentester/Tools/gemma-3n/venv/bin/python3
"""
evaluate_classifier.py - Compare tweet classifications against reference ground truth

This script evaluates the performance of tweet classifications by comparing
results against a reference classifier. This tests whether the classifier 
can truly generalize from the fewshot examples.

Usage:
  python evaluate_classifier.py [--classified-file CLASSIFIED_FILE] [--create-reference]
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import structlog

# Set up structured logging
logger = structlog.get_logger()

# Constants
DEFAULT_CLASSIFIED_PATH = Path("transcripts/classified.json")
DEFAULT_TWEETS_PATH = Path("transcripts/tweets.json")
DEFAULT_REFERENCE_PATH = Path("transcripts/gemini_classifications.json")


def load_json_file(file_path: Path) -> List:
    """
    Load data from a JSON file
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Loaded data
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        logger.info(
            "Loaded JSON data",
            count=len(data) if isinstance(data, list) else "non-list",
            path=str(file_path)
        )
        return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load data",
            error=str(e),
            path=str(file_path)
        )
        raise


def create_gemini_reference(tweets_path: Path = DEFAULT_TWEETS_PATH, output_path: Path = DEFAULT_REFERENCE_PATH) -> Dict[str, str]:
    """
    Create reference classifications using gemini directly on the test tweets
    
    Args:
        tweets_path: Path to the tweets JSON file
        output_path: Path to save reference classifications
        
    Returns:
        Dictionary mapping tweet text to classification
    """
    # Load tweets
    tweets = load_json_file(tweets_path)
    
    # Create a temporary file with one tweet per line
    tweets_file = Path("temp_tweets_for_gemini.txt")
    with open(tweets_file, "w") as f:
        for tweet in tweets:
            f.write(f"{tweet['text']}\n")
    
    # Build the command to run gemini directly
    cmd = [
        "gemini",
        "-p",
        "You are an expert classifier determining if tweets relate to the War, Divorce or Federalism podcast. "
        "For each tweet, output only RELEVANT or SKIP. No explanation, just the label.\n\n"
        "Here are the tweets to classify, one per line:\n"
    ]
    
    logger.info(
        "Running gemini for reference classifications",
        tweet_count=len(tweets)
    )
    
    # Run gemini
    try:
        result = subprocess.run(
            cmd,
            input=open(tweets_file).read(),
            text=True,
            capture_output=True,
            check=True
        )
        
        # Clean up
        tweets_file.unlink()
        
        # Parse gemini output
        output_lines = result.stdout.strip().splitlines()
        
        # Extract RELEVANT/SKIP classifications
        classifications = []
        for line in output_lines:
            # Look for RELEVANT or SKIP
            if "RELEVANT" in line:
                classifications.append("RELEVANT")
            elif "SKIP" in line:
                classifications.append("SKIP")
            else:
                # If line doesn't contain either, try to infer
                if re.search(r'relevant', line, re.IGNORECASE):
                    classifications.append("RELEVANT")
                else:
                    classifications.append("SKIP")
        
        # Check if we have the right number of classifications
        if len(classifications) != len(tweets):
            logger.warning(
                "Number of gemini classifications doesn't match number of tweets",
                tweets=len(tweets),
                classifications=len(classifications)
            )
            # Try to extract at least the first N classifications
            classifications = classifications[:len(tweets)]
            if len(classifications) < len(tweets):
                # Pad with SKIP for any missing
                classifications.extend(["SKIP"] * (len(tweets) - len(classifications)))
        
        # Create a dictionary mapping tweet text to classification
        reference = {}
        for tweet, classification in zip(tweets, classifications):
            reference[tweet["text"]] = classification
        
        # Save reference classifications
        with open(output_path, "w") as f:
            json.dump(reference, f, indent=2)
            
        logger.info(
            "Created reference classifications",
            path=str(output_path),
            count=len(reference),
            relevant_count=sum(1 for c in reference.values() if c == "RELEVANT"),
            skip_count=sum(1 for c in reference.values() if c == "SKIP")
        )
        
        return reference
        
    except subprocess.CalledProcessError as e:
        logger.error(
            "gemini command failed",
            returncode=e.returncode,
            stdout=e.stdout,
            stderr=e.stderr
        )
        raise
    except Exception as e:
        logger.error(
            "Error creating reference classifications",
            error=str(e)
        )
        raise


def load_reference_classifications(path: Path = DEFAULT_REFERENCE_PATH) -> Dict[str, str]:
    """
    Load reference classifications from file
    
    Args:
        path: Path to reference classifications file
        
    Returns:
        Dictionary mapping tweet text to classification
    """
    try:
        with open(path, "r") as f:
            reference = json.load(f)
            
        logger.info(
            "Loaded reference classifications",
            count=len(reference),
            relevant_count=sum(1 for c in reference.values() if c == "RELEVANT"),
            skip_count=sum(1 for c in reference.values() if c == "SKIP")
        )
        
        return reference
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load reference classifications",
            error=str(e),
            path=str(path)
        )
        raise


def evaluate_classifications(classified_tweets: List[Dict], reference: Dict[str, str]) -> Dict:
    """
    Evaluate tweet classifications against reference
    
    Args:
        classified_tweets: List of tweet dictionaries with classifications
        reference: Dictionary mapping tweet text to classification
        
    Returns:
        Dictionary of evaluation metrics
    """
    # Initialize counters
    true_positives = 0  # Correctly classified as RELEVANT
    false_positives = 0  # Incorrectly classified as RELEVANT
    true_negatives = 0  # Correctly classified as SKIP
    false_negatives = 0  # Incorrectly classified as SKIP
    total_matched = 0
    
    # Match classified tweets with reference
    for tweet in classified_tweets:
        tweet_text = tweet.get("text")
        test_classification = tweet.get("classification")
        
        if not tweet_text or not test_classification:
            continue
        
        # Get reference classification for this tweet
        if tweet_text in reference:
            total_matched += 1
            reference_classification = reference[tweet_text]
            
            # Update counters
            if test_classification == "RELEVANT" and reference_classification == "RELEVANT":
                true_positives += 1
            elif test_classification == "RELEVANT" and reference_classification == "SKIP":
                false_positives += 1
            elif test_classification == "SKIP" and reference_classification == "SKIP":
                true_negatives += 1
            elif test_classification == "SKIP" and reference_classification == "RELEVANT":
                false_negatives += 1
    
    # Calculate metrics
    accuracy = (true_positives + true_negatives) / total_matched if total_matched > 0 else 0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Also calculate raw agreement percentage
    agreement = sum(1 for tweet in classified_tweets if tweet.get("text") in reference and 
                     tweet.get("classification") == reference[tweet.get("text")]) / total_matched if total_matched > 0 else 0
    
    # Prepare results
    results = {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "total_matched": total_matched,
        "total_classified": len(classified_tweets),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "agreement": agreement
    }
    
    return results


def print_evaluation_results(results: Dict) -> None:
    """
    Print evaluation results in a readable format
    
    Args:
        results: Dictionary of evaluation metrics
    """
    print("\n===== CLASSIFIER EVALUATION RESULTS =====\n")
    
    print(f"Total tweets classified: {results['total_classified']}")
    print(f"Tweets matched with reference: {results['total_matched']}\n")
    
    print("Confusion Matrix:")
    print("                 | GEMINI: RELEVANT | GEMINI: SKIP")
    print("-----------------+-----------------+-------------")
    print(f"CLASSIFIER: RELEVANT | {results['true_positives']:15d} | {results['false_positives']:11d}")
    print(f"CLASSIFIER: SKIP     | {results['false_negatives']:15d} | {results['true_negatives']:11d}\n")
    
    print("Metrics:")
    print(f"Accuracy:  {results['accuracy']:.4f} ({results['accuracy']*100:.1f}%)")
    print(f"Precision: {results['precision']:.4f} ({results['precision']*100:.1f}%)")
    print(f"Recall:    {results['recall']:.4f} ({results['recall']*100:.1f}%)")
    print(f"F1 Score:  {results['f1_score']:.4f}")
    print(f"Agreement: {results['agreement']:.4f} ({results['agreement']*100:.1f}%)\n")
    
    # Overall assessment
    if results['accuracy'] >= 0.9:
        assessment = "EXCELLENT"
    elif results['accuracy'] >= 0.8:
        assessment = "GOOD"
    elif results['accuracy'] >= 0.7:
        assessment = "FAIR"
    else:
        assessment = "NEEDS IMPROVEMENT"
        
    print(f"Overall performance: {assessment}")
    print("\n=====================================\n")


def main() -> int:
    """
    Main entry point
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Evaluate tweet classifications against reference"
    )
    parser.add_argument(
        "--classified-file",
        type=str,
        default=str(DEFAULT_CLASSIFIED_PATH),
        help=f"Path to the classified tweets JSON file (default: {DEFAULT_CLASSIFIED_PATH})"
    )
    parser.add_argument(
        "--create-reference",
        action="store_true",
        help="Force creation of new reference classifications using gemini"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    classified_path = Path(args.classified_file)
    
    try:
        # Load classified tweets from classifier
        classified_tweets = load_json_file(classified_path)
        
        # Get or create reference classifications from gemini
        reference_path = DEFAULT_REFERENCE_PATH
        if args.create_reference or not reference_path.exists():
            logger.info("Creating new reference classifications with gemini")
            reference = create_gemini_reference()
        else:
            logger.info("Loading existing reference classifications")
            reference = load_reference_classifications()
        
        # Evaluate classifications
        results = evaluate_classifications(classified_tweets, reference)
        
        # Print results
        print_evaluation_results(results)
        
        logger.info(
            "Evaluation complete",
            accuracy=results["accuracy"],
            precision=results["precision"],
            recall=results["recall"],
            f1_score=results["f1_score"],
            agreement=results["agreement"]
        )
        
        return 0
    
    except Exception as e:
        logger.error(
            "Error evaluating classifications",
            error=str(e)
        )
        return 1


if __name__ == "__main__":
    sys.exit(main()) 