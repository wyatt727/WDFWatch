"""
OAuth 2.0 Token Manager for WDFwatch
Handles automatic token refresh before expiry.
"""

import os
import json
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

class WDFWatchTokenManager:
    """Manages OAuth 2.0 tokens for WDFwatch with automatic refresh."""
    
    def __init__(self):
        self.env_path = Path(__file__).parent.parent.parent / ".env"
        self.wdfwatch_env_path = Path(__file__).parent.parent.parent / ".env.wdfwatch"
        self.token_info_path = Path(__file__).parent.parent.parent / ".wdfwatch_token_info.json"
        self.token_url = "https://api.x.com/2/oauth2/token"
        
        # Load environment
        self._load_environment()
        
    def _load_environment(self):
        """Load environment variables from .env files."""
        if self.env_path.exists():
            load_dotenv(self.env_path)
        if self.wdfwatch_env_path.exists():
            load_dotenv(self.wdfwatch_env_path, override=True)
    
    def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
            
        Raises:
            ValueError: If token cannot be obtained or refreshed
        """
        # Check current token
        current_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
        
        if not current_token:
            raise ValueError("No WDFWATCH_ACCESS_TOKEN found. Run generate_wdfwatch_tokens.py")
        
        # Check if token needs refresh
        if self._token_needs_refresh():
            logger.info("Token needs refresh, refreshing now...")
            new_token = self._refresh_token()
            if new_token:
                return new_token
            else:
                logger.warning("Token refresh failed, using existing token")
                return current_token
        
        return current_token
    
    def _token_needs_refresh(self) -> bool:
        """Check if the token needs to be refreshed."""
        if not self.token_info_path.exists():
            # No timestamp info, be safe and refresh
            logger.warning("No token timestamp found, assuming refresh needed")
            return True
        
        try:
            with open(self.token_info_path, 'r') as f:
                token_info = json.load(f)
            
            issued_at = datetime.fromisoformat(token_info.get('issued_at', ''))
            expires_in = token_info.get('expires_in', 7200)
            
            # Calculate expiry with 5-minute buffer
            expires_at = issued_at + timedelta(seconds=expires_in - 300)
            now = datetime.now()
            
            if now >= expires_at:
                logger.info(f"Token expired or expiring soon (expires at {expires_at})")
                return True
            
            remaining = expires_at - now
            logger.debug(f"Token valid for {remaining}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
            # Be safe and refresh
            return True
    
    def _refresh_token(self) -> Optional[str]:
        """
        Refresh the OAuth 2.0 token.
        
        Returns:
            New access token if successful, None otherwise
        """
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        refresh_token = os.getenv("WDFWATCH_REFRESH_TOKEN")
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing credentials for token refresh")
            return None
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id
        }
        
        auth = (client_id, client_secret)
        
        try:
            response = requests.post(
                self.token_url,
                data=data,
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )
            
            if response.status_code == 200:
                new_tokens = response.json()
                
                # Update environment variables
                self._save_tokens(new_tokens)
                
                # Save timestamp
                self._save_token_info(new_tokens)
                
                logger.info("✅ Tokens refreshed successfully")
                return new_tokens.get('access_token')
            
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None
    
    def _save_tokens(self, tokens: Dict):
        """Save new tokens to .env files."""
        try:
            # Update .env.wdfwatch
            if self.wdfwatch_env_path.exists():
                set_key(self.wdfwatch_env_path, "WDFWATCH_ACCESS_TOKEN", tokens.get('access_token', ''))
                set_key(self.wdfwatch_env_path, "WDFWATCH_REFRESH_TOKEN", tokens.get('refresh_token', ''))
                set_key(self.wdfwatch_env_path, "WDFWATCH_EXPIRES_IN", str(tokens.get('expires_in', 7200)))
                
                # Also update in memory
                os.environ["WDFWATCH_ACCESS_TOKEN"] = tokens.get('access_token', '')
                os.environ["WDFWATCH_REFRESH_TOKEN"] = tokens.get('refresh_token', '')
                
            # Also update main .env if tokens are there
            if self.env_path.exists() and "WDFWATCH_ACCESS_TOKEN" in open(self.env_path).read():
                set_key(self.env_path, "WDFWATCH_ACCESS_TOKEN", tokens.get('access_token', ''))
                set_key(self.env_path, "WDFWATCH_REFRESH_TOKEN", tokens.get('refresh_token', ''))
                
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
    
    def _save_token_info(self, tokens: Dict):
        """Save token timestamp information."""
        try:
            token_info = {
                'issued_at': datetime.now().isoformat(),
                'expires_in': tokens.get('expires_in', 7200),
                'token_type': tokens.get('token_type', 'bearer')
            }
            
            with open(self.token_info_path, 'w') as f:
                json.dump(token_info, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving token info: {e}")
    
    def verify_account(self, access_token: str) -> Tuple[bool, str]:
        """
        Verify the token belongs to WDFwatch account.
        
        Returns:
            Tuple of (is_correct_account, username)
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(
                "https://api.twitter.com/2/users/me",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('data', {}).get('username', 'unknown')
                
                is_wdfwatch = username.lower() in ['wdfwatch', 'wdf_watch']
                
                if not is_wdfwatch:
                    logger.error(f"⚠️  Token belongs to @{username}, not WDFwatch!")
                
                return is_wdfwatch, username
            else:
                logger.error(f"Failed to verify account: {response.status_code}")
                return False, "unknown"
                
        except Exception as e:
            logger.error(f"Error verifying account: {e}")
            return False, "unknown"


# Global instance for easy access
token_manager = WDFWatchTokenManager()

def get_wdfwatch_token() -> str:
    """
    Get a valid WDFwatch access token, refreshing if necessary.
    
    This is the main function to use in the pipeline.
    """
    return token_manager.get_valid_token()