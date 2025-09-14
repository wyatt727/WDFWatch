Here’s a tight, up-to-date playbook for keyword search on X (Twitter) and how to stretch your read limits.

# What to use (and how they differ)

* **Recent Search** — `GET /2/tweets/search/recent`
  • Window: last **7 days**
  • Page size: **10 default**, up to **100** via `max_results`
  • Sort: `recency` or `relevancy` (use `recency` when paginating)
  • Query string technical max: docs show **up to 4096 chars**, but your **plan may cap** lower (see plan limits below). ([docs.x.com][1])

* **Full-archive Search** — `GET /2/tweets/search/all`
  • Window: **entire public archive** (since 2006)
  • Page size: **10 default**, **up to 500** via `max_results`
  • Same sort options as above
  • Query string technical max listed as **up to 4096 chars** in the ref; again, your **plan may cap** lower. ([docs.x.com][2])

* **Post Counts** (don’t fetch the Tweets—just get volumes)
  • Recent: `GET /2/tweets/counts/recent` (7-day)
  • Full-archive: `GET /2/tweets/counts/all`
  • Use this to *forecast volume before you read data*. Same boolean/query operators as search. ([docs.x.com][3])

* **Filtered Stream** — `GET /2/tweets/search/stream` (+ `/rules`)
  • Real-time delivery using 1,000 rules (each up to \~1,024 chars on Pro)
  • Recovery/backfill options exist for outages (where allowed by plan). ([X Developer][4], [docs.x.com][5])

# Keyword (operator) tips that actually save quota

Build one **single query** using boolean logic and operators; parentheses matter.

**Noise-cutters (use these a lot):**

* `-is:retweet` (drop RTs), `-is:reply` (original posts only), `-is:quote`, `-is:nullcast` (exclude ads/promoted, must be negated), `lang:en` (or other ISO code). ([docs.x.com][6])

**Targeting content types:**

* `has:links`, `has:media`, `has:images`, `has:video_link`, `has:mentions`, `has:cashtags`, `has:hashtags`. ([docs.x.com][6])

**Entities, URLs, places, topics:**

* `url:example.com` to match shared links to a domain;
* `place:"new york city"` or `place:fd70c22040963ac7` and `place_country:US` to focus geo-tagged posts;
* `context:domain_id.entity_id` and `entity:"Named Thing"` to use X’s context annotations (great for high-recall topic tracking). ([docs.x.com][6])

**Examples that reduce reads**

* Track *brand* chatter w/o noise:
  `"Acme" OR @AcmeOfficial (has:links OR has:media) -is:retweet lang:en`
* Competitive set with topics, not just keywords:
  `(context:10.799022225751871488 OR "Acme Widget") -is:retweet lang:en` (context id is for a topic domain/entity). ([docs.x.com][6])

# Read-limit conservation (what materially helps)

1. **Preflight with Counts**
   Ask “how big is this?” before you fetch content. Use `/counts/*` to check volumes by hour/day; adjust your keywords, language, and time window until the counts are manageable. This avoids burning monthly post caps and per-15-min windows on trial-and-error. ([docs.x.com][3], [X Developer][7])

2. **Always request the max page size**
   Use `max_results=100` (recent) or `=500` (full-archive) to minimize the number of requests. Fewer requests = fewer rate-limit hits. ([docs.x.com][1])

3. **Paginate on `recency`**
   When you need multiple pages, set `sort_order=recency`. Pagination tokens are reliable there; with `relevancy` you might not get a `next_token`. ([docs.x.com][1])

4. **Checkpoint your runs**
   Persist `since_id`/`until_id` (or `start_time`/`end_time`) across jobs so each run only fetches new data. RFC 3339 timestamps in UTC are required. ([docs.x.com][1], [X Developer][8])

5. **Use expansions instead of extra lookups**
   Need authors, media, places, or quoted/original posts? Add `expansions=` plus the specific `*.fields` in the *same* search call (e.g., `expansions=author_id&user.fields=verified,username`). That’s one request instead of many. ([docs.x.com][9])

6. **Narrow early**
   Add `-is:retweet`, `lang:`, and `has:` filters to your *search query* rather than post-filtering client-side. That reduces both results and pages. ([docs.x.com][6])

7. **Time-slice long pulls**
   For big histories, break by day/hour using `start_time`/`end_time` (RFC 3339). This keeps pages consistent and helps resume safely if you hit 429s. ([X Developer][8])

8. **Watch the actual plan limits (and monthly post caps)**
   The official **Rate limits** page lists per-endpoint quotas by plan (Free/Basic/Pro) and notes a monthly post-consumption cap. Your app vs user token also affects what limit bucket is used. ([X Developer][7])

# Up-to-date plan nuances (as of today)

* **Search recent**: up to **300 req/15m per user** (Pro) and **60 req/15m** (Basic/Free).
* **Counts endpoints**: up to **300 req/15m per app** (Pro).
* **Filtered stream**: connection/rules quotas vary; Pro allows **\~1000 rules** with rule length up to \~**1024 chars**.
* **Query length**: the endpoint definitions show **1–4096** chars accepted, but **your plan may enforce 512/1024** caps and operator gating (core vs enhanced). Check your plan’s caps against the Rate Limits page. ([X Developer][7], [docs.x.com][10])

# Minimal, quota-friendly request patterns

**1) Preflight volume (Counts)**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  --get 'https://api.x.com/2/tweets/counts/recent' \
  --data-urlencode 'query=("Acme" OR @AcmeOfficial) -is:retweet lang:en' \
  --data-urlencode 'granularity=hour'
```

(Use the `total_tweet_count` and hourly buckets to decide page size and slicing.) ([docs.x.com][3])

**2) One-pass enriched fetch (Search recent)**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  --get 'https://api.x.com/2/tweets/search/recent' \
  --data-urlencode 'query=("Acme" OR @AcmeOfficial) -is:retweet lang:en' \
  --data-urlencode 'max_results=100' \
  --data-urlencode 'sort_order=recency' \
  --data-urlencode 'tweet.fields=created_at,public_metrics,lang,source' \
  --data-urlencode 'expansions=author_id,referenced_tweets.id' \
  --data-urlencode 'user.fields=username,verified,public_metrics'
```

(All in one call: fewer requests than separate user/media lookups.) ([docs.x.com][1])

**3) Real-time monitoring (Filtered stream)**
Create narrow rules (use the same noise-cutters) and rely on stream instead of polling search. Add/remove rules without dropping the connection; use recovery/backfill features if your plan allows. ([docs.x.com][11])

# Common gotchas (and fixes)

* **Wrong timestamps** → API requires **RFC 3339 UTC** (`YYYY-MM-DDTHH:mm:ssZ`). ([X Developer][8])
* **Paginating with `relevancy`** → may not return `next_token`; switch to `recency`. ([docs.x.com][1])
* **Over-expanding** → expansions don’t cost *more requests*, but only request fields you actually use to reduce payload/latency. ([docs.x.com][9])
* **Plan/operator mismatch** → some operators are **core** (all access), others **enhanced** (higher tiers). Check the operator table before building queries. ([docs.x.com][10])

If you want, tell me your **exact plan (Free/Basic/Pro)** and a sample query, and I’ll optimize it for both **relevance** *and* **read-limit efficiency** using the right operators and page strategy.

[1]: https://docs.x.com/x-api/posts/recent-search "Search recent Posts - X"
[2]: https://docs.x.com/x-api/posts/full-archive-search "Search all Posts - X"
[3]: https://docs.x.com/x-api/posts/get-count-of-recent-posts "Get count of recent Posts - X"
[4]: https://developer.x.com/en/docs/x-api/filtered-stream-overview?utm_source=chatgpt.com "Twitter API's filtered streaming endpoints - Twitter Developer - X"
[5]: https://docs.x.com/x-api/posts/filtered-stream/integrate/recovery-and-redundancy-features?utm_source=chatgpt.com "Recovery and redundancy - X"
[6]: https://docs.x.com/x-api/posts/search/integrate/build-a-query?utm_source=chatgpt.com "Build a query - X"
[7]: https://developer.x.com/en/docs/x-api/rate-limits "Rate limits - X"
[8]: https://developer.x.com/en/docs/twitter-api/tweets/search/migrate/enterprise-to-twitter-api-v2.html?utm_source=chatgpt.com "Search Tweets enterprise to v2 migration guide | Docs"
[9]: https://docs.x.com/x-api/fundamentals/fields?utm_source=chatgpt.com "Fields - X"
[10]: https://docs.x.com/x-api/posts/counts/integrate/build-a-query?utm_source=chatgpt.com "Build a query - X API"
[11]: https://docs.x.com/x-api/posts/filtered-stream/integrate/build-a-rule?utm_source=chatgpt.com "Build a rule - X API"
