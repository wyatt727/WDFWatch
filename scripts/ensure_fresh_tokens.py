#!/usr/bin/env python3
"""
Ensure OAuth 2.0 tokens are fresh before any Twitter API operation.
This script checks token age and refreshes if needed, providing guaranteed fresh tokens.

Exit codes:
  0 - Tokens are fresh (or successfully refreshed)
  1 - Error refreshing tokens
  2 - Missing credentials
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent / ".env"
wdfwatch_env_path = Path(__file__).parent.parent / ".env.wdfwatch"

def load_env_files():
    """Load both environment files."""
    if env_path.exists():
        load_dotenv(env_path)
    if wdfwatch_env_path.exists():
        load_dotenv(wdfwatch_env_path, override=True)

def get_token_age():
    """Get the age of the current token in minutes."""
    token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"

    if not token_file.exists():
        print(f"[{datetime.now()}] No token info file found")
        return float('inf')  # Consider as expired if no info

    try:
        with open(token_file, 'r') as f:
            token_info = json.load(f)
            issued_at = datetime.fromisoformat(token_info.get('issued_at', ''))
            age = datetime.now() - issued_at
            return age.total_seconds() / 60  # Return age in minutes
    except Exception as e:
        print(f"[{datetime.now()}] Error reading token info: {e}")
        return float('inf')

def check_token_validity(access_token):
    """Verify token works by making a simple API call."""
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(
            "https://api.twitter.com/2/users/me",
            headers=headers,
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False

def refresh_tokens():
    """Refresh the OAuth 2.0 tokens."""
    load_env_files()

    client_id = os.getenv("CLIENT_ID") or os.getenv("API_KEY")
    client_secret = os.getenv("CLIENT_SECRET") or os.getenv("API_KEY_SECRET")
    refresh_token = os.getenv("WDFWATCH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print(f"[{datetime.now()}] ERROR: Missing required credentials")
        if not client_id:
            print("  - Missing CLIENT_ID/API_KEY")
        if not client_secret:
            print("  - Missing CLIENT_SECRET/API_KEY_SECRET")
        if not refresh_token:
            print("  - Missing WDFWATCH_REFRESH_TOKEN")
        return False

    print(f"[{datetime.now()}] Refreshing tokens...")

    token_url = "https://api.x.com/2/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    auth = (client_id, client_secret)

    try:
        response = requests.post(
            token_url,
            data=data,
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )

        if response.status_code == 200:
            new_tokens = response.json()

            # Update .env.wdfwatch with new tokens
            if wdfwatch_env_path.exists():
                set_key(wdfwatch_env_path, "WDFWATCH_ACCESS_TOKEN", new_tokens.get('access_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_REFRESH_TOKEN", new_tokens.get('refresh_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_TOKEN_TYPE", new_tokens.get('token_type', 'bearer'))
                set_key(wdfwatch_env_path, "WDFWATCH_EXPIRES_IN", str(new_tokens.get('expires_in', 7200)))
                set_key(wdfwatch_env_path, "WDFWATCH_SCOPE", new_tokens.get('scope', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_TOKEN_REFRESHED_AT", datetime.now().isoformat())

            # Also update main .env if it contains WDFWATCH tokens
            if env_path.exists() and os.getenv("WDFWATCH_ACCESS_TOKEN"):
                set_key(env_path, "WDFWATCH_ACCESS_TOKEN", new_tokens.get('access_token', ''))
                set_key(env_path, "WDFWATCH_REFRESH_TOKEN", new_tokens.get('refresh_token', ''))
                set_key(env_path, "WDFWATCH_TOKEN_REFRESHED_AT", datetime.now().isoformat())

            # Save token timestamp
            token_info = {
                'issued_at': datetime.now().isoformat(),
                'expires_in': new_tokens.get('expires_in', 7200),
                'token_type': new_tokens.get('token_type', 'bearer'),
                'scope': new_tokens.get('scope', '')
            }

            token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"
            with open(token_file, 'w') as f:
                json.dump(token_info, f, indent=2)

            print(f"[{datetime.now()}] ✅ Tokens refreshed successfully")

            # Verify the new token
            if check_token_validity(new_tokens.get('access_token')):
                print(f"[{datetime.now()}] ✅ Token verified - ready for use")
            else:
                print(f"[{datetime.now()}] ⚠️ Token refreshed but verification failed")

            return True

        else:
            print(f"[{datetime.now()}] ❌ Token refresh failed: {response.status_code}")
            print(f"[{datetime.now()}] Response: {response.text}")

            if response.status_code == 401:
                print(f"[{datetime.now()}] ⚠️ Refresh token expired - manual re-authentication needed")

            return False

    except requests.exceptions.Timeout:
        print(f"[{datetime.now()}] ❌ Timeout refreshing tokens")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error refreshing tokens: {e}")
        return False

def ensure_fresh_tokens(max_age_minutes=90):
    """
    Ensure tokens are fresh, refreshing if older than max_age_minutes.

    Args:
        max_age_minutes: Maximum acceptable token age in minutes (default: 90)

    Returns:
        bool: True if tokens are fresh or successfully refreshed
    """
    # Load environment to check current token
    load_env_files()

    # Check token age
    token_age = get_token_age()
    print(f"[{datetime.now()}] Token age: {token_age:.1f} minutes")

    # If token is fresh enough, verify it still works
    if token_age < max_age_minutes:
        access_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
        if access_token and check_token_validity(access_token):
            print(f"[{datetime.now()}] ✅ Token is fresh and valid ({token_age:.1f} minutes old)")
            return True
        else:
            print(f"[{datetime.now()}] ⚠️ Token appears fresh but validation failed - refreshing...")
    else:
        print(f"[{datetime.now()}] ⚠️ Token too old ({token_age:.1f} minutes) - refreshing...")

    # Token needs refresh
    if refresh_tokens():
        print(f"[{datetime.now()}] ✅ Fresh tokens ready for use")
        return True
    else:
        print(f"[{datetime.now()}] ❌ Failed to ensure fresh tokens")
        return False

def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='Ensure OAuth tokens are fresh')
    parser.add_argument('--max-age', type=int, default=90,
                       help='Maximum token age in minutes (default: 90)')
    parser.add_argument('--force', action='store_true',
                       help='Force refresh regardless of age')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check token age, do not refresh')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress output except errors')

    args = parser.parse_args()

    # Redirect output if quiet mode
    if args.quiet:
        import io
        sys.stdout = io.StringIO()

    # Check-only mode
    if args.check_only:
        token_age = get_token_age()
        if not args.quiet:
            print(f"Token age: {token_age:.1f} minutes")
        if token_age < args.max_age:
            sys.exit(0)
        else:
            sys.exit(1)

    # Force refresh mode
    if args.force:
        if refresh_tokens():
            sys.exit(0)
        else:
            sys.exit(1)

    # Normal mode: ensure fresh tokens
    if ensure_fresh_tokens(args.max_age):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()