"""
Tweet moderation task

This module provides a Rich-based TUI for moderating generated tweet responses.
"""

import csv
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
from prometheus_client import Counter
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from ..settings import settings
from ..twitter_client import TweetReply, get_twitter_client

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics
TWEETS_APPROVED = Counter(
    "tweets_approved_total",
    "Number of tweet responses approved"
)
TWEETS_EDITED = Counter(
    "tweets_edited_total",
    "Number of tweet responses edited before approval"
)
TWEETS_REJECTED = Counter(
    "tweets_rejected_total",
    "Number of tweet responses rejected"
)

# File paths
RESPONSES_PATH = Path(settings.transcript_dir) / "responses.json"
AUDIT_PATH = Path(settings.transcript_dir) / "audit.csv"

# Rich theme
THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "tweet": "bold white on blue",
    "response": "bold white on green",
    "approved": "bold green",
    "rejected": "bold red",
    "edited": "bold yellow",
    "pending": "bold cyan",
    "help": "italic"
})

# Console for rich output
console = Console(theme=THEME)


def load_responses() -> List[Dict]:
    """
    Load responses from the responses.json file
    
    Returns:
        List[Dict]: List of tweet dictionaries with responses
    """
    try:
        with open(RESPONSES_PATH, "r") as f:
            tweets = json.load(f)
            
        if not isinstance(tweets, list):
            logger.error(
                "Responses file has invalid format",
                expected="list of tweet objects",
                path=str(RESPONSES_PATH)
            )
            return []
            
        # Filter for tweets with responses
        tweets_with_responses = [t for t in tweets if t.get("response")]
        
        logger.info(
            "Loaded tweets with responses",
            count=len(tweets_with_responses),
            pending_count=sum(1 for t in tweets_with_responses if t.get("status") == "pending")
        )
        return tweets
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load responses",
            error=str(e),
            path=str(RESPONSES_PATH)
        )
        return []


def save_responses(tweets: List[Dict]) -> None:
    """
    Save responses to the responses.json file
    
    Args:
        tweets: List of tweet dictionaries with responses
    """
    try:
        with open(RESPONSES_PATH, "w") as f:
            json.dump(tweets, f, indent=2)
            
        logger.info(
            "Saved tweets with responses",
            path=str(RESPONSES_PATH),
            count=len(tweets)
        )
    except Exception as e:
        logger.error(
            "Failed to save responses",
            error=str(e),
            path=str(RESPONSES_PATH)
        )
        raise


def log_audit(tweet_id: str, tweet_text: str, response: str, action: str, edited: bool = False):
    """
    Log moderation actions to an audit file
    
    Args:
        tweet_id: Tweet ID
        tweet_text: Original tweet text
        response: Generated response
        action: Action taken (approved, rejected)
        edited: Whether the response was edited
    """
    # Create audit file if it doesn't exist
    if not AUDIT_PATH.exists():
        with open(AUDIT_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "tweet_id", "action", "edited", "tweet_text", "response"])
        
        logger.info(
            "Created audit log file",
            path=str(AUDIT_PATH)
        )
    
    # Append record
    with open(AUDIT_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().isoformat(),
            tweet_id,
            action,
            "yes" if edited else "no",
            tweet_text,
            response
        ])
        
    logger.info(
        "Logged action to audit file",
        tweet_id=tweet_id,
        action=action,
        edited=edited
    )


def edit_response(text: str) -> str:
    """
    Open an editor to edit the response
    
    Args:
        text: Original response text
        
    Returns:
        str: Edited response text
    """
    editor = os.environ.get("EDITOR", "nano")
    
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+", delete=False) as temp:
        temp_path = temp.name
        temp.write(text)
        
    try:
        subprocess.run([editor, temp_path], check=True)
        with open(temp_path, "r") as f:
            edited_text = f.read().strip()
        return edited_text
    finally:
        os.unlink(temp_path)


def display_tweet(tweet: Dict, index: int, total: int) -> None:
    """
    Display a tweet and its response in the console
    
    Args:
        tweet: Tweet dictionary
        index: Current index
        total: Total number of tweets
    """
    # Clear the screen
    console.clear()
    
    # Display header
    console.print(f"[bold]Tweet Moderation ({index + 1}/{total})[/bold]")
    console.print()
    
    # Display original tweet
    console.print(Panel(
        Text(tweet["text"], style="tweet"),
        title=f"Original Tweet (by {tweet.get('user', 'unknown')})",
        expand=False
    ))
    console.print()
    
    # Display response
    status = tweet.get("status", "pending")
    console.print(Panel(
        Text(tweet.get("response", ""), style="response"),
        title=f"Response ({len(tweet.get('response', ''))} chars)",
        subtitle=f"Status: [{status}]{status}[/{status}]",
        expand=False
    ))
    console.print()
    
    # Display help
    console.print(Text(
        "Actions: [a]pprove | [e]dit | [r]eject | [q]uit",
        style="help"
    ))
    console.print()


def moderate_tweets(tweets: List[Dict], run_id: str = "unknown") -> Tuple[int, int, int]:
    """
    Run the moderation TUI
    
    Args:
        tweets: List of tweet dictionaries with responses
        run_id: Run ID for metrics and tracking
        
    Returns:
        Tuple[int, int, int]: Count of approved, edited, and rejected tweets
    """
    # Filter for tweets with responses that are pending moderation
    pending_tweets = [
        t for t in tweets 
        if t.get("response") and t.get("status") == "pending"
    ]
    
    if not pending_tweets:
        console.print("[info]No pending tweets to moderate.[/info]")
        return 0, 0, 0
    
    # Initialize counters
    approved = 0
    edited = 0
    rejected = 0
    
    # Get Twitter client for publishing
    twitter_client = get_twitter_client()
    
    # Process each pending tweet
    for i, tweet in enumerate(pending_tweets):
        while True:
            display_tweet(tweet, i, len(pending_tweets))
            
            # Get user action
            action = console.input("Action: ").lower().strip()
            
            if action == "q":
                console.print("[info]Moderation paused. Progress has been saved.[/info]")
                return approved, edited, rejected
                
            elif action == "a":
                # Approve and publish
                tweet["status"] = "approved"
                
                # Publish to Twitter
                success = twitter_client.reply_to_tweet(tweet["id"], tweet["response"], run_id=run_id)
                
                if success:
                    console.print("[approved]Tweet approved and published![/approved]")
                    log_audit(tweet["id"], tweet["text"], tweet["response"], "approved", edited=False)
                    approved += 1
                    TWEETS_APPROVED.inc()
                else:
                    console.print("[error]Failed to publish tweet![/error]")
                    tweet["status"] = "error"
                    
                break
                
            elif action == "e":
                # Edit the response
                original_response = tweet["response"]
                edited_response = edit_response(original_response)
                
                if edited_response != original_response:
                    tweet["response"] = edited_response
                    tweet["edited"] = True
                    edited += 1
                    TWEETS_EDITED.inc()
                    console.print("[edited]Response edited.[/edited]")
                    
                    # Save after each edit
                    save_responses(tweets)
                
            elif action == "r":
                # Reject
                tweet["status"] = "rejected"
                console.print("[rejected]Tweet rejected.[/rejected]")
                log_audit(tweet["id"], tweet["text"], tweet["response"], "rejected", edited=False)
                rejected += 1
                TWEETS_REJECTED.inc()
                break
                
            else:
                console.print("[error]Invalid action. Try again.[/error]")
    
    console.print("[info]All pending tweets have been moderated![/info]")
    return approved, edited, rejected


def run(run_id: str = None, non_interactive: bool = False) -> Path:
    """
    Run the tweet moderation task
    
    Args:
        run_id: Optional run ID for artefact storage
        non_interactive: If True, skip the interactive moderation
        
    Returns:
        Path: Path to the responses file
    """
    logger.info(
        "Starting tweet moderation task",
        run_id=run_id,
        non_interactive=non_interactive
    )
    
    # Create artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_dir.mkdir(parents=True, exist_ok=True)
    
    # Load responses
    tweets = load_responses()
    if not tweets:
        logger.warning("No tweets with responses found")
        return RESPONSES_PATH
    
    # Count pending tweets
    pending_count = sum(1 for t in tweets if t.get("response") and t.get("status") == "pending")
    
    if pending_count == 0:
        logger.info("No pending tweets to moderate")
        console.print("[info]No pending tweets to moderate.[/info]")
        return RESPONSES_PATH
        
    logger.info(
        "Found pending tweets",
        count=pending_count
    )
    console.print(f"[bold cyan]Found {pending_count} pending tweets to moderate[/bold cyan]")
    
    if non_interactive:
        logger.info("Skipping interactive moderation (non-interactive mode)")
    else:
        # Run moderation TUI
        try:
            console.print("[bold]Starting Moderation TUI[/bold]")
            console.print("Use [a]pprove | [e]dit | [r]eject | [q]uit to moderate tweets")
            
            approved, edited, rejected = moderate_tweets(tweets, run_id=run_id or "unknown")
            
            logger.info(
                "Moderation completed",
                approved=approved,
                edited=edited,
                rejected=rejected
            )
            
            console.print(f"[bold green]Moderation completed:[/bold green] {approved} approved, {edited} edited, {rejected} rejected")
            console.print(f"[bold cyan]Audit log:[/bold cyan] {AUDIT_PATH}")
            
            # Save responses
            save_responses(tweets)
            
        except Exception as e:
            logger.error(
                "Error during moderation",
                error=str(e)
            )
            raise
    
    # Copy to artefacts directory if run_id is provided
    if run_id:
        artefact_responses = artefact_dir / "responses.json"
        artefact_responses.write_text(RESPONSES_PATH.read_text())
        
        # Copy audit log if it exists
        if AUDIT_PATH.exists():
            artefact_audit = artefact_dir / "audit.csv"
            artefact_audit.write_text(AUDIT_PATH.read_text())
            
            logger.info(
                "Copied audit log to artefacts directory",
                path=str(artefact_audit)
            )
        
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
    
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="Tweet moderation task")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive moderation")
    args = parser.parse_args()
    
    # Run the task
    run(non_interactive=args.non_interactive) 