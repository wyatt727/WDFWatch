/**
 * DraftEditor component for editing draft responses
 * Provides character counting and validation feedback
 * Interacts with: DraftReviewPanel parent component
 */

import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

interface DraftEditorProps {
  value: string
  onChange: (value: string) => void
  maxLength?: number
  placeholder?: string
  className?: string
  autoFocus?: boolean
}

export function DraftEditor({
  value,
  onChange,
  maxLength = 280,
  placeholder = "Type your response...",
  className,
  autoFocus = false,
}: DraftEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [value])

  // Auto-focus on mount if requested
  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      textareaRef.current.focus()
      // Place cursor at end of text
      textareaRef.current.setSelectionRange(value.length, value.length)
    }
  }, [autoFocus, value.length])

  const isOverLimit = value.length > maxLength
  const remainingChars = maxLength - value.length

  return (
    <div className="space-y-2">
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cn(
            "w-full min-h-[120px] p-4 rounded-lg border bg-background resize-none",
            "placeholder:text-muted-foreground",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            isOverLimit && "border-destructive focus:ring-destructive",
            className
          )}
          style={{ overflow: "hidden" }}
        />
        
        {/* Character count overlay */}
        <div
          className={cn(
            "absolute bottom-2 right-2 text-xs font-mono px-2 py-1 rounded",
            isOverLimit
              ? "bg-destructive/10 text-destructive"
              : remainingChars <= 20
              ? "bg-warning/10 text-warning"
              : "bg-muted text-muted-foreground"
          )}
        >
          {value.length}/{maxLength}
        </div>
      </div>

      {/* Visual progress bar */}
      <div className="h-1 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full transition-all duration-300",
            isOverLimit
              ? "bg-destructive"
              : remainingChars <= 20
              ? "bg-warning"
              : "bg-primary"
          )}
          style={{ width: `${Math.min((value.length / maxLength) * 100, 100)}%` }}
        />
      </div>

      {/* Helper text */}
      {isOverLimit && (
        <p className="text-sm text-destructive">
          {Math.abs(remainingChars)} characters over the limit
        </p>
      )}

      {/* Suggested snippets for common responses */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChange(value + " Check out WDF podcast: ")}
          className="text-xs px-2 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
        >
          + Add podcast link
        </button>
        <button
          type="button"
          onClick={() => onChange(value + " @RickBeckerND explores this in depth ")}
          className="text-xs px-2 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
        >
          + Mention Rick
        </button>
        <button
          type="button"
          onClick={() => onChange(value + " Latest episode: ")}
          className="text-xs px-2 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
        >
          + Latest episode
        </button>
      </div>
    </div>
  )
}