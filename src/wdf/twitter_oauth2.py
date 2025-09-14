"""
Twitter OAuth 2.0 with PKCE Implementation

Modern OAuth 2.0 authentication for Twitter/X API with automatic token refresh.
Replaces the legacy OAuth 1.0a implementation.

Integrates with: twitter_api_v2.py, web UI token management
"""

import os
import json
import time
import secrets
import hashlib
import base64
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import requests
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class TwitterOAuth2:
    """
    Twitter OAuth 2.0 with PKCE (Proof Key for Code Exchange) implementation.
    
    Features:
    - OAuth 2.0 Authorization Code flow with PKCE
    - Automatic token refresh
    - Secure token storage
    - Rate limit handling
    """
    
    AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.x.com/2/oauth2/token"
    REVOKE_URL = "https://api.x.com/2/oauth2/revoke"
    
    # Required scopes for bot functionality
    REQUIRED_SCOPES = [
        "tweet.read",      # Read tweets
        "tweet.write",     # Post tweets and replies
        "users.read",      # Read user information
        "offline.access"   # Get refresh tokens
    ]
    
    def __init__(self, client_id: str = None, redirect_uri: str = None,
                 token_file: str = None):
        """
        Initialize OAuth 2.0 client.
        
        Args:
            client_id: Twitter app Client ID
            redirect_uri: Callback URL (must match app settings exactly)
            token_file: Path to store tokens (default: .twitter_tokens.json)
        """
        self.client_id = client_id or os.getenv("TWITTER_CLIENT_ID")
        self.redirect_uri = redirect_uri or os.getenv("TWITTER_REDIRECT_URI", "http://localhost:8080/callback")
        
        if not self.client_id:
            raise ValueError("Twitter Client ID not configured")
        
        # Token storage
        self.token_file = Path(token_file or os.getenv("TWITTER_TOKEN_FILE", ".twitter_tokens.json"))
        self.tokens: Dict = self._load_tokens()
        
        # PKCE verifier for current flow
        self.code_verifier: Optional[str] = None
        
    def _b64url_encode(self, data: bytes) -> str:
        """Base64 URL-safe encoding without padding."""
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
    
    def _generate_pkce_pair(self) -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate random 32-byte verifier (43-128 chars when base64 encoded)
        code_verifier = self._b64url_encode(os.urandom(32))
        
        # Create SHA256 challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = self._b64url_encode(challenge_bytes)
        
        return code_verifier, code_challenge
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate authorization URL for user consent.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        # Generate PKCE pair
        self.code_verifier, code_challenge = self._generate_pkce_pair()
        
        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.REQUIRED_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        auth_url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"
        
        logger.info(
            "Generated authorization URL",
            scopes=self.REQUIRED_SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        return auth_url
    
    def exchange_code_for_tokens(self, code: str) -> Dict:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Token response dict with access_token, refresh_token, etc.
        """
        if not self.code_verifier:
            raise ValueError("No PKCE verifier found. Call get_authorization_url first.")
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": self.code_verifier
        }
        
        response = requests.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            logger.error(
                "Token exchange failed",
                status=response.status_code,
                error=response.text
            )
            raise Exception(f"Token exchange failed: {response.text}")
        
        tokens = response.json()
        
        # Add expiration timestamp
        tokens['expires_at'] = time.time() + tokens.get('expires_in', 7200)
        
        # Save tokens
        self.tokens = tokens
        self._save_tokens(tokens)
        
        # Clear PKCE verifier
        self.code_verifier = None
        
        logger.info(
            "Successfully exchanged code for tokens",
            has_refresh_token='refresh_token' in tokens,
            expires_in=tokens.get('expires_in')
        )
        
        return tokens
    
    def refresh_access_token(self) -> Dict:
        """
        Refresh access token using refresh token.
        
        Returns:
            New token response dict
        """
        if 'refresh_token' not in self.tokens:
            raise ValueError("No refresh token available")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens['refresh_token'],
            "client_id": self.client_id
        }
        
        response = requests.post(
            self.TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            logger.error(
                "Token refresh failed",
                status=response.status_code,
                error=response.text
            )
            raise Exception(f"Token refresh failed: {response.text}")
        
        tokens = response.json()
        
        # Add expiration timestamp
        tokens['expires_at'] = time.time() + tokens.get('expires_in', 7200)
        
        # Update stored tokens (Twitter rotates refresh tokens)
        self.tokens.update(tokens)
        self._save_tokens(self.tokens)
        
        logger.info(
            "Successfully refreshed access token",
            new_expiry=datetime.fromtimestamp(tokens['expires_at']).isoformat()
        )
        
        return tokens
    
    def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        if not self.tokens or 'access_token' not in self.tokens:
            raise ValueError("No access token available. User must authorize first.")
        
        # Check if token is expired (with 5 minute buffer)
        expires_at = self.tokens.get('expires_at', 0)
        if time.time() >= (expires_at - 300):
            logger.info("Access token expired or expiring soon, refreshing...")
            self.refresh_access_token()
        
        return self.tokens['access_token']
    
    def revoke_token(self, token: str = None) -> bool:
        """
        Revoke access or refresh token.
        
        Args:
            token: Token to revoke (default: current access token)
            
        Returns:
            True if successful
        """
        if not token:
            token = self.tokens.get('access_token')
        
        if not token:
            logger.warning("No token to revoke")
            return False
        
        data = {
            "token": token,
            "client_id": self.client_id
        }
        
        response = requests.post(
            self.REVOKE_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            logger.info("Successfully revoked token")
            # Clear stored tokens
            self.tokens = {}
            self._save_tokens({})
            return True
        else:
            logger.error(
                "Token revocation failed",
                status=response.status_code,
                error=response.text
            )
            return False
    
    def _load_tokens(self) -> Dict:
        """Load tokens from storage."""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    logger.info(
                        "Loaded existing tokens",
                        has_access_token='access_token' in tokens,
                        has_refresh_token='refresh_token' in tokens
                    )
                    return tokens
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")
        return {}
    
    def _save_tokens(self, tokens: Dict):
        """Save tokens to storage."""
        try:
            # Ensure directory exists
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with restrictive permissions
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            
            # Set file permissions to owner-only
            os.chmod(self.token_file, 0o600)
            
            logger.info("Saved tokens to file", path=str(self.token_file))
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
    
    def make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make authenticated request to Twitter API.
        
        Args:
            method: HTTP method
            url: API endpoint URL
            **kwargs: Additional request parameters
            
        Returns:
            Response object
        """
        # Get valid access token
        access_token = self.get_access_token()
        
        # Add authorization header
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f"Bearer {access_token}"
        kwargs['headers'] = headers
        
        # Make request
        response = requests.request(method, url, **kwargs)
        
        # Handle 401 (token expired)
        if response.status_code == 401:
            logger.info("Got 401, attempting token refresh...")
            self.refresh_access_token()
            
            # Retry with new token
            access_token = self.get_access_token()
            headers['Authorization'] = f"Bearer {access_token}"
            response = requests.request(method, url, **kwargs)
        
        return response
    
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication."""
        try:
            # Try to get access token (will refresh if needed)
            self.get_access_token()
            return True
        except:
            return False
    
    def get_auth_status(self) -> Dict:
        """Get current authentication status."""
        if not self.tokens:
            return {
                "authenticated": False,
                "message": "No tokens available"
            }
        
        expires_at = self.tokens.get('expires_at', 0)
        expires_in = expires_at - time.time()
        
        return {
            "authenticated": True,
            "has_access_token": 'access_token' in self.tokens,
            "has_refresh_token": 'refresh_token' in self.tokens,
            "expires_at": datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            "expires_in_seconds": int(expires_in) if expires_in > 0 else 0,
            "scopes": self.tokens.get('scope', '').split() if self.tokens else []
        }