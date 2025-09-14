Below is a **practical, numbers‑driven strategy** for harvesting only the *most relevant* new tweets that match your evolving keyword space **without burning through a 10K / month read quota**. (I’ll assume “10K reads” = 10K billable Tweet objects returned across all GET/stream deliveries, which is how X tiers typically notionally meter *retrieval*; if your plan counts requests instead of tweets, adjust—but the same throttling logic applies.)

---

## 1. Core Principles

1. **Push over Pull:** Use the *Filtered Stream* for continuous capture; use *Search (recent)* only for (a) cold start backfill, (b) resilience gap fill after downtime, (c) low‑frequency “miss audit.”
2. **Pre‑Filter on X as Much as Possible:** Push high‑precision lexical rules upstream so you ingest fewer junk tweets (each junk tweet *is still a read*).
3. **Two‑Tier Keyword Strategy:**

   * *Tier A (High Precision / Core)* → goes into live stream rules.
   * *Tier B (Broader / Exploratory)* → polled intermittently with small windows & since\_id to sample, classify locally, and promote good terms to Tier A.
4. **Aggressive Local Post‑Filter:** Even with precise rules, run your local classifier to eject borderline or spam *before* allocating downstream pipeline cost (embedding, LLM).
5. **Quota Accounting + Adaptive Throttle:** Track real consumption per hour/day; auto‑tighten (remove least performing rules or reduce search frequency) if projected burn > budget.

---

## 2. Budgeting the 10K Reads

Assume 30‑day month:

| Purpose                             | Target % | Tweet Reads | Rationale                          |
| ----------------------------------- | -------- | ----------- | ---------------------------------- |
| Filtered Stream (Tier A)            | 70%      | 7,000       | Primary continuous source          |
| Backfill & Gap Recovery             | 10%      | 1,000       | Outages / downtime windows         |
| Exploratory Sampling (Tier B)       | 10%      | 1,000       | Discover new high‑precision tokens |
| Manual / On‑Demand Searches (debug) | 5%       | 500         | Operator queries                   |
| Safety Buffer                       | 5%       | 500         | Unplanned spikes                   |

**Daily “allowance” for stream:** \~7,000 / 30 ≈ 233 tweets/day.
If current day’s stream > 233, auto‑shrink rule set; if << 233, you have slack to temporarily widen exploratory sampling.

---

## 3. Filtered Stream Rule Engineering

### 3.1 Craft High-Precision Boolean Blocks

* Combine *inclusion* AND *disambiguators*:

  ```
  ("federalism" OR "interstate compact") (podcast OR episode OR ep OR "listened to")
  ```
* Use **grouped OR lists** for synonyms; remove generic high‑noise terms unless paired with a narrow co-term.
* Apply **negative terms** to cut junk:

  ```
  "divorce" -("celebrity" OR "kardashian" OR "astrology")
  ```
* If the API tier allows rule tags, tag each rule with a stable identifier so you can measure yield (tweets per day).

### 3.2 Partition by Intent Buckets

Examples:

| Tag                 | Focus                         | Example Rule Skeleton                                                     |
| ------------------- | ----------------------------- | ------------------------------------------------------------------------- |
| `EP_DISCUSSION`     | Direct discussion of episodes | ("War, Divorce, or Federalism" OR WDFPodcast) (ep OR episode OR listened) |
| `FEDERALISM_POLICY` | Policy-level tweets           | federalism (supreme OR court OR state OR sovereignty) -sports             |
| `DIVORCE_SOCIAL`    | Social/legal discourse        | divorce (custody OR settlement OR prenup) -celebrity                      |

Keep total number of active rules low (start 5–10). Each additional rule increases surface → potential read burn.

### 3.3 Rule Scoring Loop

Maintain per rule every 24h:

* **Tweets Captured**
* **% Locally Classified Relevant**
* **Approved Replies Generated**
* **Cost per Approved Reply** (reads / approved)

Cull or tighten bottom performers weekly.

---

## 4. Stream Lifecycle & Minimal Backfill

**State you track locally:**

* `last_stream_tweet_id` (monotonic) per rule tag
* Intermittent health pings (no tweets for X minutes? Check connection/backpressure)

**If stream disconnects:**

1. Note outage window `[t_down_start, t_down_end]`.
2. Run targeted *recent search* queries for each *Tier A* rule using:

   * Original rule keywords (but possibly narrower) + `since_id=last_stream_tweet_id`.
   * Limit pages until you reach either the time boundary or you fetch 2× expected volume (guard).

**Backfill Guard:** Stop search if cumulative search tweets for recovery exceed that day’s backfill budget slice (e.g., 1,000 / 30 ≈ 33 tweets). If exceeded, log a “gap risk” event for manual review.

---

## 5. Exploratory Tier (Tier B Sampling)

Goal: discover new high-yield terms without letting them explode reads.

**Method:**

* Maintain a *candidate keyword list* produced by: (a) local embedding similarity expansion, (b) co-occurrence within high performing tweets, (c) user suggestions.
* Once per *N* hours (e.g., every 6h), issue *one* composed search query that ORs 2–3 candidate tokens with a mandatory anchor narrowing term (e.g., “federal”).
* Fetch *only first page* (or until 10 tweets). Classify locally. If **relevance rate > threshold (e.g., 60%)** for ≥ 3 consecutive samples, escalate that candidate into a proper Tier A rule (after merging logic with existing rules).

**Why not put them in stream immediately?** They’re unproven; they could blow up daily read usage if high frequency.

---

## 6. Local Classifier Throttling

**Stage 1 (cheap embedding / lexical score)** quickly rejects tweets with insufficient semantic overlap BEFORE counting against downstream budgets (LLM). (They already cost you a read—but they won’t cascade cost.)

**Stage 2 (small fine-tuned model)** only applied to borderline Stage 1 passes.

You record:

* Rule Tag
* Stage 1 Score
* Stage 2 Probability
* Final Decision

So you can refine upstream rule expressions to absorb Stage 1 patterns (e.g., if many rejections contain a certain noisy co-term, add it to negatives).

---

## 7. Quota Projection & Adaptive Rule Tightening

Implement a *daily projection function*:

```
projected_monthly = (reads_so_far / days_elapsed) * 30
if projected_monthly > 10_000:
   excess_ratio = projected_monthly / 10_000
   # Strategy: remove lowest yield rules until projection <= 1.0
```

**Yield Ranking Metric:**

```
yield_score = (approved_replies + 0.5 * pending_high_confidence) / reads_consumed
```

Sort ascending, prune until safe.

**Alternative Tightening:** For a chatty rule, add an extra required token (e.g., require "podcast" or "episode") rather than removing it entirely.

---

## 8. De-Duplication & Re-Processing Avoidance

Keep a hash (e.g. SHA1 of normalized tweet text) → if two different rule matches deliver same tweet, only count once for analytics. You still *receive* one tweet object from X; duplicates within your pipeline should not double-spend internal processing budget.

Also avoid re-classifying:

* Maintain a `processed_tweet_ids` LRU in memory + persisted store. If classification state already exists, skip.

---

## 9. Thread Expansion Minimization

Fetching full threads can multiply reads quickly (if your tier charges additional calls). Strategy:

1. **Default:** Do *not* fetch conversation context unless Stage 2 classifier confidence is within an “uncertainty band” AND the tweet has a `reply_count > 0` (if the field is present in payload) or contains an obviously truncated context clue (e.g., starts with pronoun “That” / “This” referencing earlier content).
2. **On Demand by Human:** In UI, thread expansion button displays estimated additional read cost (“≈ 1–5 tweets”). Confirm before fetching.
3. Cache thread tweets for future classification of siblings.

---

## 10. Rate (Traffic) Shaping

If a breaking news event triggers a spike causing a surge in matches:

* Temporarily switch certain ambiguous rules to *“cooldown mode”* = hold tweets in an in-memory ring buffer and *sample* (e.g., accept 1 out of every N). Promote the first 50 accepted for classification; if >X% are relevant, keep sampling; else hard-throttle rule entirely for 30 minutes.

Pseudo:

```python
if rule_tweets_last_10m > rule_threshold:
    sampling_ratio = min( (rule_tweets_last_10m / rule_threshold), max_ratio )
    accept = (hash(tweet_id) % sampling_ratio) == 0
```

---

## 11. Observability Metrics You Must Track

| Metric                               | Purpose              | Action Trigger                           |
| ------------------------------------ | -------------------- | ---------------------------------------- |
| Reads per rule per day               | Precision insight    | Cull bottom 20% yield rules weekly       |
| Relevance rate per rule              | Upstream quality     | Add negative tokens to rules < target    |
| Approved replies per 100 reads       | ROI                  | Optimize prompts/classifier if dropping  |
| Gap detection (expected vs received) | Reliability          | Run targeted backfill if gap > threshold |
| Exploratory promotion success (%)    | Expansion efficiency | Adjust candidate generation method       |
| Projected monthly reads              | Budget health        | Auto-tightening event                    |

---

## 12. Implementation Sequence

1. **Phase 0:** Manually craft 5 seed Tier A rules (conservative). Start stream. Log volume.
2. **Phase 1:** Add per-rule counters + daily projection logic; build adaptive pruning.
3. **Phase 2:** Add Tier B sampling scheduler + promotion logic.
4. **Phase 3:** Implement cooldown sampling for surges.
5. **Phase 4:** Build rule optimization suggestion tool (generate negatives from frequent rejection tokens).
6. **Phase 5:** UI surface (per-rule yield dashboard, quota meter).

---

## 13. Data Structures (Minimal)

| Store                       | Key             | Value                                                 |
| --------------------------- | --------------- | ----------------------------------------------------- |
| `rule_stats:{rule_tag}:day` | date            | { reads, classified\_relevant, approved, rejections } |
| `tweet_proc`                | tweet\_id       | { ts, stage1, stage2, decision }                      |
| `hash_dedupe` (LRU)         | text\_hash      | tweet\_id                                             |
| `gap_log`                   | ISO time window | status                                                |
| `quota`                     | daily\_date     | reads\_int                                            |

---

## 14. Practical Rule Refinement Loop (Weekly)

1. Export all rejected tweets grouped by rule.
2. Tokenize & get top TF-IDF terms for *rejected-only* vs *accepted-only*.
3. Suggest:

   * **Negatives** = high frequency in rejects, low in accepts.
   * **Promotions** = bigrams in accepts not present in rule; test in Tier B.
4. Human approves modifications → update rule set atomically (log old & new).

---

## 15. Example (Concrete)

**Initial Rule (too broad):**

```
federalism
```

Average daily reads: 150 (kills budget). Relevance rate: 10%.

**Refined (two-step):**

1. Add co-terms:

   ```
   (federalism ("podcast" OR "episode" OR "listen" OR "listened")) OR
   ("federalism debate" -sports -football)
   ```
2. Negative terms learned from rejects: `-("college" OR "ncaa" OR "fantasy")`

Reads drop to 25/day; relevance climbs to 65%; ROI improves drastically.

---

## 16. Tooling Enhancements (Later)

| Enhancement                                            | Benefit                                                                                         |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Automated “simulated rule” re-run on historical corpus | See hypothetical effect before deploying                                                        |
| Canary rule deployment (shadow)                        | Measure yield without counting toward quota (if you already have local archive or use sampling) |
| Embedding-based candidate generation                   | Finds semantically close terms to high-ROI tweets                                               |
| Active learning loop                                   | Borderline tweets manually labeled feed fine-tuned classifier to reduce Stage 2 calls           |

---

## 17. Quick Checklist

* [ ] Baseline Tier A rules defined & tagged
* [ ] Stream consumer logs per-rule counts
* [ ] Daily projection vs 10K with adaptive pruning logic
* [ ] Backfill script using since\_id & time window
* [ ] Tier B sampler (one combined search every 6h)
* [ ] Rule yield dashboard
* [ ] Surges → sampling fallback
* [ ] Weekly negative-term suggestion report
* [ ] Dedupe & processed cache

---

### TL;DR

**Use a narrow, tagged filtered stream + adaptive rule pruning, confine searches to surgical backfill & exploration, and continuously learn negatives & high-yield expansions.** Track per-rule ROI, project monthly burn daily, and clamp noisy rules early. This keeps you comfortably under 10K while still surfacing the highest-value tweets for your LLM reply pipeline.

---
