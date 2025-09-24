#!/usr/bin/env python3
"""
tweet_response_generator.py – WDF-podcast tweet response generator
-----------------------------------------------------------------
• Reads transcripts/summary.md (truncated to keep context small).
• Reads transcripts/VIDEO_URL.txt for the latest podcast URL.
• ASSUMES every user prompt is a tweet to respond to.
• Produces ONE tweet response (<280 chars) that:
    – Introduces the WDF podcast to unfamiliar audiences
    – Invites engagement with the latest podcast episode
    – STRICTLY stays under 280 characters
    – Always contains the latest YouTube URL
• WDF = "War, Divorce or Federalism" - a libertarian/constitutionalist podcast
• Supports multiple LLM backends through configuration
• Streams response to the terminal
-----------------------------------------------------------------
"""

import argparse
import logging
from pathlib import Path
from textwrap import shorten
import sys
import re

from ollama import Client  # pip install ollama

# Import prompt utilities
sys.path.append(str(Path(__file__).parent))
try:
    from src.wdf.prompt_utils import build_response_prompt, get_context_file
except ImportError:
    # Fallback if module not available
    build_response_prompt = None
    get_context_file = None

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
import os
DEFAULT_MODEL = os.environ.get("WDF_LLM_MODEL_RESPONSE", os.environ.get("WDF_LLM_MODELS__RESPONSE", "deepseek-r1:latest"))
DEFAULT_HOST = "http://localhost:11434"
SUMMARY_PATH = Path("transcripts/summary.md")
OVERVIEW_PATH = Path("transcripts/podcast_overview.txt")
VIDEO_URL_PATH = Path("transcripts/VIDEO_URL.txt")
MAX_SUMMARY_CHARS = 20_000   # fits well inside 128 k context
MAX_TWEET_LENGTH = 200  # Twitter's limit is 280, but leave some buffer
THINKING_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def load_summary(path: Path = SUMMARY_PATH,
                 max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Return podcast summary, trimmed if necessary."""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        if max_chars and len(txt) > max_chars:
            logging.info("Truncating summary from %s to %s chars",
                         len(txt), max_chars)
            return shorten(txt, width=max_chars, placeholder="...")
        return txt
    except Exception as exc:
        logging.error("Failed to load summary: %s", exc)
        print(f"ERROR: Could not load summary from {path}")
        sys.exit(1)

def load_video_url(path: Path = VIDEO_URL_PATH) -> str:
    """Return the latest podcast video URL."""
    # Try to get from database first
    if get_context_file:
        db_url = get_context_file('video_url')
        if db_url:
            return db_url
    
    # Fall back to file
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as exc:
        logging.error("Failed to load video URL: %s", exc)
        print(f"ERROR: Could not load video URL from {path}")
        sys.exit(1)

def strip_thinking(text: str) -> str:
    """Remove <think>...</think> tags and their content."""
    return THINKING_PATTERN.sub('', text).strip()

def load_overview(path: Path = OVERVIEW_PATH) -> str:
    """
    Load the podcast overview
    
    Args:
        path: Path to the podcast overview file
        
    Returns:
        str: The podcast overview text
    """
    # Try to get from database first
    if get_context_file:
        db_overview = get_context_file('podcast_overview')
        if db_overview:
            return db_overview
    
    # Fall back to file
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as e:
        logging.error(
            "Failed to load podcast overview",
            error=str(e),
            path=str(path)
        )
        logging.warning("Using empty podcast overview")
        return "The WDF (War, Divorce or Federalism) podcast features discussions on liberty, constitutionalism, and state sovereignty."

def build_prompt(tweet: str, summary: str, video_url: str, podcast_overview: str) -> str:
    """
    Assemble prompt using chat template format.

    ┌ System (instructions + summary) – NO role tag
    ├ <|User|> {tweet}
    └ <|Assistant|>                (model will continue here)
    """
    # Use database prompt if available
    if build_response_prompt:
        system_msg = build_response_prompt(
            max_length=MAX_TWEET_LENGTH,
            video_url=video_url,
            podcast_overview=podcast_overview,
            summary=summary
        )
    else:
        # Fallback to hardcoded prompt
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


# ----------------------------------------------------------------------
# Main CLI
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tweet response generator for WDF Podcast (War, Divorce or Federalism)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Ollama API host (default: {DEFAULT_HOST})")
    parser.add_argument("--no-trim", action="store_true",
                        help="Don't truncate summary")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()

    # Logging setup
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    summary = load_summary(max_chars=None if args.no_trim else MAX_SUMMARY_CHARS)
    logging.info("Loaded summary: %d characters", len(summary))

    video_url = load_video_url()
    logging.info("Loaded video URL: %s", video_url)
    
    # Load podcast overview
    podcast_overview = load_overview()
    logging.info("Loaded podcast overview: %d characters", len(podcast_overview))

    # Connect to Ollama
    try:
        client = Client(host=args.host)
        logging.info("Connected to Ollama at %s", args.host)
    except Exception as exc:
        logging.error("Ollama connection failed: %s", exc)
        print(f"ERROR: Could not connect to Ollama at {args.host}")
        sys.exit(1)

    # REPL loop
    print("WDF Podcast Tweet Response Generator")
    print("(War, Divorce or Federalism)")
    print(f"Model: {args.model}")
    print(f"Latest podcast URL: {video_url}")
    print("Type a tweet to respond to (Ctrl-C to quit).")

    while True:
        try:
            tweet = input("\n> ").strip()
            if not tweet:
                continue

            prompt = build_prompt(tweet, summary, video_url, podcast_overview)
            if args.debug:
                logging.debug("Prompt length ≈ %d chars", len(prompt))

            try:
                # Stream the response
                print("Response: ", end="", flush=True)
                full_response = ""
                for chunk in client.generate(
                    model=args.model,
                    prompt=prompt,
                    stream=True,
                    options={
                        "stop": [
                    "<｜begin▁of▁sentence｜>",
                    "<｜end▁of▁sentence｜>",
                    "<｜User｜>",
                    "<｜Assistant｜>"
                        ]
                    }
                ):
                    response_chunk = chunk["response"]
                    print(response_chunk, end="", flush=True)
                    full_response += response_chunk
                
                print()  # Add newline after streaming completes
                
                # Strip thinking tags and check character count
                actual_response = strip_thinking(full_response)
                char_count = len(actual_response)
                
                # Log both the full response and the filtered response
                logging.debug("Full response: %s", full_response)
                logging.debug("Actual tweet response (%d chars): %s", char_count, actual_response)
                
                if char_count > 250:
                    print(f"\n⚠️  WARNING: Response exceeds 250 chars (actual: {char_count})")
            except Exception as exc:
                logging.error("Generation error: %s", exc)
                print(f"ERROR: {exc}")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nInput stream closed. Exiting.")
            break
        except Exception as exc:
            logging.error("Unexpected error: %s", exc)
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
