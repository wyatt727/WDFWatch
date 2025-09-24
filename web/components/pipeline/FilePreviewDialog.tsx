/**
 * Enhanced File Preview Dialog Component
 * 
 * Provides beautiful file preview with:
 * - Markdown rendering with GitHub flavored markdown
 * - Syntax highlighting for code/JSON files
 * - Copy to clipboard functionality
 * - Download file capability
 * - Smart file type detection
 * 
 * Integrates with: File preview API, PipelineVisualizer
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Download, 
  Copy, 
  FileText, 
  CheckCircle2, 
  FileJson,
  FileCode,
  AlertCircle,
  Eye,
  Code
} from 'lucide-react'
import { toast } from '@/components/ui/use-toast'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface FilePreviewDialogProps {
  episodeId: number
  fileKey: string
  fileName: string
  onClose: () => void
}

interface FileInfo {
  content: string
  size: number
  lastModified: string
  mimeType: string
  filename: string
  fileKey: string
}

// Detect file type from extension or mime type
function getFileType(filename: string, mimeType: string): 'markdown' | 'json' | 'code' | 'text' {
  const ext = filename.split('.').pop()?.toLowerCase()
  
  if (ext === 'md' || mimeType === 'text/markdown') return 'markdown'
  if (ext === 'json' || mimeType === 'application/json') return 'json'
  if (['js', 'ts', 'tsx', 'jsx', 'py', 'sh', 'bash', 'css', 'html', 'xml', 'yaml', 'yml'].includes(ext || '')) return 'code'
  
  return 'text'
}

// Get language for syntax highlighting
function getLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase()
  
  const languageMap: Record<string, string> = {
    'js': 'javascript',
    'ts': 'typescript',
    'tsx': 'tsx',
    'jsx': 'jsx',
    'py': 'python',
    'sh': 'bash',
    'bash': 'bash',
    'css': 'css',
    'html': 'html',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'md': 'markdown',
    'txt': 'text',
  }
  
  return languageMap[ext || ''] || 'text'
}

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FilePreviewDialog({ 
  episodeId, 
  fileKey, 
  fileName, 
  onClose 
}: FilePreviewDialogProps) {
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'preview' | 'raw'>('preview')

  const fetchFileContent = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const res = await fetch(`/api/episodes/${episodeId}/files/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileKey })
      })
      
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.error || 'Failed to load file')
      }
      
      const data = await res.json()
      setFileInfo(data)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load file content'
      setError(errorMessage)
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive'
      })
    } finally {
      setIsLoading(false)
    }
  }, [episodeId, fileKey])

  useEffect(() => {
    fetchFileContent()
  }, [fetchFileContent])

  const handleCopy = async () => {
    if (!fileInfo) return
    
    try {
      await navigator.clipboard.writeText(fileInfo.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      toast({
        title: 'Copied!',
        description: 'File content copied to clipboard'
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to copy content',
        variant: 'destructive'
      })
    }
  }

  const handleDownload = () => {
    if (!fileInfo) return
    
    const blob = new Blob([fileInfo.content], { type: fileInfo.mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileInfo.filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    toast({
      title: 'Downloaded!',
      description: `${fileInfo.filename} has been downloaded`
    })
  }

  const renderContent = () => {
    if (!fileInfo) return null
    
    const fileType = getFileType(fileInfo.filename, fileInfo.mimeType)
    
    // For preview tab, render based on file type
    if (activeTab === 'preview') {
      switch (fileType) {
        case 'markdown':
          return (
            <div className="prose prose-sm dark:prose-invert prose-pre:bg-transparent prose-pre:p-0 max-w-none p-6">
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '')
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        {...props}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    )
                  },
                  // Ensure proper rendering of headers
                  h1: ({children}) => <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>,
                  h2: ({children}) => <h2 className="text-xl font-semibold mt-5 mb-3">{children}</h2>,
                  h3: ({children}) => <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>,
                  p: ({children}) => <p className="mb-4">{children}</p>,
                  ul: ({children}) => <ul className="list-disc pl-6 mb-4">{children}</ul>,
                  ol: ({children}) => <ol className="list-decimal pl-6 mb-4">{children}</ol>,
                  li: ({children}) => <li className="mb-1">{children}</li>,
                  blockquote: ({children}) => <blockquote className="border-l-4 border-gray-300 pl-4 italic my-4">{children}</blockquote>,
                  hr: () => <hr className="my-6 border-gray-300" />,
                }}
              >
                {fileInfo.content}
              </ReactMarkdown>
            </div>
          )
          
        case 'json':
          try {
            const jsonContent = JSON.parse(fileInfo.content)
            return (
              <div className="w-full h-full overflow-auto bg-[#282c34] rounded-md">
                <SyntaxHighlighter
                  style={oneDark}
                  language="json"
                  customStyle={{ 
                    margin: 0, 
                    borderRadius: 0, 
                    background: '#282c34',
                    padding: '1.5rem',
                    fontSize: '0.875rem',
                    minWidth: 'fit-content'
                  }}
                  showLineNumbers
                  wrapLines
                >
                  {JSON.stringify(jsonContent, null, 2)}
                </SyntaxHighlighter>
              </div>
            )
          } catch {
            // If JSON is invalid, show as text
            return (
              <pre className="text-sm font-mono whitespace-pre-wrap break-words p-6 bg-muted/50">
                {fileInfo.content}
              </pre>
            )
          }
          
        case 'code':
          return (
            <div className="w-full h-full overflow-auto bg-[#282c34] rounded-md">
              <SyntaxHighlighter
                style={oneDark}
                language={getLanguage(fileInfo.filename)}
                customStyle={{ 
                  margin: 0, 
                  borderRadius: 0, 
                  background: '#282c34',
                  padding: '1.5rem',
                  fontSize: '0.875rem',
                  minWidth: 'fit-content'
                }}
                showLineNumbers
                wrapLines
              >
                {fileInfo.content}
              </SyntaxHighlighter>
            </div>
          )
          
        default:
          return (
            <pre className="text-sm font-mono whitespace-pre-wrap break-words p-6">
              {fileInfo.content}
            </pre>
          )
      }
    }
    
    // For raw tab, always show plain text
    return (
      <pre className="text-sm font-mono whitespace-pre p-6 bg-muted/50 overflow-auto h-full">
        {fileInfo.content}
      </pre>
    )
  }

  const getFileIcon = () => {
    if (!fileInfo) return <FileText className="h-5 w-5" />
    
    const fileType = getFileType(fileInfo.filename, fileInfo.mimeType)
    switch (fileType) {
      case 'json':
        return <FileJson className="h-5 w-5 text-yellow-500" />
      case 'code':
        return <FileCode className="h-5 w-5 text-blue-500" />
      case 'markdown':
        return <FileText className="h-5 w-5 text-purple-500" />
      default:
        return <FileText className="h-5 w-5" />
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-5xl h-[90vh] flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            {getFileIcon()}
            <span className="truncate">{fileName}</span>
          </DialogTitle>
          <DialogDescription className="flex items-center gap-3 mt-2 flex-wrap">
            {fileInfo && (
              <>
                <Badge variant="outline" className="text-xs">
                  {formatFileSize(fileInfo.size)}
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  {getFileType(fileInfo.filename, fileInfo.mimeType).toUpperCase()}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  Modified: {new Date(fileInfo.lastModified).toLocaleString()}
                </span>
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden px-6">
          {isLoading ? (
            <div className="space-y-3 py-6">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          ) : error ? (
            <Alert variant="destructive" className="my-6">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : fileInfo ? (
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'preview' | 'raw')} className="flex flex-col h-full">
              <TabsList className="grid w-full max-w-[400px] grid-cols-2 mx-auto my-4">
                <TabsTrigger value="preview" className="flex items-center gap-2">
                  <Eye className="h-4 w-4" />
                  Preview
                </TabsTrigger>
                <TabsTrigger value="raw" className="flex items-center gap-2">
                  <Code className="h-4 w-4" />
                  Raw
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="preview" className="flex-1 mt-0 mb-4 overflow-hidden">
                {/* For code/JSON, use direct div with overflow, for markdown use ScrollArea */}
                {fileInfo && ['json', 'code'].includes(getFileType(fileInfo.filename, fileInfo.mimeType)) ? (
                  <div className="h-full w-full rounded-md border bg-background overflow-hidden">
                    {renderContent()}
                  </div>
                ) : (
                  <ScrollArea className="h-full w-full rounded-md border bg-background">
                    {renderContent()}
                  </ScrollArea>
                )}
              </TabsContent>
              
              <TabsContent value="raw" className="flex-1 mt-0 mb-4 overflow-hidden">
                <div className="h-full w-full rounded-md border bg-background overflow-hidden">
                  {renderContent()}
                </div>
              </TabsContent>
            </Tabs>
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-2 px-6 py-4 border-t mt-auto">
          <div className="text-xs text-muted-foreground">
            {fileInfo && (
              <span>File: {fileInfo.fileKey}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              disabled={isLoading || !fileInfo || !!error}
            >
              {copied ? (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4 mr-2" />
                  Copy
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={isLoading || !fileInfo || !!error}
            >
              <Download className="h-4 w-4 mr-2" />
              Download
            </Button>
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}