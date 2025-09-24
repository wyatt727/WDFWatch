# Twitter API Setup Guide

## Overview

The WDFWatch bot requires Twitter API credentials to search for and reply to tweets. This guide explains which credentials you need and how to obtain them.

## Required Credentials

The credentials you need depend on what functionality you want:

### For Reading Tweets Only
- **API Key** (also called Consumer Key)
- **API Secret** (also called Consumer Secret)
- **Bearer Token**

### For Reading AND Posting Tweets

You'll need all the above, plus one of these authentication methods:

#### Option 1: OAuth 2.0 (Recommended for new apps)
- **Access Token** (OAuth 2.0 token)
- No Access Token Secret needed

#### Option 2: OAuth 1.0a (Legacy, but still supported)
- **Access Token** (User access token)
- **Access Token Secret** (User access token secret)

## How to Get These Credentials

### Step 1: Create a Twitter Developer Account

1. Go to [https://developer.twitter.com/en/portal/dashboard](https://developer.twitter.com/en/portal/dashboard)
2. Sign up for a developer account if you haven't already
3. Create a new App (or use an existing one)

### Step 2: Get Your App Credentials

1. In your app settings, go to "Keys and tokens"
2. You'll find:
   - **API Key and Secret** - Copy these
   - **Bearer Token** - Generate and copy this

### Step 3: Get Access Tokens (for posting)

#### For OAuth 2.0:
1. Set up OAuth 2.0 in your app settings
2. Configure your redirect URI
3. Use the OAuth 2.0 flow to get an access token
4. Or use the `generate_wdfwatch_tokens.py` script

#### For OAuth 1.0a:
1. In "Keys and tokens", under "Access Token and Secret"
2. Generate these tokens (they're tied to your account)
3. Copy both the Access Token and Access Token Secret

## Entering Credentials in WDFWatch

### Via Web UI (Recommended)

1. Navigate to Settings → API Keys in the web interface
2. Select the "Twitter/X" tab
3. Enter your credentials:
   - **API Key**: Your app's API key
   - **API Secret**: Your app's API secret
   - **Bearer Token**: Your app's bearer token
   - **Access Token**: Your OAuth 2.0 or OAuth 1.0a access token
   - **Access Token Secret**: Only if using OAuth 1.0a (leave empty for OAuth 2.0)
4. Click "Save Configuration"

### Via Environment Variables

Alternatively, set these environment variables:

```bash
# Basic credentials (always needed)
export API_KEY="your_api_key"
export API_KEY_SECRET="your_api_secret"
export BEARER_TOKEN="your_bearer_token"

# For OAuth 2.0
export WDFWATCH_ACCESS_TOKEN="your_oauth2_access_token"

# For OAuth 1.0a (legacy)
export WDFWATCH_ACCESS_TOKEN="your_access_token"
export WDFWATCH_ACCESS_TOKEN_SECRET="your_access_token_secret"
```

## Which Authentication Method Should I Use?

### Use OAuth 2.0 if:
- You're setting up a new app
- You want to use the latest Twitter API features
- You're comfortable with OAuth 2.0 flows
- You want automatic token refresh capability

### Use OAuth 1.0a if:
- You have an existing app using OAuth 1.0a
- You want simpler setup (just generate tokens in the dashboard)
- You don't need the latest OAuth 2.0 features

## Testing Your Configuration

After entering your credentials, you can test them by:

1. Going to the Manual Scrape page
2. Entering a test keyword
3. Clicking "Start Focused Search"
4. Checking if tweets are successfully retrieved

## Troubleshooting

### "API key not found" error
- Make sure you've saved your credentials in Settings → API Keys
- Check that the keys are not expired or revoked
- Verify you're using the correct environment (development/production)

### "Unauthorized" error
- Your access tokens might be expired
- For OAuth 2.0: Generate new tokens using the OAuth flow
- For OAuth 1.0a: Regenerate tokens in the Twitter dashboard

### Rate limiting
- Twitter API has rate limits (300 requests per 15 minutes for search)
- The app tracks quota usage automatically
- Check the quota meter in the web UI sidebar

## Security Notes

- **Never commit API keys to Git**
- All keys are encrypted before storage in the database
- Use environment-specific keys (dev/staging/production)
- Regularly rotate your access tokens
- Monitor the audit logs for unauthorized usage

## Additional Resources

- [Twitter API Documentation](https://developer.twitter.com/en/docs/twitter-api)
- [OAuth 2.0 Setup Guide](https://developer.twitter.com/en/docs/authentication/oauth-2-0)
- [Rate Limits](https://developer.twitter.com/en/docs/twitter-api/rate-limits)