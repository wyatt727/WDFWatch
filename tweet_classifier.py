#!/Users/pentester/Tools/gemma-3n/venv/bin/python3
"""
tweet_classifier.py – Relevancy scorer that determines how relevant tweets are to the WDF podcast using few-shot examples.
Returns a score from 0.00 to 1.00, where 1.00 is highly relevant and 0.00 is not relevant.
Supports multiple LLM backends through configuration.
"""

import argparse
import logging
import sys
import random
import os
import json
import hashlib
import time
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from ollama import Client          # pip install ollama

# Import prompt utilities and score utilities
sys.path.append(str(Path(__file__).parent))
try:
    from src.wdf.prompt_utils import build_classification_prompt
    from src.wdf.score_utils import parse_score, validate_score, score_to_classification
except ImportError:
    # Fallback if module not available
    build_classification_prompt = None
    parse_score = None
    validate_score = None
    score_to_classification = None

# Load few-shot examples from JSON file
FEWSHOTS_PATH = Path("transcripts/fewshots.json")
if FEWSHOTS_PATH.exists():
    with open(FEWSHOTS_PATH, 'r') as f:
        FEW_SHOT_EXAMPLES = json.load(f)
else:
    # Fallback examples if file doesn't exist
    FEW_SHOT_EXAMPLES = [
        ["This is a tweet about federalism", "RELEVANT"],
        ["Random tweet about cats", "SKIP"]
    ]

# Constants
DEFAULT_MODEL = os.environ.get("WDF_LLM_MODEL_CLASSIFICATION", os.environ.get("WDF_LLM_MODELS__CLASSIFICATION", "gemma3n:e4b"))
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_EXAMPLES = 20  # Default to 5 examples for faster performance
DEFAULT_CACHE_DIR = os.path.expanduser("~/.3n_cache")
DEFAULT_SUMMARY_PATH = os.path.join("transcripts", "summary.md")
DEFAULT_MAX_WORKERS = 8  # Increased from 4 to 8 for faster processing

# System prompt that clearly defines the expected behavior
SYSTEM_MSG = (
    "You are an assistant that scores tweet relevancy from 0.00 to 1.00 by using few-shot examples.\n"
    "You must follow these rules exactly:\n"
    "1. Analyze the tweet's relevance to the topic based on the few-shot examples.\n"
    "2. Reply with ONLY a decimal number between 0.00 and 1.00.\n"
    "3. Use two decimal places (e.g., 0.85, 0.42, 1.00).\n"
    "4. Higher scores mean more relevant to the topic.\n"
    "5. Do not include any other text, explanations, or formatting.\n"
    "\nSCORING GUIDELINES:\n"
    "- 0.85-1.00: Highly relevant - directly discusses topic themes\n"
    "- 0.70-0.84: Relevant - relates to topic, good for engagement\n"
    "- 0.30-0.69: Somewhat relevant - tangentially related\n"
    "- 0.00-0.29: Not relevant - unrelated to topic\n"
    "\nNEVER deviate from the numeric format. Accuracy is critical."
)

def build_messages(user_msg: str, examples: list, topic_summary: str = None) -> str:
    """
    Build the complete message using Gemma 3n's specific chat template format
    with <start_of_turn> and <end_of_turn> tags
    
    Args:
        user_msg: The tweet to classify
        examples: List of tuples containing (tweet, classification)
        topic_summary: Optional topic summary for additional context
        
    Returns:
        Formatted message for Ollama API
    """
    # Use database prompt if available, otherwise use default
    if build_classification_prompt:
        system_with_context = build_classification_prompt(topic_summary)
    else:
        # Fallback to hardcoded prompt
        system_with_context = SYSTEM_MSG
        if topic_summary:
            system_with_context += f"\n\nTOPIC CONTEXT:\n{topic_summary}"
        
    messages = f"<start_of_turn>system\n{system_with_context}<end_of_turn>\n"
    
    # Add few-shot examples from the imported module
    for user_example, assistant_response in examples:
        messages += f"<start_of_turn>user\n{user_example}<end_of_turn>\n"
        messages += f"<start_of_turn>model\n{assistant_response}<end_of_turn>\n"
    
    # Add the current user query
    messages += f"<start_of_turn>user\n{user_msg}<end_of_turn>\n"
    messages += "<start_of_turn>model\n"
    
    return messages

def get_cache_key(model: str, user_msg: str, examples_hash: str, summary_hash: str = None) -> str:
    """Generate a unique cache key for the request"""
    key_input = f"{model}:{user_msg}:{examples_hash}"
    if summary_hash:
        key_input += f":{summary_hash}"
    return hashlib.md5(key_input.encode()).hexdigest()

def load_cache() -> Dict:
    """Load the cache from disk or create a new one"""
    os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(DEFAULT_CACHE_DIR, "response_cache.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.warning("Cache file corrupted, creating new cache")
            return {}
    return {}

def save_cache(cache: Dict) -> None:
    """Save the cache to disk"""
    cache_file = os.path.join(DEFAULT_CACHE_DIR, "response_cache.json")
    with open(cache_file, 'w') as f:
        json.dump(cache, f)

def classify_tweet(client: Client, model: str, user_msg: str, examples: List, 
                  cache: Dict, examples_hash: str, use_cache: bool = True,
                  topic_summary: str = None, summary_hash: str = None) -> float:
    """
    Score a single tweet using the model, with caching support
    
    Args:
        client: Ollama client
        model: Model name
        user_msg: The tweet to score
        examples: List of examples for few-shot learning
        cache: Cache dictionary
        examples_hash: Hash of the examples used
        use_cache: Whether to use cache
        topic_summary: Optional topic summary
        summary_hash: Hash of the topic summary
        
    Returns:
        float: Relevancy score (0.00-1.00)
    """
    cache_key = get_cache_key(model, user_msg, examples_hash, summary_hash)
    
    # Check cache first
    if use_cache and cache_key in cache:
        logging.debug(f"Cache hit for: {user_msg[:30]}...")
        return cache[cache_key]
    
    # Format the prompt
    prompt = build_messages(user_msg, examples, topic_summary)
    
    # Get response from model
    try:
        resp = client.generate(
            model=model,
            prompt=prompt,
            options={"stop": ["<end_of_turn>", "<start_of_turn>"]}
        )
        reply = resp["response"].strip()
        
        # Parse the score
        if parse_score:
            score = parse_score(reply)
            if score is None:
                # If parsing fails, try to handle old format
                if reply.upper() in ["RELEVANT", "SKIP"]:
                    score = 1.0 if reply.upper() == "RELEVANT" else 0.0
                else:
                    logging.warning(f"Failed to parse score from response: {reply}")
                    score = 0.5  # Default to medium score if parsing fails
        else:
            # Fallback parsing without score_utils
            try:
                score = float(reply)
                if not (0.0 <= score <= 1.0):
                    logging.warning(f"Score out of range: {score}")
                    score = max(0.0, min(1.0, score))  # Clamp to valid range
            except ValueError:
                # Handle old format
                if reply.upper() == "RELEVANT":
                    score = 1.0
                elif reply.upper() == "SKIP":
                    score = 0.0
                else:
                    logging.warning(f"Could not parse score: {reply}")
                    score = 0.5
        
        # Update cache
        if use_cache:
            cache[cache_key] = score
            
        return score
    except Exception as e:
        logging.error(f"Ollama API error for tweet '{user_msg[:30]}...': {e}")
        return f"ERROR: {e}"

def batch_classify(tweets: List[str], client: Client, model: str, examples: List, 
                  cache: Dict, examples_hash: str, use_cache: bool = True, 
                  max_workers: int = DEFAULT_MAX_WORKERS, topic_summary: str = None, summary_hash: str = None) -> List[Tuple[str, float]]:
    """
    Score a batch of tweets in parallel
    
    Args:
        tweets: List of tweets to score
        client: Ollama client
        model: Model name
        examples: Examples for few-shot learning
        cache: Cache dictionary
        examples_hash: Hash of the examples used
        use_cache: Whether to use cache
        max_workers: Maximum number of parallel workers
        topic_summary: Optional topic summary
        summary_hash: Hash of the topic summary
        
    Returns:
        List of (tweet, score) tuples where score is 0.00-1.00
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(
            classify_tweet, client, model, tweet, examples, cache, examples_hash, use_cache, topic_summary, summary_hash
        ): tweet for tweet in tweets}
        
        for future in futures:
            tweet = futures[future]
            try:
                score = future.result()
                results.append((tweet, score))
            except Exception as e:
                logging.error(f"Error scoring tweet '{tweet[:30]}...': {e}")
                results.append((tweet, 0.0))  # Default to 0.0 on error
    
    return results

def calculate_examples_hash(examples: List) -> str:
    """Calculate a hash for the set of examples being used"""
    examples_str = json.dumps(examples)
    return hashlib.md5(examples_str.encode()).hexdigest()[:10]

def calculate_summary_hash(summary: str) -> str:
    """Calculate a hash for the topic summary"""
    if not summary:
        return None
    return hashlib.md5(summary.encode()).hexdigest()[:10]

def select_balanced_examples(examples: List, count: int) -> List:
    """
    Select a balanced set of examples across score ranges or labels
    
    Args:
        examples: Full list of examples with scores or labels
        count: Number of examples to select
        
    Returns:
        Balanced list of examples
    """
    # Check if examples use numeric scores or string labels
    if examples and isinstance(examples[0][1], str):
        # String labels (RELEVANT/SKIP)
        relevant_examples = [ex for ex in examples if ex[1] == "RELEVANT"]
        skip_examples = [ex for ex in examples if ex[1] == "SKIP"]
        
        # Try to get equal distribution
        half = count // 2
        remaining = count - (half * 2)
        
        selected = []
        if relevant_examples:
            selected.extend(random.sample(relevant_examples, min(half + (1 if remaining > 0 else 0), len(relevant_examples))))
        if skip_examples:
            selected.extend(random.sample(skip_examples, min(half, len(skip_examples))))
        
        # If we don't have enough, add more from whichever category has examples
        while len(selected) < count:
            if relevant_examples and len(relevant_examples) > len([s for s in selected if s[1] == "RELEVANT"]):
                remaining_relevant = [ex for ex in relevant_examples if ex not in selected]
                if remaining_relevant:
                    selected.append(random.choice(remaining_relevant))
            elif skip_examples and len(skip_examples) > len([s for s in selected if s[1] == "SKIP"]):
                remaining_skip = [ex for ex in skip_examples if ex not in selected]
                if remaining_skip:
                    selected.append(random.choice(remaining_skip))
            else:
                break
        
        random.shuffle(selected)
        return selected[:count]
    else:
        # Numeric scores (backward compatibility)
        high = [ex for ex in examples if ex[1] >= 0.85]  # High relevance
        relevant = [ex for ex in examples if 0.70 <= ex[1] < 0.85]  # Relevant
        medium = [ex for ex in examples if 0.30 <= ex[1] < 0.70]  # Medium
        low = [ex for ex in examples if ex[1] < 0.30]  # Low relevance
    
    # Try to get roughly equal distribution across ranges
    quarter = count // 4
    remaining = count - (quarter * 4)
    
    # Select examples from each category
    selected = []
    if high:
        selected.extend(random.sample(high, min(quarter + (1 if remaining > 0 else 0), len(high))))
        remaining = max(0, remaining - 1)
    if relevant:
        selected.extend(random.sample(relevant, min(quarter + (1 if remaining > 0 else 0), len(relevant))))
        remaining = max(0, remaining - 1)
    if medium:
        selected.extend(random.sample(medium, min(quarter + (1 if remaining > 0 else 0), len(medium))))
        remaining = max(0, remaining - 1)
    if low:
        selected.extend(random.sample(low, min(quarter + remaining, len(low))))
    
    # If we don't have enough, just sample randomly from all
    if len(selected) < count:
        all_remaining = [ex for ex in examples if ex not in selected]
        if all_remaining:
            selected.extend(random.sample(all_remaining, min(count - len(selected), len(all_remaining))))
    
    # Shuffle the final selection
    random.shuffle(selected)
    return selected[:count]  # Ensure we don't exceed count

def read_tweets_from_file(file_path: str) -> List[str]:
    """
    Read tweets from a file, one per line
    
    Args:
        file_path: Path to the file containing tweets
        
    Returns:
        List of tweets
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read all lines and filter out empty ones
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading tweets file: {e}")
        print(f"ERROR: Could not read tweets from {file_path}: {e}")
        return []

def read_summary_file(file_path: str) -> str:
    """
    Read the summary.md file and extract the keywords section
    
    Args:
        file_path: Path to the summary file
        
    Returns:
        Keywords or summary extract, or None if file not found
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Try to extract keywords section
            keywords_match = re.search(r'### Keywords signaling tweet relevance\s*\n(.*?)(\n\s*---|\Z)', 
                                     content, re.DOTALL)
            if keywords_match:
                return keywords_match.group(1).strip()
            
            # If no keywords section, return a summary (first 500 chars)
            return content[:500] + "..."
    except Exception as e:
        logging.warning(f"Could not read summary file: {e}")
        return None

def process_batch(tweets: List[str], client: Client, model: str, examples: List,
                 cache: Dict, examples_hash: str, use_cache: bool, workers: int,
                 topic_summary: str = None, summary_hash: str = None) -> None:
    """
    Process a batch of tweets and display results
    
    Args:
        tweets: List of tweets to process
        client: Ollama client
        model: Model name
        examples: Examples for few-shot learning
        cache: Cache dictionary
        examples_hash: Hash of examples used
        use_cache: Whether to use cache
        workers: Number of parallel workers
        topic_summary: Optional topic summary
        summary_hash: Hash of the topic summary
    """
    if not tweets:
        print("No tweets to process.")
        return
    
    logging.info(f"Processing batch of {len(tweets)} tweets")
    batch_start = time.time()
    
    # Process tweets in parallel
    results = batch_classify(
        tweets, client, model, examples, 
        cache, examples_hash, use_cache, workers,
        topic_summary, summary_hash
    )
    
    # Display results
    print(f"\n--- Results for {len(tweets)} tweets ---")
    relevant_count = 0
    for i, (tweet, score) in enumerate(results):
        print(f"Tweet {i+1}: {tweet[:50]}{'...' if len(tweet) > 50 else ''}")
        
        # Format score display
        if score_to_classification:
            classification = score_to_classification(score)
            label = "Highly Relevant" if score >= 0.85 else "Relevant" if score >= 0.70 else "Maybe" if score >= 0.30 else "Not Relevant"
            print(f"Score: {score:.2f} ({label}) - {classification}")
        else:
            # Fallback display without score_utils
            classification = "RELEVANT" if score >= 0.70 else "SKIP"
            print(f"Score: {score:.2f} - {classification}")
        
        if score >= 0.70:
            relevant_count += 1
        print()
    
    # Output stats
    batch_time = time.time() - batch_start
    avg_time = batch_time / len(tweets)
    print(f"Processed {len(tweets)} tweets in {batch_time:.2f}s ({avg_time:.2f}s per tweet)")
    
    # Save cache after batch processing
    if use_cache:
        save_cache(cache)

def main() -> None:
    """Main function to run the tweet classifier"""
    # Check if Claude is selected for classification
    classification_model = os.environ.get("WDF_LLM_MODEL_CLASSIFICATION", os.environ.get("WDF_LLM_MODELS__CLASSIFICATION", DEFAULT_MODEL))
    
    # If Claude is selected, redirect to Claude wrapper script
    if classification_model == "claude":
        import subprocess
        claude_script = Path(__file__).parent / "scripts" / "claude_classifier.py"
        if claude_script.exists():
            # Pass through all arguments to Claude wrapper
            cmd = [sys.executable, str(claude_script)] + sys.argv[1:]
            logging.info("Redirecting to Claude classifier wrapper")
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        else:
            logging.warning(f"Claude classifier wrapper not found at {claude_script}, falling back to Ollama")
    
    parser = argparse.ArgumentParser(description="Tweet Relevance Classifier for WDF Podcast")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama API host (default: {DEFAULT_HOST})")
    parser.add_argument("--examples", type=int, default=DEFAULT_EXAMPLES, 
                        help=f"Number of examples to use (default: {DEFAULT_EXAMPLES})")
    parser.add_argument("--max-examples", type=int, 
                        help="Maximum index of examples to use (e.g., 20 means use only the first 20 examples)")
    parser.add_argument("--random", action="store_true", 
                        help="Randomly select examples instead of using the first N")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-cache", dest="cache", action="store_false", 
                        help="Disable response caching")
    parser.add_argument("--batch", action="store_true", 
                        help="Enable interactive batch processing mode")
    parser.add_argument("--input-file", type=str, 
                        help="Path to file containing tweets to process (one per line)")
    parser.add_argument("--workers", type=int, default=DEFAULT_MAX_WORKERS,
                        help=f"Maximum number of parallel workers (default: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--summary-file", type=str, default=DEFAULT_SUMMARY_PATH,
                        help=f"Path to summary file providing topic context (default: {DEFAULT_SUMMARY_PATH})")
    parser.add_argument("--no-summary", dest="use_summary", action="store_false",
                        help="Don't use summary file for additional context")
    parser.set_defaults(cache=True, use_summary=True)
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    # Select examples based on command line args
    if args.max_examples:
        # If max_examples is specified, use only the first N examples
        limited_examples = FEW_SHOT_EXAMPLES[:args.max_examples]
        logging.info(f"Using only the first {len(limited_examples)} examples (limited by --max-examples)")
        
        if args.random:
            examples = select_balanced_examples(limited_examples, args.examples)
            logging.info(f"Using {len(examples)} randomly selected examples from the first {len(limited_examples)}")
        else:
            examples = limited_examples[:args.examples]
            logging.info(f"Using first {len(examples)} examples from limited set of {len(limited_examples)}")
    elif args.random:
        examples = select_balanced_examples(FEW_SHOT_EXAMPLES, args.examples)
        logging.info(f"Using {len(examples)} randomly selected examples ({len(examples)//2} RELEVANT, {len(examples)//2} SKIP)")
    else:
        examples = FEW_SHOT_EXAMPLES[:args.examples]
        logging.info(f"Using first {len(examples)} examples from few_shot_examples.py")
    
    # Read summary file if specified
    topic_summary = None
    summary_hash = None
    if args.use_summary:
        topic_summary = read_summary_file(args.summary_file)
        if topic_summary:
            summary_hash = calculate_summary_hash(topic_summary)
            logging.info(f"Loaded topic context from {args.summary_file}")
        else:
            logging.warning(f"Could not load topic context from {args.summary_file}")
    
    # Calculate a hash for the examples being used
    examples_hash = calculate_examples_hash(examples)
    
    # Load response cache
    cache = load_cache() if args.cache else {}
    
    # Initialize Ollama client
    try:
        client = Client(host=args.host)
        logging.info(f"Connected to Ollama at {args.host}")
    except Exception as e:
        logging.error(f"Failed to connect to Ollama: {e}")
        print(f"ERROR: Could not connect to Ollama at {args.host}")
        sys.exit(1)

    # Print header
    print("Tweet Relevancy Scorer")
    print(f"Model: {args.model}")
    print(f"Using {len(examples)} examples, caching {'enabled' if args.cache else 'disabled'}")
    print(f"Relevancy threshold: 0.70 (scores >= 0.70 are considered relevant)")
    if topic_summary:
        print("Using topic context from summary file")
    
    start_time = time.time()
    total_processed = 0
    
    try:
        # Process file input if specified
        if args.input_file:
            tweets = read_tweets_from_file(args.input_file)
            if tweets:
                process_batch(tweets, client, args.model, examples, 
                            cache, examples_hash, args.cache, args.workers,
                            topic_summary, summary_hash)
                total_processed = len(tweets)
            return
            
        # Interactive batch mode
        if args.batch:
            print("Batch processing mode")
            print("Enter tweets separated by empty lines, then type '!process' to classify them")
            print("Type '!exit' to quit")
            
            batch_tweets = []
            lines = []
            
            while True:
                line = input().strip()
                
                if line == "!exit":
                    break
                    
                if line == "!process":
                    # Add any remaining lines as a tweet
                    if lines:
                        tweet = "\n".join(lines).strip()
                        if tweet:
                            batch_tweets.append(tweet)
                        lines = []
                    
                    # Process the batch
                    process_batch(batch_tweets, client, args.model, examples, 
                                cache, examples_hash, args.cache, args.workers,
                                topic_summary, summary_hash)
                    
                    # Update counters
                    total_processed += len(batch_tweets)
                    batch_tweets = []
                    
                elif not line and lines:
                    # Empty line marks the end of a tweet
                    tweet = "\n".join(lines).strip()
                    if tweet:
                        batch_tweets.append(tweet)
                    lines = []
                elif line:
                    lines.append(line)
        
        # Normal interactive mode (default)
        else:
            print("Enter tweets to score for relevancy (0.00-1.00) (Ctrl-C to quit)")
            
            while True:
                user_in = input("\n> ").strip()
                if not user_in:
                    continue
                    
                logging.debug(f"Tweet: {user_in}")
                
                # Score the tweet
                start = time.time()
                score = classify_tweet(client, args.model, user_in, examples, 
                                      cache, examples_hash, args.cache,
                                      topic_summary, summary_hash)
                                      
                # Display result and timing info
                if score_to_classification:
                    classification = score_to_classification(score)
                    label = "Highly Relevant" if score >= 0.85 else "Relevant" if score >= 0.70 else "Maybe" if score >= 0.30 else "Not Relevant"
                    print(f"Score: {score:.2f} ({label}) - {classification}")
                else:
                    classification = "RELEVANT" if score >= 0.70 else "SKIP"
                    print(f"Score: {score:.2f} - {classification}")
                    
                elapsed = time.time() - start
                logging.debug(f"Score: {score:.2f} (took {elapsed:.2f}s)")
                
                # Update counters
                total_processed += 1
                
                # Save cache periodically
                if args.cache and total_processed % 5 == 0:
                    save_cache(cache)
            
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except EOFError:
        print("\nInput stream closed. Exiting.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"ERROR: {e}")
    finally:
        # Final stats
        total_time = time.time() - start_time
        if total_processed > 0:
            print(f"\nTotal: {total_processed} tweets processed in {total_time:.2f}s")
            print(f"Overall average: {total_time/total_processed:.2f}s per tweet")
            
            # Score statistics (only in file mode with cached results)
            if args.input_file and 'results' in locals() and results:
                relevant_count = sum(1 for _, score in results if score >= 0.70)
                skip_count = sum(1 for _, score in results if score < 0.70)
                relevancy_percentage = (relevant_count / len(results) * 100) if results else 0
                avg_score = sum(score for _, score in results) / len(results) if results else 0
                print(f"\nScoring Results:")
                print(f"  Average Score: {avg_score:.2f}")
                print(f"  Relevant (>= 0.70): {relevant_count} ({relevancy_percentage:.1f}%)")
                print(f"  Not Relevant (< 0.70): {skip_count} ({100 - relevancy_percentage:.1f}%)")
        
        # Save cache on exit
        if args.cache:
            save_cache(cache)

if __name__ == "__main__":
    main()
