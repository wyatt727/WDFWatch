/**
 * React Query hook for managing draft responses
 * Handles fetching, approval, rejection, and editing of drafts
 * Interacts with: /api/drafts route, SSE event handler
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { DraftDetail, DraftStatus, ApprovalFormData } from "@/lib/types"

interface UseDraftsOptions {
  status?: DraftStatus
}

export function useDrafts({ status = "pending" }: UseDraftsOptions = {}) {
  const queryClient = useQueryClient()
  const queryKey = ["drafts", { status }]

  const { data, error, isLoading, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      if (status) params.append("status", status)
      // Fetch more drafts to see all pending items
      params.append("limit", "10000")

      const response = await fetch(`/api/drafts?${params}`)
      if (!response.ok) {
        throw new Error("Failed to fetch drafts")
      }
      const data = await response.json()
      return data.items as DraftDetail[]
    },
    staleTime: 30 * 1000, // 30 seconds as per spec
  })

  // Set up SSE for real-time updates
  useEffect(() => {
    const eventSource = new EventSource("/api/events")

    eventSource.addEventListener("draft_ready", (event) => {
      const data = JSON.parse(event.data)
      // Invalidate drafts query when new draft is ready
      queryClient.invalidateQueries({ queryKey: ["drafts", { status: "pending" }] })
    })

    return () => {
      eventSource.close()
    }
  }, [queryClient])

  return {
    drafts: data ?? [],
    error,
    isLoading,
    refetch,
  }
}

// Mutation hooks for draft actions
export function useApproveDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ draftId, data }: { draftId: string; data: ApprovalFormData }) => {
      const response = await fetch(`/api/drafts/${draftId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        throw new Error("Failed to approve draft")
      }
      return response.json()
    },
    onSuccess: () => {
      // Invalidate both pending and approved drafts
      queryClient.invalidateQueries({ queryKey: ["drafts"] })
    },
  })
}

export function useRejectDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (draftId: string) => {
      const response = await fetch(`/api/drafts/${draftId}/reject`, {
        method: "POST",
      })
      if (!response.ok) {
        throw new Error("Failed to reject draft")
      }
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] })
    },
  })
}

export function useEditDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ draftId, text }: { draftId: string; text: string }) => {
      const response = await fetch(`/api/drafts/${draftId}/edit`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      })
      if (!response.ok) {
        throw new Error("Failed to edit draft")
      }
      return response.json()
    },
    onSuccess: (_, variables) => {
      // Update the specific draft in cache
      queryClient.invalidateQueries({ queryKey: ["drafts"] })
    },
  })
}