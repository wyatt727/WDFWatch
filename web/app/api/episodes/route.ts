/**
 * Episode API Routes
 * 
 * Handles CRUD operations for podcast episodes.
 * Integrates with: Database, Python pipeline
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { writeFile, mkdir, copyFile, access } from 'fs/promises';
import { join } from 'path';

export const dynamic = 'force-dynamic';

// Configure large body size limit for transcript uploads (50MB)
export const runtime = 'nodejs';
export const maxDuration = 60; // 60 seconds timeout

// Schema for creating an episode
const createEpisodeSchema = z.object({
  title: z.string().min(1).max(255),
  transcript: z.string().min(100),
});

// Schema for form data validation
const formDataSchema = z.object({
  title: z.string().min(1).max(255),
  videoUrl: z.string().refine(
    (val) => {
      // Accept valid URLs or @WDF_Show (case-insensitive)
      if (!val) return true; // Optional field
      const isUrl = /^https?:\/\/.+/.test(val);
      const isWdfShow = /^@wdf_show$/i.test(val);
      return isUrl || isWdfShow;
    },
    { message: 'Must be a valid URL or @WDF_Show' }
  ).optional(),
});

// Helper function to create episode directory structure for Claude pipeline
async function setupEpisodeDirectory(episodeTitle: string, transcript: string, videoUrl?: string, pipelineType: 'claude' | 'legacy' = 'legacy') {
  // Always use claude-pipeline/episodes directory - never use /episodes/
  const episodesBaseDir = join(process.cwd(), '..', 'claude-pipeline', 'episodes');
  
  let episodeDirName: string;
  let episodeDir: string;
  
  if (pipelineType === 'claude') {
    // Claude pipeline: Use sanitized title as episode identifier
    const sanitizedTitle = episodeTitle
      .replace(/[^a-zA-Z0-9\s-]/g, '') // Remove special chars
      .replace(/\s+/g, '_') // Replace spaces with underscores
      .toLowerCase()
      .substring(0, 50); // Limit length
    episodeDirName = sanitizedTitle;
    episodeDir = join(episodesBaseDir, episodeDirName);
    
    // Check if episode with this name already exists
    try {
      await access(episodeDir);
      // Directory exists, episode name is taken
      return NextResponse.json(
        { error: `Episode with title "${episodeTitle}" already exists. Please choose a different title.` },
        { status: 409 }
      );
    } catch {
      // Directory doesn't exist, we can create it
    }
    
    // Create Claude pipeline structure
    await mkdir(episodeDir, { recursive: true });
    
    // Write transcript directly in episode directory for Claude
    const transcriptPath = join(episodeDir, 'transcript.txt');
    await writeFile(transcriptPath, transcript, 'utf-8');
    
    // Copy podcast overview to episode directory for Claude
    const globalOverviewPath = join(process.cwd(), '..', 'transcripts', 'podcast_overview.txt');
    const episodeOverviewPath = join(episodeDir, 'podcast_overview.txt');
    
    try {
      await copyFile(globalOverviewPath, episodeOverviewPath);
    } catch (error) {
      console.warn('Could not copy podcast_overview.txt:', error);
      // Create a default overview if the global one doesn't exist
      const defaultOverview = '"WDF - War, Divorce, or Federalism; America at a Crossroads" is a podcast with a focus on the future of America in the context of addressing political incivility, secession, a strong National government vs strong sovereign states, etc.';
      await writeFile(episodeOverviewPath, defaultOverview, 'utf-8');
    }
    
    // Write video URL if provided
    if (videoUrl) {
      const videoUrlPath = join(episodeDir, 'video_url.txt');
      await writeFile(videoUrlPath, videoUrl, 'utf-8');
    }
    
    // Don't create EPISODE_CONTEXT.md here - the orchestrator will handle that
    
  } else {
    // Legacy pipeline structure
    const sanitizedTitle = episodeTitle
      .replace(/[^a-zA-Z0-9\s-]/g, '') // Remove special chars
      .replace(/\s+/g, '-') // Replace spaces with hyphens
      .toLowerCase()
      .substring(0, 50); // Limit length
    
    const timestamp = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    episodeDirName = `${timestamp}-${sanitizedTitle}`;
    episodeDir = join(episodesBaseDir, episodeDirName);
    
    const inputsDir = join(episodeDir, 'inputs');
    const outputsDir = join(episodeDir, 'outputs');
    const cacheDir = join(episodeDir, 'cache');
    
    // Create directories
    await mkdir(inputsDir, { recursive: true });
    await mkdir(outputsDir, { recursive: true });
    await mkdir(cacheDir, { recursive: true });
    
    // Write transcript file
    const transcriptPath = join(inputsDir, 'transcript.txt');
    await writeFile(transcriptPath, transcript, 'utf-8');
    
    // Copy podcast overview from global location
    const globalOverviewPath = join(process.cwd(), '..', 'transcripts', 'podcast_overview.txt');
    const episodeOverviewPath = join(inputsDir, 'podcast_overview.txt');
    
    try {
      await copyFile(globalOverviewPath, episodeOverviewPath);
    } catch (error) {
      console.warn('Could not copy podcast_overview.txt:', error);
      const defaultOverview = '"WDF - War, Divorce, or Federalism; America at a Crossroads" is a podcast with a focus on the future of America in the context of addressing political incivility, secession, a strong National government vs strong sovereign states, etc.';
      await writeFile(episodeOverviewPath, defaultOverview, 'utf-8');
    }
    
    // Write video URL if provided
    if (videoUrl) {
      const videoUrlPath = join(inputsDir, 'video_url.txt');
      await writeFile(videoUrlPath, videoUrl, 'utf-8');
    }
  }
  
  // Always maintain legacy files for backward compatibility
  const transcriptDir = join(process.cwd(), '..', 'transcripts');
  await mkdir(transcriptDir, { recursive: true });
  
  const legacyTranscriptPath = join(transcriptDir, 'latest.txt');
  await writeFile(legacyTranscriptPath, transcript, 'utf-8');
  
  if (videoUrl) {
    const legacyVideoUrlPath = join(transcriptDir, 'VIDEO_URL.txt');
    await writeFile(legacyVideoUrlPath, videoUrl, 'utf-8');
  }
  
  return { episodeDirName, claudeEpisodeDir: pipelineType === 'claude' ? episodeDirName : null };
}

export async function GET(req: NextRequest) {
  try {
    // Get query parameters for filtering
    const searchParams = req.nextUrl.searchParams;
    const status = searchParams.get('status');
    const limit = parseInt(searchParams.get('limit') || '20');
    const offset = parseInt(searchParams.get('offset') || '0');

    // Build where clause
    const where: any = {};
    if (status) {
      where.processingStatus = status;
    }

    // Fetch episodes with aggregated data
    const episodes = await prisma.podcastEpisode.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: limit,
      skip: offset,
      include: {
        _count: {
          select: {
            keywords_entries: true,
            tweets: true,
          },
        },
        tweets: {
          where: {
            status: 'posted',
          },
          select: {
            id: true,
          },
        },
        keywords_entries: {
          select: {
            id: true,
          },
        },
      },
    });

    // Transform the data
    const transformedEpisodes = episodes.map((episode) => ({
      id: episode.id,
      title: episode.title,
      transcriptLength: episode.transcriptText?.length || 0,
      keywordCount: episode._count.keywords_entries,
      tweetCount: episode._count.tweets,
      draftCount: 0, // TODO: Add draft count from drafts table
      postedCount: episode.tweets.length,
      processingStatus: episode.status,
      videoUrl: episode.videoUrl,
      createdAt: episode.createdAt.toISOString(),
      updatedAt: episode.updatedAt.toISOString(),
    }));

    return NextResponse.json(transformedEpisodes);
  } catch (error) {
    console.error('Failed to fetch episodes:', error);
    return NextResponse.json(
      { error: 'Failed to fetch episodes' },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get('content-type') || '';
    let title: string;
    let transcript: string;
    let videoUrl: string | undefined;
    let pipelineType: 'claude' | 'legacy' = 'claude'; // Default to Claude pipeline

    // Handle multipart form data (for file uploads)
    if (contentType.includes('multipart/form-data')) {
      const formData = await req.formData();
      
      // Extract form fields
      title = formData.get('title') as string;
      videoUrl = formData.get('videoUrl') as string;
      const pipelineTypeStr = formData.get('pipelineType') as string;
      const transcriptFile = formData.get('transcript') as File;
      
      // Override to legacy pipeline if explicitly requested
      if (pipelineTypeStr === 'legacy' && process.env.WDF_USE_CLAUDE_PIPELINE !== 'true') {
        pipelineType = 'legacy';
      }
      
      // Validate form data
      const validatedForm = formDataSchema.parse({ title, videoUrl });
      title = validatedForm.title;
      videoUrl = validatedForm.videoUrl;
      
      // Normalize @WDF_Show to consistent format
      if (videoUrl && /^@wdf_show$/i.test(videoUrl)) {
        videoUrl = '@WDF_Show';
      }
      
      // Validate file
      if (!transcriptFile || !(transcriptFile instanceof File)) {
        return NextResponse.json(
          { error: 'Transcript file is required' },
          { status: 400 }
        );
      }
      
      // Check file size (50MB limit)
      const maxFileSize = 50 * 1024 * 1024; // 50MB
      if (transcriptFile.size > maxFileSize) {
        return NextResponse.json(
          { error: `File too large. Maximum size is ${maxFileSize / (1024 * 1024)}MB` },
          { status: 413 }
        );
      }
      
      // Check file type
      if (transcriptFile.type !== 'text/plain') {
        return NextResponse.json(
          { error: 'Invalid file type. Only .txt files are allowed' },
          { status: 400 }
        );
      }
      
      // Read transcript content
      transcript = await transcriptFile.text();
      
      // Validate transcript length
      if (transcript.length < 100) {
        return NextResponse.json(
          { error: 'Transcript must be at least 100 characters' },
          { status: 400 }
        );
      }
    } 
    // Handle JSON data (legacy support)
    else {
      const body = await req.json();
      const validatedData = createEpisodeSchema.parse(body);
      title = validatedData.title;
      transcript = validatedData.transcript;
      videoUrl = body.videoUrl;
      pipelineType = body.pipelineType === 'legacy' ? 'legacy' : 'claude'; // Default to Claude pipeline
    }
    
    // Generate a unique run ID
    const runId = `episode-${Date.now()}`;
    
    // Create episode in database FIRST to get the ID
    const episode = await prisma.podcastEpisode.create({
      data: {
        title,
        transcriptText: transcript,
        status: 'pending',
        videoUrl,
        pipelineType,
      },
    });
    
    // Set up episode directory structure and files with the episode title
    const { episodeDirName, claudeEpisodeDir } = await setupEpisodeDirectory(
      title, 
      transcript, 
      videoUrl,
      pipelineType
    );
    
    // Update episode with directory information
    await prisma.podcastEpisode.update({
      where: { id: episode.id },
      data: {
        episodeDir: episodeDirName,
        claudeEpisodeDir: claudeEpisodeDir,
        claudePipelineStatus: pipelineType === 'claude' ? 'initialized' : null,
      },
    });
    
    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'episode_created',
        resourceType: 'episode',
        resourceId: episode.id,
        metadata: {
          title: episode.title,
          transcriptLength: transcript.length,
          videoUrl: videoUrl || null,
          pipelineType: pipelineType,
        },
      },
    });
    
    // Auto-trigger Claude pipeline if selected
    if (pipelineType === 'claude') {
      try {
        // Trigger Claude pipeline in background
        const pipelineResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/episodes/${episode.id}/pipeline/run`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': process.env.WEB_API_KEY || 'development',
          },
          body: JSON.stringify({
            stageId: 'full',
            force: false,
          }),
        });
        
        if (pipelineResponse.ok) {
          console.log(`Auto-triggered Claude pipeline for episode ${episode.id}`);
        } else {
          console.error(`Failed to auto-trigger Claude pipeline for episode ${episode.id}: ${pipelineResponse.statusText}`);
        }
      } catch (error) {
        console.error(`Error auto-triggering Claude pipeline for episode ${episode.id}:`, error);
        // Don't fail the episode creation if pipeline trigger fails
      }
    }
    
    return NextResponse.json({
      id: episode.id,
      title: episode.title,
      status: episode.status,
      transcriptLength: transcript.length,
      videoUrl: videoUrl || null,
      createdAt: episode.createdAt.toISOString(),
      pipelineType: pipelineType,
      autoTriggered: pipelineType === 'claude',
    });
  } catch (error) {
    console.error('Failed to create episode:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    
    // Handle specific error types
    if (error instanceof Error) {
      if (error.message.includes('ENOSPC')) {
        return NextResponse.json(
          { error: 'Server storage full. Please try again later.' },
          { status: 507 }
        );
      }
      if (error.message.includes('timeout')) {
        return NextResponse.json(
          { error: 'Upload timeout. File may be too large.' },
          { status: 408 }
        );
      }
    }
    
    return NextResponse.json(
      { error: 'Failed to create episode' },
      { status: 500 }
    );
  }
}