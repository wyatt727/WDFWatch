# Product‑Requirements Document (PRD)

**Product:** WDF Podcast Social‑Engagement Pipeline
**Doc Owner:** Wobbz
**Revision:** 2025‑06‑28

---

## 1. Purpose & Background

The War‑Divorce‑Federalism (WDF) podcast drives lively political discussion. Currently, the team manually finds relevant tweets, crafts replies, and moderates tone—slow, inconsistent and hard to scale.
The **pipeline** automates discovery, classification, and response while preserving human oversight via a moderation TUI.

> *Goal:* Transform social‑engagement from ad‑hoc to **continuous, data‑driven, and low‑latency**, freeing editors to focus on high‑value interaction.

---

## 2. Objectives & Success Metrics

| Objective                 | KPI                                         | Target (90‑day post‑launch)  |
| ------------------------- | ------------------------------------------- | ---------------------------- |
| Boost relevant engagement | Avg. *meaningful* replies per episode       | **↑ 5×** (baseline ≈ 4 → 20) |
| Reduce response latency   | Median time: transcript → first tweet reply | **≤ 60 min**                 |
| Lower manual workload     | Moderator time per episode                  | **≤ 20 min**                 |
| Stability                 | Failed flow runs / month                    | **< 2** (with auto‑retry)    |

---

## 3. Personas

* **Podcast Editor (Sarah)** – uploads transcripts, wants same‑day buzz. Limited coding skills.
* **Moderator (Alex)** – approves/edits replies, values fast UI and audit trails.
* **DevOps Engineer (Priya)** – maintains infra; needs clear logging and metrics.
* **End‑User (Twitter Follower)** – sees quick, insightful replies that feel human and on‑brand.

---

## 4. User Stories

1. **As Sarah**, when I drop *latest.txt* into the folder, the system should summarise the episode and start outreach without further clicks.
2. **As Alex**, I can triage generated replies in a keyboard‑friendly interface and publish them in bulk.
3. **As Priya**, I receive alerts if any stage fails repeatedly or latency exceeds SLA.
4. **As a follower**, I get timely, context‑rich replies that invite discussion and link back to the show.

---

## 5. Functional Requirements

### 5.1 Transcript Ingestion

* Detect new/updated `transcripts/latest.txt` via file‑watcher.
* Attach SHA‑256 run‑id for provenance.

### 5.2 Episode Summarisation

* Use Gemini‑Pro to output `summary.json` with `{summary, keywords}`.
* Retry (exp‑back‑off × 5) on 5xx/timeout.

### 5.3 Tweet Discovery

* Query Twitter for each keyword (mock mode in dev).
* Persist raw tweets to `tweets.json` (≤ 100 per keyword).

### 5.4 Few‑Shot Generation

* Generate **20** balanced examples via Gemma‑3n, store in `fewshots.json`.

### 5.5 Tweet Classification

* Classify all scraped tweets as `RELEVANT` vs `SKIP` using 3n model + above few‑shots.
* Output `classified.json`.

### 5.6 Reply Generation

* Batch DeepSeek prompt with all relevant tweets; produce `replies.json` containing candidate responses.

### 5.7 Moderation Interface

* Rich‑TUI lists each tweet + proposed reply.
* Moderator can **approve / edit / reject**; edits open in `$EDITOR`.
* Audit CSV created per action.

### 5.8 Publishing

* Approved replies are posted via Twitter v2 API.
* Mock mode writes to `published.json` instead.

### 5.9 Observability

* Emit structured logs (structlog) + Prometheus metrics (`*_total`, `latency_seconds`).
* Prefect UI shows DAG status and retries.

---

## 6. Non‑Functional Requirements

| Category            | Requirement                                                  |
| ------------------- | ------------------------------------------------------------ |
| **Performance**     | End‑to‑end < 60 min for 30‑minute transcript on 8‑core host. |
| **Reliability**     | Auto‑retry with exponential back‑off; idempotent stages.     |
| **Scalability**     | Able to process 3 episodes/day without pipeline tuning.      |
| **Maintainability** | 100 % tasks import‑safe, `ruff`/`mypy` clean; CI passes.     |
| **Security**        | (Future) OAuth secrets via HashiCorp Vault.                  |
| **Compliance**      | Logs redact PII; GDPR deletion hook available.               |

---

## 7. Out of Scope (v1)

* Multi‑language transcript support.
* Sentiment analysis for follow‑up thread tone.
* Auto‑image / meme generation.
* Real‑time streaming replies (focus on batch first).

---

## 8. Milestones & Timeline

| Date       | Milestone                                       |
| ---------- | ----------------------------------------------- |
| **Jul 08** | Repo bootstrap (Poetry + docker‑compose)        |
| **Jul 22** | Summarise & scrape tasks complete w/ unit tests |
| **Aug 05** | Classification + DeepSeek reply gen done        |
| **Aug 19** | Moderation TUI + publishing integrated          |
| **Aug 26** | Load‑test, SLA dashboards, playbook finalised   |
| **Sep 02** | GA launch (mock‑off, real Twitter creds)        |

---

## 9. Open Questions

1. **Twitter rate‑limits:** Do we need an allowlist of keywords to throttle search volume?
2. **Brand voice:** Which style‑guide rules should DeepSeek follow (emoji use, hashtags, length)?
3. **Legal review:** Any constraints on auto‑replying to political content?

---

## 10. Approval

| Role             | Name         | Date       | Status |
| ---------------- | ------------ | ---------- | ------ |
| Product Owner    | Wobbz        | 2025‑06‑28 | ✅      |
| Engineering Lead | TBD          |            |        |
| Legal            | TBD          |            |        |
| Marketing        | TBD          |            |        |
