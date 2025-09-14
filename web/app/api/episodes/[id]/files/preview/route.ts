/**
 * File Preview API Route
 * 
 * Provides file content preview for episode pipeline files.
 * Supports multiple file types with appropriate MIME type detection.
 * Integrates with: Episode file system, FilePreviewDialog component
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { readFile, stat } from 'fs/promises'
import { join } from 'path'
import { existsSync } from 'fs'

// Helper to determine MIME type based on file extension
function getMimeType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase()
  
  const mimeTypes: Record<string, string> = {
    'json': 'application/json',
    'md': 'text/markdown',
    'txt': 'text/plain',
    'log': 'text/plain',
    'yaml': 'text/yaml',
    'yml': 'text/yaml',
    'xml': 'text/xml',
    'html': 'text/html',
    'css': 'text/css',
    'js': 'text/javascript',
    'ts': 'text/typescript',
    'tsx': 'text/typescript',
    'jsx': 'text/javascript',
    'py': 'text/x-python',
    'sh': 'text/x-shellscript',
    'bash': 'text/x-shellscript',
  }
  
  return mimeTypes[ext || ''] || 'text/plain'
}

// File path mapping based on file key
function getFilePath(episodeDir: string, fileKey: string, isClaudePipeline: boolean): string {
  // Claude pipeline file mappings
  const claudeFileMap: Record<string, string> = {
    transcript: 'transcript.txt',
    summary: 'summary.md',
    keywords: 'keywords.json',
    tweets: 'tweets.json',
    classified: 'classified.json',
    responses: 'responses.json',
    published: 'published.json',
    // Additional files that might exist
    'CLAUDE.md': 'CLAUDE.md',
    'pipeline.log': 'pipeline.log',
    'error.log': 'error.log',
  }
  
  // Legacy pipeline file mappings
  const legacyFileMap: Record<string, string> = {
    transcript: 'inputs/transcript.txt',
    overview: 'inputs/podcast_overview.txt',
    videoUrl: 'inputs/video_url.txt',
    summary: 'outputs/summary.md',
    keywords: 'outputs/keywords.json',
    fewshots: 'outputs/fewshots.json',
    tweets: 'outputs/tweets.json',
    classified: 'outputs/classified.json',
    responses: 'outputs/responses.json',
    published: 'outputs/published.json',
  }
  
  const fileMap = isClaudePipeline ? claudeFileMap : legacyFileMap
  const filename = fileMap[fileKey]
  
  if (!filename) {
    throw new Error(`Unknown file key: ${fileKey}`)
  }
  
  return join(episodeDir, filename)
}

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id)
    const { fileKey } = await request.json()
    
    if (!fileKey) {
      return NextResponse.json({ error: 'File key is required' }, { status: 400 })
    }
    
    // Get episode details
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        episodeDir: true,
        claudeEpisodeDir: true,
      }
    })
    
    if (!episode) {
      return NextResponse.json({ error: 'Episode not found' }, { status: 404 })
    }
    
    // Determine episode directory
    let episodeDirPath: string
    const isClaudePipeline = true // Always use Claude pipeline structure
    
    if (episode.claudeEpisodeDir) {
      episodeDirPath = join(process.cwd(), '..', 'claude-pipeline', 'episodes', episode.claudeEpisodeDir)
    } else if (episode.episodeDir) {
      episodeDirPath = join(process.cwd(), '..', 'claude-pipeline', 'episodes', episode.episodeDir)
    } else {
      // Fallback to transcripts directory for legacy episodes
      episodeDirPath = join(process.cwd(), '..', 'transcripts')
    }
    
    // Get the file path
    const filePath = getFilePath(episodeDirPath, fileKey, isClaudePipeline)
    
    // Check if file exists
    if (!existsSync(filePath)) {
      // Try alternate locations for backwards compatibility
      const alternatePaths = [
        filePath.replace('/inputs/', '/'),
        filePath.replace('/outputs/', '/'),
        join(process.cwd(), '..', 'transcripts', fileKey + '.json'),
        join(process.cwd(), '..', 'transcripts', fileKey + '.txt'),
        join(process.cwd(), '..', 'transcripts', fileKey + '.md'),
      ]
      
      let foundPath: string | null = null
      for (const altPath of alternatePaths) {
        if (existsSync(altPath)) {
          foundPath = altPath
          break
        }
      }
      
      if (!foundPath) {
        return NextResponse.json({ 
          error: `File not found: ${fileKey}`,
          details: `Looked in: ${filePath}`
        }, { status: 404 })
      }
      
      // Use the found alternate path
      const content = await readFile(foundPath, 'utf-8')
      const stats = await stat(foundPath)
      
      return NextResponse.json({
        content,
        size: stats.size,
        lastModified: stats.mtime.toISOString(),
        mimeType: getMimeType(foundPath),
        filename: foundPath.split('/').pop() || fileKey,
        fileKey,
      })
    }
    
    // Read the file content
    const content = await readFile(filePath, 'utf-8')
    const stats = await stat(filePath)
    
    return NextResponse.json({
      content,
      size: stats.size,
      lastModified: stats.mtime.toISOString(),
      mimeType: getMimeType(filePath),
      filename: filePath.split('/').pop() || fileKey,
      fileKey,
    })
    
  } catch (error) {
    console.error('Failed to preview file:', error)
    return NextResponse.json({ 
      error: 'Failed to preview file',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 })
  }
}

// Support GET method for direct file downloads
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const url = new URL(request.url)
  const fileKey = url.searchParams.get('fileKey')
  
  if (!fileKey) {
    return NextResponse.json({ error: 'File key is required' }, { status: 400 })
  }
  
  // Create a POST-like request and use the POST handler
  const mockRequest = new NextRequest(request.url, {
    method: 'POST',
    body: JSON.stringify({ fileKey }),
  })
  
  return POST(mockRequest, { params })
}