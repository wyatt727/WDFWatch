'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, Save, History, TestTube, RotateCcw, FileText, Globe, Code2, GitBranch, AlertCircle } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'
import { PromptEditor } from '@/components/settings/PromptEditor'
import { ContextFileEditor } from '@/components/settings/ContextFileEditor'
import { PromptHistory } from '@/components/settings/PromptHistory'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'

// Monaco Editor for rich text editing
const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => <div className="flex items-center justify-center h-96">Loading editor...</div>
})

interface PromptTemplate {
  id: number
  key: string
  name: string
  description: string | null
  template: string
  variables: string[] | any
  isActive: boolean
  version: number
  historyCount?: number
}

interface ContextFile {
  id: number
  key: string
  name: string
  description: string | null
  content: string
  isActive: boolean
  updatedAt: string
}

const PROMPT_INFO = {
  summarization: {
    icon: '📝',
    description: 'Generates comprehensive episode summary and keywords from transcript',
    sampleData: {
      is_first_chunk: true,
      is_last_chunk: false,
      overview: 'The War, Divorce, or Federalism podcast explores critical issues of liberty and constitutional governance.',
      chunk: 'In this episode, Rick Becker discusses the importance of state sovereignty...'
    }
  },
  fewshot_generation: {
    icon: '🎯',
    description: 'Generates example tweets for classification training',
    sampleData: {
      required_examples: 40,
      overview: 'The WDF podcast focuses on liberty, constitutional rights, and federalism.',
      summary: 'This episode covers the debate over federal overreach and state rights...'
    }
  },
  tweet_classification: {
    icon: '🔍',
    description: 'Scores tweet relevancy from 0.00 to 1.00',
    sampleData: {
      topic_summary: 'Discussion about federal government overreach and state sovereignty'
    }
  },
  response_generation: {
    icon: '💬',
    description: 'Generates engaging responses to relevant tweets',
    sampleData: {
      max_length: 200,
      video_url: 'https://youtu.be/example-episode',
      podcast_overview: 'The WDF podcast explores liberty and constitutional governance.',
      summary: 'Latest episode discusses federal overreach and state rights...'
    }
  }
}

const CLAUDE_STAGES = [
  {
    id: 'classifier',
    name: 'Classifier',
    description: 'Classifies tweets as relevant or irrelevant to the podcast topics'
  },
  {
    id: 'moderator',
    name: 'Moderator',
    description: 'Reviews and moderates generated responses before publishing'
  },
  {
    id: 'responder',
    name: 'Responder',
    description: 'Generates engaging responses to relevant tweets'
  },
  {
    id: 'summarizer',
    name: 'Summarizer',
    description: 'Creates comprehensive summaries of podcast episodes'
  }
];

interface ClaudePrompt {
  id: number;
  stage: string;
  template: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  createdBy?: string;
  history?: ClaudePromptHistory[];
}

interface ClaudePromptHistory {
  id: number;
  version: number;
  template: string;
  changedBy?: string;
  changeNote?: string;
  createdAt: string;
}

interface ClaudePromptOriginal {
  stage: string;
  content: string;
  backedUpAt: string;
}

export default function PromptsSettingsPage() {
  const router = useRouter()
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [contextFiles, setContextFiles] = useState<ContextFile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null)
  const [selectedContext, setSelectedContext] = useState<ContextFile | null>(null)
  const [activeTab, setActiveTab] = useState('prompts')
  const [showHistory, setShowHistory] = useState<number | null>(null)
  
  // CLAUDE.md editor state
  const [activeClaudeStage, setActiveClaudeStage] = useState('classifier')
  const [claudePrompts, setClaudePrompts] = useState<Record<string, ClaudePrompt>>({})
  const [claudeOriginals, setClaudeOriginals] = useState<Record<string, ClaudePromptOriginal>>({})
  const [claudeEditedContent, setClaudeEditedContent] = useState<Record<string, string>>({})
  const [claudeSaveNotes, setClaudeSaveNotes] = useState<Record<string, string>>({})
  const [claudeHasChanges, setClaudeHasChanges] = useState<Record<string, boolean>>({})
  const [claudeLoading, setClaudeLoading] = useState(true)
  const [claudeSaving, setClaudeSaving] = useState(false)
  const [claudeShowHistory, setClaudeShowHistory] = useState(false)
  const [claudeShowDiff, setClaudeShowDiff] = useState(false)
  const [claudeInitialized, setClaudeInitialized] = useState(false)

  const handlePromptChange = useCallback((updatedPrompt: PromptTemplate) => {
    setSelectedPrompt(prev => ({ ...updatedPrompt, historyCount: prev?.historyCount || 0 }))
  }, [])

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      
      // Fetch prompts
      const promptsRes = await fetch('/api/settings/prompts')
      if (!promptsRes.ok) throw new Error('Failed to fetch prompts')
      const promptsData = await promptsRes.json()
      setPrompts(promptsData.prompts)
      
      // Fetch context files
      const contextRes = await fetch('/api/settings/context-files')
      if (!contextRes.ok) throw new Error('Failed to fetch context files')
      const contextData = await contextRes.json()
      setContextFiles(contextData.contextFiles)
      
      // Select first prompt by default
      if (promptsData.prompts.length > 0 && !selectedPrompt) {
        setSelectedPrompt(promptsData.prompts[0])
      }
      
      // Select first context file by default
      if (contextData.contextFiles.length > 0 && !selectedContext) {
        setSelectedContext(contextData.contextFiles[0])
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load prompts and context files',
        variant: 'destructive'
      })
    } finally {
      setIsLoading(false)
    }
  }, [selectedPrompt, selectedContext])

  useEffect(() => {
    fetchData()
    initializeClaudePrompts()
  }, [])
  
  useEffect(() => {
    if (claudeInitialized) {
      loadClaudePrompts()
    }
  }, [claudeInitialized])
  
  const initializeClaudePrompts = async () => {
    try {
      const response = await fetch('/api/prompts/init', {
        method: 'POST'
      });
      const data = await response.json();
      
      if (data.success) {
        console.log('CLAUDE prompts initialized:', data.initialized);
        if (data.errors?.length > 0) {
          console.error('CLAUDE initialization errors:', data.errors);
          toast({
            title: 'Warning',
            description: `Some CLAUDE prompts failed to initialize: ${data.errors.map((e: any) => e.stage).join(', ')}`,
            variant: 'destructive'
          });
        }
        setClaudeInitialized(true);
      }
    } catch (error) {
      console.error('Failed to initialize CLAUDE prompts:', error);
      toast({
        title: 'Error',
        description: 'Failed to initialize CLAUDE prompts',
        variant: 'destructive'
      });
    }
  };
  
  const loadClaudePrompts = async () => {
    try {
      setClaudeLoading(true);
      const response = await fetch('/api/prompts?includeHistory=true');
      
      if (!response.ok) {
        throw new Error(`Failed to load prompts: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Transform array to object keyed by stage
      const promptsByStage: Record<string, ClaudePrompt> = {};
      
      // Check if data.prompts exists and is an array
      if (data.prompts && Array.isArray(data.prompts)) {
        for (const prompt of data.prompts) {
          if (prompt.stage) {
            promptsByStage[prompt.stage] = prompt;
            // Initialize edited content
            if (!claudeEditedContent[prompt.stage]) {
              setClaudeEditedContent(prev => ({ ...prev, [prompt.stage]: prompt.template }));
            }
          }
        }
      }
      
      setClaudePrompts(promptsByStage);
      setClaudeOriginals(data.originals || {});
    } catch (error) {
      console.error('Failed to load CLAUDE prompts:', error);
      toast({
        title: 'Error',
        description: 'Failed to load CLAUDE prompts',
        variant: 'destructive'
      });
    } finally {
      setClaudeLoading(false);
    }
  };
  
  const handleClaudeEditorChange = (stage: string, value: string | undefined) => {
    if (value === undefined) return;
    
    setClaudeEditedContent(prev => ({ ...prev, [stage]: value }));
    
    // Check if content has changed
    const hasChanged = value !== claudePrompts[stage]?.template;
    setClaudeHasChanges(prev => ({ ...prev, [stage]: hasChanged }));
  };
  
  const handleClaudeSave = async (stage: string) => {
    try {
      setClaudeSaving(true);
      
      const response = await fetch('/api/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stage,
          template: claudeEditedContent[stage],
          notes: claudeSaveNotes[stage] || undefined,
          createdBy: 'web-ui'
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to save CLAUDE prompt');
      }
      
      const updated = await response.json();
      
      // Update local state
      setClaudePrompts(prev => ({ ...prev, [stage]: updated }));
      setClaudeHasChanges(prev => ({ ...prev, [stage]: false }));
      setClaudeSaveNotes(prev => ({ ...prev, [stage]: '' }));
      
      toast({
        title: 'Success',
        description: `CLAUDE prompt for ${stage} saved (v${updated.version})`
      });
      
      // Reload to get fresh data
      await loadClaudePrompts();
    } catch (error) {
      console.error('Failed to save CLAUDE prompt:', error);
      toast({
        title: 'Error',
        description: 'Failed to save CLAUDE prompt',
        variant: 'destructive'
      });
    } finally {
      setClaudeSaving(false);
    }
  };
  
  const handleClaudeRollback = async (stage: string, version: number) => {
    try {
      const response = await fetch(`/api/prompts/${stage}/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version,
          changedBy: 'web-ui'
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to rollback CLAUDE prompt');
      }
      
      toast({
        title: 'Success',
        description: `Rolled back to version ${version}`
      });
      await loadClaudePrompts();
      setClaudeShowHistory(false);
    } catch (error) {
      console.error('Failed to rollback:', error);
      toast({
        title: 'Error',
        description: 'Failed to rollback CLAUDE prompt',
        variant: 'destructive'
      });
    }
  };
  
  const handleClaudeReset = async (stage: string) => {
    try {
      const response = await fetch(`/api/prompts/${stage}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          changedBy: 'web-ui'
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to reset CLAUDE prompt');
      }
      
      toast({
        title: 'Success',
        description: 'Reset to original CLAUDE prompt'
      });
      await loadClaudePrompts();
      
      // Update editor content
      if (claudeOriginals[stage]) {
        setClaudeEditedContent(prev => ({ ...prev, [stage]: claudeOriginals[stage].content }));
      }
    } catch (error) {
      console.error('Failed to reset:', error);
      toast({
        title: 'Error',
        description: 'Failed to reset CLAUDE prompt',
        variant: 'destructive'
      });
    }
  };

  const handleSavePrompt = async (prompt: PromptTemplate) => {
    try {
      setIsSaving(true)
      
      const res = await fetch('/api/settings/prompts', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: prompt.id,
          template: prompt.template,
          description: prompt.description,
          changeNote: `Updated ${prompt.name} template`
        })
      })
      
      if (!res.ok) throw new Error('Failed to save prompt')
      
      const data = await res.json()
      
      // Update local state
      setPrompts(prompts.map(p => p.id === data.prompt.id ? { ...data.prompt, historyCount: (p.historyCount || 0) + 1 } : p))
      setSelectedPrompt({ ...data.prompt, historyCount: (selectedPrompt?.historyCount || 0) + 1 })
      
      toast({
        title: 'Success',
        description: 'Prompt template saved successfully'
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to save prompt template',
        variant: 'destructive'
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleSaveContext = async (context: ContextFile) => {
    try {
      setIsSaving(true)
      
      const res = await fetch('/api/settings/context-files', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: context.id,
          content: context.content,
          description: context.description
        })
      })
      
      if (!res.ok) throw new Error('Failed to save context file')
      
      const data = await res.json()
      
      // Update local state
      setContextFiles(contextFiles.map(c => c.id === data.contextFile.id ? data.contextFile : c))
      setSelectedContext(data.contextFile)
      
      toast({
        title: 'Success',
        description: 'Context file saved successfully'
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to save context file',
        variant: 'destructive'
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleRestoreVersion = async (promptId: number, historyId: number) => {
    try {
      const res = await fetch(`/api/settings/prompts/${promptId}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          historyId,
          changeNote: 'Restored from history'
        })
      })
      
      if (!res.ok) throw new Error('Failed to restore version')
      
      const data = await res.json()
      
      // Update local state
      setPrompts(prompts.map(p => p.id === data.prompt.id ? { ...data.prompt, historyCount: (p.historyCount || 0) + 1 } : p))
      setSelectedPrompt({ ...data.prompt, historyCount: (selectedPrompt?.historyCount || 0) + 1 })
      setShowHistory(null)
      
      toast({
        title: 'Success',
        description: 'Previous version restored successfully'
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to restore version',
        variant: 'destructive'
      })
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Prompt Management</h1>
        <p className="text-muted-foreground mt-2">
          Customize prompts and context files used by the LLM pipeline
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 max-w-2xl">
          <TabsTrigger value="prompts" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Prompts
          </TabsTrigger>
          <TabsTrigger value="context" className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Context Files
          </TabsTrigger>
          <TabsTrigger value="claude" className="flex items-center gap-2">
            <Code2 className="h-4 w-4" />
            CLAUDE.md
          </TabsTrigger>
        </TabsList>

        <TabsContent value="prompts" className="space-y-4 mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Prompt List */}
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Templates</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {prompts.map((prompt) => {
                    const info = PROMPT_INFO[prompt.key as keyof typeof PROMPT_INFO]
                    return (
                      <button
                        key={prompt.id}
                        onClick={() => {
                          setSelectedPrompt(prompt)
                          setShowHistory(null)
                        }}
                        className={`w-full text-left p-4 hover:bg-accent transition-colors ${
                          selectedPrompt?.id === prompt.id ? 'bg-accent' : ''
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">{info?.icon || '📄'}</span>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium">{prompt.name}</div>
                            <div className="text-sm text-muted-foreground truncate">
                              {prompt.description || info?.description}
                            </div>
                            <div className="flex items-center gap-2 mt-2">
                              <Badge variant="outline" className="text-xs">
                                v{prompt.version}
                              </Badge>
                              {(prompt.historyCount || 0) > 0 && (
                                <Badge variant="secondary" className="text-xs">
                                  {prompt.historyCount || 0} edits
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Prompt Editor */}
            <div className="lg:col-span-3">
              {selectedPrompt && !showHistory && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{selectedPrompt.name}</CardTitle>
                        <CardDescription>
                          {selectedPrompt.description || PROMPT_INFO[selectedPrompt.key as keyof typeof PROMPT_INFO]?.description}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowHistory(selectedPrompt.id)}
                        >
                          <History className="h-4 w-4 mr-2" />
                          History
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => handleSavePrompt(selectedPrompt)}
                          disabled={isSaving}
                        >
                          {isSaving ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Save className="h-4 w-4 mr-2" />
                          )}
                          Save
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <PromptEditor
                      prompt={selectedPrompt}
                      onChange={handlePromptChange}
                      sampleData={PROMPT_INFO[selectedPrompt.key as keyof typeof PROMPT_INFO]?.sampleData || {}}
                    />
                  </CardContent>
                </Card>
              )}

              {showHistory && selectedPrompt && (
                <PromptHistory
                  promptId={showHistory}
                  promptName={selectedPrompt.name}
                  onClose={() => setShowHistory(null)}
                  onRestore={handleRestoreVersion}
                />
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="context" className="space-y-4 mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Context File List */}
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Context Files</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {contextFiles.map((context) => (
                    <button
                      key={context.id}
                      onClick={() => setSelectedContext(context)}
                      className={`w-full text-left p-4 hover:bg-accent transition-colors ${
                        selectedContext?.id === context.id ? 'bg-accent' : ''
                      }`}
                    >
                      <div className="font-medium">{context.name}</div>
                      <div className="text-sm text-muted-foreground truncate">
                        {context.description}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Updated {new Date(context.updatedAt).toLocaleDateString()}
                      </div>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Context File Editor */}
            <div className="lg:col-span-3">
              {selectedContext && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{selectedContext.name}</CardTitle>
                        <CardDescription>
                          {selectedContext.description}
                        </CardDescription>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => handleSaveContext(selectedContext)}
                        disabled={isSaving}
                      >
                        {isSaving ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Save className="h-4 w-4 mr-2" />
                        )}
                        Save
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ContextFileEditor
                      context={selectedContext}
                      onChange={setSelectedContext}
                    />
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="claude" className="space-y-4 mt-6">
          {!claudeInitialized && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                CLAUDE prompts are being initialized from filesystem. This may take a moment...
              </AlertDescription>
            </Alert>
          )}
          
          {claudeLoading ? (
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                <p className="text-muted-foreground">Loading CLAUDE prompts...</p>
              </div>
            </div>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>CLAUDE.md Templates</CardTitle>
                  <CardDescription>
                    Edit the CLAUDE.md files used by each pipeline stage in the claude-pipeline/specialized directory
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Tabs value={activeClaudeStage} onValueChange={setActiveClaudeStage}>
                    <TabsList className="grid w-full grid-cols-4">
                      {CLAUDE_STAGES.map((stage) => (
                        <TabsTrigger key={stage.id} value={stage.id}>
                          {stage.name}
                          {claudeHasChanges[stage.id] && (
                            <Badge variant="destructive" className="ml-2 h-2 w-2 p-0 rounded-full" />
                          )}
                        </TabsTrigger>
                      ))}
                    </TabsList>

                    {CLAUDE_STAGES.map((stage) => {
                      const currentPrompt = claudePrompts[stage.id];
                      const currentOriginal = claudeOriginals[stage.id];
                      const currentContent = claudeEditedContent[stage.id] || '';
                      const hasChange = claudeHasChanges[stage.id] || false;
                      
                      return (
                        <TabsContent key={stage.id} value={stage.id} className="space-y-4">
                          <div className="space-y-4">
                            <div className="flex justify-between items-start">
                              <div>
                                <h4 className="font-medium">{stage.name} Stage</h4>
                                <p className="text-sm text-muted-foreground">{stage.description}</p>
                              </div>
                              <div className="flex items-center gap-2">
                                {currentPrompt && (
                                  <>
                                    <Badge variant="outline">
                                      v{currentPrompt.version}
                                    </Badge>
                                    <Badge variant="outline">
                                      {currentContent.length} chars
                                    </Badge>
                                    <Badge variant="outline">
                                      {currentContent.split('\n').length} lines
                                    </Badge>
                                  </>
                                )}
                              </div>
                            </div>
                            
                            <div className="border rounded-lg overflow-hidden">
                              <MonacoEditor
                                height="500px"
                                language="markdown"
                                theme="vs-dark"
                                value={currentContent}
                                onChange={(value) => handleClaudeEditorChange(stage.id, value)}
                                options={{
                                  minimap: { enabled: true },
                                  fontSize: 14,
                                  wordWrap: 'on',
                                  scrollBeyondLastLine: false,
                                  automaticLayout: true
                                }}
                              />
                            </div>

                            {hasChange && (
                              <div className="space-y-2">
                                <Textarea
                                  placeholder="Add a note about this change (optional)..."
                                  value={claudeSaveNotes[stage.id] || ''}
                                  onChange={(e) => setClaudeSaveNotes(prev => ({ ...prev, [stage.id]: e.target.value }))}
                                  rows={2}
                                />
                              </div>
                            )}

                            <div className="flex justify-between">
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  onClick={() => setClaudeShowHistory(true)}
                                  disabled={!currentPrompt?.history?.length}
                                >
                                  <History className="h-4 w-4 mr-2" />
                                  History ({currentPrompt?.history?.length || 0})
                                </Button>
                                
                                {currentOriginal && (
                                  <Button
                                    variant="outline"
                                    onClick={() => setClaudeShowDiff(true)}
                                  >
                                    <GitBranch className="h-4 w-4 mr-2" />
                                    Compare with Original
                                  </Button>
                                )}
                                
                                {currentOriginal && (
                                  <Button
                                    variant="outline"
                                    onClick={() => handleClaudeReset(stage.id)}
                                  >
                                    <RotateCcw className="h-4 w-4 mr-2" />
                                    Reset to Original
                                  </Button>
                                )}
                              </div>

                              <div className="flex gap-2">
                                {hasChange && (
                                  <Button
                                    variant="outline"
                                    onClick={() => {
                                      setClaudeEditedContent(prev => ({ 
                                        ...prev, 
                                        [stage.id]: currentPrompt?.template || '' 
                                      }));
                                      setClaudeHasChanges(prev => ({ ...prev, [stage.id]: false }));
                                    }}
                                  >
                                    Discard Changes
                                  </Button>
                                )}
                                
                                <Button
                                  onClick={() => handleClaudeSave(stage.id)}
                                  disabled={!hasChange || claudeSaving}
                                >
                                  <Save className="h-4 w-4 mr-2" />
                                  {claudeSaving ? 'Saving...' : 'Save Changes'}
                                </Button>
                              </div>
                            </div>
                          </div>
                        </TabsContent>
                      );
                    })}
                  </Tabs>
                </CardContent>
              </Card>
              
              {/* CLAUDE History Dialog */}
              <Dialog open={claudeShowHistory} onOpenChange={setClaudeShowHistory}>
                <DialogContent className="max-w-4xl max-h-[80vh]">
                  <DialogHeader>
                    <DialogTitle>Version History - {activeClaudeStage}</DialogTitle>
                    <DialogDescription>
                      View and rollback to previous versions
                    </DialogDescription>
                  </DialogHeader>
                  <ScrollArea className="h-[500px]">
                    <div className="space-y-4 pr-4">
                      {claudePrompts[activeClaudeStage]?.history?.map((entry) => (
                        <Card key={entry.id}>
                          <CardHeader>
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="flex items-center gap-2">
                                  <Badge>v{entry.version}</Badge>
                                  <span className="text-sm text-muted-foreground">
                                    {new Date(entry.createdAt).toLocaleString()}
                                  </span>
                                </div>
                                {entry.changedBy && (
                                  <p className="text-sm text-muted-foreground mt-1">
                                    By: {entry.changedBy}
                                  </p>
                                )}
                                {entry.changeNote && (
                                  <p className="text-sm mt-1">{entry.changeNote}</p>
                                )}
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleClaudeRollback(activeClaudeStage, entry.version)}
                              >
                                <RotateCcw className="h-3 w-3 mr-1" />
                                Rollback
                              </Button>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto">
                              {entry.template.substring(0, 300)}...
                            </pre>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </ScrollArea>
                </DialogContent>
              </Dialog>

              {/* CLAUDE Diff Dialog */}
              <Dialog open={claudeShowDiff} onOpenChange={setClaudeShowDiff}>
                <DialogContent className="max-w-5xl max-h-[80vh]">
                  <DialogHeader>
                    <DialogTitle>Compare with Original - {activeClaudeStage}</DialogTitle>
                    <DialogDescription>
                      Showing differences between current and original CLAUDE prompt
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="font-semibold mb-2">Original</h3>
                      <ScrollArea className="h-[500px] border rounded-md p-4">
                        <pre className="text-xs whitespace-pre-wrap">
                          {claudeOriginals[activeClaudeStage]?.content}
                        </pre>
                      </ScrollArea>
                    </div>
                    <div>
                      <h3 className="font-semibold mb-2">Current (v{claudePrompts[activeClaudeStage]?.version})</h3>
                      <ScrollArea className="h-[500px] border rounded-md p-4">
                        <pre className="text-xs whitespace-pre-wrap">
                          {claudeEditedContent[activeClaudeStage]}
                        </pre>
                      </ScrollArea>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}