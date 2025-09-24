"""
DeepSeek tweet response generation task

This module generates responses to relevant tweets using the DeepSeek model.
It extends the existing deepseek.py script with task-specific functionality.
Integrates with: web_bridge.py (when WDF_WEB_MODE=true)
"""

import json
import logging
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from textwrap import shorten
from typing import Dict, List, Optional, Tuple
import time

import structlog
from ollama import Client
from prometheus_client import Counter, Histogram

from ..settings import settings
from ..episode_files import get_episode_file_manager

# Import web bridge for draft creation
try:
    web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
    sys.path.insert(0, str(web_scripts_path))
    from web_bridge import create_draft_if_web_mode
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge imported successfully")
except ImportError:
    # Web bridge not available, continue without it
    def create_draft_if_web_mode(tweet_id, response, model):
        return None
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge not available, continuing without database sync")

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics
DEEPSEEK_LATENCY = Histogram(
    "deepseek_latency_seconds", 
    "Time taken to generate tweet responses",
    ["run_id"],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)
RESPONSES_GENERATED = Counter(
    "responses_generated_total",
    "Number of tweet responses generated"
)
RESPONSES_OVERSIZED = Counter(
    "responses_oversized_total",
    "Number of responses exceeding character limit"
)
DEEPSEEK_ERRORS = Counter(
    "deepseek_errors_total",
    "Number of DeepSeek generation errors"
)

# File paths
CLASSIFIED_PATH = Path(settings.transcript_dir) / "classified.json"
SUMMARY_PATH = Path(settings.transcript_dir) / "summary.md"
OVERVIEW_PATH = Path(settings.transcript_dir) / "podcast_overview.txt"
VIDEO_URL_PATH = Path(settings.transcript_dir) / "VIDEO_URL.txt"
RESPONSES_PATH = Path(settings.transcript_dir) / "responses.json"

# Constants
MAX_SUMMARY_CHARS = 20_000
MAX_TWEET_LENGTH = 280  # Twitter's actual character limit
THINKING_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)

# Default number of workers
DEFAULT_NUM_WORKERS = 1

# Thread lock for file operations
file_lock = threading.Lock()


def load_summary(file_manager=None, path: Path = SUMMARY_PATH, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """
    Load and optionally truncate the podcast summary
    
    Args:
        file_manager: Optional episode file manager
        path: Path to the summary file (used if file_manager is None)
        max_chars: Maximum number of characters to include
        
    Returns:
        str: The summary text
    """
    try:
        if file_manager:
            txt = file_manager.read_input('summary')
        else:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            
        if max_chars and len(txt) > max_chars:
            logger.info(
                "Truncating summary",
                original_length=len(txt),
                new_length=max_chars,
                using_episode_files=bool(file_manager)
            )
            return shorten(txt, width=max_chars, placeholder="...")
        return txt
    except Exception as e:
        logger.error(
            "Failed to load summary",
            error=str(e),
            path=str(path if not file_manager else file_manager.get_output_path('summary'))
        )
        raise


def load_overview(file_manager=None, path: Path = OVERVIEW_PATH) -> str:
    """
    Load the podcast overview
    
    Args:
        file_manager: Optional episode file manager
        path: Path to the podcast overview file (used if file_manager is None)
        
    Returns:
        str: The podcast overview text
    """
    try:
        if file_manager:
            return file_manager.read_input('overview').strip()
        else:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as e:
        logger.error(
            "Failed to load podcast overview",
            error=str(e),
            path=str(path if not file_manager else file_manager.get_input_path('overview'))
        )
        logger.warning("Using empty podcast overview")
        return "The WDF (War, Divorce or Federalism) podcast features discussions on liberty, constitutionalism, and state sovereignty."


def load_video_url(file_manager=None, path: Path = VIDEO_URL_PATH) -> str:
    """
    Load the podcast video URL
    
    Args:
        file_manager: Optional episode file manager
        path: Path to the video URL file (used if file_manager is None)
        
    Returns:
        str: The video URL
    """
    try:
        if file_manager:
            return file_manager.read_input('video_url').strip()
        else:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as e:
        logger.error(
            "Failed to load video URL",
            error=str(e),
            path=str(path if not file_manager else file_manager.get_input_path('video_url'))
        )
        raise


def strip_thinking(text: str) -> str:
    """
    Remove <think>...</think> tags and their content
    
    Args:
        text: Text to process
        
    Returns:
        str: Text with thinking tags removed
    """
    return THINKING_PATTERN.sub('', text).strip()


def build_prompt(tweet: str, summary: str, video_url: str, podcast_overview: str = "") -> str:
    """
    Assemble prompt using DeepSeek-R1 template.

    ┌ System (instructions + summary) – NO role tag
    ├ <|User|> {tweet}
    └ <|Assistant|>                (model will continue here)
    """
    system_msg = (
        "You are a controversial social media manager for the WDF Podcast (War, Divorce or Federalism)\n"
        "The podcast has a strong libertarian/constitutionalist audience that values liberty, limited government, and individual rights.\n"
        "\n"
        "CRITICAL RULES:\n"
        "1. The user message is a tweet you are responding to.\n"
        "2. ASSUME THE USER HAS NEVER HEARD OF THE WDF PODCAST BEFORE.\n"
        f"3. Your response MUST be LESS THAN {MAX_TWEET_LENGTH} characters - this is ABSOLUTELY REQUIRED.\n"
        "4. Every response must reference the WDF Podcast by name.\n"
        "5. Make the user want to listen to the podcast.\n" 
        "6. Briefly mention what the latest episode discusses.\n"
        "7. Use language that resonates with liberty-minded, constitutionalist audiences.\n"
        "8. Be provocative and engaging, not just informational.\n"
        f"9. ALWAYS include the link {video_url}.\n"
        "10. Only output the tweet text—no extra formatting.\n"
        "11. No emojis allowed!\n"
        f"12. Double check your response is less than {MAX_TWEET_LENGTH} characters.\n"
        f"13. Triple check that your response is less than {MAX_TWEET_LENGTH} characters!\n"
        "\n"
        "PODCAST OVERVIEW:\n"
        f"{podcast_overview}\n"
        "\n"
        "EPISODE SUMMARY:\n"
        f"{summary}\n"
    )

    # Build the conversation prompt with proper DeepSeek role tokens
    prompt = (
        "<|User|>\n"
        f"{system_msg}\n"
        f"\n\n"
        f"This is the tweet you are replying to:\n"
        f"{tweet}\n\n"
        "<|User|>\n"
        "<|Assistant|>\n"
    )
    
    return prompt


def generate_response(client: Client, model: str, tweet_text: str, summary: str, overview: str, video_url: str, run_id: str = "unknown") -> str:
    """
    Generate a response to a tweet
    
    Args:
        client: Ollama client
        model: Model name
        tweet_text: The tweet to respond to
        summary: The podcast summary
        overview: The podcast overview
        video_url: The podcast video URL
        run_id: Run ID for metrics labeling
        
    Returns:
        str: The generated response
    """
    prompt = build_prompt(tweet_text, summary, video_url, overview)
    
    logger.debug(
        "Generating response",
        tweet_text=tweet_text[:50] + "..." if len(tweet_text) > 50 else tweet_text,
        prompt_length=len(prompt)
    )
    
    with DEEPSEEK_LATENCY.labels(run_id=run_id).time():
        resp = client.generate(
            model=model,
            prompt=prompt,
            options={
                "stop": [
                    "<｜begin▁of▁sentence｜>",
                    "<｜end▁of▁sentence｜>",
                    "<｜User｜>",
                    "<｜Assistant｜>"
                ]
            }
        )
    
    response = resp["response"].strip()
    
    # Strip thinking tags
    actual_response = strip_thinking(response)
    char_count = len(actual_response)
    
    logger.debug(
        "Generated response",
        char_count=char_count,
        response=actual_response[:50] + "..." if len(actual_response) > 50 else actual_response
    )
    
    # Log if response exceeds character limit but DO NOT trim
    if char_count > MAX_TWEET_LENGTH:
        logger.warning(
            "Response exceeds character limit",
            original_length=char_count,
            max_length=MAX_TWEET_LENGTH
        )
        RESPONSES_OVERSIZED.inc()
    
    return actual_response


def load_classified_tweets(file_manager=None) -> List[Dict]:
    """
    Load classified tweets from the classified.json file
    
    Args:
        file_manager: Optional episode file manager
    
    Returns:
        List[Dict]: List of classified tweet dictionaries
    """
    try:
        if file_manager:
            tweets_text = file_manager.read_input('classified')
            tweets = json.loads(tweets_text)
            path = file_manager.get_output_path('classified')
        else:
            with open(CLASSIFIED_PATH, "r") as f:
                tweets = json.load(f)
            path = CLASSIFIED_PATH
            
        if not isinstance(tweets, list):
            logger.error(
                "Classified tweets file has invalid format",
                expected="list of tweet objects",
                path=str(path)
            )
            return []
            
        from ..constants import RELEVANCY_THRESHOLD
        
        logger.info(
            "Loaded classified tweets",
            count=len(tweets),
            relevant_count=sum(1 for t in tweets if t.get("relevance_score", 0) >= RELEVANCY_THRESHOLD),
            avg_score=sum(t.get("relevance_score", 0) for t in tweets) / len(tweets) if tweets else 0,
            using_episode_files=bool(file_manager)
        )
        return tweets
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load classified tweets",
            error=str(e),
            path=str(path if 'path' in locals() else CLASSIFIED_PATH)
        )
        return []


def process_tweet(tweet: Dict, tweets: List[Dict], client: Client, model: str, 
                 summary: str, overview: str, video_url: str, run_id: str, 
                 responses_path: Path = RESPONSES_PATH, file_manager=None) -> Tuple[bool, Optional[Dict]]:
    """
    Process a single tweet and generate a response
    
    Args:
        tweet: The tweet to process
        tweets: The full list of tweets (for updating)
        client: Ollama client
        model: Model name
        summary: The podcast summary
        overview: The podcast overview
        video_url: The podcast video URL
        run_id: Run ID for metrics labeling
        responses_path: Path to write responses file
        file_manager: Optional episode file manager
        
    Returns:
        Tuple[bool, Optional[Dict]]: Success status and response summary if successful
    """
    if not tweet.get("classification") == "RELEVANT" or tweet.get("response"):
        # Skip tweets that are not relevant or already have responses
        return False, None
        
    try:
        response = generate_response(client, model, tweet["text"], summary, overview, video_url, run_id=run_id or "unknown")
        
        with file_lock:
            # Update the tweet with the response
            # Find the tweet in the tweets list (it might have been updated by other threads)
            for t in tweets:
                if t.get("id") == tweet.get("id"):
                    t["response"] = response
                    t["status"] = "pending"  # Will be approved/rejected in moderation
                    
                    # Write to file after each successful response generation
                    if file_manager:
                        file_manager.write_output('responses', tweets)
                    else:
                        with open(responses_path, "w") as f:
                            json.dump(tweets, f, indent=2)
                    
                    logger.info(
                        "Updated responses file with new response",
                        tweet_id=tweet.get("id", "unknown"),
                        path=str(responses_path if not file_manager else file_manager.get_output_path('responses')),
                        using_episode_files=bool(file_manager)
                    )
                    
                    # Create draft in web UI database if enabled
                    try:
                        draft_id = create_draft_if_web_mode(
                            tweet.get("id"),
                            response,
                            model
                        )
                        if draft_id:
                            logger.info(
                                "Created draft in web UI database",
                                tweet_id=tweet.get("id"),
                                draft_id=draft_id
                            )
                    except Exception as e:
                        logger.warning(
                            "Failed to create draft in web UI",
                            tweet_id=tweet.get("id"),
                            error=str(e)
                        )
                    
                    # Copy to artefacts directory if run_id is provided
                    if run_id:
                        artefact_dir = settings.get_run_dir(run_id)
                        artefact_responses = artefact_dir / "responses.json"
                        if file_manager:
                            artefact_responses.write_text(json.dumps(tweets, indent=2))
                        else:
                            artefact_responses.write_text(responses_path.read_text())
                        
                        logger.info(
                            "Updated responses in artefacts directory",
                            tweet_id=tweet.get("id", "unknown"),
                            path=str(artefact_responses)
                        )
                    break
        
        RESPONSES_GENERATED.inc()
        
        # Create response summary for logging
        response_summary = {
            "tweet_id": tweet.get("id", "unknown"),
            "user": tweet.get("user", "unknown"),
            "tweet_text": tweet["text"][:50] + "..." if len(tweet["text"]) > 50 else tweet["text"],
            "response": response,
            "char_count": len(response)
        }
        
        return True, response_summary
        
    except Exception as e:
        logger.error(
            "Error generating response",
            tweet_id=tweet.get("id", "unknown"),
            error=str(e)
        )
        DEEPSEEK_ERRORS.inc()
        return False, None


def run(run_id: str = None, model: str = None, num_workers: int = DEFAULT_NUM_WORKERS, episode_id: str = None) -> Path:
    """
    Run the DeepSeek response generation task with multiple workers
    
    Args:
        run_id: Optional run ID for artefact storage
        model: Optional model name override
        num_workers: Number of worker threads to use for parallel processing
        episode_id: Optional episode ID for file management
        
    Returns:
        Path: Path to the responses file
    """
    # Ensure num_workers is set to a valid value
    if num_workers is None:
        num_workers = DEFAULT_NUM_WORKERS
        
    logger.info(
        "Starting DeepSeek response generation task",
        run_id=run_id,
        num_workers=num_workers,
        episode_id=episode_id
    )
    
    # Use episode file manager if episode_id provided
    use_episode_files = episode_id or os.environ.get('WDF_EPISODE_ID')
    if use_episode_files:
        file_manager = get_episode_file_manager(episode_id)
        logger.info(
            "Using episode file manager",
            episode_dir=file_manager.episode_dir
        )
    
    # Create artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_dir.mkdir(parents=True, exist_ok=True)
    
    # Load classified tweets
    tweets = load_classified_tweets(file_manager if use_episode_files else None)
    if not tweets:
        raise RuntimeError("No classified tweets found")
    
    # Filter relevant tweets without responses
    relevant_tweets = [
        t for t in tweets 
        if t.get("classification") == "RELEVANT" and not t.get("response")
    ]
    
    if not relevant_tweets:
        logger.info("No relevant tweets without responses found")
        if use_episode_files:
            return file_manager.get_output_path('responses')
        else:
            return RESPONSES_PATH
    
    logger.info(
        "Found relevant tweets without responses",
        count=len(relevant_tweets),
        relevancy_threshold=RELEVANCY_THRESHOLD
    )
    
    # Load summary and video URL
    summary = load_summary(file_manager if use_episode_files else None)
    overview = load_overview(file_manager if use_episode_files else None)
    video_url = load_video_url(file_manager if use_episode_files else None)
    
    # Determine responses path
    if use_episode_files:
        responses_path = file_manager.get_output_path('responses')
    else:
        responses_path = RESPONSES_PATH
    
    # Initialize Ollama client
    model = model or settings.llm_models.deepseek
    client = Client(host=settings.ollama_host)
    
    # Generate responses in parallel
    new_responses = 0
    response_summaries = []
    
    # Adjust number of workers based on available tweets
    effective_num_workers = min(num_workers, len(relevant_tweets))
    if effective_num_workers < num_workers:
        logger.info(
            "Reducing worker count to match available tweets",
            requested_workers=num_workers,
            effective_workers=effective_num_workers
        )
    
    logger.info(f"Processing {len(relevant_tweets)} tweets with {effective_num_workers} workers")
    
    # For single worker mode, process sequentially with delay between requests
    if effective_num_workers == 1:
        print(f"\n[DeepSeek] Starting to process {len(relevant_tweets)} tweets sequentially...\n")
        
        for i, tweet in enumerate(relevant_tweets):
            # Process tweet
            success, summary = process_tweet(
                tweet, tweets, client, model, summary, overview, video_url, run_id,
                responses_path, file_manager if use_episode_files else None
            )
            
            # Update counters
            if success:
                new_responses += 1
                response_summaries.append(summary)
            
            # Display progress
            completed = i + 1
            progress_msg = f"Progress: {completed}/{len(relevant_tweets)} tweets processed ({(completed/len(relevant_tweets))*100:.1f}%)"
            logger.info(
                progress_msg,
                completed=completed,
                total=len(relevant_tweets),
                remaining=len(relevant_tweets)-completed
            )
            
            # Print directly to console for better visibility
            if success:
                tweet_snippet = summary["tweet_text"][:30] + "..." if len(summary["tweet_text"]) > 30 else summary["tweet_text"]
                response_snippet = summary["response"][:40] + "..." if len(summary["response"]) > 40 else summary["response"]
                print(f"[{completed}/{len(relevant_tweets)}] ✓ Generated response for tweet: \"{tweet_snippet}\"")
                print(f"    Response: \"{response_snippet}\"")
                print(f"    Remaining: {len(relevant_tweets)-completed} tweets\n")
            else:
                print(f"[{completed}/{len(relevant_tweets)}] ✗ Failed to generate response for a tweet")
                print(f"    Remaining: {len(relevant_tweets)-completed} tweets\n")
            
            # Add delay between requests to prevent overloading Ollama
            if completed < len(relevant_tweets):
                time.sleep(0.5)  # 500ms delay between requests
    else:
        # Process tweets in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=effective_num_workers) as executor:
            # Submit all relevant tweets for processing
            futures = [
                executor.submit(
                    process_tweet, 
                    tweet, 
                    tweets, 
                    client, 
                    model, 
                    summary, 
                    overview, 
                    video_url, 
                    run_id,
                    responses_path,
                    file_manager if use_episode_files else None
                )
                for tweet in relevant_tweets
            ]
            
            # Setup progress tracking
            total_tweets = len(futures)
            completed = 0
            
            # Collect results as they complete
            print(f"\n[DeepSeek] Starting to process {total_tweets} tweets with {effective_num_workers} workers...\n")
            for future in futures:
                success, summary = future.result()
                if success:
                    new_responses += 1
                    response_summaries.append(summary)
                    
                # Update and display progress
                completed += 1
                
                # Log to both logger and print directly to console for better visibility
                progress_msg = f"Progress: {completed}/{total_tweets} tweets processed ({(completed/total_tweets)*100:.1f}%)"
                logger.info(
                    progress_msg,
                    completed=completed,
                    total=total_tweets,
                    remaining=total_tweets-completed
                )
                
                # Print directly to console for better visibility
                if success:
                    tweet_snippet = summary["tweet_text"][:30] + "..." if len(summary["tweet_text"]) > 30 else summary["tweet_text"]
                    response_snippet = summary["response"][:40] + "..." if len(summary["response"]) > 40 else summary["response"]
                    print(f"[{completed}/{total_tweets}] ✓ Generated response for tweet: \"{tweet_snippet}\"")
                    print(f"    Response: \"{response_snippet}\"")
                    print(f"    Remaining: {total_tweets-completed} tweets\n")
                else:
                    print(f"[{completed}/{total_tweets}] ✗ Failed to generate response for a tweet")
                    print(f"    Remaining: {total_tweets-completed} tweets\n")
    
    # Final summary log
    logger.info(
        "Completed DeepSeek response generation",
        path=str(RESPONSES_PATH),
        new_responses=new_responses
    )
    
    # Document the responses
    if new_responses > 0:
        logger.info("Generated response summaries:")
        for i, summary in enumerate(response_summaries, 1):
            logger.info(
                f"Response {i}/{len(response_summaries)}",
                tweet_id=summary["tweet_id"],
                user=summary["user"],
                tweet_snippet=summary["tweet_text"],
                response=summary["response"],
                char_count=summary["char_count"]
            )
    
    if run_id:
        return artefact_dir / "responses.json"
    elif use_episode_files:
        return file_manager.get_output_path('responses')
    else:
        return RESPONSES_PATH


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Set up argument parser for command line usage
    import argparse
    parser = argparse.ArgumentParser(description="Generate responses to relevant tweets using DeepSeek")
    parser.add_argument("--workers", type=int, default=DEFAULT_NUM_WORKERS,
                        help=f"Number of worker threads (default: {DEFAULT_NUM_WORKERS})")
    parser.add_argument("--run-id", type=str, help="Run ID for artefact storage")
    parser.add_argument("--model", type=str, help="Model name override")
    args = parser.parse_args()
    
    # Run the task
    run(run_id=args.run_id, model=args.model, num_workers=args.workers) 