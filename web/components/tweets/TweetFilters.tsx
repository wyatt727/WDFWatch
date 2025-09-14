/**
 * TweetFilters component for filtering tweet list
 * Provides status filtering and search functionality
 * Interacts with: InboxPage parent component
 */

import { TweetStatus } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search } from "lucide-react"

interface TweetFiltersProps {
  selectedStatus?: TweetStatus
  onStatusChange: (status: TweetStatus | undefined) => void
  searchTerm?: string
  onSearchChange?: (search: string) => void
}

const statusOptions: Array<{ value: TweetStatus | undefined; label: string; count?: number }> = [
  { value: undefined, label: "All tweets" },
  { value: "unclassified", label: "Unclassified" },
  { value: "relevant", label: "Relevant" },
  { value: "drafted", label: "Drafted" },
  { value: "posted", label: "Posted" },
  { value: "skipped", label: "Skipped" },
]

export function TweetFilters({
  selectedStatus,
  onStatusChange,
  searchTerm = "",
  onSearchChange,
}: TweetFiltersProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      {/* Status filter buttons */}
      <div className="flex flex-wrap gap-2">
        {statusOptions.map((option) => (
          <Button
            key={option.value ?? "all"}
            variant={selectedStatus === option.value ? "default" : "outline"}
            size="sm"
            onClick={() => onStatusChange(option.value)}
            className="text-xs"
          >
            {option.label}
            {option.count !== undefined && (
              <span className="ml-1 text-muted-foreground">({option.count})</span>
            )}
          </Button>
        ))}
      </div>

      {/* Search input */}
      {onSearchChange && (
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tweets..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
      )}
    </div>
  )
}