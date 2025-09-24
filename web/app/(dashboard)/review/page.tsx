/**
 * Draft review page - human approval workflow interface
 * Allows operators to review, edit, and approve/reject draft responses
 * Interacts with: DraftReviewPanel, useDrafts hook, drafts API
 */

"use client"

import { useState, useEffect } from "react"
import { useDrafts } from "@/hooks/useDrafts"
import { DraftReviewPanel } from "@/components/drafts/DraftReviewPanel"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertCircle, 
  ArrowLeft, 
  ArrowRight,
  RefreshCw 
} from "lucide-react"

export default function ReviewPage() {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [filter, setFilter] = useState<"pending" | "approved" | "rejected">("pending")
  
  const { 
    drafts, 
    isLoading,
    error,
    refetch
  } = useDrafts({ status: filter })

  // Reset index when filter changes
  useEffect(() => {
    setCurrentIndex(0)
  }, [filter])

  const currentDraft = drafts[currentIndex]

  const handleApprove = async (draftId: string, finalText: string) => {
    try {
      const response = await fetch(`/api/drafts/${draftId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ finalText }),
      })

      if (!response.ok) {
        throw new Error("Failed to approve draft")
      }

      // Refresh drafts list
      await refetch()
    } catch (error) {
      console.error("Error approving draft:", error)
      throw error
    }
  }

  const handleReject = async (draftId: string, reason?: string) => {
    try {
      const response = await fetch(`/api/drafts/${draftId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reason || "Manual rejection" }),
      })

      if (!response.ok) {
        throw new Error("Failed to reject draft")
      }

      // Refresh drafts list
      await refetch()
    } catch (error) {
      console.error("Error rejecting draft:", error)
      throw error
    }
  }

  const handleNext = () => {
    if (currentIndex < drafts.length - 1) {
      setCurrentIndex(currentIndex + 1)
    } else {
      // Refresh to get new drafts
      refetch()
      setCurrentIndex(0)
    }
  }

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const stats = {
    pending: drafts.filter(d => d.status === "pending").length,
    approved: drafts.filter(d => d.status === "approved" || d.status === "posted").length,
    rejected: drafts.filter(d => d.status === "rejected").length,
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Draft Review</h2>
          <p className="text-muted-foreground">
            Review and approve AI-generated responses before posting
          </p>
        </div>
        
        <Button 
          onClick={() => refetch()} 
          variant="outline" 
          size="sm"
          disabled={isLoading}
        >
          <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Stats overview */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-lg border bg-card">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <span className="text-sm font-medium">Pending Review</span>
          </div>
          <p className="text-2xl font-bold mt-2">{stats.pending}</p>
        </div>
        <div className="p-4 rounded-lg border bg-card">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium">Approved/Posted</span>
          </div>
          <p className="text-2xl font-bold mt-2">{stats.approved}</p>
        </div>
        <div className="p-4 rounded-lg border bg-card">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            <span className="text-sm font-medium">Rejected Today</span>
          </div>
          <p className="text-2xl font-bold mt-2">{stats.rejected}</p>
        </div>
      </div>

      {/* Filter tabs */}
      <Tabs value={filter} onValueChange={(v) => setFilter(v as any)}>
        <TabsList>
          <TabsTrigger value="pending">
            Pending ({stats.pending})
          </TabsTrigger>
          <TabsTrigger value="approved">
            Approved/Posted ({stats.approved})
          </TabsTrigger>
          <TabsTrigger value="rejected">
            Rejected ({stats.rejected})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={filter} className="mt-6">
          {error && (
            <div className="p-4 rounded-lg border border-destructive bg-destructive/10">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <p className="text-sm">Failed to load drafts. Please try again.</p>
              </div>
            </div>
          )}

          {!error && drafts.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <p className="text-lg font-medium">No drafts to review</p>
              <p className="text-sm mt-2">
                {filter === "pending" 
                  ? "New drafts will appear here when generated"
                  : `No ${filter} drafts yet`}
              </p>
            </div>
          )}

          {!error && currentDraft && (
            <>
              {/* Navigation controls */}
              <div className="flex items-center justify-between mb-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrevious}
                  disabled={currentIndex === 0}
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Previous
                </Button>
                
                <span className="text-sm text-muted-foreground">
                  {currentIndex + 1} of {drafts.length}
                </span>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNext}
                  disabled={currentIndex === drafts.length - 1}
                >
                  Next
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>

              {/* Draft review panel */}
              <DraftReviewPanel
                draft={currentDraft}
                onApprove={filter === "pending" ? handleApprove : undefined}
                onReject={filter === "pending" ? handleReject : undefined}
                onNext={handleNext}
              />
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}