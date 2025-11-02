/**
 * DraftReviewPanel component for human approval workflow
 * Displays tweet context alongside editable draft response
 * Interacts with: Review page, drafts API, SSE events
 */

import { useState, useEffect } from "react"
import { DraftDetail } from "@/lib/types"
import { TweetContext } from "./TweetContext"
import { DraftEditor } from "./DraftEditor"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle, Clock, AlertCircle, RotateCw } from "lucide-react"

interface DraftReviewPanelProps {
  draft: DraftDetail
  onApprove?: (draftId: string, finalText: string) => Promise<void>
  onReject?: (draftId: string, reason?: string) => Promise<void>
  onNext?: () => void
}

export function DraftReviewPanel({
  draft,
  onApprove,
  onReject,
  onNext,
}: DraftReviewPanelProps) {
  const [editedText, setEditedText] = useState(draft.text)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [characterCount, setCharacterCount] = useState(draft.text.length)
  const [regenerationCount, setRegenerationCount] = useState(0)
  const { toast } = useToast()

  useEffect(() => {
    setEditedText(draft.text)
    setCharacterCount(draft.text.length)
  }, [draft])

  const handleTextChange = (text: string) => {
    setEditedText(text)
    setCharacterCount(text.length)
  }

  const handleApprove = async () => {
    console.log('==================== UI: APPROVE BUTTON CLICKED ====================')
    console.log('[UI] Draft ID:', draft.id)
    console.log('[UI] Draft status:', draft.status)
    console.log('[UI] Original text:', draft.text.substring(0, 50) + '...')
    console.log('[UI] Edited text:', editedText.substring(0, 50) + '...')
    console.log('[UI] Text changed:', editedText !== draft.text)
    console.log('[UI] Character count:', characterCount)

    if (!onApprove) {
      console.error('[UI] ❌ onApprove prop is undefined!')
      return
    }

    setIsSubmitting(true)
    console.log('[UI] Submitting state set to true')

    try {
      console.log('[UI] Calling onApprove function...')
      const startTime = Date.now()

      await onApprove(draft.id, editedText)

      const endTime = Date.now()
      console.log(`[UI] ✅ onApprove completed in ${endTime - startTime}ms`)

      toast({
        title: "Draft approved",
        description: "The response has been approved and queued for posting.",
      })
      console.log('[UI] Toast notification shown')

      console.log('[UI] Calling onNext to move to next draft...')
      onNext?.()
      console.log('==================== UI: APPROVE SUCCESS ====================')
    } catch (error: any) {
      console.error('==================== UI: APPROVE ERROR ====================')
      console.error('[UI] ❌ Error caught in handleApprove')
      console.error('[UI] Error type:', error?.constructor?.name)
      console.error('[UI] Error message:', error?.message)
      console.error('[UI] Error stack:', error?.stack)
      console.error('[UI] Full error:', error)

      toast({
        title: "Error",
        description: error?.message || "Failed to approve draft. Please try again.",
        variant: "destructive",
      })
      console.error('==================== UI: APPROVE FAILED ====================')
    } finally {
      setIsSubmitting(false)
      console.log('[UI] Submitting state set to false')
    }
  }

  const handleRegenerate = async () => {
    console.log('[UI] Regenerate clicked for draft:', draft.id)
    setIsRegenerating(true)
    try {
      console.log('[UI] Sending regenerate request...')
      const response = await fetch(`/api/drafts/${draft.id}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      if (!response.ok) {
        console.error('[UI] ❌ Regenerate failed:', response.status, response.statusText)
        const error = await response.json()
        throw new Error(error.error || "Failed to regenerate")
      }

      const result = await response.json()
      console.log('[UI] ✅ Regenerate successful:', result)

      // Update the local state with the new response
      setEditedText(result.text)
      setCharacterCount(result.text.length)
      setRegenerationCount(prev => prev + 1)

      toast({
        title: "Response regenerated",
        description: `New response generated (v${result.version})`,
      })
    } catch (error: any) {
      console.error('[UI] ❌ Error regenerating response:', error)
      console.error('[UI] Error details:', {
        type: error?.constructor?.name,
        message: error?.message,
        stack: error?.stack
      })
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to regenerate response",
        variant: "destructive",
      })
    } finally {
      setIsRegenerating(false)
      console.log('[UI] Regenerating state reset')
    }
  }

  const handleTrueReject = async () => {
    setIsSubmitting(true)
    try {
      const response = await fetch(`/api/drafts/${draft.id}/true-reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          reason: "Tweet marked as irrelevant to podcast topics" 
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to mark as irrelevant")
      }

      toast({
        title: "Tweet marked as irrelevant",
        description: "This tweet has been removed from the relevant pool and keyword weights have been adjusted.",
      })
      onNext?.()
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to mark tweet as irrelevant. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Keep the old handleReject for backward compatibility (partial reject)
  const handleReject = async () => {
    if (!onReject) return

    setIsSubmitting(true)
    try {
      await onReject(draft.id, "Low quality response - keyword weight will be reduced")
      toast({
        title: "Draft rejected",
        description: "The draft has been rejected and keyword weights have been adjusted.",
      })
      onNext?.()
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to reject draft. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
      {/* Left side: Tweet context */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Original Tweet</h3>
        <TweetContext tweet={draft.tweet || { id: draft.tweetId }} />
      </div>

      {/* Right side: Draft editor and actions */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Draft Response</h3>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{draft.model}</span>
            <span>•</span>
            <span>v{draft.version}</span>
          </div>
        </div>

        <DraftEditor
          value={editedText}
          onChange={handleTextChange}
          maxLength={280}
          placeholder="Edit the draft response..."
        />

        {/* Character count and warnings */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            {characterCount > 280 && (
              <span className="text-destructive flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                Exceeds character limit
              </span>
            )}
            {draft.toxicityScore && draft.toxicityScore > 0.7 && (
              <span className="text-warning flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                High toxicity score
              </span>
            )}
          </div>
          <span
            className={cn(
              "font-mono",
              characterCount > 280 ? "text-destructive" : "text-muted-foreground"
            )}
          >
            {characterCount}/280
          </span>
        </div>

        {/* Style and toxicity scores */}
        {(draft.styleScore !== undefined || draft.toxicityScore !== undefined) && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-muted rounded-lg">
            {draft.styleScore !== undefined && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Style Score</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${draft.styleScore * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {Math.round(draft.styleScore * 100)}%
                  </span>
                </div>
              </div>
            )}
            {draft.toxicityScore !== undefined && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Toxicity Score</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full transition-all",
                        draft.toxicityScore > 0.7 ? "bg-destructive" : 
                        draft.toxicityScore > 0.4 ? "bg-warning" : "bg-primary"
                      )}
                      style={{ width: `${draft.toxicityScore * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {Math.round(draft.toxicityScore * 100)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Edit history */}
        {draft.editHistory && draft.editHistory.length > 1 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              View edit history ({draft.editHistory.length} versions)
            </summary>
            <div className="mt-2 space-y-2">
              {draft.editHistory.map((edit, index) => (
                <div key={index} className="p-3 bg-muted rounded-lg">
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>Version {edit.version}</span>
                    <span>{new Date(edit.editedAt).toLocaleString()}</span>
                  </div>
                  <p className="text-sm">{edit.text}</p>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Regeneration indicator */}
        {regenerationCount > 0 && (
          <div className="text-sm text-muted-foreground">
            Response regenerated {regenerationCount} time{regenerationCount !== 1 ? 's' : ''}
          </div>
        )}

        {/* Action buttons */}
        <div className="space-y-3 pt-4">
          {/* Primary actions row */}
          <div className="flex gap-3">
            <Button
              onClick={() => {
                console.log('[UI] === APPROVE BUTTON CLICKED ===')
                console.log('[UI] Button state:', {
                  isSubmitting,
                  isRegenerating,
                  characterCount,
                  hasOnApprove: !!onApprove,
                  disabled: isSubmitting || isRegenerating || characterCount > 280 || !onApprove
                })
                if (isSubmitting) console.warn('[UI] ⚠️ Already submitting!')
                if (isRegenerating) console.warn('[UI] ⚠️ Currently regenerating!')
                if (characterCount > 280) console.warn('[UI] ⚠️ Text too long!')
                if (!onApprove) console.error('[UI] ❌ No onApprove handler!')
                handleApprove()
              }}
              disabled={isSubmitting || isRegenerating || characterCount > 280 || !onApprove}
              className="flex-1"
            >
              <CheckCircle2 className="w-4 h-4 mr-2" />
              {isSubmitting ? 'Posting...' : 'Approve & Post'}
            </Button>
            <Button
              onClick={handleRegenerate}
              disabled={isSubmitting || isRegenerating}
              variant="secondary"
              className="flex-1"
            >
              <RotateCw className={cn("w-4 h-4 mr-2", isRegenerating && "animate-spin")} />
              {isRegenerating ? "Regenerating..." : "Regenerate"}
            </Button>
          </div>
          
          {/* Secondary actions row */}
          <div className="flex gap-3">
            <Button
              onClick={handleTrueReject}
              disabled={isSubmitting || isRegenerating}
              variant="destructive"
              className="flex-1"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Mark Irrelevant
            </Button>
            <Button
              variant="outline"
              disabled={isSubmitting || isRegenerating || characterCount > 280 || !onApprove}
              onClick={async () => {
                setIsSubmitting(true)
                try {
                  const response = await fetch(`/api/drafts/${draft.id}/schedule`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ finalText: editedText }),
                  })
                  
                  if (!response.ok) {
                    throw new Error("Failed to schedule draft")
                  }
                  
                  toast({
                    title: "Draft scheduled",
                    description: "The response has been scheduled for later posting.",
                  })
                  onNext?.()
                } catch (error) {
                  toast({
                    title: "Error",
                    description: "Failed to schedule draft. Please try again.",
                    variant: "destructive",
                  })
                } finally {
                  setIsSubmitting(false)
                }
              }}
            >
              <Clock className="w-4 h-4 mr-2" />
              Schedule
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}