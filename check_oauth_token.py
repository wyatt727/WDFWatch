#!/usr/bin/env python3
"""
Check OAuth token status and expiration
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('.env.wdfwatch')

def check_token_status():
    """Check the current OAuth token status"""

    print("🔑 OAuth Token Status Check")
    print("=" * 60)

    # Check if we have OAuth 2.0 tokens
    access_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
    refresh_token = os.getenv("WDFWATCH_REFRESH_TOKEN")
    expires_in = os.getenv("WDFWATCH_EXPIRES_IN", "7200")

    if not access_token:
        print("❌ No WDFWATCH_ACCESS_TOKEN found!")
        return

    print(f"✅ Access Token: {access_token[:20]}...")
    print(f"✅ Refresh Token: {refresh_token[:20]}..." if refresh_token else "❌ No refresh token!")
    print(f"Token Type: {os.getenv('WDFWATCH_TOKEN_TYPE', 'bearer')}")
    print(f"Expires In: {expires_in} seconds (from generation)")

    # Check token files for last refresh time
    token_file = Path.home() / '.wdfwatch_tokens.json'
    if token_file.exists():
        try:
            with open(token_file) as f:
                token_data = json.load(f)

            created_at = datetime.fromisoformat(token_data.get('created_at', ''))
            expires_at = datetime.fromisoformat(token_data.get('expires_at', ''))

            print(f"\n📅 Token Timeline:")
            print(f"Created: {created_at}")
            print(f"Expires: {expires_at}")
            print(f"Current: {datetime.now()}")

            # Calculate time until expiration
            time_remaining = expires_at - datetime.now()

            if time_remaining.total_seconds() <= 0:
                print(f"\n⚠️  TOKEN EXPIRED {abs(time_remaining.total_seconds() / 3600):.1f} hours ago!")
                print("This is why posting is failing!")
            else:
                hours_remaining = time_remaining.total_seconds() / 3600
                print(f"\n✅ Token valid for {hours_remaining:.1f} more hours")

        except Exception as e:
            print(f"\n⚠️  Could not read token file: {e}")
    else:
        print(f"\n⚠️  No token file found at {token_file}")
        print("Token expiration time unknown - may be expired!")

    # Test the token with a simple API call
    print("\n🔧 Testing token with Twitter API...")

    try:
        from src.wdf.twitter_api_v2 import TwitterAPIv2

        # Initialize client
        twitter = TwitterAPIv2()

        # Try to verify credentials
        response = twitter.session.get(f"{twitter.BASE_URL}/users/me")

        if response.status_code == 200:
            user_data = response.json()
            username = user_data.get('data', {}).get('username', 'unknown')
            print(f"✅ Token valid! Authenticated as @{username}")
        elif response.status_code == 401:
            print(f"❌ Token invalid or expired! Status: {response.status_code}")
            print(f"Response: {response.text}")

            if refresh_token:
                print("\n🔄 Attempting to refresh token...")
                try:
                    from src.wdf.token_manager import refresh_wdfwatch_token
                    new_token = refresh_wdfwatch_token()
                    if new_token:
                        print("✅ Token refreshed successfully!")
                        print("New token saved to .env.wdfwatch")
                    else:
                        print("❌ Failed to refresh token")
                except Exception as e:
                    print(f"❌ Error refreshing token: {e}")
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            print(f"Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error testing token: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_token_status()