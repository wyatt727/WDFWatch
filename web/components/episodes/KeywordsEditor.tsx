'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useToast } from '@/components/ui/use-toast'
import { Edit3, Save, X, Plus, Trash2, Info } from 'lucide-react'

interface KeywordsEditorProps {
  episodeId: number
  initialKeywords: Array<{ keyword: string; weight: number }>
  episodeType?: string
}

export function KeywordsEditor({ episodeId, initialKeywords, episodeType }: KeywordsEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [keywords, setKeywords] = useState<Array<{ keyword: string; weight: number }>>(initialKeywords)
  const [newKeyword, setNewKeyword] = useState('')
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const isKeywordSearch = episodeType === 'keyword_search'

  const saveKeywordsMutation = useMutation({
    mutationFn: async (updatedKeywords: Array<{ keyword: string; weight: number }>) => {
      const res = await fetch(`/api/episodes/${episodeId}/keywords`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: updatedKeywords })
      })

      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.error || 'Failed to save keywords')
      }

      return res.json()
    },
    onSuccess: () => {
      toast({
        title: 'Keywords Saved',
        description: `Successfully updated ${keywords.length} keywords for this episode.`
      })
      setIsEditing(false)
      queryClient.invalidateQueries({ queryKey: ['episode', episodeId] })
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to Save',
        description: error.message,
        variant: 'destructive'
      })
    }
  })

  const handleAddKeyword = () => {
    const trimmed = newKeyword.trim()
    if (!trimmed) return

    // Check for duplicates
    if (keywords.some(k => k.keyword.toLowerCase() === trimmed.toLowerCase())) {
      toast({
        title: 'Duplicate Keyword',
        description: 'This keyword already exists in the list.',
        variant: 'destructive'
      })
      return
    }

    setKeywords([...keywords, { keyword: trimmed, weight: 1.0 }])
    setNewKeyword('')
  }

  const handleRemoveKeyword = (index: number) => {
    setKeywords(keywords.filter((_, i) => i !== index))
  }

  const handleUpdateWeight = (index: number, weight: number) => {
    const updated = [...keywords]
    updated[index].weight = Math.max(0, Math.min(1, weight))
    setKeywords(updated)
  }

  const handleSave = () => {
    if (keywords.length === 0) {
      toast({
        title: 'No Keywords',
        description: 'Please add at least one keyword before saving.',
        variant: 'destructive'
      })
      return
    }

    saveKeywordsMutation.mutate(keywords)
  }

  const handleCancel = () => {
    setKeywords(initialKeywords)
    setNewKeyword('')
    setIsEditing(false)
  }

  if (!isEditing) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-2xl font-bold">{initialKeywords.length}</p>
            <p className="text-xs text-muted-foreground">Search terms</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEditing(true)}
          >
            <Edit3 className="h-3 w-3 mr-1" />
            Edit
          </Button>
        </div>

        {isKeywordSearch && (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription className="text-xs">
              Keyword-focused episode - edit carefully to preserve search intent
            </AlertDescription>
          </Alert>
        )}

        {initialKeywords.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {initialKeywords.map((kw, idx) => (
              <Badge key={idx} variant="outline" className="text-xs">
                {kw.keyword}
                {kw.weight !== 1.0 && (
                  <span className="ml-1 text-muted-foreground">
                    ({kw.weight.toFixed(2)})
                  </span>
                )}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No keywords configured
          </p>
        )}
      </div>
    )
  }

  return (
    <Card className="border-blue-200 bg-blue-50/20 dark:border-blue-900 dark:bg-blue-950/10">
      <CardHeader className="pb-4">
        <CardTitle className="text-base">Edit Keywords</CardTitle>
        <CardDescription>
          {isKeywordSearch
            ? 'Modify search keywords for this focused search episode'
            : 'Edit keywords that will be used for tweet discovery'
          }
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add New Keyword */}
        <div className="space-y-2">
          <Label htmlFor="new-keyword">Add Keyword</Label>
          <div className="flex gap-2">
            <Input
              id="new-keyword"
              placeholder="e.g., federalism, state sovereignty"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  handleAddKeyword()
                }
              }}
            />
            <Button
              type="button"
              size="sm"
              onClick={handleAddKeyword}
              disabled={!newKeyword.trim()}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Current Keywords */}
        <div className="space-y-2">
          <Label>Current Keywords ({keywords.length})</Label>
          {keywords.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">
              No keywords yet. Add some above.
            </p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {keywords.map((kw, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-background border rounded"
                >
                  <span className="flex-1 text-sm">{kw.keyword}</span>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      <Label htmlFor={`weight-${idx}`} className="text-xs text-muted-foreground">
                        Weight:
                      </Label>
                      <Input
                        id={`weight-${idx}`}
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={kw.weight}
                        onChange={(e) => handleUpdateWeight(idx, parseFloat(e.target.value))}
                        className="w-16 h-7 text-xs"
                      />
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveKeyword(idx)}
                      className="h-7 w-7 p-0"
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {isKeywordSearch && keywords.length > 5 && (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription className="text-xs">
              You have {keywords.length} keywords. Focused searches work best with 1-5 targeted keywords.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
      <CardFooter className="flex justify-between gap-2">
        <Button
          variant="outline"
          onClick={handleCancel}
          disabled={saveKeywordsMutation.isPending}
        >
          <X className="h-4 w-4 mr-1" />
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={saveKeywordsMutation.isPending || keywords.length === 0}
        >
          <Save className="h-4 w-4 mr-1" />
          {saveKeywordsMutation.isPending ? 'Saving...' : 'Save Keywords'}
        </Button>
      </CardFooter>
    </Card>
  )
}
