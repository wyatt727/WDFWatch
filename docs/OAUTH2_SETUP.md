# Twitter/X OAuth 2.0 Setup Guide

## ✅ Current Status: OAuth 2.0 with PKCE Implemented

WDFWatch now uses modern **OAuth 2.0 with PKCE** (Proof Key for Code Exchange) for Twitter/X API authentication, replacing the legacy OAuth 1.0a implementation.

## 🔑 Key Benefits

1. **More Secure**: PKCE prevents authorization code interception
2. **Refresh Tokens**: No need to re-authenticate - tokens auto-refresh
3. **Granular Scopes**: Only request permissions you need
4. **Modern Standard**: Aligned with current Twitter/X best practices
5. **Better User Experience**: One-time authorization for bot account

## 📋 Prerequisites

1. **Twitter Developer Account**: https://developer.twitter.com
2. **Twitter App**: Create at https://developer.twitter.com/en/portal/projects
3. **Bot Account**: The @WDF_Watch account that will post tweets

## 🚀 Quick Setup

### Step 1: Configure Your Twitter App

1. Go to your app settings in the [Twitter Developer Portal](https://developer.twitter.com/en/portal/projects)
2. Under "User authentication settings", click "Set up"
3. Configure as follows:
   - **App permissions**: Read and write
   - **Type of App**: Web App, Automated App or Bot
   - **Callback URI**: `http://localhost:8080/callback` (exact match required!)
   - **Website URL**: Your bot's website or GitHub repo

4. Save your **Client ID** (you'll need this)

### Step 2: Set Environment Variables

Add to your `.env` file (in the project root):
```bash
# OAuth 2.0 Configuration
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
# Note: Redirect URI is configured in the script, not needed in .env
```

**Note**: See `ENV_SETUP.md` for complete environment variable documentation. The `.env` file should be in the project root directory.

### Step 3: Authorize the Bot

Run the interactive setup script:
```bash
python scripts/setup_oauth2.py
```

This will:
1. Start a local server on port 8080
2. Open your browser to Twitter's authorization page
3. After you authorize, save tokens to `.env.wdfwatch` (and optionally `.env`)
4. Test the authentication with a simple API call

### Step 4: Verify Setup

Check authentication status:
```python
from src.wdf.twitter_oauth2 import TwitterOAuth2

oauth = TwitterOAuth2()
status = oauth.get_auth_status()
print(f"Authenticated: {status['authenticated']}")
print(f"Expires: {status['expires_at']}")
print(f"Scopes: {status['scopes']}")
```

## 🔄 Token Management

### Automatic Refresh
Tokens automatically refresh when:
- Access token expires (after ~2 hours)
- Any API call returns 401 Unauthorized

### Manual Refresh
```python
oauth = TwitterOAuth2()
new_tokens = oauth.refresh_access_token()
```

### Revoke Tokens
```python
oauth = TwitterOAuth2()
oauth.revoke_token()  # Revokes current access token
```

## 📝 Required Scopes

WDFWatch requests these OAuth 2.0 scopes:
- `tweet.read` - Read tweets and replies
- `tweet.write` - Post tweets and replies
- `users.read` - Read user information
- `offline.access` - Get refresh tokens for automatic renewal

## 🔧 API Usage Examples

### Post a Tweet
```python
from src.wdf.twitter_oauth2 import TwitterOAuth2

oauth = TwitterOAuth2()

# Simple tweet
response = oauth.make_authenticated_request(
    'POST',
    'https://api.x.com/2/tweets',
    json={"text": "Hello from OAuth 2.0! 🤖"}
)

# Reply to a tweet
response = oauth.make_authenticated_request(
    'POST', 
    'https://api.x.com/2/tweets',
    json={
        "text": "Great point about federalism!",
        "reply": {"in_reply_to_tweet_id": "1234567890"}
    }
)
```

### Search Tweets
```python
response = oauth.make_authenticated_request(
    'GET',
    'https://api.x.com/2/tweets/search/recent',
    params={
        'query': 'federalism -is:retweet',
        'max_results': 100
    }
)
```

## 🛡️ Security Best Practices

1. **Token Storage**: Tokens are saved to `.env.wdfwatch` (and optionally `.env`) - both files are in `.gitignore`
2. **Never Commit Tokens**: All `.env*` files are automatically ignored by git (except `.env*.example` templates)
3. **Client Secret**: Store `CLIENT_SECRET` in `.env` - it's needed for token refresh but is gitignored
4. **HTTPS in Production**: Use HTTPS redirect URIs in production
5. **Rotate Regularly**: Periodically revoke and regenerate tokens using `python scripts/generate_wdfwatch_tokens.py`
6. **Separate Files**: Consider using `.env.wdfwatch` for extra safety (separates automated account tokens from managing account credentials)

## 🚨 Troubleshooting

### "Invalid redirect URI"
- Ensure callback URL matches EXACTLY in app settings
- Check for trailing slashes, protocol (http vs https), port numbers

### "Invalid client"
- Verify TWITTER_CLIENT_ID is correct
- Ensure app has OAuth 2.0 enabled in Developer Portal

### "Insufficient scopes"
- Re-authorize with `python scripts/setup_oauth2.py`
- Check that all required scopes are granted

### Token Expired
- Tokens auto-refresh, but if refresh fails:
  ```bash
  python scripts/setup_oauth2.py  # Re-authorize
  ```

## 📊 Migration from OAuth 1.0a

### Old (OAuth 1.0a) - DEPRECATED
```python
# Required 4 credentials
TWITTER_API_KEY=xxx
TWITTER_API_SECRET=xxx
TWITTER_ACCESS_TOKEN=xxx
TWITTER_ACCESS_TOKEN_SECRET=xxx
```

### New (OAuth 2.0) - CURRENT
```python
# Need Client ID and Secret for token refresh
CLIENT_ID=xxx
CLIENT_SECRET=xxx
# Tokens stored in .env.wdfwatch (and optionally .env)
# See ENV_SETUP.md for complete setup
```

### Benefits of Migration
- ✅ Fewer credentials to manage
- ✅ Automatic token refresh
- ✅ Better rate limits
- ✅ More secure with PKCE
- ✅ Granular permissions

## 📚 Resources

- [Twitter OAuth 2.0 Documentation](https://developer.x.com/en/docs/authentication/oauth-2-0)
- [PKCE Specification](https://datatracker.ietf.org/doc/html/rfc7636)
- [Twitter API v2 Endpoints](https://docs.x.com/x-api)
- [Rate Limits](https://docs.x.com/fundamentals/rate-limits)

## 🤖 Integration with WDFWatch

The OAuth 2.0 implementation is integrated into:
- `src/wdf/twitter_oauth2.py` - Core OAuth 2.0 client
- `src/wdf/twitter_api_v2.py` - API client (uses OAuth 2.0)
- `scripts/setup_oauth2.py` - Interactive setup tool
- Web UI - Token management interface (coming soon)

For production deployment, ensure:
1. Tokens are securely stored
2. Refresh mechanism is tested
3. Rate limiting is properly handled
4. Error recovery is in place