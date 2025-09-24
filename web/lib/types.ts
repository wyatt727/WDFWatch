/**
 * TypeScript type definitions for WDFWatch Web UI
 * Shared types used across components, hooks, and API routes
 * Based on data contracts from Master_Plan.md
 */

// Tweet types
export type TweetStatus = "unclassified" | "skipped" | "relevant" | "drafted" | "posted"

export interface TweetListItem {
  id: string
  authorHandle: string
  textPreview: string
  createdAt: string
  relevanceScore?: number
  status: TweetStatus
  hasDraft: boolean
  flags?: {
    toxicity?: boolean
    duplicate?: boolean
  }
}

export interface TweetDetail extends TweetListItem {
  fullText: string
  thread: Array<{
    id: string
    authorHandle: string
    text: string
  }>
  contextSnippets: Array<{
    text: string
    relevance: number
  }>
  classificationRationale?: string
  drafts: DraftSummary[]
  replyCount?: number
  retweetCount?: number
  likeCount?: number
}

// Draft types
export interface DraftSummary {
  id: string
  model: string
  createdAt: string
  version: number
  text: string
  styleScore?: number
  toxicityScore?: number
  superseded?: boolean
}

export type DraftStatus = "pending" | "approved" | "rejected" | "posted" | "scheduled"

export interface DraftDetail extends DraftSummary {
  tweetId: string
  status: DraftStatus
  editHistory: Array<{
    version: number
    text: string
    editedAt: string
    editedBy?: string
  }>
  tweet?: {
    id: string
    authorHandle?: string
    authorName?: string
    textPreview?: string
    fullText?: string
    likeCount?: number
    retweetCount?: number
    replyCount?: number
    relevanceScore?: number
    classificationRationale?: string
    threadData?: any
    createdAt?: string
  }
}

// Episode types
export interface Episode {
  id: string
  title: string
  uploadedAt: string
  status: "no_transcript" | "processing" | "summarized" | "keywords_ready"
  summaryText?: string
  keywords?: string[]
  summaryEmbedding?: number[]
}

// Quota types
export interface QuotaStatus {
  periodStart: string
  periodEnd: string
  totalAllowed: number // 10000
  used: number
  projectedExhaustDate?: string
  avgDailyUsage: number
  lastSync: string
  sourceBreakdown: {
    stream: number
    search: number
    threadLookups: number
  }
}

// SSE Event types
export type SSEEvent =
  | { type: "tweet_status"; tweetId: string; newStatus: TweetStatus }
  | { type: "draft_ready"; draftId: string; tweetId: string }
  | { type: "quota_update"; used: number; remaining: number }
  | { type: "processing_step"; episodeId: string; step: string; status: "started" | "completed" }

// API Response types
export interface PaginatedResponse<T> {
  items: T[]
  nextCursor?: string
  hasMore: boolean
  total?: number
}

// Form types
export interface ApprovalFormData {
  finalText: string
  scheduleAt?: string
}

export interface EpisodeUploadFormData {
  file: File
  title?: string
}