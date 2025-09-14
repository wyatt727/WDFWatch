#!/usr/bin/env python3
"""
claude-response.py – WDF-podcast tweet response generator using Claude CLI
-------------------------------------------------------------------------
• Reads transcripts/summary.md (truncated to keep context small)
• Reads transcripts/podcast_overview.txt for podcast context  
• Reads transcripts/VIDEO_URL.txt for the latest podcast URL
• Uses Claude CLI (Sonnet model) to generate responses to tweets
• Produces ONE tweet response (<280 chars) that:
    – Introduces the WDF podcast to unfamiliar audiences
    – Invites engagement with the latest podcast episode
    – STRICTLY stays under 280 characters
    – Always contains the latest YouTube URL
• WDF = "War, Divorce or Federalism" - a libertarian/constitutionalist podcast
• Interacts with: tweet_response_generator.py, src/wdf/tasks/deepseek.py
-------------------------------------------------------------------------
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from textwrap import shorten
from typing import Dict, List

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
# Paths are relative to parent directory since script is in claude-tweet-responder/
PARENT_DIR = Path(__file__).parent.parent
SUMMARY_PATH = PARENT_DIR / "transcripts/summary.md"
OVERVIEW_PATH = PARENT_DIR / "transcripts/podcast_overview.txt"
VIDEO_URL_PATH = PARENT_DIR / "transcripts/VIDEO_URL.txt"
CLASSIFIED_PATH = PARENT_DIR / "transcripts/classified.json"
RESPONSES_PATH = PARENT_DIR / "transcripts/responses.json"
MAX_TWEET_LENGTH = 200  # Twitter's limit is 280, but leave some buffer
CLAUDE_CLI = "/Users/pentester/.claude/local/claude"
RATE_LIMIT_DELAY = 0  # No rate limit needed with MAX20 plan
RELEVANCY_THRESHOLD = 0.70  # Default threshold for relevant tweets

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def load_file(path: Path, max_chars: int = None) -> str:
    """Load a file, optionally truncating to max_chars."""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore").strip()
        if max_chars and len(txt) > max_chars:
            logging.info("Truncating %s from %s to %s chars", path.name, len(txt), max_chars)
            return shorten(txt, width=max_chars, placeholder="...")
        return txt
    except Exception as exc:
        logging.error("Failed to load %s: %s", path, exc)
        print(f"ERROR: Could not load {path}: {exc}")
        sys.exit(1)


def extract_episode_key_points(summary: str, max_chars: int = 500) -> str:
    """
    Extract key talking points from the full episode summary.
    
    Args:
        summary: Full episode summary
        max_chars: Maximum characters for key points
        
    Returns:
        Condensed key points string
    """
    # Look for key sections in the summary
    key_sections = []
    
    # Try to extract guest information
    if "guest" in summary.lower() or "daniel miller" in summary.lower():
        # Find guest mentions
        lines = summary.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['guest', 'daniel', 'miller', 'discusses', 'explains']):
                key_sections.append(line.strip())
                if len(key_sections) >= 3:
                    break
    
    # If we didn't find enough, take the first few non-empty lines
    if len(key_sections) < 3:
        lines = [l.strip() for l in summary.split('\n') if l.strip()]
        key_sections = lines[:5]
    
    # Join and truncate
    key_points = '\n'.join(key_sections)
    if len(key_points) > max_chars:
        key_points = key_points[:max_chars] + "..."
    
    return key_points


def build_claude_prompt(tweet: str, summary: str, video_url: str, podcast_overview: str = None) -> str:
    """
    Build the prompt for Claude CLI.
    
    Optimized to minimize token usage while maintaining quality.
    Podcast overview is now in CLAUDE.md, so we don't need to pass it.
    
    Args:
        tweet: The tweet to respond to
        summary: The podcast episode summary
        video_url: The YouTube URL for the episode
        podcast_overview: DEPRECATED - now in CLAUDE.md (kept for compatibility)
        
    Returns:
        The formatted prompt for Claude
    """
    # Extract key points instead of using full summary
    key_points = extract_episode_key_points(summary)
    
    # Streamlined prompt - CLAUDE.md has the context
    prompt = f"""EPISODE KEY POINTS:
{key_points}

VIDEO URL TO INCLUDE:
{video_url}

TWEET TO RESPOND TO:
{tweet}"""
    
    return prompt


def load_classified_tweets(path: Path = CLASSIFIED_PATH) -> List[Dict]:
    """
    Load classified tweets from JSON file.
    
    Args:
        path: Path to classified.json file
        
    Returns:
        List of tweet dictionaries
    """
    try:
        with open(path, 'r') as f:
            tweets = json.load(f)
        
        if not isinstance(tweets, list):
            logging.error("Classified tweets file has invalid format")
            return []
        
        # Import threshold if available
        try:
            from src.wdf.constants import RELEVANCY_THRESHOLD as threshold
        except ImportError:
            threshold = RELEVANCY_THRESHOLD
        
        # Filter for relevant tweets
        relevant = [t for t in tweets if t.get("relevance_score", 0) >= threshold 
                   or t.get("classification") == "RELEVANT"]
        
        logging.info("Loaded %d tweets, %d relevant", len(tweets), len(relevant))
        return tweets
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error("Failed to load classified tweets: %s", e)
        return []


def save_responses(tweets: List[Dict], path: Path = RESPONSES_PATH) -> None:
    """
    Save tweet responses to JSON file.
    
    Args:
        tweets: List of tweet dictionaries with responses
        path: Path to save responses.json
    """
    try:
        with open(path, 'w') as f:
            json.dump(tweets, f, indent=2)
        logging.debug("Saved responses to %s", path)
    except Exception as e:
        logging.error("Failed to save responses: %s", e)


def process_batch(input_file: Path, output_file: Path, 
                  summary: str, video_url: str, podcast_overview: str,
                  rate_limit_delay: float = RATE_LIMIT_DELAY) -> int:
    """
    Process a batch of tweets from classified.json and generate responses.
    
    Args:
        input_file: Path to classified.json
        output_file: Path to save responses.json
        summary: Episode summary
        video_url: Video URL
        podcast_overview: Podcast overview
        rate_limit_delay: Seconds to wait between API calls
        
    Returns:
        Number of responses generated
    """
    # Load tweets
    tweets = load_classified_tweets(input_file)
    if not tweets:
        print("No tweets to process")
        return 0
    
    # Filter for relevant tweets without responses
    to_process = []
    for t in tweets:
        if (t.get("classification") == "RELEVANT" or 
            t.get("relevance_score", 0) >= RELEVANCY_THRESHOLD):
            if not t.get("response"):
                to_process.append(t)
    
    if not to_process:
        print("No relevant tweets without responses found")
        save_responses(tweets, output_file)
        return 0
    
    print(f"\n📊 Processing {len(to_process)} relevant tweets...")
    print("=" * 60)
    
    responses_generated = 0
    errors = 0
    
    for i, tweet in enumerate(to_process, 1):
        tweet_text = tweet.get("text", "")
        tweet_id = tweet.get("id", f"unknown_{i}")
        user = tweet.get("user", "unknown")
        
        # Display progress
        print(f"\n[{i}/{len(to_process)}] Processing tweet from {user}")
        print(f"Tweet: {tweet_text[:100]}..." if len(tweet_text) > 100 else f"Tweet: {tweet_text}")
        
        try:
            # Build prompt and generate response
            prompt = build_claude_prompt(tweet_text, summary, video_url, podcast_overview)
            response = call_claude(prompt)
            
            # Update tweet with response
            for t in tweets:
                if t.get("id") == tweet_id:
                    t["response"] = response
                    t["response_length"] = len(response)
                    t["model"] = "claude-sonnet"
                    t["status"] = "pending"  # Will be approved/rejected in moderation
                    break
            
            # Save incrementally after each response
            save_responses(tweets, output_file)
            
            responses_generated += 1
            print(f"✅ Response ({len(response)} chars): {response[:80]}...")
            
            # Rate limiting - only if specified
            if rate_limit_delay > 0 and i < len(to_process):
                logging.debug("Waiting %.1f seconds for rate limit...", rate_limit_delay)
                time.sleep(rate_limit_delay)
                
        except Exception as e:
            errors += 1
            logging.error("Failed to generate response for tweet %s: %s", tweet_id, e)
            print(f"❌ Error: {e}")
            
            # Still save progress even on error
            save_responses(tweets, output_file)
    
    # Final summary
    print("\n" + "=" * 60)
    print(f"✨ Batch processing complete!")
    print(f"   Generated: {responses_generated} responses")
    print(f"   Errors: {errors}")
    print(f"   Output: {output_file}")
    
    return responses_generated


def call_claude(prompt: str) -> str:
    """
    Call Claude CLI with the given prompt.
    
    Since we're already in the claude-tweet-responder directory with CLAUDE.md,
    Claude will automatically use that context.
    
    Args:
        prompt: The prompt to send to Claude
        
    Returns:
        Claude's response text
    """
    try:
        logging.debug("Calling Claude CLI with Sonnet (prompt length: %d chars)", len(prompt))
        
        # Call Claude CLI directly - we're already in the right directory
        result = subprocess.run(
            [CLAUDE_CLI, "--model", "sonnet", "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            timeout=30  # 30 second timeout
        )
        
        if result.returncode != 0:
            logging.error("Claude CLI failed: %s", result.stderr)
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")
        
        response = result.stdout.strip()
        
        # With CLAUDE.md context, response should be clean tweet text
        # But still do basic validation
        if not response:
            raise RuntimeError("Claude returned empty response")
        
        # Remove any accidental formatting if present
        # (Claude should only output tweet text with CLAUDE.md context)
        response = response.strip()
        
        # Log warning if response seems wrong
        if len(response) > 280:
            logging.warning("Response exceeds 280 characters: %d", len(response))
        
        if 'error' in response.lower() and len(response) < 30:
            logging.warning("Response might be an error: %s", response)
        
        return response
        
    except subprocess.TimeoutExpired:
        logging.error("Claude CLI timed out after 30 seconds")
        raise RuntimeError("Claude CLI timed out - prompt may be too long or Claude is unresponsive")
    except Exception as exc:
        logging.error("Error calling Claude: %s", exc)
        raise


# ----------------------------------------------------------------------
# Main CLI
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tweet response generator for WDF Podcast using Claude CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single tweet:
    %(prog)s "The federal government is out of control!"
    
  Batch processing:
    %(prog)s --batch
    %(prog)s --batch --input classified.json --output responses.json
    
  Interactive mode:
    %(prog)s
        """
    )
    parser.add_argument("tweet", nargs="?", 
                        help="The tweet text to respond to (interactive mode if not provided)")
    parser.add_argument("--batch", action="store_true",
                        help="Process batch of tweets from classified.json")
    parser.add_argument("--input", type=Path, default=CLASSIFIED_PATH,
                        help="Input file for batch mode (default: transcripts/classified.json)")
    parser.add_argument("--output", type=Path, default=RESPONSES_PATH,
                        help="Output file for batch mode (default: transcripts/responses.json)")
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT_DELAY,
                        help="Seconds between API calls (default: 0, no limit with MAX20 plan)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("--show-prompt", action="store_true",
                        help="Show the full prompt sent to Claude")
    args = parser.parse_args()

    # Logging setup
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load context files (no truncation for Claude)
    summary = load_file(SUMMARY_PATH)  # Load full summary for better context
    logging.info("Loaded summary: %d characters", len(summary))

    video_url = load_file(VIDEO_URL_PATH)
    logging.info("Loaded video URL: %s", video_url)
    
    podcast_overview = load_file(OVERVIEW_PATH)
    logging.info("Loaded podcast overview: %d characters", len(podcast_overview))

    # Check Claude CLI exists
    if not Path(CLAUDE_CLI).exists():
        print(f"ERROR: Claude CLI not found at {CLAUDE_CLI}")
        print("Please ensure Claude CLI is installed and the path is correct.")
        sys.exit(1)

    # Handle batch mode
    if args.batch:
        print("🎙️  WDF Podcast Tweet Response Generator (Claude Sonnet)")
        print("=" * 60)
        print("Mode: Batch Processing")
        print(f"Input: {args.input}")
        print(f"Output: {args.output}")
        if args.rate_limit > 0:
            print(f"Rate limit: {args.rate_limit}s between requests")
        else:
            print("Rate limit: None (MAX20 plan)")
        print(f"Latest podcast URL: {video_url}")
        
        # Process batch
        num_responses = process_batch(
            args.input, 
            args.output,
            summary,
            video_url,
            podcast_overview,
            args.rate_limit
        )
        
        sys.exit(0 if num_responses > 0 else 1)
    
    # Single tweet or interactive mode
    print("🎙️  WDF Podcast Tweet Response Generator (Claude Sonnet)")
    print("=" * 60)
    print(f"Latest podcast URL: {video_url}")
    print()

    # Interactive or single-shot mode
    if args.tweet:
        # Single tweet mode
        tweet = args.tweet.strip()
        print(f"Tweet: {tweet}")
        print("-" * 60)
        
        prompt = build_claude_prompt(tweet, summary, video_url, podcast_overview)
        
        if args.show_prompt:
            print("PROMPT:")
            print(prompt)
            print("-" * 60)
        
        try:
            response = call_claude(prompt)
            print(f"Response: {response}")
            print(f"\nCharacter count: {len(response)}")
            
            if len(response) > 250:
                print(f"⚠️  WARNING: Response exceeds 250 chars (actual: {len(response)})")
            elif len(response) > MAX_TWEET_LENGTH:
                print(f"✅ Response is within {MAX_TWEET_LENGTH} character limit")
                
        except Exception as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
    else:
        # Interactive mode
        print("Type a tweet to respond to (Ctrl-C to quit):")
        
        while True:
            try:
                tweet = input("\n> ").strip()
                if not tweet:
                    continue

                prompt = build_claude_prompt(tweet, summary, video_url, podcast_overview)
                
                if args.show_prompt:
                    print("\nPROMPT:")
                    print(prompt)
                    print("-" * 60)
                
                try:
                    print("Generating response...")
                    response = call_claude(prompt)
                    print(f"\nResponse: {response}")
                    print(f"Character count: {len(response)}")
                    
                    if len(response) > 250:
                        print(f"⚠️  WARNING: Response exceeds 250 chars")
                    elif len(response) > MAX_TWEET_LENGTH:
                        print(f"✅ Response is within {MAX_TWEET_LENGTH} character limit")
                        
                except Exception as exc:
                    print(f"ERROR: {exc}")

            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except EOFError:
                print("\nInput stream closed. Exiting.")
                break


if __name__ == "__main__":
    main()