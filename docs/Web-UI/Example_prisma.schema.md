Below is an **opinionated `schema.prisma`** covering the entities we discussed, tuned for **PostgreSQL + pgvector**. It balances normalization with query ergonomics for the UI (lists, detail drawers, analytics, quota tracking). Adjust field lengths / optionality to your final pipelines.

> If you haven’t yet: enable pgvector in Postgres (`CREATE EXTENSION IF NOT EXISTS vector;`), then use Prisma’s vector support (`@db.Vector(d)`).

---

## 1. Generator & Datasource

```prisma
// schema.prisma
generator client {
  provider = "prisma-client-js"
  previewFeatures = ["postgresqlExtensions", "fullTextSearch", "vector"] // vector = pgvector
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  extensions = [
    { name = "vector" }
  ]
}
```

---

## 2. Enums

```prisma
enum UserRole {
  viewer
  editor
  approver
  admin
}

enum TweetStatus {
  unclassified
  skipped
  relevant
  drafted
  posted
}

enum DraftStatus {
  pending
  approved
  rejected
  superseded
}

enum ReviewDecision {
  approved
  rejected
  edited
}

enum ModelRunType {
  EPISODE_SUMMARY
  EPISODE_KEYWORDS
  TWEET_CLASSIFY
  DRAFT_REPLY
  STYLE_PASS
  SAFETY_CHECK
  EMBEDDING
}

enum AuditAction {
  CREATE
  UPDATE
  DELETE
  APPROVE
  REJECT
  POST
  SCHEDULE
  INGEST_START
  INGEST_STEP
  INGEST_COMPLETE
  LOGIN
}

enum EpisodeStepStatus {
  pending
  running
  success
  failed
}
```

---

## 3. Models

### 3.1 User

```prisma
model User {
  id          String    @id @default(cuid())
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  authProviderId String @unique
  displayName String
  role        UserRole  @default(viewer)

  draftsApproved DraftReply[] @relation("DraftApprovedBy")
  repliesReviews ReplyReview[]
  auditEvents    AuditEvent[]
}
```

### 3.2 PodcastEpisode

```prisma
model PodcastEpisode {
  id            String    @id @default(cuid())
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt

  title         String
  publishedAt   DateTime?
  createdById   String?
  createdBy     User?     @relation(fields: [createdById], references: [id])

  rawTranscript   String?   // optional raw text (could be large)
  transcriptUrl   String?   // external storage reference

  summaryText     String?
  keywords        Json?     // { list: string[], meta: {...} }
  summaryEmbedding Vector?  @db.Vector(1536) // or dimension you use

  // ingestion progress steps
  steps EpisodeIngestionStep[]

  tweets  Tweet[]
  // fast lookup by publishedAt for ordering
  @@index([publishedAt])
}
```

### 3.3 EpisodeIngestionStep

```prisma
model EpisodeIngestionStep {
  id          String             @id @default(cuid())
  episodeId   String
  episode     PodcastEpisode     @relation(fields: [episodeId], references: [id], onDelete: Cascade)
  name        String             // 'chunking' | 'embedding' | 'summary' | 'keywords'
  status      EpisodeStepStatus  @default(pending)
  startedAt   DateTime?
  finishedAt  DateTime?
  error       String?

  @@index([episodeId, name])
}
```

### 3.4 Tweet

```prisma
model Tweet {
  id            String      @id @default(cuid())
  createdAt     DateTime    @default(now())
  updatedAt     DateTime    @updatedAt

  twitterId     String      @unique
  authorHandle  String
  fullText      String
  textPreview   String      // pre-computed  (first N chars)
  postedAt      DateTime?   // when original tweet was created on X
  status        TweetStatus @default(unclassified)

  relevanceScore  Float?      // classifier probability
  flags           Json?       // { toxicity: bool, duplicate: bool, ... }

  embedding       Vector?     @db.Vector(768) // adapt dimension
  // thread association (parent tweet id for replies)
  inReplyToId     String?
  inReplyTo       Tweet?      @relation("ThreadParent", fields: [inReplyToId], references: [id])
  threadChildren  Tweet[]     @relation("ThreadParent")

  episodeId       String?     // optional link to most relevant episode
  episode         PodcastEpisode? @relation(fields: [episodeId], references: [id])

  drafts          DraftReply[]
  scheduledReplies ScheduledReply[]

  // quick filters
  @@index([status])
  @@index([episodeId])
  @@index([relevanceScore])
  @@index([inReplyToId])
  @@fulltext([fullText])
}
```

### 3.5 DraftReply

```prisma
model DraftReply {
  id          String      @id @default(cuid())
  createdAt   DateTime    @default(now())
  updatedAt   DateTime    @updatedAt

  tweetId     String
  tweet       Tweet       @relation(fields: [tweetId], references: [id], onDelete: Cascade)

  modelName   String
  promptVersion String
  version     Int         // increment per tweet (1..n)
  text        String
  status      DraftStatus @default(pending)
  styleScore  Float?
  toxicityScore Float?
  supersededById String?
  supersededBy   DraftReply? @relation("DraftSupersession", fields: [supersededById], references: [id])
  supersededChain DraftReply[] @relation("DraftSupersession")

  approvedById String?
  approvedBy   User?       @relation("DraftApprovedBy", fields: [approvedById], references: [id])

  replyReview  ReplyReview?
  scheduledReply ScheduledReply?

  // metrics
  tokensIn   Int?
  tokensOut  Int?
  costEstimateMicros Int?

  @@index([tweetId, status])
}
```

### 3.6 ReplyReview

```prisma
model ReplyReview {
  id            String         @id @default(cuid())
  createdAt     DateTime       @default(now())

  draftId       String         @unique
  draft         DraftReply     @relation(fields: [draftId], references: [id], onDelete: Cascade)

  reviewerId    String
  reviewer      User           @relation(fields: [reviewerId], references: [id])

  decision      ReviewDecision
  reason        String?
  editedText    String?        // If user edited before approval/rejection
  editDistance  Int?           // Precomputed diff char count
}
```

### 3.7 ScheduledReply

```prisma
model ScheduledReply {
  id           String     @id @default(cuid())
  createdAt    DateTime   @default(now())
  updatedAt    DateTime   @updatedAt

  tweetId      String
  tweet        Tweet      @relation(fields: [tweetId], references: [id], onDelete: Cascade)

  draftId      String?    @unique
  draft        DraftReply? @relation(fields: [draftId], references: [id])

  finalText    String
  scheduledFor DateTime?
  postedAt     DateTime?
  xResponseId  String?    @unique
  error        Json?      // { message, code, attempts }

  @@index([scheduledFor])
  @@index([postedAt])
}
```

### 3.8 ModelRunLog

```prisma
model ModelRunLog {
  id           String       @id @default(cuid())
  createdAt    DateTime     @default(now())
  runType      ModelRunType
  inputRef     String       // e.g. tweetId or episodeId
  model        String
  latencyMs    Int?
  tokensIn     Int?
  tokensOut    Int?
  costMicros   Int?
  success      Boolean      @default(true)
  error        String?
  meta         Json?
  userId       String?      // If triggered manually
  user         User?        @relation(fields: [userId], references: [id])

  @@index([runType, createdAt])
  @@index([inputRef])
}
```

### 3.9 AuditEvent

```prisma
model AuditEvent {
  id         String      @id @default(cuid())
  createdAt  DateTime    @default(now())
  userId     String?
  user       User?       @relation(fields: [userId], references: [id])
  action     AuditAction
  entityType String
  entityId   String
  diff       Json?       // { before: {}, after: {} } or patch ops
  ipAddress  String?

  @@index([entityType, entityId])
  @@index([action])
  @@index([createdAt])
}
```

### 3.10 PromptVersion (optional but useful)

```prisma
model PromptVersion {
  id           String     @id @default(cuid())
  createdAt    DateTime   @default(now())
  label        String     @unique // e.g. "reply_v1"
  kind         String     // 'reply' | 'summary'
  systemPrompt String
  userTemplate String
  active       Boolean    @default(false)
  notes        String?
  // metrics (denormalized aggregates updated periodically)
  draftsCount        Int? @default(0)
  approvalsCount     Int? @default(0)
  avgEditDistance    Float?
  approvalRateCached Float?

  @@index([kind, active])
}
```

### 3.11 QuotaUsage (tracks read budget daily)

```prisma
model QuotaUsage {
  id        String   @id @default(cuid())
  date      DateTime @unique // truncated to day (UTC or chosen zone)
  totalReads Int     @default(0)
  streamReads Int    @default(0)
  searchReads Int    @default(0)
  threadLookups Int  @default(0)
  notes     String?
}
```

### 3.12 KeywordHit (optional analytics granularity)

```prisma
model KeywordHit {
  id        String   @id @default(cuid())
  tweetId   String
  tweet     Tweet    @relation(fields: [tweetId], references: [id], onDelete: Cascade)
  keyword   String
  weight    Float?   // relevancy or tf-idf
  @@index([keyword])
  @@index([tweetId])
}
```

---

## 4. Design Rationale / Query Patterns

| Need                   | Model/Field                                                             | Notes                                                 |
| ---------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------- |
| Inbox list performance | `Tweet` narrow projection & indexes on `status`, `relevanceScore`       | Fast filtering & scrolling                            |
| Thread expansion       | Self-relation `inReplyToId`                                             | Query thread via recursive fetch or join              |
| Draft version chain    | `DraftReply.version` + `supersededById`                                 | Retrieve chronological chain & compute current head   |
| Approval analytics     | `DraftReply.status`, `ReplyReview.decision`, `PromptVersion` aggregates | Precompute daily job updates `PromptVersion` metrics  |
| Quota meter            | `QuotaUsage`                                                            | Summation over current cycle for projected exhaustion |
| Episode progress UI    | `EpisodeIngestionStep`                                                  | Step-by-step status & error messages                  |
| Model cost tracking    | `ModelRunLog.costMicros`                                                | Aggregate by runType & model                          |
| Audit diff             | `AuditEvent.diff` JSON                                                  | Avoid heavy join; elastic for various entity shapes   |
| Keyword simulation     | `KeywordHit` optional for historical analysis                           | On ingest classification pipeline                     |

---

## 5. Common Derived / Application-Level Logic (Not Prisma)

* **Tweet.nextStatus**: Derive based on presence of *approved/scheduled* replies (not stored).
* **Edit Distance**: Compute when saving `ReplyReview` if `editedText` differs.
* **Approval Rate per PromptVersion**: Batch job aggregates and updates `PromptVersion`.
* **Remaining Read Quota**: `10000 - SUM(QuotaUsage.totalReads WHERE date in current_period)`.

---

## 6. Suggested Indices Beyond Defaults

Add after seeing actual query shapes:

```prisma
@@index([status, createdAt])           // On Tweet if sorting by newest in status
@@index([episodeId, relevanceScore])   // Ranking tweets per episode
@@index([modelName, createdAt])        // On DraftReply for model performance histograms
@@index([promptVersion, status])       // On DraftReply for A/B metrics
```

(Place inside their respective model blocks.)

---

## 7. Migrations & pgvector Notes

* If changing embedding dimension later you need a new column (can't alter dimension in-place).
* For large transcripts keep them in object storage; `rawTranscript` may be omitted or truncated.

---

## 8. Seed Ordering

1. Users
2. PromptVersion (mark one active)
3. PodcastEpisode (with steps `pending`)
4. Tweets (some with statuses)
5. DraftReply versions
6. ReplyReview (link to draft)
7. QuotaUsage sample rows

---

## 9. Minimal Example Query Snippets (TS)

```ts
// Get pending drafts + tweet preview
prisma.draftReply.findMany({
  where: { status: 'pending' },
  include: {
    tweet: { select: { id: true, textPreview: true, authorHandle: true } }
  },
  orderBy: { createdAt: 'asc' },
  take: 30
});

// Latest episode ingestion status w/ steps
prisma.podcastEpisode.findUnique({
  where: { id: episodeId },
  include: { steps: { orderBy: { createdAt: 'asc' } } }
});
```

---

## 10. Trimming for MVP

Can defer initially:

* `KeywordHit`
* `PromptVersion` (start with a config file; add DB later)
* `ModelRunLog` (log to JSON store first)
* `QuotaUsage` (start as single row counters; expand to daily table later)

---
