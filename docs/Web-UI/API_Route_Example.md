Below are **representative Next.js (App Router) API route implementations** for your UI. They assume:

* You have a *server-side* data layer (e.g., Prisma or SQL helper).
* The UI **never** calls X directly—only these routes hitting your DB/cache.
* Cursor‑based pagination + **read‑quota safety** (no unintended upstream sync).
* Consistent JSON envelope + error handling.
* SSE event stream for real‑time updates.

I’ll show:

1. **tweets GET (paginated list)**
2. **tweet detail GET**
3. **drafts pending GET**
4. **approve draft POST** (with edit)
5. **quota GET**
6. **episode upload POST** (kick off processing) & status GET
7. **classification simulation POST**
8. **SSE events route**
9. Shared utilities (DB, zod schemas, auth, error helper)

> **Note:** Code is intentionally “trimmed but real”—slot in your ORM calls. Replace `db` pseudo-functions with actual Prisma / SQL.

---

## 0. Folder Layout Recap

```
app/
  api/
    tweets/route.ts
    tweets/[id]/route.ts
    drafts/route.ts
    drafts/[id]/approve/route.ts
    quota/route.ts
    episodes/route.ts
    episodes/[id]/status/route.ts
    classify/simulate/route.ts
    events/route.ts
lib/
  db.ts
  auth.ts
  errors.ts
  schemas.ts
  sse.ts
```

---

## 1. `app/api/tweets/route.ts` (GET list + optional status filter + cursor)

```ts
// app/api/tweets/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { db } from '@/lib/db';
import { ApiError, errorResponse } from '@/lib/errors';
import { z } from 'zod';

const QuerySchema = z.object({
  status: z.string().optional(),         // pipe-separated statuses
  limit: z.string().transform(Number).optional(),
  cursor: z.string().optional()
});

export async function GET(req: NextRequest) {
  try {
    const user = await requireUser(req);
    const { searchParams } = new URL(req.url);
    const parsed = QuerySchema.parse(Object.fromEntries(searchParams.entries()));
    const limit = Math.min(Math.max(parsed.limit || 30, 1), 100);

    const statuses = parsed.status
      ? parsed.status.split('|').filter(Boolean)
      : undefined;

    // DB query (projection for list)
    const { items, nextCursor } = await db.tweets.list({
      statuses,
      limit,
      cursor: parsed.cursor,
      select: [
        'id','authorHandle','textPreview','createdAt',
        'relevanceScore','status','hasDraft','flags'
      ]
    });

    return NextResponse.json({ items, nextCursor });
  } catch (e) {
    return errorResponse(e);
  }
}

// (Optional) POST here could be used for bulk operations or filtered ad‑hoc simulation
```

**DB helper contract (pseudo):**

```ts
// db.tweets.list({ statuses, limit, cursor, select }) => { items: TweetListItem[]; nextCursor?: string }
```

Cursor can be opaque base64 encoding of `(createdAt,id)` composite.

---

## 2. `app/api/tweets/[id]/route.ts` (GET detail)

```ts
// app/api/tweets/[id]/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { db } from '@/lib/db';
import { ApiError, errorResponse } from '@/lib/errors';

interface Params { params: { id: string } }

export async function GET(req: NextRequest, { params }: Params) {
  try {
    await requireUser(req);
    const tweet = await db.tweets.getDetail(params.id);
    if (!tweet) throw new ApiError(404, 'Not found');
    return NextResponse.json(tweet);
  } catch (e) {
    return errorResponse(e);
  }
}
```

`db.tweets.getDetail` returns full thread, contextSnippets, rationale, drafts array.

---

## 3. `app/api/drafts/route.ts` (GET pending review)

```ts
// app/api/drafts/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { db } from '@/lib/db';
import { errorResponse } from '@/lib/errors';
import { z } from 'zod';

const DraftQuery = z.object({
  status: z.enum(['pending','approved','rejected']).default('pending'),
  limit: z.string().transform(Number).optional(),
  cursor: z.string().optional()
});

export async function GET(req: NextRequest) {
  try {
    await requireUser(req);
    const { searchParams } = new URL(req.url);
    const q = DraftQuery.parse(Object.fromEntries(searchParams.entries()));
    const limit = Math.min(Math.max(q.limit || 30, 1), 100);

    const { items, nextCursor } = await db.drafts.list({
      status: q.status,
      limit,
      cursor: q.cursor
    });

    return NextResponse.json({ items, nextCursor });
  } catch (e) {
    return errorResponse(e);
  }
}
```

---

## 4. `app/api/drafts/[id]/approve/route.ts` (POST approve + optional edited text + scheduling)

```ts
// app/api/drafts/[id]/approve/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUserWithRole } from '@/lib/auth';
import { db } from '@/lib/db';
import { ApiError, errorResponse } from '@/lib/errors';
import { z } from 'zod';
import { emitEvent } from '@/lib/sse';

const BodySchema = z.object({
  editedText: z.string().min(1).max(280).optional(),
  scheduleAt: z.string().datetime().optional(), // ISO
  postNow: z.boolean().optional()
}).refine(b => !(b.postNow && b.scheduleAt), {
  message: 'Provide either postNow or scheduleAt, not both.'
});

interface Params { params: { id: string } }

export async function POST(req: NextRequest, { params }: Params) {
  try {
    const user = await requireUserWithRole(req, ['editor','approver','admin']);
    const body = await req.json();
    const data = BodySchema.parse(body);

    const draft = await db.drafts.get(params.id);
    if (!draft) throw new ApiError(404, 'Draft not found');
    if (draft.status !== 'pending') throw new ApiError(409, 'Already processed');

    const finalText = data.editedText?.trim() || draft.text;

    // persist approval + (optional) edited version & schedule
    const result = await db.drafts.approve({
      draftId: draft.id,
      text: finalText,
      approverId: user.id,
      scheduleAt: data.postNow ? null : data.scheduleAt || null,
      postNow: !!data.postNow
    });

    // Emit SSE to update tweet row + quota if posting now might affect counts later
    emitEvent({
      type: 'tweet_status',
      tweetId: draft.tweetId,
      newStatus: result.newTweetStatus,
      draftId: draft.id
    });

    return NextResponse.json({ ok: true, scheduled: !!result.scheduledFor, scheduledFor: result.scheduledFor || null });
  } catch (e) {
    return errorResponse(e);
  }
}
```

---

## 5. `app/api/quota/route.ts` (GET read quota snapshot)

```ts
// app/api/quota/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { quotaService } from '@/lib/quota';
import { errorResponse } from '@/lib/errors';

export async function GET(req: NextRequest) {
  try {
    await requireUser(req);
    const snapshot = await quotaService.getSnapshot(); // reads from internal table / cache
    return NextResponse.json(snapshot);
  } catch (e) {
    return errorResponse(e);
  }
}
```

`quotaService.getSnapshot()` should NEVER fetch X API; it uses internal counters updated by backend ingestion tasks.

---

## 6. Episodes

### 6a. `app/api/episodes/route.ts` (POST upload metadata / transcript)

```ts
// app/api/episodes/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUserWithRole } from '@/lib/auth';
import { errorResponse, ApiError } from '@/lib/errors';
import { z } from 'zod';
import { db } from '@/lib/db';
import { enqueueEpisodeIngestion } from '@/lib/tasks';

const Body = z.object({
  title: z.string().min(1),
  transcriptText: z.string().min(50).optional(),
  transcriptUrl: z.string().url().optional()
}).refine(b => b.transcriptText || b.transcriptUrl, {
  message: 'Provide transcriptText or transcriptUrl'
});

export async function POST(req: NextRequest) {
  try {
    const user = await requireUserWithRole(req, ['editor','admin']);
    const payload = Body.parse(await req.json());

    const episode = await db.episodes.create({
      title: payload.title,
      rawTranscript: payload.transcriptText || null,
      transcriptUrl: payload.transcriptUrl || null,
      createdBy: user.id
    });

    await enqueueEpisodeIngestion(episode.id); // push job to worker
    return NextResponse.json({ id: episode.id, status: 'queued' });
  } catch (e) {
    return errorResponse(e);
  }
}
```

### 6b. `app/api/episodes/[id]/status/route.ts` (GET status)

```ts
// app/api/episodes/[id]/status/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { db } from '@/lib/db';
import { ApiError, errorResponse } from '@/lib/errors';

interface Params { params: { id: string } }

export async function GET(req: NextRequest, { params }: Params) {
  try {
    await requireUser(req);
    const ep = await db.episodes.getStatus(params.id);
    if (!ep) throw new ApiError(404, 'Not found');
    return NextResponse.json(ep); // { id, steps: [{name,status,startedAt,endedAt}], summary?, keywords? }
  } catch (e) {
    return errorResponse(e);
  }
}
```

---

## 7. Classification Simulation Route

```ts
// app/api/classify/simulate/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/lib/auth';
import { errorResponse } from '@/lib/errors';
import { z } from 'zod';
import { classifier } from '@/lib/classifier'; // internal ML call (no X read)
import { keywordEngine } from '@/lib/keywords';

const Body = z.object({
  text: z.string().min(5).max(1000)
});

export async function POST(req: NextRequest) {
  try {
    await requireUser(req);
    const { text } = Body.parse(await req.json());
    const keywords = await keywordEngine.match(text);
    const score = await classifier.predict(text); // probability
    return NextResponse.json({
      input: text,
      score,
      triggeredKeywords: keywords
    });
  } catch (e) {
    return errorResponse(e);
  }
}
```

---

## 8. SSE Events Route

```ts
// app/api/events/route.ts
import { NextRequest } from 'next/server';
import { requireUser } from '@/lib/auth';
import { getEventStream } from '@/lib/sse';

export const runtime = 'edge'; // low latency

export async function GET(req: NextRequest) {
  // Auth once; then attach user id to stream
  await requireUser(req);

  const { readable, controller, heartbeat } = getEventStream();

  // Example: send initial handshake
  controller.enqueue(encodeSse({ event: 'message', data: JSON.stringify({ type:'hello' }) }));

  // Keepalive heartbeat
  const interval = setInterval(() => {
    controller.enqueue(encodeSse({ event: 'heartbeat', data: Date.now().toString() }));
  }, 25_000);

  readable.closed.finally(() => clearInterval(interval));

  return new Response(readable, {
    headers: {
      'Content-Type':'text/event-stream',
      'Cache-Control':'no-store',
      'Connection':'keep-alive'
    }
  });
}

// Helper
function encodeSse({ event, data }: { event?: string; data: string }) {
  return new TextEncoder().encode(
    (event ? `event: ${event}\n` : '') + `data: ${data}\n\n`
  );
}
```

`getEventStream()` returns a broadcast-connected readable stream. Elsewhere, backend tasks call `broadcast({ type:'tweet_status', tweetId,... })` which enqueues SSE lines to all connected clients.

---

## 9. Shared Utilities (Sketches)

### `lib/errors.ts`

```ts
export class ApiError extends Error {
  status: number;
  meta?: any;
  constructor(status: number, message: string, meta?: any) {
    super(message);
    this.status = status;
    this.meta = meta;
  }
}

export function errorResponse(e: unknown) {
  if (e instanceof ApiError) {
    return new Response(JSON.stringify({ error: e.message, meta: e.meta }), {
      status: e.status,
      headers: { 'Content-Type':'application/json' }
    });
  }
  console.error(e);
  return new Response(JSON.stringify({ error: 'Internal Error' }), { status: 500 });
}
```

### `lib/auth.ts` (placeholder)

```ts
import { cookies } from 'next/headers';
import { ApiError } from './errors';

export async function requireUser(req: Request) {
  const session = cookies().get('session')?.value;
  if (!session) throw new ApiError(401, 'Unauthorized');
  const user = await getUserBySession(session); // implement
  if (!user) throw new ApiError(401, 'Unauthorized');
  return user;
}

export async function requireUserWithRole(req: Request, roles: string[]) {
  const user = await requireUser(req);
  if (!roles.includes(user.role)) throw new ApiError(403, 'Forbidden');
  return user;
}
```

### `lib/sse.ts` (simple broadcast bus in-memory)

```ts
type Listener = {
  controller: ReadableStreamDefaultController<Uint8Array>;
};

const listeners = new Set<Listener>();

export function getEventStream() {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      listeners.add({ controller });
    },
    cancel() {
      // find & remove
      // (Set iteration; remove matching controller)
      for (const l of listeners) {
        if (l.controller.desiredSize === null) { /* ignore */ }
      }
    }
  });

  return {
    readable: stream,
    controller: {
      enqueue: (chunk: Uint8Array) => {
        // Only for initial push to THIS stream
        // (Edge nuance: we can store its controller reference)
      }
    },
    heartbeat: () => {}
  };
}

export function emitEvent(evt: any) {
  const payload = new TextEncoder().encode(`data: ${JSON.stringify(evt)}\n\n`);
  for (const { controller } of listeners) {
    try { controller.enqueue(payload); } catch {}
  }
}
```

(You’d refine `cancel()` removal, and maybe upgrade to a redis pub/sub or serverless durable object later.)

---

## 10. Patterns & Safeguards Embedded

| Aspect                        | Implementation                                                                    |
| ----------------------------- | --------------------------------------------------------------------------------- |
| **Quota Protection**          | None of these routes fetch X; they only surface cached DB state.                  |
| **Pagination**                | Cursor-based; client controls `limit`; server enforces max 100.                   |
| **Partial Projection**        | Tweet list route selects minimal fields vs detail route full payload.             |
| **Role Separation**           | Approve endpoint checks `editor/approver/admin`.                                  |
| **Validation**                | zod schemas per route; transformed numeric limit.                                 |
| **Error Uniformity**          | `ApiError` + `errorResponse` keep consistent JSON errors.                         |
| **SSE Scalability**           | In-memory now; pluggable to Redis fan-out later.                                  |
| **Optimistic UI**             | Approval endpoint returns new status; SSE broadcast ensures other clients update. |
| **Scheduling Conflict Guard** | Refine `postNow` vs `scheduleAt` w/ zod `.refine`.                                |

---

