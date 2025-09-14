Perfect—PKCE is the right call. Here’s a clean, current setup to post as **@WDF\_Watch** using an app owned by **WDF\_Show**, via **OAuth 2.0 Authorization Code + PKCE (user context)**.

# What you need (scopes + support)

* **Endpoints supported by OAuth2 PKCE:** `POST /2/tweets` (Create Post) is allowed with OAuth 2.0 Authorization Code with PKCE (user context). Needed scopes: **`tweet.write`**, plus **`tweet.read`** and **`users.read`**; add **`offline.access`** for refresh tokens. Include **`media.write`** if you’ll upload media. ([docs.x.com][1])
* **Token lifetimes:** access tokens ≈ **2 hours**; add `offline.access` to receive a **refresh\_token** and rotate without re-consent. ([X Developer][2])

---

# One-time app setup (in WDF\_Show’s dev portal)

1. Enable **OAuth 2.0** for the app; note the **Client ID** (and Client Secret if you chose a confidential “Web/Automated App,” though you’ll still use PKCE). Add an **exact-match** redirect URL (e.g., `https://your.app/callback`). ([X Developer][2])
2. Ask **@WDF\_Watch** to complete the 3-leg flow once; you’ll store that account’s user tokens and post **as that user** thereafter. ([docs.x.com][1])

---

# The PKCE flow (copy/paste endpoints)

**Authorize URL (open in browser):**
`https://x.com/i/oauth2/authorize` with:

* `response_type=code`
* `client_id=…`
* `redirect_uri=https://your.app/callback` (must exactly match)
* `scope=tweet.read tweet.write users.read offline.access`
* `state=<random>`
* `code_challenge=<S256(base64url(SHA256(code_verifier)))>`
* `code_challenge_method=S256` ([X Developer][2])

**Token exchange (within \~30 seconds of the redirect):**

```
POST https://api.x.com/2/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=<auth_code_from_callback>&
code_verifier=<original_code_verifier>&
redirect_uri=https://your.app/callback&
client_id=<your_client_id>
```

Returns `{ access_token, refresh_token?, token_type, expires_in, scope }`. ([X Developer][2])

**Refreshing silently (token rotation):**

```
POST https://api.x.com/2/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=<stored_refresh_token>&
client_id=<your_client_id>
```

(You get a **new** access\_token *and* a **new** refresh\_token; store the new pair.) ([X Developer][2])

---

# Post as @WDF\_Watch (plain JSON)

Minimal post:

```bash
curl -X POST https://api.x.com/2/tweets \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"hello from PKCE 👋"}'
```

Reply / media / quoting are in the same endpoint; for a reply:

```json
{
  "text": "replying…",
  "reply": { "in_reply_to_tweet_id": "1234567890" }
}
```

(See the “Create Post” schema for supported fields like `media.media_ids`, `quote_tweet_id`, `reply.exclude_reply_user_ids`, etc.) ([docs.x.com][3])

---

# Drop-in code (Node + Express)

```ts
import express from "express";
import crypto from "crypto";
import fetch from "node-fetch";

const app = express();
const clientId = process.env.X_CLIENT_ID!;
const redirectUri = "http://localhost:8787/callback";
const scope = "tweet.read tweet.write users.read offline.access";

let codeVerifier = ""; // store per-session (or tie to user session)

function b64url(buf: Buffer) {
  return buf.toString("base64").replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
}

app.get("/login", (_, res) => {
  codeVerifier = b64url(crypto.randomBytes(32)); // 43–128 chars recommended
  const challenge = b64url(crypto.createHash("sha256").update(codeVerifier).digest());
  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope,
    state: crypto.randomUUID(),
    code_challenge: challenge,
    code_challenge_method: "S256"
  });
  res.redirect(`https://x.com/i/oauth2/authorize?${params}`);
});

app.get("/callback", async (req, res) => {
  const code = String(req.query.code || "");
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    code_verifier: codeVerifier,
    redirect_uri: redirectUri,
    client_id: clientId
  });
  const tok = await fetch("https://api.x.com/2/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  }).then(r => r.json());

  // persist tok.access_token and tok.refresh_token for @WDF_Watch
  // then post a tweet:
  const r2 = await fetch("https://api.x.com/2/tweets", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${tok.access_token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ text: "Hello from OAuth2 PKCE 🤖" })
  }).then(r => r.json());

  res.json({ token: tok, postResponse: r2 });
});

app.listen(8787, () => console.log("Go to http://localhost:8787/login"));
```

(Params, endpoints, and scopes per X docs.) ([X Developer][2], [docs.x.com][1])

---

# Minimal Python (Flask)

```python
import os, secrets, hashlib, base64
from flask import Flask, redirect, request
import requests

app = Flask(__name__)
CLIENT_ID = os.environ["X_CLIENT_ID"]
REDIRECT_URI = "http://localhost:5000/callback"
SCOPE = "tweet.read tweet.write users.read offline.access"
code_verifier = ""

def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

@app.route("/login")
def login():
    global code_verifier
    code_verifier = b64url(os.urandom(32))
    challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())
    params = {
        "response_type":"code","client_id":CLIENT_ID,
        "redirect_uri":REDIRECT_URI,"scope":SCOPE,
        "state":secrets.token_urlsafe(16),
        "code_challenge":challenge,"code_challenge_method":"S256"
    }
    return redirect("https://x.com/i/oauth2/authorize?" + "&".join(f"{k}={requests.utils.quote(v)}" for k,v in params.items()))

@app.route("/callback")
def callback():
    code = request.args.get("code","")
    data = {
        "grant_type":"authorization_code","code":code,
        "code_verifier":code_verifier,"redirect_uri":REDIRECT_URI,
        "client_id":CLIENT_ID
    }
    tok = requests.post("https://api.x.com/2/oauth2/token", data=data).json()
    r = requests.post(
        "https://api.x.com/2/tweets",
        headers={"Authorization": f"Bearer {tok['access_token']}", "Content-Type":"application/json"},
        json={"text":"Posted via PKCE 🎯"}
    ).json()
    return {"token": tok, "post": r}

app.run(port=5000)
```

(Uses the same authorize/token endpoints and `POST /2/tweets`.) ([X Developer][2], [docs.x.com][3])

---

# Quotas & safety levers you’ll want

* **Rate limit buckets:** Requests count against **per-user** and **per-app** buckets; inspect `x-rate-limit-*` headers and back off accordingly. ([docs.x.com][4])
* **Retry logic:** On `429`, sleep until `x-rate-limit-reset`. On `401` with `invalid_token`, refresh and retry once. ([docs.x.com][4])
* **Time-box paging:** If you later add reads (e.g., search), use `start_time`/`end_time`, max page sizes, and counts endpoints to conserve quota. (You already have these from earlier; just noting best practices.)

---

# Common gotchas

* **Exact redirect match** required, including scheme/host/port/path. Mismatch = `invalid_redirect_uri`. ([X Developer][2])
* **Exchange deadline:** The `code` must be redeemed quickly (docs note a short window). Don’t defer the token call. ([X Developer][2])
* **Scopes sticky:** If you add scopes later (e.g., `media.write`), the user must re-consent to mint tokens with the new scope set. ([X Developer][2])
* **Posting fields:** Replies use `reply.in_reply_to_tweet_id`; polls, places, communities, tagging, and quoting are all fields on the same JSON. ([docs.x.com][3])

If you want, I can tailor this to your stack (e.g., Go or Rust), add media upload (v2 media endpoints with `media.write`), and wire in a tiny token store with automatic refresh + rate-limit backoff.

[1]: https://docs.x.com/fundamentals/authentication/guides/v2-authentication-mapping "X API v2 authentication mapping - X"
[2]: https://developer.x.com/en/docs/authentication/oauth-2-0/authorization-code "OAuth 2.0 Authorization Code Flow with PKCE - X"
[3]: https://docs.x.com/x-api/posts/create-post "Create Post - X"
[4]: https://docs.x.com/fundamentals/rate-limits?utm_source=chatgpt.com "Rate limits - X - Welcome to the X Developer Platform"
