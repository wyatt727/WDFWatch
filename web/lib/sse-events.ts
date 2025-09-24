/**
 * SSE event helpers and types
 * Provides type-safe event emission for real-time updates
 * Used by: API routes, Python pipeline bridge
 */

import { TweetStatus } from "./types"

// Define all possible SSE event types
export type SSEEvent =
  | { type: "tweet_status"; tweetId: string; newStatus: TweetStatus }
  | { type: "draft_ready"; draftId: string; tweetId: string }
  | { type: "quota_update"; used: number; remaining: number }
  | { type: "processing_step"; episodeId: string; step: string; status: "started" | "completed" }
  | { type: "tweets_classified"; count: number }
  | { type: "pipeline_status"; stage: string; status: "started" | "completed" | "failed"; message?: string }
  | { type: "pipeline_stage_started"; episodeId: string; stage: string; runId: string }
  | { type: "pipeline_stage_progress"; episodeId: string; stage: string; runId: string; output: string }
  | { type: "pipeline_stage_error"; episodeId: string; stage: string; runId: string; error: string }
  | { type: "pipeline_stage_completed"; episodeId: string; stage: string; runId: string; status: string; exitCode: number }
  | { type: "episode_processing_complete"; episodeId: string; status: string }

// Import the emitter from the API route
let emitFunction: ((event: SSEEvent) => Promise<void>) | null = null

// Set the emit function (called from API route initialization)
export function setSSEEmitter(emitter: (event: SSEEvent) => Promise<void>) {
  emitFunction = emitter
}

// Type-safe event emission
export async function emitEvent(event: SSEEvent): Promise<void> {
  if (!emitFunction) {
    console.warn("SSE emitter not initialized, event dropped:", event)
    return
  }

  try {
    await emitFunction(event)
    console.log("SSE event emitted:", event.type)
  } catch (error) {
    console.error("Failed to emit SSE event:", error)
  }
}

// Convenience functions for common events
export const SSEEvents = {
  tweetStatusChanged(tweetId: string, newStatus: TweetStatus) {
    return emitEvent({ type: "tweet_status", tweetId, newStatus })
  },

  draftReady(draftId: string, tweetId: string) {
    return emitEvent({ type: "draft_ready", draftId, tweetId })
  },

  quotaUpdate(used: number, remaining: number) {
    return emitEvent({ type: "quota_update", used, remaining })
  },

  processingStep(episodeId: string, step: string, status: "started" | "completed") {
    return emitEvent({ type: "processing_step", episodeId, step, status })
  },

  tweetsClassified(count: number) {
    return emitEvent({ type: "tweets_classified", count })
  },

  pipelineStatus(stage: string, status: "started" | "completed" | "failed", message?: string) {
    return emitEvent({ type: "pipeline_status", stage, status, message })
  },

  pipelineStageStarted(episodeId: string, stage: string, runId: string) {
    return emitEvent({ type: "pipeline_stage_started", episodeId, stage, runId })
  },

  pipelineStageProgress(episodeId: string, stage: string, runId: string, output: string) {
    return emitEvent({ type: "pipeline_stage_progress", episodeId, stage, runId, output })
  },

  pipelineStageError(episodeId: string, stage: string, runId: string, error: string) {
    return emitEvent({ type: "pipeline_stage_error", episodeId, stage, runId, error })
  },

  pipelineStageCompleted(episodeId: string, stage: string, runId: string, status: string, exitCode: number) {
    return emitEvent({ type: "pipeline_stage_completed", episodeId, stage, runId, status, exitCode })
  },

  episodeProcessingComplete(episodeId: string, status: string) {
    return emitEvent({ type: "episode_processing_complete", episodeId, status })
  },
}