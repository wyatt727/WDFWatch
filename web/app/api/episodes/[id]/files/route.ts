/**
 * Episode Files API Route
 * 
 * Provides file status and pipeline state for episode processing visualization.
 * Integrates with: Episode file system, pipeline runs database
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { readFile, access } from 'fs/promises';
import { join } from 'path';
import { PIPELINE_STAGES, CLAUDE_PIPELINE_STAGES, LEGACY_PIPELINE_STAGES, FileReference, PipelineState } from '@/lib/types/file-management';

interface FileConfig {
  episodeDir: string;
  files: {
    // Input files
    transcript: string;
    overview: string;
    videoUrl: string;
    // Output files  
    summary: string;
    keywords: string;
    fewshots: string;
    tweets: string;
    classified: string;
    responses: string;
    published: string;
  };
}

// File path helpers
function getEpisodeFilePath(episodeDir: string, fileKey: keyof FileConfig['files'], isLegacy: boolean = false, isClaudePipeline: boolean = false): string {
  if (isLegacy) {
    // Legacy file paths in transcripts directory
    const legacyFileMap: Record<keyof FileConfig['files'], string> = {
      transcript: 'latest.txt',
      overview: 'podcast_overview.txt', 
      videoUrl: 'VIDEO_URL.txt',
      summary: 'summary.md',
      keywords: 'keywords.json',
      fewshots: 'fewshots.json',
      tweets: 'tweets.json',
      classified: 'classified.json',
      responses: 'responses.json',
      published: 'published.json'
    };
    
    return join(episodeDir, legacyFileMap[fileKey]);
  } else if (isClaudePipeline) {
    // Claude pipeline - files directly in episode directory
    const claudeFileMap: Record<keyof FileConfig['files'], string> = {
      transcript: 'transcript.txt',
      overview: 'podcast_overview.txt', 
      videoUrl: 'video_url.txt',
      summary: 'summary.md',
      keywords: 'keywords.json',
      fewshots: '', // Not used in Claude pipeline
      tweets: 'tweets.json',
      classified: 'classified.json',
      responses: 'responses.json',
      published: 'published.json'
    };
    
    return claudeFileMap[fileKey] ? join(episodeDir, claudeFileMap[fileKey]) : '';
  } else {
    // Legacy episode-specific directory structure with subdirs
    const fileMap: Record<keyof FileConfig['files'], string> = {
      // Inputs
      transcript: 'inputs/transcript.txt',
      overview: 'inputs/podcast_overview.txt', 
      videoUrl: 'inputs/video_url.txt',
      // Outputs
      summary: 'outputs/summary.md',
      keywords: 'outputs/keywords.json',
      fewshots: 'outputs/fewshots.json',
      tweets: 'outputs/tweets.json',
      classified: 'outputs/classified.json',
      responses: 'outputs/responses.json',
      published: 'outputs/published.json'
    };
    
    return join(episodeDir, fileMap[fileKey]);
  }
}

async function checkFileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function getFileInfo(path: string, key: string, episodeDir?: string): Promise<FileReference> {
  let finalPath = path;
  let exists = await checkFileExists(path);
  
  // For Claude episodes, if file doesn't exist in expected location, check root directory
  if (!exists && episodeDir && path.includes('/inputs/')) {
    const rootPath = path.replace('/inputs/', '/');
    const rootExists = await checkFileExists(rootPath);
    if (rootExists) {
      finalPath = rootPath;
      exists = true;
    }
  }
  
  if (!exists) {
    return {
      key,
      path: finalPath,
      exists: false
    };
  }
  
  try {
    const content = await readFile(finalPath, 'utf-8');
    const stats = await import('fs').then(fs => fs.promises.stat(finalPath));
    
    return {
      key,
      path: finalPath,
      exists: true,
      size: stats.size,
      lastModified: stats.mtime,
      preview: content.substring(0, 500)
    };
  } catch (error) {
    return {
      key,
      path: finalPath,
      exists: false
    };
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        episodeDir: true,
        claudeEpisodeDir: true,
        videoUrl: true
      }
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Get episode directory and pipeline type
    let episodeDirPath: string;
    let isClaudePipeline: boolean;
    
    // Always use Claude pipeline - we're not using /episodes/ anymore
    isClaudePipeline = true;
    
    if (episode.claudeEpisodeDir) {
      // Claude pipeline with episode-specific directory
      episodeDirPath = process.env.EPISODES_DIR
        ? join(process.env.EPISODES_DIR, episode.claudeEpisodeDir)
        : join(process.cwd(), '..', 'claude-pipeline', 'episodes', episode.claudeEpisodeDir);
    } else if (episode.episodeDir) {
      // Legacy field but still use claude-pipeline directory
      episodeDirPath = process.env.EPISODES_DIR
        ? join(process.env.EPISODES_DIR, episode.episodeDir)
        : join(process.cwd(), '..', 'claude-pipeline', 'episodes', episode.episodeDir);
    } else {
      // Fallback to legacy transcripts directory
      episodeDirPath = process.env.EPISODES_DIR
        ? process.env.EPISODES_DIR.replace('/episodes', '/transcripts')
        : join(process.cwd(), '..', 'transcripts');
      isClaudePipeline = false;
    }
    
    // Build file configuration based on pipeline type
    const fileConfig: FileConfig = {
      episodeDir: episodeDirPath,
      files: {} as FileConfig['files']
    };
    
    if (isClaudePipeline) {
      // Claude pipeline file structure - no overview/videoUrl files, context is in CLAUDE.md
      fileConfig.files = {
        transcript: getEpisodeFilePath(episodeDirPath, 'transcript', false, true),
        overview: '', // Not used in Claude pipeline - context is embedded
        videoUrl: '', // Not used as file - comes from database
        summary: getEpisodeFilePath(episodeDirPath, 'summary', false, true),
        keywords: getEpisodeFilePath(episodeDirPath, 'keywords', false, true),
        fewshots: '', // Not used in Claude pipeline - no few-shots needed
        tweets: getEpisodeFilePath(episodeDirPath, 'tweets', false, true),
        classified: getEpisodeFilePath(episodeDirPath, 'classified', false, true),
        responses: getEpisodeFilePath(episodeDirPath, 'responses', false, true),
        published: getEpisodeFilePath(episodeDirPath, 'published', false, true)
      };
    } else {
      // Legacy pipeline file structure
      const isLegacyMode = !episode.episodeDir; // True if using transcripts directory
      fileConfig.files = {
        transcript: getEpisodeFilePath(episodeDirPath, 'transcript', isLegacyMode),
        overview: getEpisodeFilePath(episodeDirPath, 'overview', isLegacyMode),
        videoUrl: getEpisodeFilePath(episodeDirPath, 'videoUrl', isLegacyMode),
        summary: getEpisodeFilePath(episodeDirPath, 'summary', isLegacyMode),
        keywords: getEpisodeFilePath(episodeDirPath, 'keywords', isLegacyMode),
        fewshots: getEpisodeFilePath(episodeDirPath, 'fewshots', isLegacyMode),
        tweets: getEpisodeFilePath(episodeDirPath, 'tweets', isLegacyMode),
        classified: getEpisodeFilePath(episodeDirPath, 'classified', isLegacyMode),
        responses: getEpisodeFilePath(episodeDirPath, 'responses', isLegacyMode),
        published: getEpisodeFilePath(episodeDirPath, 'published', isLegacyMode)
      };
    }
    
    // Get file information for all files (skip empty paths)
    const files: Record<string, FileReference> = {};
    
    for (const [key, path] of Object.entries(fileConfig.files)) {
      if (path) { // Only check files that have actual paths
        files[key] = await getFileInfo(path, key, episodeDirPath);
      } else {
        // Create placeholder for files not used in this pipeline type
        files[key] = {
          key,
          path: '',
          exists: false
        };
      }
    }
    
    // Get pipeline runs from database
    const pipelineRuns = await prisma.pipelineRun.findMany({
      where: { episodeId },
      orderBy: { startedAt: 'desc' }
    });
    
    // Build pipeline state
    const pipelineState: PipelineState = {
      stages: {},
      currentStage: undefined,
      startedAt: undefined,
      completedAt: undefined
    };
    
    // Get the latest run for each stage
    const stageRuns = new Map<string, any>();
    for (const run of pipelineRuns) {
      if (!stageRuns.has(run.stage)) {
        stageRuns.set(run.stage, run);
      }
    }
    
    // Build stage states - use correct stages for pipeline type
    const stages = isClaudePipeline ? CLAUDE_PIPELINE_STAGES : LEGACY_PIPELINE_STAGES;
    for (const stageConfig of stages) {
      const run = stageRuns.get(stageConfig.id);
      
      if (run) {
        pipelineState.stages[stageConfig.id] = {
          status: run.status as any,
          lastRun: run.startedAt.toISOString(),
          duration: run.completedAt ? 
            run.completedAt.getTime() - run.startedAt.getTime() : 
            undefined,
          error: run.errorMessage || undefined
        };
        
        // Set current stage to the one that's running
        if (run.status === 'running') {
          pipelineState.currentStage = stageConfig.id;
        }
      } else {
        // Check if outputs exist to determine if stage was completed
        const hasAllOutputs = stageConfig.outputs.every(outputKey => 
          files[outputKey]?.exists
        );
        
        pipelineState.stages[stageConfig.id] = {
          status: hasAllOutputs ? 'completed' : 'pending'
        };
      }
    }
    
    return NextResponse.json({
      files,
      pipelineState,
      fileConfig,
      pipelineType: isClaudePipeline ? 'claude' : 'legacy'
    });
    
  } catch (error) {
    console.error('Failed to fetch episode files:', error);
    
    return NextResponse.json(
      { error: 'Failed to fetch episode files' },
      { status: 500 }
    );
  }
}