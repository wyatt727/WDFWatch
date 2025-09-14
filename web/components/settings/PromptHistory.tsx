'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, RotateCcw, User, Calendar, FileText, GitCompare } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'
import { formatDistanceToNow } from 'date-fns'

interface HistoryEntry {
  id: number
  promptId: number
  version: number
  template: string
  changedBy: string | null
  changeNote: string | null
  createdAt: string
  isCurrent?: boolean
}

interface PromptHistoryProps {
  promptId: number
  promptName: string
  onClose: () => void
  onRestore: (promptId: number, historyId: number) => void
}

export function PromptHistory({ promptId, promptName, onClose, onRestore }: PromptHistoryProps) {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEntry, setSelectedEntry] = useState<HistoryEntry | null>(null)
  const [compareEntry, setCompareEntry] = useState<HistoryEntry | null>(null)
  const [showDiff, setShowDiff] = useState(false)

  const fetchHistory = useCallback(async () => {
    try {
      setIsLoading(true)
      const res = await fetch(`/api/settings/prompts/${promptId}/history`)
      if (!res.ok) throw new Error('Failed to fetch history')
      
      const data = await res.json()
      setHistory(data.history)
      
      // Select current version by default
      const current = data.history.find((h: HistoryEntry) => h.isCurrent)
      if (current) {
        setSelectedEntry(current)
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load version history',
        variant: 'destructive'
      })
    } finally {
      setIsLoading(false)
    }
  }, [promptId])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const handleRestore = () => {
    if (selectedEntry && !selectedEntry.isCurrent) {
      onRestore(promptId, selectedEntry.id)
    }
  }

  const getDiffLines = (oldText: string, newText: string) => {
    const oldLines = oldText.split('\n')
    const newLines = newText.split('\n')
    const maxLines = Math.max(oldLines.length, newLines.length)
    const diff = []

    for (let i = 0; i < maxLines; i++) {
      if (oldLines[i] !== newLines[i]) {
        if (i < oldLines.length && i < newLines.length) {
          diff.push({ type: 'changed', lineNum: i + 1, old: oldLines[i], new: newLines[i] })
        } else if (i >= oldLines.length) {
          diff.push({ type: 'added', lineNum: i + 1, text: newLines[i] })
        } else {
          diff.push({ type: 'removed', lineNum: i + 1, text: oldLines[i] })
        }
      }
    }

    return diff
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <CardTitle>Version History</CardTitle>
              <CardDescription>{promptName}</CardDescription>
            </div>
          </div>
          {selectedEntry && !selectedEntry.isCurrent && (
            <Button
              size="sm"
              onClick={handleRestore}
              className="flex items-center gap-2"
            >
              <RotateCcw className="h-4 w-4" />
              Restore This Version
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-20 w-full" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Version List */}
            <div className="lg:col-span-1 space-y-2">
              <h3 className="text-sm font-medium mb-3">Versions</h3>
              <ScrollArea className="h-[500px] pr-4">
                <div className="space-y-2">
                  {history.map((entry) => (
                    <button
                      key={entry.id}
                      onClick={() => {
                        setSelectedEntry(entry)
                        setCompareEntry(null)
                        setShowDiff(false)
                      }}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedEntry?.id === entry.id 
                          ? 'bg-accent border-accent-foreground/20' 
                          : 'hover:bg-accent/50'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant={entry.isCurrent ? 'default' : 'outline'}>
                          v{entry.version}
                        </Badge>
                        {entry.isCurrent && (
                          <Badge variant="secondary" className="text-xs">
                            Current
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground space-y-1">
                        <div className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          <span>{entry.changedBy || 'System'}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          <span>{formatDistanceToNow(new Date(entry.createdAt), { addSuffix: true })}</span>
                        </div>
                        {entry.changeNote && (
                          <div className="text-xs italic truncate">
                            {entry.changeNote}
                          </div>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Version Details */}
            <div className="lg:col-span-2">
              {selectedEntry && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Version {selectedEntry.version}
                    </h3>
                    {!selectedEntry.isCurrent && history.length > 1 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const current = history.find(h => h.isCurrent)
                          if (current) {
                            setCompareEntry(current)
                            setShowDiff(true)
                          }
                        }}
                      >
                        <GitCompare className="h-4 w-4 mr-2" />
                        Compare with Current
                      </Button>
                    )}
                  </div>

                  <div className="rounded-lg border bg-muted/50 p-4">
                    <ScrollArea className="h-[400px]">
                      {showDiff && compareEntry ? (
                        <div className="space-y-2">
                          <div className="text-sm font-medium mb-3">
                            Changes from v{selectedEntry.version} to v{compareEntry.version}
                          </div>
                          {getDiffLines(selectedEntry.template, compareEntry.template).map((diff, i) => (
                            <div key={i} className="font-mono text-xs">
                              {diff.type === 'changed' && (
                                <>
                                  <div className="bg-destructive/20 text-destructive p-2 rounded">
                                    - Line {diff.lineNum}: {diff.old}
                                  </div>
                                  <div className="bg-primary/20 text-primary p-2 rounded mt-1">
                                    + Line {diff.lineNum}: {diff.new}
                                  </div>
                                </>
                              )}
                              {diff.type === 'added' && (
                                <div className="bg-primary/20 text-primary p-2 rounded">
                                  + Line {diff.lineNum}: {diff.text}
                                </div>
                              )}
                              {diff.type === 'removed' && (
                                <div className="bg-destructive/20 text-destructive p-2 rounded">
                                  - Line {diff.lineNum}: {diff.text}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <pre className="text-sm whitespace-pre-wrap font-mono">
                          {selectedEntry.template}
                        </pre>
                      )}
                    </ScrollArea>
                  </div>

                  <div className="text-sm text-muted-foreground space-y-1">
                    <p>Changed by: {selectedEntry.changedBy || 'System'}</p>
                    <p>Date: {new Date(selectedEntry.createdAt).toLocaleString()}</p>
                    {selectedEntry.changeNote && (
                      <p>Note: {selectedEntry.changeNote}</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}