#!/bin/bash
# Setup automatic token refresh for WDFwatch

# Add cron job to refresh tokens every hour
SCRIPT_PATH="/home/debian/Tools/WDFWatch/scripts/refresh_wdfwatch_tokens_auto.py"
PYTHON_PATH="/home/debian/Tools/WDFWatch/venv/bin/python"

# Create auto version of refresh script that doesn't ask for input
cat > "$SCRIPT_PATH" << 'EOF'
#!/usr/bin/env python3
"""Auto-refresh OAuth 2.0 tokens for WDFwatch account (non-interactive)."""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent / ".env"
wdfwatch_env_path = Path(__file__).parent.parent / ".env.wdfwatch"

if env_path.exists():
    load_dotenv(env_path)
if wdfwatch_env_path.exists():
    load_dotenv(wdfwatch_env_path, override=True)

def check_token_expiry():
    """Check if the current token is expired or about to expire."""
    token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"

    if token_file.exists():
        with open(token_file, 'r') as f:
            token_info = json.load(f)
            issued_at = datetime.fromisoformat(token_info.get('issued_at', ''))
            expires_in = token_info.get('expires_in', 7200)

            expires_at = issued_at + timedelta(seconds=expires_in)
            now = datetime.now()

            # Refresh if less than 30 minutes remaining
            if now >= expires_at - timedelta(minutes=30):
                return True
            return False
    return True

def refresh_tokens():
    """Refresh the OAuth 2.0 tokens."""
    client_id = os.getenv("CLIENT_ID") or os.getenv("API_KEY")
    client_secret = os.getenv("CLIENT_SECRET") or os.getenv("API_KEY_SECRET")
    refresh_token = os.getenv("WDFWATCH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print(f"[{datetime.now()}] Missing credentials for refresh")
        return False

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
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code == 200:
            new_tokens = response.json()

            # Update .env.wdfwatch
            if wdfwatch_env_path.exists():
                set_key(wdfwatch_env_path, "WDFWATCH_ACCESS_TOKEN", new_tokens.get('access_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_REFRESH_TOKEN", new_tokens.get('refresh_token', ''))
                set_key(wdfwatch_env_path, "WDFWATCH_TOKEN_TYPE", new_tokens.get('token_type', 'bearer'))
                set_key(wdfwatch_env_path, "WDFWATCH_EXPIRES_IN", str(new_tokens.get('expires_in', 7200)))
                set_key(wdfwatch_env_path, "WDFWATCH_SCOPE", new_tokens.get('scope', ''))

            # Save token timestamp
            token_info = {
                'issued_at': datetime.now().isoformat(),
                'expires_in': new_tokens.get('expires_in', 7200),
                'token_type': new_tokens.get('token_type', 'bearer')
            }

            token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"
            with open(token_file, 'w') as f:
                json.dump(token_info, f, indent=2)

            print(f"[{datetime.now()}] Tokens refreshed successfully")
            return True
        else:
            print(f"[{datetime.now()}] Refresh failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False

if __name__ == "__main__":
    if check_token_expiry():
        refresh_tokens()
    else:
        print(f"[{datetime.now()}] Token still valid, skipping refresh")
EOF

chmod +x "$SCRIPT_PATH"

# Add to crontab (runs every 30 minutes)
CRON_JOB="*/30 * * * * $PYTHON_PATH $SCRIPT_PATH >> /home/debian/Tools/WDFWatch/logs/token_refresh.log 2>&1"

# Check if cron job already exists
if ! crontab -l 2>/dev/null | grep -q "refresh_wdfwatch_tokens"; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Added cron job for automatic token refresh every 30 minutes"
    echo "   Logs will be saved to: /home/debian/Tools/WDFWatch/logs/token_refresh.log"
else
    echo "⚠️  Cron job already exists"
fi

# Create logs directory if it doesn't exist
mkdir -p /home/debian/Tools/WDFWatch/logs

echo ""
echo "To view current cron jobs: crontab -l"
echo "To monitor refresh logs: tail -f /home/debian/Tools/WDFWatch/logs/token_refresh.log"