Below is a **refined, domain‑aligned filtered stream strategy** tuned to *your* topical universe:

> **Themes you specified / implied:** “National Divorce” (i.e., secession / peaceful separation), Federalism & States’ Rights, Libertarianism, Civil War (historical & hypothetical future fracturing), Supreme Court rulings / constitutional doctrine, Executive Orders / presidential power, plus adjacent constitutional decentralization concepts (nullification, 10th Amendment, interstate compacts, decentralization, enumerated powers, executive overreach).

Goal: **High topical breadth** *without* blowing a 10K/month read budget.
Approach: **Layered rule clusters** with *precision anchors*, *semantic disambiguators*, *topic‑specific negatives*, and *adaptive gating*.

---

## 1. Clustering the Topic Space

| Cluster Code              | Theme Focus                                                                   |
| ------------------------- | ----------------------------------------------------------------------------- |
| NDIV                      | “National Divorce” / secession / peaceful separation rhetoric                 |
| FED\_CORE                 | Federalism, states’ rights, Tenth Amendment, enumerated powers                |
| LIBERTY                   | Libertarian / minarchist / NAP / decentralization discourse                   |
| CIVIL\_FRAG               | Civil war breakup / internal conflict risk (policy or structural, not gaming) |
| SCOTUS                    | Supreme Court decisions, constitutional doctrine debates                      |
| EXEC\_PWR                 | Executive orders, executive overreach, administrative state                   |
| DECENTRAL                 | Institutional decentralization, nullification, interstate compacts            |
| POLY\_CRISIS\* (optional) | Combined institutional stress semantics (for future expansion)                |

We’ll define **Tier A (Always‑On)** high‑precision rules + **Tier B (Conditional / Adaptive)** broader capture that activates only when daily volume < threshold or on schedule.

---

## 2. Lexical / Semantic Seed Sets

### 2.1 Core Positive Lexemes (by cluster)

| Cluster     | Primary Terms (OR groups)                                                                                                                                                       | Anchor / Co‑Term Requirements (AND)                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| NDIV        | "national divorce" OR "peaceful separation" OR "peaceful secession" OR "peaceful divorce" OR "soft secession"                                                                   | (america OR american OR US OR "united states" OR USA OR union)                        |
| FED\_CORE   | federalism OR "states' rights" OR "state sovereignty" OR "tenth amendment" OR "10th amendment" OR "enumerated powers" OR preemption                                             | (constitution OR constitutional OR doctrine OR court OR authority OR powers)          |
| LIBERTY     | libertarianism OR libertarian OR minarchism OR minarchist OR "non aggression principle" OR "non-aggression principle" OR ancap OR "an-cap" OR voluntarism OR decentralization   | (policy OR principle OR philosophy OR law OR governance OR government OR state)       |
| CIVIL\_FRAG | "civil war" OR "second civil war" OR "2nd civil war" OR "american breakup" OR "national breakup" OR "balkanization"                                                             | (US OR america OR american OR states)                                                 |
| SCOTUS      | scotus OR "supreme court" OR certiorari OR "en banc" OR "oral argument" OR "major question doctrine" OR "nondelegation doctrine" OR "commerce clause" OR "administrative state" | (decision OR ruling OR opinion OR case OR docket OR holding OR precedent)             |
| EXEC\_PWR   | "executive order" OR "executive orders" OR "executive action" OR "executive overreach" OR "article ii" OR "unitary executive" OR "presidential power"                           | (constitution OR constitutional OR authority OR separation OR "separation of powers") |
| DECENTRAL   | "interstate compact" OR nullification OR nullify OR subsidiarity OR devolution                                                                                                  | (states OR states' OR federal OR congress OR legislative)                             |

### 2.2 Negative Term Packs (Noise Suppression)

| Pack                        | Negatives                                                                                                              | Rationale                                 |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| CELEB\_DIVORCE              | -kardashian -celebrity -gossip -astrology -tmz -hollywood -kylie                                                       | Filter pop/celebrity “divorce” chatter    |
| RELATIONSHIP                | -"my divorce" -"her divorce" -"his divorce" -ex-wife -exhusband -custody (keep if you *don’t* want private-case noise) |                                           |
| GAMING\_WAR                 | -callofduty -cod -fortnite -gta -warzone -minecraft -roblox                                                            | Filter gaming uses of “civil war / war”   |
| INVESTOR\_BUZZ              | -airdrop -giveaway -sweepstakes -promo -shill                                                                          | Filter spam / crypto tie-ins              |
| GENERIC\_RETWEET (optional) | -is\:retweet                                                                                                           | De-duplicate if volume comfortable        |
| SPORTS\_FED                 | -ncaa -football -basketball -draft -recruiting                                                                         | Avoid sports metaphors using “federalism” |

Apply only those needed per cluster (avoid over-pruning early).

---

## 3. Tier A (Always-On) Filtered Stream Rules

> **Language filter**: `lang:en` (adjust if you want multi-language).
> **Retweets**: Start with `-is:retweet` on clusters prone to echoing; leave off for SCOTUS if you want spread analysis.

Below: Each rule shown as **value** + **tag**. Combine negatives by context.

### 3.1 National Divorce / Secession

```
("national divorce" OR "peaceful separation" OR "peaceful secession" OR "peaceful divorce" OR "soft secession")
(america OR american OR "united states" OR USA OR US OR union)
lang:en -is:retweet -kardashian -celebrity -gossip
```

Tag: `NDIV_CORE`

Add variant capturing *implicit phrasing* (avoid “regular divorce”):

```
(secession OR "break up the union" OR "national breakup" OR "american breakup")
(peaceful OR negotiated OR orderly)
(US OR america OR american)
lang:en -is:retweet -kardashian -custody -ex-wife -exhusband
```

Tag: `NDIV_SECESSION`

### 3.2 Federalism / Enumerated Powers

```
(federalism OR "states' rights" OR "state sovereignty" OR "tenth amendment" OR "10th amendment" OR "enumerated powers")
(constitution OR constitutional OR doctrine OR authority OR powers OR preemption)
lang:en -is:retweet -ncaa -football -fantasy -draft
```

Tag: `FED_CORE`

```
(federalism (preemption OR "commerce clause" OR "major question doctrine" OR nondelegation))
lang:en -is:retweet -ncaa -football
```

Tag: `FED_DOCTRINE`

### 3.3 Libertarianism / Decentralization

```
(libertarianism OR libertarian OR minarchism OR minarchist OR ancap OR "an-cap" OR voluntarism OR "non aggression principle" OR "non-aggression principle")
(policy OR philosophy OR principle OR governance OR government)
lang:en -is:retweet -airdrop -giveaway -promo -shill
```

Tag: `LIBERTY_CORE`

```
(decentralization OR "decentralized governance" OR subsidiarity OR devolution)
(government OR state OR states OR policy)
lang:en -is:retweet -crypto -nft -token -airdrop
```

Tag: `LIBERTY_DECENTRAL`

### 3.4 Civil War / Fragmentation (Policy Angle)

```
("civil war" OR "second civil war" OR "2nd civil war" OR balkanization)
(US OR america OR american OR states)
(risk OR prevent OR avoid OR avert OR scenario OR hypothetical)
lang:en -is:retweet -callofduty -cod -fortnite -warzone -gta
```

Tag: `CIVIL_FRAG_SCENARIO`

```
("civil war" (future OR upcoming OR looming OR potential))
(US OR america)
lang:en -is:retweet -gaming -callofduty -cod -warzone
```

Tag: `CIVIL_FRAG_FUTURE`

### 3.5 Supreme Court / Doctrine

```
(scotus OR "supreme court")
(decision OR ruling OR opinion OR case OR docket OR precedent OR argument OR "oral argument")
(federalism OR "tenth amendment" OR "commerce clause" OR "major question doctrine" OR preemption OR "enumerated powers")
lang:en -fantasy -ncaa
```

Tag: `SCOTUS_FEDERALISM`

```
("major question doctrine" OR "nondelegation doctrine" OR "commerce clause" OR "unitary executive" OR "administrative state")
(scotus OR "supreme court" OR decision OR ruling OR case)
lang:en
```

Tag: `SCOTUS_DOCTRINE`

### 3.6 Executive Power / Orders

```
("executive order" OR "executive orders" OR "executive action" OR "presidential power" OR "unitary executive")
(overreach OR constitutional OR authority OR abuse OR limits OR limitation OR separation)
lang:en -is:retweet
```

Tag: `EXEC_PWR_OVERREACH`

```
("article ii" OR "article 2")
(executive OR "presidential power" OR authority)
(separation OR "separation of powers" OR constraint OR limit)
lang:en
```

Tag: `EXEC_PWR_ARTICLEII`

### 3.7 Interstate Compacts / Nullification

```
("interstate compact" (congress OR approval OR constitutional OR federal))
lang:en
```

Tag: `DECENTRAL_COMPACT`

```
(nullification OR nullify)
(federal OR mandate OR law OR order OR act)
(states OR "state legislature" OR legislature)
lang:en -vaccine*?   // (decide if you want vaccine mandate discourse; can add -covid if not)
```

Tag: `DECENTRAL_NULLIFICATION`

---

## 4. Tier B (Adaptive / Low-Frequency) Rules

Activated only when **daily total < X (e.g., 50)** or during *scheduled “exploration windows”*.

| Tag                | Rule (Broader)                                                                                    | Activation Condition               |
| ------------------ | ------------------------------------------------------------------------------------------------- | ---------------------------------- |
| `NDIV_BROAD`       | `"national breakup" OR "break up America" OR "break up the US"` lang\:en -is\:retweet -kardashian | Low volume day; monitor precision  |
| `LIBERTY_BROAD`    | (libertarian OR libertarians) lang\:en -promo -airdrop -giveaway                                  | If LIBERTY\_CORE < 20/day          |
| `EXEC_PWR_BROAD`   | ("executive order" OR "executive action") lang\:en -fashion -merch                                | If EXEC cluster < 15/day           |
| `CIVIL_FRAG_BROAD` | ("civil war") (america OR US) lang\:en -callofduty -cod -fortnite -warzone -gta                   | Only if CIVIL\_FRAG total < 10/day |

**Gating:** Your ingestion service watches per-cluster counts and API substitutionally enables/disables these “broad” rules via automation.

---

## 5. Overlap & De-Duplication Strategy

1. **Tag uniqueness**: Each rule MUST have a distinct tag; you log tweets with *first arrival tag*.
2. **Local de‑dupe**: Maintain a `tweet_id -> [tags]` set for analytics but count a read once.
3. Periodically analyze overlap: If two rules share >50% of captured tweet ids, **merge** or tighten one.

---

## 6. Adaptive Tightening Heuristics

| Symptom                                    | Action                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| Rule >30% of daily volume & precision <60% | Add *one* more mandatory co-term OR new negative token from reject top TF-IDF        |
| Precision 40–60% steady                    | Add 1–2 tailored negatives (avoid over-prune); track delta for 48h                   |
| Precision <40% 3 days                      | Disable or move to Tier B sampling                                                   |
| Precision >80% & volume <5/day             | Consider broad companion rule (Tier B) to broaden capture while keeping core precise |

---

## 7. Negative Token Mining Loop (Weekly)

1. For each tag, gather rejected tweets’ token frequencies (after lowercasing & stopword removal).
2. Subtract accepted token frequencies → compute *reject‑distinctive score*.
3. Candidate negatives = top N distinctive tokens not already in rule & not part of positive lexeme sets.
4. Human review → integrate 1–3 per week (slow, measured changes).

(You can ask later for a script outline.)

---

## 8. Metrics Per Tag (Minimal Schema)

```json
{
  "tag": "FED_CORE",
  "day": "2025-07-19",
  "reads": 22,
  "relevant": 18,
  "precision": 0.818,
  "approved_replies": 4,
  "yield": 0.182,
  "negatives": ["ncaa","football","fantasy","draft"]
}
```

Use these to compute global projection and gating.

---

## 9. Implementation Notes

* **Start small**: Maybe deploy only: `NDIV_CORE`, `FED_CORE`, `LIBERTY_CORE`, `SCOTUS_FEDERALISM`, `EXEC_PWR_OVERREACH`, `DECENTRAL_COMPACT`, `CIVIL_FRAG_SCENARIO`. That’s *7 rules*—measure baseline.
* **Observe 72h**: Add additional specialized doctrine rules if budget headroom >30% of daily allowance.
* **Edge Cases**: Some tweets might mention “divorce” metaphorically without “national” — purposely excluded to keep precision; Tier B rule could test `(divorce (america OR union)) -kardashian -custody` if you want to explore.

---

## 10. Quick Bulk “Add” JSON (Initial 7)

```json
{
  "add": [
    { "value": "(\"national divorce\" OR \"peaceful separation\" OR \"peaceful secession\" OR \"soft secession\") (america OR american OR \"united states\" OR USA OR US OR union) lang:en -is:retweet -kardashian -celebrity -gossip", "tag": "NDIV_CORE" },
    { "value": "(federalism OR \"states' rights\" OR \"state sovereignty\" OR \"tenth amendment\" OR \"10th amendment\" OR \"enumerated powers\") (constitution OR constitutional OR doctrine OR authority OR powers OR preemption) lang:en -is:retweet -ncaa -football -fantasy -draft", "tag": "FED_CORE" },
    { "value": "(libertarianism OR libertarian OR minarchism OR ancap OR \"non aggression principle\" OR \"non-aggression principle\" OR voluntarism) (policy OR philosophy OR principle OR governance OR government OR state) lang:en -is:retweet -airdrop -giveaway -promo -shill", "tag": "LIBERTY_CORE" },
    { "value": "(\"civil war\" OR \"second civil war\" OR balkanization) (US OR america OR american OR states) (risk OR prevent OR avoid OR avert OR scenario OR hypothetical) lang:en -is:retweet -callofduty -cod -fortnite -warzone -gta", "tag": "CIVIL_FRAG_SCENARIO" },
    { "value": "(scotus OR \"supreme court\") (decision OR ruling OR opinion OR case OR docket OR precedent OR argument) (federalism OR \"tenth amendment\" OR \"commerce clause\" OR \"major question doctrine\" OR preemption OR \"enumerated powers\") lang:en -fantasy -ncaa", "tag": "SCOTUS_FEDERALISM" },
    { "value": "(\"executive order\" OR \"executive orders\" OR \"executive action\" OR \"executive overreach\" OR \"presidential power\" OR \"unitary executive\") (overreach OR constitutional OR authority OR abuse OR limits OR limitation OR separation) lang:en -is:retweet", "tag": "EXEC_PWR_OVERREACH" },
    { "value": "(\"interstate compact\" (congress OR approval OR constitutional OR federal)) lang:en", "tag": "DECENTRAL_COMPACT" }
  ]
}
```

---

## 11. Expansion Candidates (After Baseline Data)

| Candidate Tag        | Promote If                                             | Example Rule                                                                                                       |
| -------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `NDIV_SECESSION`     | NDIV\_CORE < 15/day & precision >70%                   | (secession (peaceful OR negotiated) (US OR america)) lang\:en -kardashian -custody                                 |
| `SCOTUS_DOCTRINE`    | SCOTUS\_FEDERALISM precision >75% & volume < threshold | ("major question doctrine" OR "nondelegation doctrine" OR "commerce clause") (decision OR ruling OR case) lang\:en |
| `EXEC_PWR_ARTICLEII` | EXEC cluster < 20/day                                  | ("article ii" OR "article 2") (executive OR presidential) (power OR authority OR overreach OR limits) lang\:en     |

---

## 12. Why This Is Tighter / Better

| Your Concern                                          | Prior Version Issue                             | This Version Improvement                                |
| ----------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------- |
| “National Divorce (not normal divorce)”               | Prior divorce rules captured family-law chatter | Explicit national/secession lexemes + strong negatives  |
| Federalism nuance                                     | Earlier rules generic & sports noise risk       | Doctrine & enumerated powers anchors + sports negatives |
| Libertarianism breadth                                | Not previously covered                          | Dedicated cluster with spam filter terms                |
| Civil War dependency                                  | Previously risked gaming noise                  | Requires US context + scenario verbs + gaming negatives |
| Supreme Court rulings                                 | Only lightly touched                            | Doctrine + decision/opinion lexeme AND gating           |
| Executive orders                                      | Not fully separated                             | Distinct cluster w/ overreach / separation semantics    |
| Decentralization (interstate compacts, nullification) | Minimal                                         | Targeted rare phrase capture (high precision)           |

---

