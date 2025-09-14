Below are **opinionated Prisma client helper utilities** organized to keep application code clean, enforce invariants (statuses, versioning, quota safety), and centralize pagination + error semantics.

Hybrid Option

You can adopt Prisma only for the UI side (Next.js) while your heavy Python pipeline does its own DB access (via SQLAlchemy) because they share the same Postgres. Just keep schema changes coordinated (Prisma migrations generate SQL you can apply universally).

**Sections**

1. File Layout
2. Shared Utilities (Prisma init, typed errors, pagination helpers, cursor codec)
3. Tweet Repository Helpers
4. Draft / Approval Workflow Helpers
5. Episode Ingestion Helpers
6. Quota / Metrics Helpers
7. Prompt Version Helpers
8. Model Run Logging Helpers
9. Audit Logging Helper
10. Transaction Patterns & Concurrency Notes
11. Optional Caching Layer (Redis) Sketch
12. Usage Examples

---

## 1. Suggested File Layout

```
lib/
  prisma/
    client.ts
    errors.ts
    pagination.ts
    cursor.ts
    tweets.ts
    drafts.ts
    episodes.ts
    quota.ts
    prompts.ts
    modelRuns.ts
    audit.ts
    tx.ts
    cache.ts
  util/
    diff.ts
```

---

## 2. Shared Utilities

### `client.ts`

```ts
// lib/prisma/client.ts
import { PrismaClient } from '@prisma/client';

declare global {
  // eslint-disable-next-line no-var
  var __PRISMA__: PrismaClient | undefined;
}

export const prisma =
  global.__PRISMA__ ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development'
      ? ['query','error','warn']
      : ['error'],
  });

if (process.env.NODE_ENV !== 'production') {
  global.__PRISMA__ = prisma;
}
```

### `errors.ts`

```ts
// lib/prisma/errors.ts
export class RepoError extends Error {
  code: string;
  meta?: any;
  constructor(code: string, message: string, meta?: any) {
    super(message);
    this.code = code;
    this.meta = meta;
  }
}

export function notFound(entity: string, meta?: any) {
  return new RepoError('NOT_FOUND', `${entity} not found`, meta);
}

export function conflict(message: string, meta?: any) {
  return new RepoError('CONFLICT', message, meta);
}

export function validation(message: string, meta?: any) {
  return new RepoError('VALIDATION', message, meta);
}
```

### `pagination.ts`

```ts
// lib/prisma/pagination.ts
export interface CursorPage<T> {
  items: T[];
  nextCursor?: string;
}

export interface ListParams {
  limit: number;
  cursor?: string;
}

export function clampLimit(n: number, min = 1, max = 100) {
  return Math.min(Math.max(n, min), max);
}
```

### `cursor.ts`

```ts
// lib/prisma/cursor.ts
// Opaque base64 cursor combining createdAt + id (or any sortable tuple)
export function encodeCursor(createdAt: Date, id: string) {
  return Buffer.from(`${createdAt.toISOString()}::${id}`).toString('base64url');
}

export function decodeCursor(cur: string) {
  const raw = Buffer.from(cur, 'base64url').toString('utf8');
  const [iso, id] = raw.split('::');
  return { createdAt: new Date(iso), id };
}
```

---

## 3. Tweet Repository Helpers (`tweets.ts`)

```ts
// lib/prisma/tweets.ts
import { prisma } from './client';
import { encodeCursor, decodeCursor } from './cursor';
import type { CursorPage } from './pagination';
import { TweetStatus } from '@prisma/client';

interface TweetListParams {
  statuses?: TweetStatus[];
  limit: number;
  cursor?: string;
  episodeId?: string;
  order?: 'desc'|'asc'; // by createdAt
  select?: (keyof ReturnType<typeof mapListItem> extends infer K ? K : never)[];
}

function mapListItem(t: any) {
  return {
    id: t.id,
    authorHandle: t.authorHandle,
    textPreview: t.textPreview,
    createdAt: t.createdAt,
    relevanceScore: t.relevanceScore,
    status: t.status,
    hasDraft: t.drafts.length > 0,
    flags: t.flags ?? undefined
  };
}

export async function listTweets(params: TweetListParams): Promise<CursorPage<ReturnType<typeof mapListItem>>> {
  const { statuses, limit, cursor, episodeId, order = 'desc' } = params;

  let cursorFilter: any = {};
  if (cursor) {
    const dec = decodeCursor(cursor);
    cursorFilter = order === 'desc'
      ? { lt: dec.createdAt }
      : { gt: dec.createdAt };
  }

  const where: any = {
    ...(statuses && statuses.length ? { status: { in: statuses } } : {}),
    ...(episodeId ? { episodeId } : {}),
    ...(cursor ? { createdAt: cursorFilter } : {})
  };

  const rows = await prisma.tweet.findMany({
    where,
    orderBy: { createdAt: order },
    take: limit + 1,
    include: {
      drafts: {
        where: { status: { in: ['pending','approved'] } },
        select: { id: true }
      }
    }
  });

  const hasMore = rows.length > limit;
  if (hasMore) rows.pop();

  const items = rows.map(mapListItem);
  const nextCursor = hasMore
    ? encodeCursor(items[items.length - 1].createdAt, items[items.length - 1].id)
    : undefined;

  return { items, nextCursor };
}

export async function getTweetDetail(id: string) {
  return prisma.tweet.findUnique({
    where: { id },
    include: {
      drafts: {
        orderBy: { createdAt: 'asc' },
        include: { replyReview: true }
      },
      threadChildren: {
        select: { id: true, authorHandle: true, fullText: true, createdAt: true }
      }
    }
  });
}

export async function updateTweetStatus(id: string, status: TweetStatus) {
  return prisma.tweet.update({
    where: { id },
    data: { status }
  });
}
```

---

## 4. Draft / Approval Helpers (`drafts.ts`)

```ts
// lib/prisma/drafts.ts
import { prisma } from './client';
import { conflict, notFound } from './errors';
import { DraftStatus, TweetStatus } from '@prisma/client';

interface CreateDraftInput {
  tweetId: string;
  modelName: string;
  promptVersion: string;
  text: string;
  styleScore?: number;
  toxicityScore?: number;
  tokensIn?: number;
  tokensOut?: number;
  costEstimateMicros?: number;
}

export async function createDraft(input: CreateDraftInput) {
  return prisma.$transaction(async tx => {
    const tweet = await tx.tweet.findUnique({ where: { tweetId: input.tweetId }, select: { id: true } });
    const t = tweet || await tx.tweet.findUnique({ where: { id: input.tweetId } }); // support internal id
    if (!t) throw notFound('Tweet');

    const currentMax = await tx.draftReply.aggregate({
      _max: { version: true },
      where: { tweetId: t.id }
    });
    const version = (currentMax._max.version ?? 0) + 1;

    const draft = await tx.draftReply.create({
      data: {
        tweetId: t.id,
        modelName: input.modelName,
        promptVersion: input.promptVersion,
        version,
        text: input.text,
        styleScore: input.styleScore,
        toxicityScore: input.toxicityScore,
        tokensIn: input.tokensIn,
        tokensOut: input.tokensOut,
        costEstimateMicros: input.costEstimateMicros
      }
    });

    // Optionally update tweet status → drafted (only if still 'relevant')
    await tx.tweet.update({
      where: { id: t.id },
      data: {
        status: TweetStatus.drafted
      }
    });

    return draft;
  });
}

interface ApproveDraftInput {
  draftId: string;
  approverId: string;
  finalText?: string;
  scheduleAt?: Date | null;
  postNow?: boolean;
}

export async function approveDraft(input: ApproveDraftInput) {
  return prisma.$transaction(async tx => {
    const draft = await tx.draftReply.findUnique({
      where: { id: input.draftId },
      include: { tweet: true }
    });
    if (!draft) throw notFound('Draft');
    if (draft.status !== DraftStatus.pending) throw conflict('Draft already processed');

    const finalText = (input.finalText || draft.text).trim();

    const updated = await tx.draftReply.update({
      where: { id: draft.id },
      data: {
        status: DraftStatus.approved,
        approvedById: input.approverId
      }
    });

    // schedule or immediate
    const scheduled = await tx.scheduledReply.create({
      data: {
        tweetId: draft.tweetId,
        draftId: draft.id,
        finalText,
        scheduledFor: input.postNow ? null : input.scheduleAt,
        // postedAt will be filled by worker if postNow
      }
    });

    await tx.tweet.update({
      where: { id: draft.tweetId },
      data: {
        status: input.postNow ? TweetStatus.posted : TweetStatus.drafted
      }
    });

    return { draft: updated, scheduled };
  });
}

export async function rejectDraft(draftId: string, reviewerId: string, reason?: string) {
  return prisma.$transaction(async tx => {
    const draft = await tx.draftReply.findUnique({ where: { id: draftId } });
    if (!draft) throw notFound('Draft');
    if (draft.status !== DraftStatus.pending) throw conflict('Draft already processed');

    const updated = await tx.draftReply.update({
      where: { id: draftId },
      data: { status: DraftStatus.rejected }
    });

    await tx.replyReview.create({
      data: {
        draftId,
        reviewerId,
        decision: 'rejected',
        reason
      }
    });

    return updated;
  });
}

export async function listDrafts(status: DraftStatus, limit: number, cursor?: string) {
  // Similar to tweets pagination; omitted for brevity
}

export async function supersedeDraft(oldDraftId: string, newDraftId: string) {
  return prisma.draftReply.update({
    where: { id: oldDraftId },
    data: { status: DraftStatus.superseded, supersededById: newDraftId }
  });
}
```

---

## 5. Episode Ingestion Helpers (`episodes.ts`)

```ts
// lib/prisma/episodes.ts
import { prisma } from './client';
import { EpisodeStepStatus } from '@prisma/client';

export async function createEpisode(opts: {
  title: string;
  rawTranscript?: string | null;
  transcriptUrl?: string | null;
  createdById?: string;
}) {
  return prisma.podcastEpisode.create({
    data: {
      title: opts.title,
      rawTranscript: opts.rawTranscript ?? null,
      transcriptUrl: opts.transcriptUrl ?? null,
      createdById: opts.createdById ?? null
    }
  });
}

export async function addIngestionSteps(episodeId: string, names: string[]) {
  await prisma.episodeIngestionStep.createMany({
    data: names.map(name => ({ episodeId, name }))
  });
}

export async function markStepRunning(episodeId: string, name: string) {
  return prisma.episodeIngestionStep.updateMany({
    where: { episodeId, name },
    data: { status: EpisodeStepStatus.running, startedAt: new Date() }
  });
}

export async function markStepFinished(episodeId: string, name: string, ok: boolean, error?: string) {
  return prisma.episodeIngestionStep.updateMany({
    where: { episodeId, name },
    data: {
      status: ok ? EpisodeStepStatus.success : EpisodeStepStatus.failed,
      finishedAt: new Date(),
      error: ok ? null : error
    }
  });
}

export async function updateEpisodeSummaryKeywords(episodeId: string, summary: string, keywords: string[], embedding?: number[]) {
  return prisma.podcastEpisode.update({
    where: { id: episodeId },
    data: {
      summaryText: summary,
      keywords: { list: keywords },
      summaryEmbedding: embedding ? embedding as any : undefined
    }
  });
}
```

---

## 6. Quota / Metrics Helpers (`quota.ts`)

```ts
// lib/prisma/quota.ts
import { prisma } from './client';
import { addDays, startOfDay } from 'date-fns';

const PERIOD_DAYS = 30;
const LIMIT = 10_000;

export async function incrementQuota(kind: 'stream'|'search'|'threadLookups', count: number) {
  const today = startOfDay(new Date());
  await prisma.quotaUsage.upsert({
    where: { date: today },
    create: {
      date: today,
      totalReads: count,
      streamReads: kind === 'stream' ? count : 0,
      searchReads: kind === 'search' ? count : 0,
      threadLookups: kind === 'threadLookups' ? count : 0
    },
    update: {
      totalReads: { increment: count },
      ...(kind === 'stream' && { streamReads: { increment: count } }),
      ...(kind === 'search' && { searchReads: { increment: count } }),
      ...(kind === 'threadLookups' && { threadLookups: { increment: count } })
    }
  });
}

export async function quotaSnapshot() {
  const cutoff = addDays(new Date(), -PERIOD_DAYS);
  const rows = await prisma.quotaUsage.findMany({
    where: { date: { gt: cutoff } },
    orderBy: { date: 'asc' }
  });

  const used = rows.reduce((a, r) => a + r.totalReads, 0);
  const avgDaily = rows.length ? used / rows.length : 0;
  const remaining = Math.max(LIMIT - used, 0);
  const projectedExhaustDate =
    avgDaily > 0
      ? new Date(Date.now() + (remaining / avgDaily) * 24 * 3600 * 1000)
      : null;

  const breakdown = rows.reduce(
    (acc, r) => {
      acc.stream += r.streamReads;
      acc.search += r.searchReads;
      acc.threadLookups += r.threadLookups;
      return acc;
    },
    { stream: 0, search: 0, threadLookups: 0 }
  );

  return {
    periodStart: cutoff.toISOString(),
    periodEnd: addDays(cutoff, PERIOD_DAYS).toISOString(),
    totalAllowed: LIMIT,
    used,
    avgDailyUsage: avgDaily,
    projectedExhaustDate: projectedExhaustDate?.toISOString() ?? null,
    sourceBreakdown: breakdown,
    lastSync: new Date().toISOString()
  };
}
```

---

## 7. Prompt Version Helpers (`prompts.ts`)

```ts
// lib/prisma/prompts.ts
import { prisma } from './client';

export async function getActivePrompt(kind: string) {
  return prisma.promptVersion.findFirst({
    where: { kind, active: true }
  });
}

export async function activatePrompt(id: string) {
  return prisma.$transaction(async tx => {
    const pv = await tx.promptVersion.findUnique({ where: { id } });
    if (!pv) throw new Error('Prompt not found');
    await tx.promptVersion.updateMany({
      where: { kind: pv.kind, active: true },
      data: { active: false }
    });
    return tx.promptVersion.update({
      where: { id },
      data: { active: true }
    });
  });
}

// Periodic metric recompute
export async function recomputePromptMetrics(promptId: string) {
  const stats = await prisma.draftReply.groupBy({
    by: ['status'],
    where: { promptVersion: (await prisma.promptVersion.findUnique({ where: { id: promptId } }))?.label },
    _count: { _all: true }
  });
  // This assumes storing label in draft.promptVersion
  const approved = stats.find(s => s.status === 'approved')?._count._all ?? 0;
  const total = stats.reduce((a, s) => a + s._count._all, 0);
  const approvalRate = total ? approved / total : 0;

  await prisma.promptVersion.update({
    where: { id: promptId },
    data: { approvalsCount: approved, draftsCount: total, approvalRateCached: approvalRate }
  });
}
```

---

## 8. Model Run Logging (`modelRuns.ts`)

```ts
// lib/prisma/modelRuns.ts
import { prisma } from './client';
import { ModelRunType } from '@prisma/client';

interface RunLog {
  runType: ModelRunType;
  inputRef: string;
  model: string;
  latencyMs?: number;
  tokensIn?: number;
  tokensOut?: number;
  costMicros?: number;
  success?: boolean;
  error?: string;
  meta?: any;
  userId?: string;
}

export async function logModelRun(entry: RunLog) {
  return prisma.modelRunLog.create({
    data: {
      ...entry,
      success: entry.success !== false
    }
  });
}
```

---

## 9. Audit Logging (`audit.ts`)

```ts
// lib/prisma/audit.ts
import { prisma } from './client';
import { AuditAction } from '@prisma/client';

interface AuditInput {
  userId?: string;
  action: AuditAction;
  entityType: string;
  entityId: string;
  diff?: any;          // structured before/after or patch
  ipAddress?: string;
}

export async function auditLog(entry: AuditInput) {
  return prisma.auditEvent.create({
    data: {
      userId: entry.userId ?? null,
      action: entry.action,
      entityType: entry.entityType,
      entityId: entry.entityId,
      diff: entry.diff ?? null,
      ipAddress: entry.ipAddress ?? null
    }
  });
}
```

---

## 10. Transaction Patterns & Concurrency Notes (`tx.ts`)

```ts
// lib/prisma/tx.ts
import { prisma } from './client';

export async function withSerializable<T>(fn: (tx: typeof prisma) => Promise<T>): Promise<T> {
  return prisma.$transaction(async tx => fn(tx), {
    isolationLevel: 'Serializable'
  });
}
```

**Use cases**: approving drafts (ensures no double‑approve race); version increment.

**Optimistic Concurrency**: Add a `revision Int @default(0)` column to frequently updated rows (e.g. Tweet) and check:

```ts
await prisma.tweet.update({
  where: { id_revision: { id, revision: expectedRevision } },
  data: { revision: { increment: 1 }, status: newStatus }
});
```

(Composite unique needed.)

---

## 11. Optional Redis Cache Layer (`cache.ts`)

```ts
// lib/prisma/cache.ts
import Redis from 'ioredis';
import { quotaSnapshot } from './quota';

const redis = process.env.REDIS_URL ? new Redis(process.env.REDIS_URL) : null;

export async function cachedQuotaSnapshot(ttlSec = 300) {
  if (!redis) return quotaSnapshot();
  const key = 'quota:snapshot:v1';
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);
  const snap = await quotaSnapshot();
  await redis.set(key, JSON.stringify(snap), 'EX', ttlSec);
  return snap;
}
```

---

## 12. Usage Examples

### List Tweets (API Route):

```ts
import { listTweets } from '@/lib/prisma/tweets';

const page = await listTweets({
  statuses: ['relevant','drafted'],
  limit: 30,
  cursor: maybeCursor
});
```

### Create Draft:

```ts
import { createDraft } from '@/lib/prisma/drafts';
const draft = await createDraft({
  tweetId,
  modelName: 'claude-3.5',
  promptVersion: 'reply_v1',
  text: modelOutput,
  styleScore: metrics.style,
  toxicityScore: metrics.tox,
  tokensIn: usage.in,
  tokensOut: usage.out,
  costEstimateMicros: usage.cost
});
```

### Approve Draft:

```ts
import { approveDraft } from '@/lib/prisma/drafts';
const { draft: approved, scheduled } = await approveDraft({
  draftId,
  approverId: user.id,
  finalText: edited,
  postNow: true
});
```

### Log Model Run:

```ts
import { logModelRun } from '@/lib/prisma/modelRuns';
await logModelRun({
  runType: 'DRAFT_REPLY',
  inputRef: tweetId,
  model: 'claude-3.5',
  latencyMs: 1420,
  tokensIn: 1200,
  tokensOut: 110,
  costMicros: 5500
});
```

### Quota Snapshot (API):

```ts
import { cachedQuotaSnapshot } from '@/lib/prisma/cache';
const snapshot = await cachedQuotaSnapshot();
```

---

## Final Notes

* Keep helpers **pure**: no HTTP concerns inside.
* Centralize **status transitions** so you can insert side-effects (emit SSE, audit) in one place later (wrap helpers or add event bus).
* Gradually introduce caching only where profiling shows DB hot spots (quotaSnapshot, analytics aggregates).
* Add unit tests per helper (mock Prisma with in-memory test DB or use `testcontainers`).

