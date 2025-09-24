#!/usr/bin/env python3
"""
Generate OAuth 1.0a tokens for WDFwatch account
These are needed for posting replies to Twitter
"""

import os
import sys
import webbrowser
from pathlib import Path
import tweepy

# Load environment
env_file = Path(__file__).parent / '.env.wdfwatch'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip('"').strip("'")
                os.environ[key] = value

# Get API credentials
api_key = os.environ.get('API_KEY')
api_secret = os.environ.get('API_KEY_SECRET')

if not api_key or not api_secret:
    print("❌ API_KEY and API_KEY_SECRET must be set in .env.wdfwatch")
    sys.exit(1)

print("🔑 Generating OAuth 1.0a tokens for WDFwatch...")
print("=" * 60)

# OAuth 1.0a flow
auth = tweepy.OAuthHandler(api_key, api_secret)

try:
    # Get authorization URL
    redirect_url = auth.get_authorization_url()
    print(f"Please visit this URL to authorize the app:")
    print(redirect_url)
    print()

    # Open in browser
    webbrowser.open(redirect_url)

    # Get PIN from user
    verifier = input('Enter the PIN from Twitter: ').strip()

    # Get access tokens
    auth.get_access_token(verifier)

    print()
    print("✅ Successfully generated OAuth 1.0a tokens!")
    print("=" * 60)
    print()
    print("Add these lines to your .env.wdfwatch file:")
    print()
    print(f"WDFWATCH_ACCESS_TOKEN={auth.access_token}")
    print(f"WDFWATCH_ACCESS_TOKEN_SECRET={auth.access_token_secret}")
    print()
    print("=" * 60)

    # Ask if user wants to append to file
    append = input("Append to .env.wdfwatch? (y/n): ").strip().lower()
    if append == 'y':
        with open('.env.wdfwatch', 'a') as f:
            f.write(f"\n# OAuth 1.0a tokens (for posting)\n")
            f.write(f"WDFWATCH_ACCESS_TOKEN={auth.access_token}\n")
            f.write(f"WDFWATCH_ACCESS_TOKEN_SECRET={auth.access_token_secret}\n")
        print("✅ Tokens saved to .env.wdfwatch!")

except tweepy.TweepyException as e:
    print(f"❌ Error during authorization: {e}")
    sys.exit(1)