Below is a **Web‑UI–only master plan**: tech stack, architectural patterns, components, data contracts, UX flows, and—critically—how the UI helps *preserve scarce Twitter/X read quota (10K / month)*, manage transcript ingestion, draft review, approval/edit, and scheduling. I omit broader backend internals unless directly affecting UI decisions.

---

## 1. Web UI Tech Stack (Opinionated)

| Concern                         | Choice                                                                                                    | Rationale (UI‑specific)                                                                  |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Framework                       | **Next.js 14 App Router + TypeScript**                                                                    | Hybrid SSR + streaming, good DX, fast data hydration for dashboard metrics               |
| Styling                         | **TailwindCSS + shadcn/ui (Radix primitives)**                                                            | Rapid iteration + accessible base + consistent design tokens                             |
| State (Server Data)             | **TanStack Query**                                                                                        | Fine‑grained cache control, request de‑dup, pagination & infinite scroll for tweet lists |
| Local (Ephemeral) State         | **Zustand**                                                                                               | Lightweight for panel toggles, unsaved edits, multi‑select                               |
| Real‑time                       | **SSE** (EventSource) (upgrade path to WS)                                                                | One-way push is simpler; low overhead for “tweet status changed” events                  |
| Forms                           | **React Hook Form + Zod**                                                                                 | High‑performance validation, schema reuse                                                |
| Text Editing                    | **Plain textarea + inline AI assist button** (Phase 1) → optional Rich Markdown Editor (TipTap) (Phase 2) | Start minimal, scale later                                                               |
| Diff/Version View               | **react-diff-viewer** (or custom inline word diff)                                                        | Fast comprehension of edits vs model draft                                               |
| Charts                          | **Recharts**                                                                                              | Light, declarative for moderation KPIs                                                   |
| Theming                         | **CSS variables + Tailwind themes (dark/light + high contrast)**                                          | Consistent brand styling & accessibility                                                 |
| Accessibility Tooling           | **Radix primitives + axe-core in CI**                                                                     | Ensures keyboard + screenreader support                                                  |
| Internationalization (optional) | **next-intl**                                                                                             | Prepared for future expansion                                                            |
| Error Tracking                  | **Sentry Browser SDK**                                                                                    | Production error triage                                                                  |
| Performance Profiling           | **Web Vitals + custom metrics**                                                                           | Monitor perceived latency, SSR/CSR splits                                                |

---

## 2. Information Architecture (Operator Mental Model)

Top‑level navigation:

1. **Inbox (Tweet Feed)** – stream / queue of candidate tweets (filter + sort)
2. **Review** – drafts awaiting approval
3. **Scheduled / Posted** – outgoing pipeline states
4. **Episodes** – transcript ingestion + summary & keyword assets
5. **Keywords / Rules** – keyword sets & relevance thresholds (read‑only if not admin)
6. **Prompts** – (optional) view active prompt templates and versions
7. **Analytics** – approval rates, read quota usage, model latency
8. **Audit** – compliance log
9. **Settings** – credentials masked, user roles, UI preferences

Breadcrumbs + persistent top bar with: remaining monthly *Read Budget* meter, notifications (toast + panel), quick search.

---

## 3. Read‑Quota Preservation Strategy (10K Monthly)

**Goal:** Minimize X API calls triggered *from* UI interactions.

### 3.1 Data Acquisition Strategy (UI-visible)

* **Server Aggregation Layer:** UI never calls X directly. All tweets in UI come from internal DB snapshot.
* **Batch Fetching:** Backend ingests tweets (stream rules + periodic search) and stores *lean proxy objects* (id, author, short text, timestamps, lightweight metrics). UI consumes only DB cached rows.

### 3.2 UI Constraints / Patterns

| Technique                                                                               | Why it Saves Reads                                                                                                                                    |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cursor-based pagination** (no infinite “auto-drain”)                                  | Prevent uncontrolled scrolling pulling large pages                                                                                                    |
| **Progressive Disclosure** (collapsed “thread” until expanded)                          | Thread expansion triggers *one* internal backend call; backend resolves thread from cache first; only if full context absent will it spend a new read |
| **Client-side Debounced Filtering** (works on cached page subset first)                 | Avoid repeated server round trips that could provoke backend to refresh remote data                                                                   |
| **Optimistic Prefetch Avoidance**                                                       | Do **not** prefetch next page of tweets automatically unless operator scroll passes 70% of list—lower idle waste                                      |
| **Staleness Banners**: “Data 3m old – Refresh (cost: \~N reads)”                        | Make cost explicit; operator chooses manual refresh                                                                                                   |
| **Quota Meter Component** (global)                                                      | Shows: *Used / Remaining / Predicted burn rate / Days left* + color states; influences operator behavior                                              |
| **Prioritized Refresh Buttons**: “Refresh only *Unclassified* tweets” vs global refresh | Narrower fetch reduces remote calls                                                                                                                   |

### 3.3 Quota Meter UI Data Points

* *Reads Remaining* (cached hourly)
* *Avg Daily Consumption*
* *Projected Exhaust Date*
* *Last Full Sync* timestamp
* *Top Source of Reads* (stream vs search percentage breakdown)
  Displayed as a tiny donut + textual line; clicking opens a modal with sparklines (Recharts) for daily consumption.

### 3.4 Avoiding Hidden Pitfalls

* **No live auto-refresh of counts** every few seconds (polling cost). Real-time events (SSE) update statuses without new reads.
* **Thread Expand Workflow:** If operator opens more than `X` threads quickly, warn: “Opening many threads may trigger additional read usage — continue?”

---

## 4. Core UI Flows

### 4.1 Tweet Discovery / Classification Flow

1. **Inbox List** (Virtualized list; columns: checkbox, relevance badge, author, truncated text, relevance score, status).
2. Clicking row → **Side Drawer** (not full page nav) with:

   * Full tweet text & thread context (if loaded)
   * Episode context snippet (top 2 matched chunks)
   * Model classification explanation (why relevant) – collapsible
   * Button: *Generate Draft* (if none yet) or link to existing drafts
3. SSE pushes: classification status / new draft ready → inline row pill animates.

**Why Drawer (vs Page)**: Maintains scroll position; faster triage; reduces re-fetch.

### 4.2 Draft Generation & Review

* Drafts collected under **Review** tab: columns (Tweet snippet, Draft snippet, Model name, Toxicity flag, Age).
* Selecting a draft opens **Split Panel**:

  * **Left:** Original tweet + thread & context chips (keyword highlight tokens).
  * **Right:** Editor pane with:

    * Current draft (editable)
    * Tabs: *AI Alternatives*, *Diff vs Orig AI*, *Prompt Metadata*
  * Top action bar: *Approve & Post Now*, *Approve & Schedule*, *Reject*, *Regenerate*
  * Footers: token count, style score, duplication warning.

**Editing UX Enhancements**

| Feature              | Details                                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| Inline AI Assist     | Button “Rewrite shorter / Add citation / Make friendlier” (calls backend; returns variant in Alternatives tab) |
| Snippet Chips        | Insert dynamic macros (e.g., `{episode_tag}`, `{short_link}`) via dropdown                                     |
| Real-time Validation | 280 char limit; color-coded count; show soft guideline warnings (over 220 chars = amber)                       |
| Diff Toggle          | Switch to side-by-side or inline word diff after any manual edit                                               |

### 4.3 Approval & Scheduling

* **Approve & Post**: modal confirm (shows final char count + preview).
* **Approve & Schedule**: opens scheduler popover (smart suggestions: “Next engagement window (in 17m)”, “Top of next hour”).
* After action, row animates out (or greyed with status). SSE event updates global counts.

### 4.4 Transcript Ingestion (Episodes Page)

1. **Episodes List**: episodes with status badges (No transcript / Processing / Summarized / Keywords Ready).
2. **Upload Modal**:

   * Drag & drop .txt / .vtt / .srt / raw audio (if audio, inform cost/time; actual heavy processing backend).
   * UI validates size & format locally before submit.
3. **Processing Progress Panel** (optimistic):

   * Steps: *Upload → Chunking → Embedding → Summary → Keywords*
   * Each step row shows spinner → checkmark. SSE events update; no polling.
4. Post-complete state displays:

   * Summary (collapsible)
   * Keyword clouds (weighted chips; copy button)
   * “Regenerate Summary” (with style options: concise / promotional / technical)

### 4.5 Keyword / Rule Management

* Keyword sets displayed as tokens with frequency usage (how often matched in last 7 days).
* Toggle chips ON/OFF influences streaming filter suggestions (but real commit requires admin Save).
* *Simulation Panel*: user enters example tweet → UI shows predicted relevance classification & which keywords triggered (no new read usage).

### 4.6 Prompt Template Viewer

* Read-only table (Version, Active flag, Approval Rate, Avg Edits Per Draft).
* Selecting version opens side panel showing system prompt + user template with syntax‑highlighted variable placeholders.

### 4.7 Analytics / Quota

* Cards: Approval Rate, Median Edit Distance, Draft Turnaround Time, Read Budget (interactive).
* Daily consumption chart uses cached aggregated metrics—**No live remote X fetch**.

### 4.8 Audit Timeline

* Infinite scroll vertical timeline with grouped date headers.
* Each event: icon + verb phrase (“Wyatt approved Draft #142 (edited 17 chars)”).
* Hover reveals JSON diff (pretty minimal; collapsed by default).

---

## 5. Component Library & Reusability

| Component         | Purpose                                                          | Notes                                                     |
| ----------------- | ---------------------------------------------------------------- | --------------------------------------------------------- |
| `QuotaMeter`      | Show remaining reads & predictions                               | Accepts props: used, total, avgDaily, projectedExhaustISO |
| `TweetRow`        | Row in virtualized tweet list                                    | Pure presentational; memoized                             |
| `StatusBadge`     | Unified status styling (relevant, borderline, skipped, drafted…) | Color tokens in CSS vars                                  |
| `Drawer`          | Right-side overlay for details                                   | Accessible focus trap                                     |
| `DiffEditor`      | Compare model vs edited reply                                    | Accepts baseline + current                                |
| `ProgressStepper` | Transcript ingestion visualization                               | Step objects array                                        |
| `KeywordChips`    | Weighted keywords view                                           | Optionally interactive toggle                             |
| `RealtimeToast`   | Surface SSE events (“Draft ready”)                               | Debounce identical events                                 |
| `SchedulePopover` | Date/time quick pick + presets                                   | Pre-populates with “+15m, +1h, Next 9am”                  |
| `SimulationPanel` | Keyword/classifier simulation                                    | Local form; hits internal classifier endpoint only        |

---

## 6. Data Fetching & Caching Patterns

| Resource            | Fetch Mode                                                                    | Cache Strategy                                                       |
| ------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Tweet List Page     | GET `/api/tweets?status=...&cursor=` (server component + client augmentation) | TanStack infinite query; `staleTime: 2m`; no refetch on window focus |
| Drafts              | GET `/api/drafts?status=pending`                                              | `staleTime: 30s`; SSE invalidation on new drafts                     |
| Single Tweet Detail | Fetched on drawer open                                                        | `staleTime: 5m`; keep previous data for smooth transitions           |
| Transcript Steps    | SSE updates; fallback GET `/api/episodes/{id}/status` on mount                | No polling                                                           |
| Quota Meter         | GET `/api/quota` every 10m or SSE event type `quota_update`                   | Manual refresh button (“Refresh now”)                                |
| Analytics           | Static generation every 15m (ISR)                                             | Revalidate on manual “Refresh KPIs”                                  |

**SSE Invalidation Flow:**
Backend publishes event of shape:

```json
{ "type":"tweet_status",
  "tweetId":"123",
  "newStatus":"draft_ready",
  "draftId":"456" }
```

Client event handler:

* Update normalized store (Zustand) for that tweet.
* Invalidate TanStack query key `['drafts','pending']` only if status moved into pending bucket.
* Show toast.

No blanket `refetch()` to avoid extra reads indirectly triggering backend sync logic.

---

## 7. Editing & Version Control UX

* Each save (manual or approve) creates a *version node* (UI shows a vertical mini version list with timestamps).
* Selecting older version loads diff; “Restore” button clones it as new *working copy* (does **not** delete history).
* Auto-save local draft changes every 5s (client only) → if user navigates away, toast: “Unsaved local edits restored” when returning (pull from localStorage keyed by `draftId:hash`).
* On Approve, localStorage entry purged.

---

## 8. Performance & Perceived Speed

| Tactic                      | Application                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| Virtualized Lists           | Tweet inbox (react-virtuoso) prevents slow scroll with thousands of rows                              |
| Skeleton Placeholders       | Drawer opening, editor loading                                                                        |
| Streaming Server Components | First paint includes top 20 tweets & quota meter concurrently                                         |
| Concurrent “Side Prefetch”  | Hover on tweet row prefetches detail (but *only* if idle & < 5 prefetches queued)                     |
| Code Splitting              | Heavy analytics & diff libs loaded only for corresponding routes                                      |
| CPU Offload                 | Embedding highlighting (keyword tag coloring) done on server; client receives spans already annotated |

---

## 9. Accessibility / UX Quality

| Concern              | Implementation                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| Keyboard Workflow    | `j/k` navigate tweet list, `o` open drawer, `a` approve, `r` reject (with confirm)                |
| Focus Management     | When drawer opens, focus first actionable button; on close return focus to previously focused row |
| Color Contrast       | Theming enforces WCAG AA; quota meter warns via icon+text (not color-only)                        |
| Reduced Motion       | Respect `prefers-reduced-motion` to disable transition animations                                 |
| Screen-reader labels | Each status badge has `aria-label="Status: Awaiting Review"`                                      |

---

## 10. Security & Safety (UI View)

* Edit actions use **Signed Server Actions** (or POST with CSRF token) — prevents replay.
* No secrets exposed: X API key never accessible client-side.
* Rate/Quota figures sanitized (no raw header leakage).
* All destructive actions (Reject, Regenerate discarding edits) require confirm or undo (5s toast with “Undo”).
* Inline content moderation indicator (toxicity badge) prevents accidental approval (requires double-confirm if flagged).

---

## 11. Design System & Visual Style

| Element            | Style Direction                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| Typography         | Inter / JetBrains Mono for code blocks (prompts)                                                             |
| Color Tokens       | `--color-accent` (brand), semantic statuses (info, success, warning, danger) using scales (e.g., accent-500) |
| Density Modes      | Default “Comfortable”; toggle for “Compact” (reduced padding in row cells to fit more tweets)                |
| Iconography        | Lucide icons; consistent 18–20px                                                                             |
| Micro‑interactions | Subtle scale/fade on row status change; progress step transitions for ingestion                              |

---

## 12. Minimal Data Contracts (Front-End Expectations)

**Tweet (list)**

```ts
interface TweetListItem {
  id: string;
  authorHandle: string;
  textPreview: string;
  createdAt: string;
  relevanceScore?: number;
  status: 'unclassified'|'skipped'|'relevant'|'drafted'|'posted';
  hasDraft: boolean;
  flags?: { toxicity?: boolean; duplicate?: boolean };
}
```

**Tweet Detail** adds:

```ts
thread: Array<{ id:string; authorHandle:string; text:string }>;
contextSnippets: Array<{ text:string; relevance:number }>;
classificationRationale?: string;
drafts: DraftSummary[];
```

**Draft Summary**

```ts
interface DraftSummary {
  id: string;
  model: string;
  createdAt: string;
  version: number;
  text: string;
  styleScore?: number;
  toxicityScore?: number;
  superseded?: boolean;
}
```

**Quota**

```ts
interface QuotaStatus {
  periodStart: string;
  periodEnd: string;
  totalAllowed: number; // 10000
  used: number;
  projectedExhaustDate?: string;
  avgDailyUsage: number;
  lastSync: string;
  sourceBreakdown: { stream:number; search:number; threadLookups:number };
}
```

---

## 13. Development Milestones (UI-Specific)

| Milestone                            | Deliverables                                         | Notes                     |
| ------------------------------------ | ---------------------------------------------------- | ------------------------- |
| M1 Scaffold                          | Nav, Auth gating, Tweet list static mock             | Establish design tokens   |
| M2 Data Fetch Core                   | Integrate real API for tweets, pagination, SSE basic | Quota meter placeholder   |
| M3 Drawer & Classification Rationale | Side drawer, context display                         | Interaction metrics       |
| M4 Draft Review Panel                | Editor + approve/reject + diff                       | Local autosave            |
| M5 Transcript Page                   | Upload flow + progress stepper via SSE               | File validation           |
| M6 Keywords & Simulation             | Keyword toggle & classification preview              | Visual frequency chips    |
| M7 Quota & Analytics                 | Quota meter functional; daily usage chart            | Warning thresholds        |
| M8 Audit & Versioning                | Version list, diff viewer, audit timeline            | Keyboard shortcuts        |
| M9 Polishing / A11y                  | Axe pass, high contrast theme, perf budget           | Lighthouse ≥ 90           |
| M10 Enhancements                     | Scheduling UI, AI alternative rewrites               | User feedback integration |

---

## 14. UX Risk Mitigations

| Risk                               | Mitigation                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- |
| Operator accidentally drains pages | Explicit “Load more (est. X reads)” with estimate                                              |
| Approving toxic reply              | Red outline + second confirm (“Contains flagged language—approve anyway?”)                     |
| Edit lost on navigation            | Autosave + unsaved changes modal guard                                                         |
| Confusing status transitions       | Consistent color-coded status chips + timeline panel (“Model draft ready → Edited → Approved”) |
| Quota anxiety                      | Clear projection + suggestion (“Reduce daily refresh to stay under budget”)                    |

---

## 15. Visual Style Snapshot (Descriptive)

* **Inbox:** 2‑column responsive layout. Left column 320px (filters) collapsible; right main area with tweet list. Rows: subtle zebra striping on hover; status pill left edge colored (3px border) for rapid scanning.
* **Review Panel:** Split view (50/50) adjustable drag handle; left tweet content uses tinted keyword highlights; right editor with monospace line numbers optional toggle.
* **Episodes:** Card grid; each card includes progress ring (circular segmented 5 steps) overlaying episode cover.

---

## 16. Future Enhancements (UI-Facing)

| Feature                      | Reason                                                      |
| ---------------------------- | ----------------------------------------------------------- |
| Multi-select bulk scheduling | Efficiency on backlog days                                  |
| Smart Snippets Library       | Insert pre-approved phrasing blocks                         |
| AB Prompt Dashboard          | Compare approval & edit metrics per prompt version visually |
| Offline Mode (limited)       | View cached tweets & continue editing drafts offline        |
| Mobile Compact Mode          | On-phone moderation (collapsible diff)                      |

---

### Final Summary

Use **Next.js + Tailwind + shadcn/ui + TanStack Query + SSE** to build a *quota-aware*, *operator-centric* console. The UI itself never burns reads directly; it surfaces cached data, exposes explicit *cost of refresh*, and uses event-driven updates to prevent poll churn. A disciplined component set (drawer for context, split panel for drafting, quotas surfaced constantly) enforces clarity and speed. Structured data contracts & selective invalidation keep the experience responsive without quota waste.

---

If you want next: wireframe sketches (described), component prop definitions in more detail, or actual code scaffold (folder structure + sample query hook). Just say which.
