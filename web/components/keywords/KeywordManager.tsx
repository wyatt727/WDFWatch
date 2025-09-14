/**
 * Keyword Manager Component
 * 
 * Provides UI for managing tweet search keywords:
 * - View all keywords with filtering
 * - Add new keywords manually
 * - Edit existing keywords (text, weight, enabled status)
 * - Bulk operations (enable/disable/delete)
 * - Import keywords from text
 * 
 * Related files:
 * - /web/app/api/keywords/route.ts (API endpoints)
 * - /web/app/(dashboard)/settings/keywords/page.tsx (Page component)
 */

'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Slider } from '@/components/ui/slider'
import { useToast } from '@/components/ui/use-toast'
import { 
  Plus, 
  Trash2, 
  Edit2, 
  Save, 
  X, 
  Upload,
  ToggleLeft,
  ToggleRight,
  Search,
  Filter,
} from 'lucide-react'

interface Keyword {
  id: string
  keyword: string
  weight: number
  enabled: boolean
  source: 'manual' | 'auto_extracted'
  episodeId: string | null
  episode?: {
    id: string
    title: string
    episodeNumber: string
  }
  createdAt: string
  updatedAt: string
}

interface KeywordManagerProps {
  episodeId?: string | number
}

export function KeywordManager({ episodeId }: KeywordManagerProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ keyword: '', weight: 1 })
  const [searchQuery, setSearchQuery] = useState('')
  const [filterEnabled, setFilterEnabled] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [newKeyword, setNewKeyword] = useState({ keyword: '', weight: 1 })
  const [importText, setImportText] = useState('')

  // Fetch keywords
  const { data: keywords = [], isLoading } = useQuery({
    queryKey: ['keywords', filterEnabled, episodeId],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filterEnabled !== 'all') {
        params.append('enabled', filterEnabled === 'enabled' ? 'true' : 'false')
      }
      if (episodeId) {
        params.append('episodeId', episodeId.toString())
      }
      const res = await fetch(`/api/keywords?${params}`)
      if (!res.ok) throw new Error('Failed to fetch keywords')
      return res.json()
    },
  })

  // Create keyword mutation
  const createMutation = useMutation({
    mutationFn: async (data: { keyword: string; weight: number }) => {
      const body: any = { ...data, enabled: true, source: 'manual' }
      if (episodeId) {
        body.episodeId = episodeId
      }
      const res = await fetch('/api/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.error || 'Failed to create keyword')
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      toast({ title: 'Keyword added successfully' })
      setShowAddDialog(false)
      setNewKeyword({ keyword: '', weight: 1 })
    },
    onError: (error: Error) => {
      toast({ 
        title: 'Failed to add keyword', 
        description: error.message,
        variant: 'destructive' 
      })
    },
  })

  // Update keyword mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, ...data }: { id: string; keyword?: string; weight?: number; enabled?: boolean }) => {
      const res = await fetch(`/api/keywords/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.error || 'Failed to update keyword')
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      toast({ title: 'Keyword updated successfully' })
      setEditingId(null)
    },
    onError: (error: Error) => {
      toast({ 
        title: 'Failed to update keyword', 
        description: error.message,
        variant: 'destructive' 
      })
    },
  })

  // Bulk operations mutation
  const bulkMutation = useMutation({
    mutationFn: async ({ action, keywordIds }: { action: string; keywordIds: string[] }) => {
      const res = await fetch('/api/keywords', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, keywordIds }),
      })
      if (!res.ok) throw new Error('Failed to perform bulk operation')
      return res.json()
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      toast({ title: data.message })
      setSelectedKeywords([])
    },
    onError: () => {
      toast({ 
        title: 'Failed to perform bulk operation', 
        variant: 'destructive' 
      })
    },
  })

  // Import keywords mutation
  const importMutation = useMutation({
    mutationFn: async (keywords: { keyword: string; weight: number }[]) => {
      const res = await fetch('/api/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords }),
      })
      if (!res.ok) throw new Error('Failed to import keywords')
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      toast({ title: `Imported ${data.count} keywords successfully` })
      setShowImportDialog(false)
      setImportText('')
    },
    onError: () => {
      toast({ 
        title: 'Failed to import keywords', 
        variant: 'destructive' 
      })
    },
  })

  // Filter keywords based on search
  const filteredKeywords = keywords.filter((kw: Keyword) =>
    kw.keyword.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Handle edit save
  const handleSaveEdit = () => {
    if (!editingId) return
    updateMutation.mutate({
      id: editingId,
      keyword: editForm.keyword,
      weight: editForm.weight,
    })
  }

  // Handle import
  const handleImport = () => {
    const lines = importText.split('\n').filter(line => line.trim())
    const keywords = lines.map(line => {
      const parts = line.split(',')
      const keyword = parts[0].trim()
      const weight = parts[1] ? parseFloat(parts[1].trim()) : 1
      return { keyword, weight: isNaN(weight) ? 1 : Math.min(1, Math.max(0, weight)) }
    })
    
    if (keywords.length === 0) {
      toast({ title: 'No keywords to import', variant: 'destructive' })
      return
    }

    importMutation.mutate(keywords)
  }

  // Toggle selection
  const toggleSelection = (id: string) => {
    setSelectedKeywords(prev =>
      prev.includes(id) ? prev.filter(k => k !== id) : [...prev, id]
    )
  }

  // Select all/none
  const selectAll = () => {
    if (selectedKeywords.length === filteredKeywords.length) {
      setSelectedKeywords([])
    } else {
      setSelectedKeywords(filteredKeywords.map((k: Keyword) => k.id))
    }
  }

  return (
    <div className="space-y-4">
      {/* Header and Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 w-64"
            />
          </div>
          <Select value={filterEnabled} onValueChange={(v: any) => setFilterEnabled(v)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="enabled">Enabled</SelectItem>
              <SelectItem value="disabled">Disabled</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          {selectedKeywords.length > 0 && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => bulkMutation.mutate({ action: 'enable', keywordIds: selectedKeywords })}
              >
                <ToggleRight className="mr-2 h-4 w-4" />
                Enable ({selectedKeywords.length})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => bulkMutation.mutate({ action: 'disable', keywordIds: selectedKeywords })}
              >
                <ToggleLeft className="mr-2 h-4 w-4" />
                Disable ({selectedKeywords.length})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => bulkMutation.mutate({ action: 'delete', keywordIds: selectedKeywords })}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete ({selectedKeywords.length})
              </Button>
            </>
          )}
          
          <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Upload className="mr-2 h-4 w-4" />
                Import
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Import Keywords</DialogTitle>
                <DialogDescription>
                  Enter keywords, one per line. Optionally add weight after comma (0-1).
                  Example: federalism, 0.8
                </DialogDescription>
              </DialogHeader>
              <Textarea
                placeholder="keyword1, 0.9\nkeyword2\nkeyword3, 0.7"
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                rows={10}
              />
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowImportDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={handleImport} disabled={importMutation.isPending}>
                  Import Keywords
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Keyword
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Keyword</DialogTitle>
                <DialogDescription>
                  Add a new keyword for tweet scraping
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="keyword">Keyword</Label>
                  <Input
                    id="keyword"
                    value={newKeyword.keyword}
                    onChange={(e) => setNewKeyword({ ...newKeyword, keyword: e.target.value })}
                    placeholder="Enter keyword..."
                  />
                </div>
                <div>
                  <Label htmlFor="weight">Weight: {newKeyword.weight.toFixed(2)}</Label>
                  <Slider
                    id="weight"
                    min={0}
                    max={1}
                    step={0.05}
                    value={[newKeyword.weight]}
                    onValueChange={(v) => setNewKeyword({ ...newKeyword, weight: v[0] })}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                  Cancel
                </Button>
                <Button 
                  onClick={() => createMutation.mutate(newKeyword)}
                  disabled={!newKeyword.keyword || createMutation.isPending}
                >
                  Add Keyword
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Keywords Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={selectedKeywords.length === filteredKeywords.length && filteredKeywords.length > 0}
                  onCheckedChange={selectAll}
                />
              </TableHead>
              <TableHead>Keyword</TableHead>
              <TableHead>Weight</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Episode</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading keywords...
                </TableCell>
              </TableRow>
            ) : filteredKeywords.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No keywords found
                </TableCell>
              </TableRow>
            ) : (
              filteredKeywords.map((keyword: Keyword) => (
                <TableRow key={keyword.id}>
                  <TableCell>
                    <Checkbox
                      checked={selectedKeywords.includes(keyword.id)}
                      onCheckedChange={() => toggleSelection(keyword.id)}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    {editingId === keyword.id ? (
                      <Input
                        value={editForm.keyword}
                        onChange={(e) => setEditForm({ ...editForm, keyword: e.target.value })}
                        className="h-8"
                      />
                    ) : (
                      keyword.keyword
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === keyword.id ? (
                      <Input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        value={editForm.weight}
                        onChange={(e) => setEditForm({ ...editForm, weight: parseFloat(e.target.value) })}
                        className="h-8 w-20"
                      />
                    ) : (
                      <Badge variant="secondary">{keyword.weight.toFixed(2)}</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={keyword.enabled ? 'default' : 'outline'}>
                      {keyword.enabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={keyword.source === 'manual' ? 'default' : 'secondary'}>
                      {keyword.source === 'manual' ? 'Manual' : 'Auto'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {keyword.episode ? (
                      <span className="text-sm">
                        Ep {keyword.episode.episodeNumber}: {keyword.episode.title}
                      </span>
                    ) : (
                      <span className="text-sm text-muted-foreground">Global</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {editingId === keyword.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={handleSaveEdit}
                        >
                          <Save className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setEditingId(null)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => {
                            setEditingId(keyword.id)
                            setEditForm({ keyword: keyword.keyword, weight: keyword.weight })
                          }}
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => updateMutation.mutate({ 
                            id: keyword.id, 
                            enabled: !keyword.enabled 
                          })}
                        >
                          {keyword.enabled ? (
                            <ToggleRight className="h-4 w-4" />
                          ) : (
                            <ToggleLeft className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Summary */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Total: {keywords.length} keywords ({keywords.filter((k: Keyword) => k.enabled).length} enabled)
        </span>
        <span>
          Showing {filteredKeywords.length} keywords
        </span>
      </div>
    </div>
  )
}