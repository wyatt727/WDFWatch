Below is an opinionated **UI folder structure** (Next.js 14 App Router + TS) plus **sample query hooks** (TanStack Query) and an **SSE invalidation helper**. Trim / expand as you wish.

---

## 1. Directory / File Layout

```
ui/
├─ app/
│  ├─ (dashboard)/
│  │  ├─ layout.tsx
│  │  ├─ page.tsx                   # Redirect to /inbox or show overview
│  │  ├─ inbox/
│  │  │  ├─ page.tsx                # Tweet Inbox list
│  │  │  ├─ TweetInboxClient.tsx    # Client component (virtual list)
│  │  │  └─ filters/                # (Optional) co-located filter UIs
│  │  ├─ review/
│  │  │  ├─ page.tsx
│  │  │  └─ DraftReviewClient.tsx
│  │  ├─ episodes/
│  │  │  ├─ page.tsx
│  │  │  └─ EpisodeUploadClient.tsx
│  │  ├─ keywords/
│  │  │  └─ page.tsx
│  │  ├─ prompts/
│  │  │  └─ page.tsx
│  │  ├─ analytics/
│  │  │  └─ page.tsx
│  │  ├─ audit/
│  │  │  └─ page.tsx
│  │  └─ settings/
│  │     └─ page.tsx
│  ├─ api/
│  │  ├─ tweets/
│  │  │  ├─ route.ts                # POST for filtering simulation etc.
│  │  │  └─ [cursor]/route.ts       # Example alt pattern if needed
│  │  ├─ drafts/route.ts
│  │  ├─ quota/route.ts
│  │  ├─ episodes/route.ts
│  │  ├─ episodes/[id]/status/route.ts
│  │  ├─ classify/simulate/route.ts
│  │  └─ events/route.ts            # SSE endpoint (Edge runtime)
│  ├─ layout.tsx                     # App shell (nav, quota meter provider)
│  └─ globals.css
├─ components/
│  ├─ layout/
│  │  ├─ SidebarNav.tsx
│  │  ├─ TopBar.tsx
│  │  └─ QuotaMeter.tsx
│  ├─ tweets/
│  │  ├─ TweetRow.tsx
│  │  ├─ TweetListVirtual.tsx
│  │  ├─ TweetDrawer.tsx
│  │  └─ StatusBadge.tsx
│  ├─ drafts/
│  │  ├─ DraftEditor.tsx
│  │  ├─ DraftDiff.tsx
│  │  └─ SchedulePopover.tsx
│  ├─ episodes/
│  │  ├─ EpisodeCard.tsx
│  │  └─ IngestionStepper.tsx
│  ├─ keywords/
│  │  └─ KeywordChips.tsx
│  ├─ analytics/
│  │  └─ MetricCard.tsx
│  ├─ audit/
│  │  └─ AuditTimeline.tsx
│  ├─ simulation/
│  │  └─ SimulationPanel.tsx
│  ├─ realtime/
│  │  ├─ SSEProvider.tsx
│  │  └─ useSSEChannel.ts
│  ├─ forms/
│  │  └─ ControlledInput.tsx
│  └─ common/
│     ├─ LoadingSkeleton.tsx
│     ├─ EmptyState.tsx
│     ├─ ConfirmDialog.tsx
│     └─ ToastViewport.tsx
├─ hooks/
│  ├─ useTweetList.ts
│  ├─ useTweetDetail.ts
│  ├─ useDrafts.ts
│  ├─ useQuota.ts
│  ├─ useEpisodes.ts
│  ├─ useEditorAutosave.ts
│  └─ queryClient.ts                # Shared TanStack Query client
├─ lib/
│  ├─ apiClient.ts                  # fetch wrapper
│  ├─ types.ts                      # Shared TS interfaces
│  ├─ constants.ts
│  ├─ sseEvents.ts                  # Event type enums
│  └─ diff.ts                       # Optional text diff helpers
├─ store/
│  ├─ uiStore.ts                    # Zustand (panel open, filters)
│  ├─ selectionStore.ts             # Multi-select tweet ids
│  └─ realtimeStore.ts              # Normalized partial updates
├─ styles/
│  ├─ theme.css
│  └─ tokens.css
├─ utils/
│  ├─ pagination.ts
│  ├─ string.ts
│  └─ time.ts
├─ tests/
│  ├─ components/
│  ├─ hooks/
│  └─ e2e/                          # Playwright specs
└─ public/
   └─ icons/ ...
```

### Notes

* **app/(dashboard)** segment isolates authenticated dashboard from potential marketing pages later.
* **hooks/** contains data hooks (TanStack Query) separate from presentational components.
* **store/** strictly ephemeral & real-time overlay state; **server data lives in query cache**.
* **realtime/** centralizes SSE subscription so multiple hooks can dispatch invalidations.

---

## 2. Shared Types (`lib/types.ts`)

```ts
export interface TweetListItem {
  id: string;
  authorHandle: string;
  textPreview: string;
  createdAt: string;
  relevanceScore?: number;
  status: 'unclassified'|'skipped'|'relevant'|'drafted'|'posted';
  hasDraft: boolean;
  flags?: { toxicity?: boolean; duplicate?: boolean };
}

export interface TweetDetail extends TweetListItem {
  fullText: string;
  thread: Array<{ id:string; authorHandle:string; text:string }>;
  contextSnippets: Array<{ text:string; relevance:number }>;
  classificationRationale?: string;
  drafts: DraftSummary[];
}

export interface DraftSummary {
  id: string;
  model: string;
  createdAt: string;
  version: number;
  text: string;
  styleScore?: number;
  toxicityScore?: number;
  superseded?: boolean;
}

export interface QuotaStatus {
  periodStart: string;
  periodEnd: string;
  totalAllowed: number;
  used: number;
  projectedExhaustDate?: string;
  avgDailyUsage: number;
  lastSync: string;
  sourceBreakdown: { stream:number; search:number; threadLookups:number };
}
```

---

## 3. Fetch Wrapper (`lib/apiClient.ts`)

```ts
export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type':'application/json',
      ...(options.headers || {})
    },
    cache: 'no-store'
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}
```

---

## 4. Query Client (`hooks/queryClient.ts`)

```ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions:{
    queries:{
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 60_000
    }
  }
});
```

---

## 5. Sample Tweet List Hook (`hooks/useTweetList.ts`)

Supports **cursor-based pagination**, status filter, and **SSE invalidation**.

```ts
import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import type { TweetListItem } from '@/lib/types';
import { useEffect } from 'react';
import { useRealtimeStore } from '@/store/realtimeStore';

interface TweetListResponse {
  items: TweetListItem[];
  nextCursor?: string;
}

export function useTweetList(statusFilter: string) {
  const updates = useRealtimeStore(s => s.tweetStatusUpdates); // Map<id, partial>

  const query = useInfiniteQuery({
    queryKey: ['tweets', statusFilter],
    queryFn: async ({ pageParam }) => {
      const url = new URL('/api/tweets', window.location.origin);
      url.searchParams.set('status', statusFilter);
      if (pageParam) url.searchParams.set('cursor', pageParam);
      return api<TweetListResponse>(url.toString());
    },
    getNextPageParam: (last) => last.nextCursor,
    staleTime: 120_000,
    refetchOnMount: false
  });

  // Merge real-time partial updates into cached data without re-fetch
  useEffect(() => {
    if (!query.data) return;
    if (updates.size === 0) return;

    query.client.setQueryData<any>(['tweets', statusFilter], (oldData: any) => {
      if (!oldData) return oldData;
      const newPages = oldData.pages.map((page: TweetListResponse) => {
        const items = page.items.map(item => {
          const u = updates.get(item.id);
            return u ? { ...item, ...u } : item;
        });
        return { ...page, items };
      });
      return { ...oldData, pages: newPages };
    });
  }, [updates, query.data, query.client, statusFilter]);

  return {
    ...query,
    tweets: query.data?.pages.flatMap(p => p.items) ?? []
  };
}
```

---

## 6. Real-Time Store & SSE Integration

### Store (`store/realtimeStore.ts`)

```ts
import { create } from 'zustand';

interface RealtimeState {
  tweetStatusUpdates: Map<string, Partial<{ status:string; hasDraft:boolean }>>;
  applyTweetStatus: (id:string, patch: Partial<{ status:string; hasDraft:boolean }>) => void;
  reset(): void;
}

export const useRealtimeStore = create<RealtimeState>((set) => ({
  tweetStatusUpdates: new Map(),
  applyTweetStatus: (id, patch) => set(state => {
    const next = new Map(state.tweetStatusUpdates);
    const prev = next.get(id) || {};
    next.set(id, { ...prev, ...patch });
    return { tweetStatusUpdates: next };
  }),
  reset: () => set({ tweetStatusUpdates: new Map() })
}));
```

### SSE Provider (`components/realtime/SSEProvider.tsx`)

```tsx
'use client';
import { ReactNode, useEffect } from 'react';
import { useRealtimeStore } from '@/store/realtimeStore';
import { queryClient } from '@/hooks/queryClient';

export function SSEProvider({ children }: { children: ReactNode }) {
  const applyTweetStatus = useRealtimeStore(s => s.applyTweetStatus);

  useEffect(() => {
    const ev = new EventSource('/api/events');
    ev.onmessage = (m) => {
      try {
        const evt = JSON.parse(m.data);
        switch (evt.type) {
          case 'tweet_status':
            applyTweetStatus(evt.tweetId, { status: evt.newStatus, hasDraft: !!evt.draftId });
            // If tweet moved into 'drafted' status, invalidate drafts list only.
            if (evt.newStatus === 'drafted') {
              queryClient.invalidateQueries({ queryKey: ['drafts','pending'] });
            }
            break;
          case 'quota_update':
            queryClient.invalidateQueries({ queryKey: ['quota'] });
            break;
          default:
            break;
        }
      } catch { /* ignore */ }
    };
    ev.onerror = () => {
      // Let the browser auto-retry; optionally show toast after repeated failures
    };
    return () => ev.close();
  }, [applyTweetStatus]);

  return <>{children}</>;
}
```

Wrap your root layout (client boundary) or a dashboard-specific layout with `<SSEProvider>`.

---

## 7. Quota Hook (`hooks/useQuota.ts`)

```ts
import { useQuery } from '@tanstack/react-query';
import type { QuotaStatus } from '@/lib/types';
import { api } from '@/lib/apiClient';

export function useQuota() {
  const query = useQuery({
    queryKey: ['quota'],
    queryFn: () => api<QuotaStatus>('/api/quota'),
    staleTime: 10 * 60 * 1000,
    refetchInterval: false // Updated via SSE
  });

  return {
    ...query,
    quota: query.data
  };
}
```

---

## 8. Tweet Detail Hook (`hooks/useTweetDetail.ts`)

Fetch only when needed (drawer open):

```ts
import { useQuery } from '@tanstack/react-query';
import type { TweetDetail } from '@/lib/types';
import { api } from '@/lib/apiClient';

export function useTweetDetail(id?: string, enabled = true) {
  return useQuery({
    queryKey: ['tweet', id],
    queryFn: () => api<TweetDetail>(`/api/tweets/${id}`),
    enabled: !!id && enabled,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev
  });
}
```

---

## 9. Example Usage in Inbox Client Component

```tsx
'use client';
import { useTweetList } from '@/hooks/useTweetList';
import { useState } from 'react';
import TweetRow from '@/components/tweets/TweetRow';

export default function TweetInboxClient() {
  const [statusFilter, setStatusFilter] = useState('relevant|drafted|unclassified');
  const { tweets, fetchNextPage, hasNextPage, isFetchingNextPage } = useTweetList(statusFilter);

  return (
    <div className="flex flex-col h-full">
      {/* filter controls omitted */}
      <div className="flex-1 overflow-auto">
        {tweets.map(t => (
          <TweetRow key={t.id} tweet={t} />
        ))}
        {hasNextPage && (
          <button
            className="mt-4 px-4 py-2 rounded border"
            disabled={isFetchingNextPage}
            onClick={() => fetchNextPage()}
          >
            {isFetchingNextPage ? 'Loading…' : 'Load more'}
          </button>
        )}
      </div>
    </div>
  );
}
```

---

## 10. Autosave Hook (Draft Editing) (`hooks/useEditorAutosave.ts`)

```ts
import { useEffect, useRef } from 'react';

export function useEditorAutosave(draftId: string, text: string) {
  const key = `draft:${draftId}`;
  const prev = useRef(text);

  // Load existing
  useEffect(() => {
    const stored = localStorage.getItem(key);
    if (stored && stored !== text) {
      // Caller can decide how to merge; simplest is emit custom event
      window.dispatchEvent(new CustomEvent('draft-autosave-restore', { detail: { draftId, stored } }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId]);

  useEffect(() => {
    if (prev.current === text) return;
    const handle = setTimeout(() => {
      localStorage.setItem(key, text);
      prev.current = text;
    }, 1000);
    return () => clearTimeout(handle);
  }, [text, key]);

  const clear = () => localStorage.removeItem(key);
  return { clear };
}
```

---

## 11. Where to Plug It All Together

* In `app/layout.tsx` (or `(dashboard)/layout.tsx`) wrap children with:

  * `<QueryClientProvider>` (hydrate if SSR)
  * `<SSEProvider>`
  * `<ToastViewport />`
  * Theme provider (if using one)

---

## 12. Minimal `(dashboard)/layout.tsx` Sketch

```tsx
import '../globals.css';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/hooks/queryClient';
import { SSEProvider } from '@/components/realtime/SSEProvider';
import SidebarNav from '@/components/layout/SidebarNav';
import TopBar from '@/components/layout/TopBar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex bg-background text-foreground">
        <QueryClientProvider client={queryClient}>
          <SSEProvider>
            <SidebarNav />
            <div className="flex-1 flex flex-col">
              <TopBar />
              <main className="flex-1 overflow-hidden">{children}</main>
            </div>
          </SSEProvider>
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

---

## 13. Summary

* **Separation:** Data hooks isolated in `/hooks`, presentational in `/components`.
* **Real-time:** Central SSE provider writes minimal patches to a Zustand store; hooks merge patches without triggering extra fetches.
* **Pagination & Caching:** `useTweetList` with `useInfiniteQuery` and explicit merging of real-time updates.
* **Quota-Safe:** UI never initiates remote (X) fetches; only hits internal `/api/*` which serve cached DB data.

---
