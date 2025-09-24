#!/usr/bin/env python3
"""
Setup OAuth 2.0 for Twitter/X Bot

Interactive script to authorize @WDF_Watch bot with OAuth 2.0 PKCE flow.
Run this once to get refresh tokens for the bot account.

Usage:
    python scripts/setup_oauth2.py
"""

import sys
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.wdf.twitter_oauth2 import TwitterOAuth2


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    
    def do_GET(self):
        """Handle GET request from Twitter callback."""
        # Parse query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        # Store code and state in server instance
        self.server.auth_code = params.get('code', [None])[0]
        self.server.auth_state = params.get('state', [None])[0]
        self.server.auth_error = params.get('error', [None])[0]
        
        # Send response to browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if self.server.auth_code:
            html = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #1DA1F2;">✅ Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <p style="color: #666;">The bot is now authorized to post as @WDF_Watch</p>
            </body>
            </html>
            """
        else:
            error_msg = self.server.auth_error or "Unknown error"
            html = f"""
            <html>
            <head><title>Authorization Failed</title></head>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #E1444D;">❌ Authorization Failed</h1>
                <p>Error: {error_msg}</p>
                <p>Please try again.</p>
            </body>
            </html>
            """
        
        self.wfile.write(html.encode())
        
        # Shutdown server after response
        threading.Thread(target=self.server.shutdown).start()
    
    def log_message(self, format, *args):
        """Suppress request logs."""
        pass


def setup_oauth2():
    """Interactive OAuth 2.0 setup."""
    print("\n🔐 Twitter/X OAuth 2.0 Setup for @WDF_Watch Bot")
    print("=" * 50)
    
    # Check for Client ID
    client_id = os.getenv("TWITTER_CLIENT_ID")
    if not client_id:
        print("\n⚠️  TWITTER_CLIENT_ID not set in environment!")
        print("\nTo get your Client ID:")
        print("1. Go to https://developer.twitter.com/en/portal/projects")
        print("2. Select your app (or create one)")
        print("3. Go to 'Keys and tokens' → 'OAuth 2.0'")
        print("4. Copy the Client ID")
        print()
        client_id = input("Enter your Client ID: ").strip()
        if not client_id:
            print("❌ Client ID is required!")
            return False
    
    # Set up OAuth client
    redirect_uri = "http://localhost:8080/callback"
    oauth = TwitterOAuth2(
        client_id=client_id,
        redirect_uri=redirect_uri
    )
    
    # Check if already authenticated
    status = oauth.get_auth_status()
    if status['authenticated']:
        print("\n✅ Already authenticated!")
        print(f"   Access token: {'Yes' if status['has_access_token'] else 'No'}")
        print(f"   Refresh token: {'Yes' if status['has_refresh_token'] else 'No'}")
        print(f"   Expires: {status['expires_at']}")
        print(f"   Scopes: {', '.join(status['scopes'])}")
        
        renew = input("\nDo you want to re-authenticate? (y/N): ").lower()
        if renew != 'y':
            return True
    
    # Generate authorization URL
    auth_url = oauth.get_authorization_url()
    
    print(f"\n📋 Redirect URI: {redirect_uri}")
    print("   (This must be added to your app's callback URLs)")
    
    # Start local server to handle callback
    print("\n🌐 Starting local server to handle callback...")
    server = HTTPServer(('localhost', 8080), CallbackHandler)
    server.auth_code = None
    server.auth_state = None
    server.auth_error = None
    
    # Start server in background thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Open browser
    print(f"\n🚀 Opening browser for authorization...")
    print(f"   If browser doesn't open, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)
    
    # Wait for callback
    print("⏳ Waiting for authorization...")
    server_thread.join(timeout=120)  # 2 minute timeout
    
    if server.auth_code:
        print("\n✅ Authorization code received!")
        
        # Exchange code for tokens
        try:
            tokens = oauth.exchange_code_for_tokens(server.auth_code)
            
            print("\n🎉 Success! Bot is now authorized.")
            print(f"   Access token expires in: {tokens.get('expires_in', 0)} seconds")
            print(f"   Refresh token: {'✅ Saved' if 'refresh_token' in tokens else '❌ Not received'}")
            print(f"   Scopes: {tokens.get('scope', 'Unknown')}")
            
            # Test the token with a simple API call
            print("\n🧪 Testing authentication...")
            response = oauth.make_authenticated_request(
                'GET',
                'https://api.x.com/2/users/me',
                params={'user.fields': 'username,name'}
            )
            
            if response.status_code == 200:
                user_data = response.json().get('data', {})
                print(f"✅ Authenticated as: @{user_data.get('username', 'Unknown')}")
                print(f"   Name: {user_data.get('name', 'Unknown')}")
            else:
                print(f"⚠️  Test failed: {response.status_code} - {response.text}")
            
            print("\n📝 Next steps:")
            print("1. Tokens are saved to .twitter_tokens.json")
            print("2. The bot will automatically refresh tokens as needed")
            print("3. You can now run the pipeline with OAuth 2.0!")
            
            # Save client ID to .env if not already there
            env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    env_content = f.read()
                if 'TWITTER_CLIENT_ID' not in env_content:
                    print(f"\n💡 Adding TWITTER_CLIENT_ID to .env file...")
                    with open(env_file, 'a') as f:
                        f.write(f"\n# OAuth 2.0 Configuration\n")
                        f.write(f"TWITTER_CLIENT_ID={client_id}\n")
                        f.write(f"TWITTER_REDIRECT_URI={redirect_uri}\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Token exchange failed: {e}")
            return False
    
    elif server.auth_error:
        print(f"\n❌ Authorization failed: {server.auth_error}")
        return False
    
    else:
        print("\n⏱️  Timeout waiting for authorization")
        return False


if __name__ == "__main__":
    success = setup_oauth2()
    sys.exit(0 if success else 1)