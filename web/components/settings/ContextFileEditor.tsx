'use client'

import { useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Info, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface ContextFile {
  id: number
  key: string
  name: string
  description: string | null
  content: string
  isActive: boolean
  updatedAt: string
}

interface ContextFileEditorProps {
  context: ContextFile
  onChange: (context: ContextFile) => void
}

const CONTEXT_INFO: Record<string, { hint: string; example?: string; maxLength?: number }> = {
  podcast_overview: {
    hint: 'A comprehensive description of the WDF podcast that will be included in all prompts',
    example: 'The War, Divorce, or Federalism podcast, hosted by Rick Becker, explores critical issues of liberty, constitutional governance, and state sovereignty...',
    maxLength: 1000
  },
  video_url: {
    hint: 'The YouTube URL for the latest podcast episode',
    example: 'https://youtu.be/abc123xyz',
    maxLength: 200
  }
}

export function ContextFileEditor({ context, onChange }: ContextFileEditorProps) {
  const info = CONTEXT_INFO[context.key] || {}
  const [charCount, setCharCount] = useState(context.content.length)

  const handleContentChange = (value: string) => {
    setCharCount(value.length)
    onChange({ ...context, content: value })
  }

  return (
    <div className="space-y-6">
      {/* Key Information */}
      <div className="flex items-center gap-2">
        <Badge variant="outline">
          Key: {context.key}
        </Badge>
        <Badge variant="secondary">
          Last updated: {new Date(context.updatedAt).toLocaleDateString()}
        </Badge>
      </div>

      {/* Content Editor */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="content" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Content
          </Label>
          {info.maxLength && (
            <span className={`text-sm ${charCount > info.maxLength ? 'text-destructive' : 'text-muted-foreground'}`}>
              {charCount} / {info.maxLength} characters
            </span>
          )}
        </div>
        
        <Textarea
          id="content"
          value={context.content}
          onChange={(e) => handleContentChange(e.target.value)}
          className={`min-h-[${context.key === 'video_url' ? '150' : '400'}px] font-mono text-sm`}
          placeholder={info.example || 'Enter content...'}
        />
        
        {info.hint && (
          <p className="text-sm text-muted-foreground">{info.hint}</p>
        )}
      </div>

      {/* Context-specific hints */}

      {context.key === 'video_url' && (
        <p className="text-sm text-muted-foreground">
          URL included in tweet responses. Update for each new episode.
        </p>
      )}

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">Description (Optional)</Label>
        <Textarea
          id="description"
          value={context.description || ''}
          onChange={(e) => onChange({ ...context, description: e.target.value })}
          className="min-h-[80px]"
          placeholder="Add notes about this context file..."
        />
      </div>

      {/* Usage Information */}
      <div className="rounded-lg border bg-muted/50 p-4 space-y-2">
        <h4 className="text-sm font-medium">Usage in Pipeline</h4>
        <ul className="text-sm text-muted-foreground space-y-1">
          {context.key === 'podcast_overview' && (
            <>
              <li>• Used in transcript summarization prompts</li>
              <li>• Included in few-shot generation</li>
              <li>• Provides context for tweet responses</li>
            </>
          )}
          {context.key === 'video_url' && (
            <>
              <li>• Automatically included in all tweet responses</li>
              <li>• Ensures viewers can find the latest episode</li>
              <li>• Should be updated with each new episode release</li>
            </>
          )}
        </ul>
      </div>
    </div>
  )
}