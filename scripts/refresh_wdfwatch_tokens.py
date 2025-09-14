#!/usr/bin/env python3
"""
Refresh OAuth 2.0 tokens for the WDFwatch account.
This should be run before tokens expire (within 2 hours of generation).

The refresh token can be used to get a new access token without re-authentication.
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

# Load environment
env_path = Path(__file__).parent.parent / ".env"
wdfwatch_env_path = Path(__file__).parent.parent / ".env.wdfwatch"

# Load both env files
if env_path.exists():
    load_dotenv(env_path)
if wdfwatch_env_path.exists():
    load_dotenv(wdfwatch_env_path, override=True)

def check_token_expiry():
    """Check if the current token is expired or about to expire."""
    # Check if we have a token timestamp (we should add this)
    token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"
    
    if token_file.exists():
        with open(token_file, 'r') as f:
            token_info = json.load(f)
            issued_at = datetime.fromisoformat(token_info.get('issued_at', ''))
            expires_in = token_info.get('expires_in', 7200)
            
            expires_at = issued_at + timedelta(seconds=expires_in)
            now = datetime.now()
            
            if now >= expires_at:
                print(f"❌ Token expired at {expires_at}")
                return True
            elif now >= expires_at - timedelta(minutes=10):
                print(f"⚠️  Token expires soon at {expires_at}")
                return True
            else:
                remaining = expires_at - now
                print(f"✅ Token valid for {remaining}")
                return False
    else:
        print("⚠️  No token timestamp found, assuming refresh needed")
        return True

def refresh_tokens():
    """Refresh the OAuth 2.0 tokens using the refresh token."""
    
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    refresh_token = os.getenv("WDFWATCH_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        print("❌ Missing required credentials:")
        if not client_id:
            print("  - CLIENT_ID")
        if not client_secret:
            print("  - CLIENT_SECRET")
        if not refresh_token:
            print("  - WDFWATCH_REFRESH_TOKEN")
        return False
    
    print("🔄 Refreshing WDFwatch tokens...")
    
    # Token refresh endpoint
    token_url = "https://api.x.com/2/oauth2/token"
    
    # Prepare refresh request
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    
    # Use Basic Auth with client credentials
    auth = (client_id, client_secret)
    
    try:
        response = requests.post(
            token_url,
            data=data,
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            new_tokens = response.json()
            
            print("✅ Tokens refreshed successfully!")
            
            # Update .env.wdfwatch with new tokens
            if wdfwatch_env_path.exists():
                set_key(wdfwatch_env_path, "WDFWATCH_ACCESS_TOKEN", new_tokens.get('access_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_REFRESH_TOKEN", new_tokens.get('refresh_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_TOKEN_TYPE", new_tokens.get('token_type', 'bearer'))
                set_key(wdfwatch_env_path, "WDFWATCH_EXPIRES_IN", str(new_tokens.get('expires_in', 7200)))
                set_key(wdfwatch_env_path, "WDFWATCH_SCOPE", new_tokens.get('scope', ''))
                print(f"✅ Updated {wdfwatch_env_path}")
            
            # Also update main .env if tokens are there
            if env_path.exists() and os.getenv("WDFWATCH_ACCESS_TOKEN"):
                set_key(env_path, "WDFWATCH_ACCESS_TOKEN", new_tokens.get('access_token', ''))
                set_key(env_path, "WDFWATCH_REFRESH_TOKEN", new_tokens.get('refresh_token', ''))
                print(f"✅ Updated {env_path}")
            
            # Save token timestamp
            token_info = {
                'issued_at': datetime.now().isoformat(),
                'expires_in': new_tokens.get('expires_in', 7200),
                'token_type': new_tokens.get('token_type', 'bearer')
            }
            
            token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"
            with open(token_file, 'w') as f:
                json.dump(token_info, f, indent=2)
            print(f"✅ Saved token info to {token_file}")
            
            # Verify the new token works
            verify_token(new_tokens.get('access_token'))
            
            return True
            
        else:
            print(f"❌ Token refresh failed!")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 401:
                print("\n⚠️  Refresh token may be expired or invalid.")
                print("You need to run generate_wdfwatch_tokens.py to get new tokens.")
            
            return False
            
    except Exception as e:
        print(f"❌ Error refreshing tokens: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_token(access_token):
    """Verify the token works by getting user info."""
    print("\n🔍 Verifying new token...")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(
        "https://api.twitter.com/2/users/me",
        headers=headers
    )
    
    if response.status_code == 200:
        user_data = response.json()
        username = user_data.get('data', {}).get('username', 'unknown')
        user_id = user_data.get('data', {}).get('id', 'unknown')
        
        if username.lower() in ['wdfwatch', 'wdf_watch']:
            print(f"✅ Token verified for @{username} (ID: {user_id})")
        else:
            print(f"⚠️  Unexpected account: @{username}")
    else:
        print(f"❌ Failed to verify token: {response.status_code}")

def setup_auto_refresh():
    """Setup a cron job or scheduled task for auto-refresh."""
    print("\n📅 To setup automatic refresh, add this to your crontab:")
    print("   (Run 'crontab -e' and add this line)")
    print("")
    script_path = Path(__file__).resolve()
    print(f"0 */1 * * * /usr/bin/python3 {script_path}")
    print("")
    print("This will check and refresh tokens every hour.")

def main():
    print("=" * 60)
    print("WDFwatch Token Refresh Manager")
    print("=" * 60)
    
    # Check if refresh is needed
    if not check_token_expiry():
        print("\n✅ Token is still valid, no refresh needed.")
        response = input("Refresh anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Refresh the tokens
    if refresh_tokens():
        print("\n" + "=" * 60)
        print("✅ Token refresh complete!")
        print("=" * 60)
        
        # Offer to setup auto-refresh
        print("\n💡 Tip: Tokens expire every 2 hours.")
        response = input("Would you like to see how to setup auto-refresh? (y/n): ")
        if response.lower() == 'y':
            setup_auto_refresh()
    else:
        print("\n" + "=" * 60)
        print("❌ Token refresh failed!")
        print("Run generate_wdfwatch_tokens.py to get new tokens")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()