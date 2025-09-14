'use client'

import { useState, useRef } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Upload, FileText, AlertCircle } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'

interface FileUploadDialogProps {
  fileKey: string
  fileName: string
  onUpload: (file: File) => void
  onClose: () => void
}

const FILE_TYPES: Record<string, {
  accept: string
  maxSize: number
  description: string
}> = {
  transcript: {
    accept: '.txt,.md',
    maxSize: 10 * 1024 * 1024, // 10MB
    description: 'Text file containing the podcast transcript'
  },
  overview: {
    accept: '.txt,.md',
    maxSize: 1 * 1024 * 1024, // 1MB
    description: 'General description of the podcast'
  },
  videoUrl: {
    accept: '.txt',
    maxSize: 1024, // 1KB
    description: 'Text file containing the YouTube URL'
  },
  summary: {
    accept: '.md,.txt',
    maxSize: 5 * 1024 * 1024, // 5MB
    description: 'Generated episode summary (markdown)'
  },
  keywords: {
    accept: '.json',
    maxSize: 100 * 1024, // 100KB
    description: 'JSON array of keywords'
  },
  fewshots: {
    accept: '.json',
    maxSize: 500 * 1024, // 500KB
    description: 'JSON array of classification examples'
  },
  tweets: {
    accept: '.json',
    maxSize: 10 * 1024 * 1024, // 10MB
    description: 'JSON array of scraped tweets'
  },
  classified: {
    accept: '.json',
    maxSize: 10 * 1024 * 1024, // 10MB
    description: 'JSON array of classified tweets'
  },
  responses: {
    accept: '.json',
    maxSize: 5 * 1024 * 1024, // 5MB
    description: 'JSON array of generated responses'
  }
}

export function FileUploadDialog({ 
  fileKey, 
  fileName, 
  onUpload, 
  onClose 
}: FileUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const fileType = FILE_TYPES[fileKey] || {
    accept: '*',
    maxSize: 50 * 1024 * 1024,
    description: 'Any file type'
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      validateAndSetFile(droppedFile)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      validateAndSetFile(selectedFile)
    }
  }

  const validateAndSetFile = (selectedFile: File) => {
    // Check file size
    if (selectedFile.size > fileType.maxSize) {
      toast({
        title: 'File too large',
        description: `Maximum size is ${(fileType.maxSize / 1024 / 1024).toFixed(1)}MB`,
        variant: 'destructive'
      })
      return
    }
    
    // Check file type
    const extension = `.${selectedFile.name.split('.').pop()?.toLowerCase()}`
    const acceptedTypes = fileType.accept.split(',')
    
    if (fileType.accept !== '*' && !acceptedTypes.includes(extension)) {
      toast({
        title: 'Invalid file type',
        description: `Accepted types: ${fileType.accept}`,
        variant: 'destructive'
      })
      return
    }
    
    setFile(selectedFile)
  }

  const handleUpload = () => {
    if (file) {
      onUpload(file)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload File</DialogTitle>
          <DialogDescription>
            Replace <strong>{fileName}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {fileType.description}
              <br />
              Max size: {(fileType.maxSize / 1024 / 1024).toFixed(1)}MB
              {fileType.accept !== '*' && (
                <>
                  <br />
                  Accepted: {fileType.accept}
                </>
              )}
            </AlertDescription>
          </Alert>

          <div
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
              transition-colors
              ${dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'}
              ${file ? 'bg-accent' : 'hover:bg-accent/50'}
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={fileType.accept}
              onChange={handleFileSelect}
              className="hidden"
            />
            
            {file ? (
              <div className="space-y-2">
                <FileText className="h-8 w-8 mx-auto text-primary" />
                <p className="font-medium">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Drag and drop a file here, or click to select
                </p>
              </div>
            )}
          </div>

          {fileKey === 'transcript' && (
            <Alert>
              <AlertDescription>
                Uploading a new transcript will reset all downstream pipeline stages.
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file}>
            <Upload className="h-4 w-4 mr-2" />
            Upload
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}