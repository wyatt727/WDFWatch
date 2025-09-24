import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';
import path from 'path';
import os from 'os';

const prisma = new PrismaClient();

/**
 * POST /api/episodes/[id]/claude-pipeline/run
 * Trigger Claude pipeline for a specific episode
 */
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Validate episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId }
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Check if transcript exists
    if (!episode.transcriptText) {
      return NextResponse.json(
        { error: 'Episode has no transcript' },
        { status: 400 }
      );
    }
    
    // Get request options
    const body = await req.json();
    const { force = false, stages = ['all'] } = body;
    
    // Update episode to use Claude pipeline
    await prisma.podcastEpisode.update({
      where: { id: episodeId },
      data: {
        pipelineType: 'claude',
        claudePipelineStatus: 'initializing'
      }
    });
    
    // Create a new pipeline run record
    const runId = `claude_${episodeId}_${Date.now()}`;
    await prisma.claudePipelineRun.create({
      data: {
        episodeId,
        runId,
        stage: 'full_pipeline',
        claudeMode: 'full',
        status: 'running',
        startedAt: new Date()
      }
    });
    
    // FIX: Setup proper environment for Claude CLI
    const homeDir = os.homedir();
    const fixedEnv = {
      ...process.env,
      // Ensure PATH includes all necessary directories for Node.js and Claude CLI
      PATH: [
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
        '/usr/sbin',
        '/sbin',
        `${homeDir}/.nvm/versions/node/v18.17.0/bin`,  // Node via nvm
        `${homeDir}/.nvm/versions/node/v20.10.0/bin`,  // Alternative Node version
        `${homeDir}/.claude/local`,  // Claude CLI location for current user
        '/home/debian/.claude/local',  // Claude CLI location for debian user
        process.env.PATH || ''
      ].join(':'),
      // Explicitly set Node.js paths
      NODE_PATH: '/usr/lib/node_modules',
      // Set Claude CLI path explicitly
      CLAUDE_CLI_PATH: '/home/debian/.claude/local/claude',
      // Ensure Python uses unbuffered output for real-time logs
      PYTHONUNBUFFERED: '1',
      // Pass through important environment variables
      DATABASE_URL: process.env.DATABASE_URL,
      WDF_WEB_MODE: 'true'
    };

    console.log('Spawning Claude pipeline with fixed environment');
    console.log('PATH:', fixedEnv.PATH);

    // Spawn the Claude pipeline process with fixed environment
    const scriptPath = path.join(process.cwd(), 'scripts', 'claude_pipeline_bridge.py');
    const pythonProcess = spawn('python3', [
      scriptPath,
      '--episode-id', episodeId.toString(),
      '--episode-dir', episode.claudeEpisodeDir || episode.title.replace(/[^a-zA-Z0-9\s-]/g, '').replace(/\s+/g, '_').toLowerCase().substring(0, 50),
      '--stage', stages.includes('all') ? 'full' : stages[0],
      ...(force ? ['--force'] : [])
    ], {
      cwd: process.cwd(),
      env: fixedEnv,
      shell: false  // Don't use shell to avoid environment issues
    });
    
    let output = '';
    let errorOutput = '';
    
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
      console.log(`Claude pipeline output: ${data}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
      console.error(`Claude pipeline error: ${data}`);
    });
    
    pythonProcess.on('close', async (code) => {
      if (code === 0) {
        // Success - update pipeline run
        await prisma.claudePipelineRun.updateMany({
          where: { runId },
          data: {
            status: 'completed',
            completedAt: new Date()
          }
        });
        
        await prisma.podcastEpisode.update({
          where: { id: episodeId },
          data: {
            claudePipelineStatus: 'completed'
          }
        });
      } else {
        // Failure - update with error
        await prisma.claudePipelineRun.updateMany({
          where: { runId },
          data: {
            status: 'failed',
            errorMessage: errorOutput,
            completedAt: new Date()
          }
        });
        
        await prisma.podcastEpisode.update({
          where: { id: episodeId },
          data: {
            claudePipelineStatus: 'failed'
          }
        });
      }
    });
    
    // Return immediately with run information
    return NextResponse.json({
      success: true,
      runId,
      episodeId,
      status: 'started',
      message: 'Claude pipeline started in background'
    });
    
  } catch (error) {
    console.error('Failed to start Claude pipeline:', error);
    return NextResponse.json(
      { error: 'Failed to start Claude pipeline' },
      { status: 500 }
    );
  }
}

/**
 * GET /api/episodes/[id]/claude-pipeline/run
 * Get Claude pipeline status for an episode
 */
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Get episode with Claude status
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        claudePipelineStatus: true,
        claudeEpisodeDir: true,
        claudeContextGenerated: true,
        pipelineType: true
      }
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Get latest pipeline runs
    const runs = await prisma.claudePipelineRun.findMany({
      where: { episodeId },
      orderBy: { startedAt: 'desc' },
      take: 5
    });
    
    // Get cost summary for this episode
    const costs = await prisma.$queryRaw`
      SELECT 
        SUM(cost_usd) as total_cost,
        COUNT(*) as run_count,
        MIN(started_at) as first_run,
        MAX(completed_at) as last_run
      FROM claude_pipeline_runs
      WHERE episode_id = ${episodeId}
      AND status = 'completed'
    `;
    
    return NextResponse.json({
      episode: {
        id: episode.id,
        title: episode.title,
        pipelineType: episode.pipelineType,
        claudeStatus: episode.claudePipelineStatus,
        claudeEpisodeDir: episode.claudeEpisodeDir,
        contextGenerated: episode.claudeContextGenerated
      },
      runs,
      costs: costs[0] || {
        total_cost: 0,
        run_count: 0,
        first_run: null,
        last_run: null
      }
    });
    
  } catch (error) {
    console.error('Failed to get Claude pipeline status:', error);
    return NextResponse.json(
      { error: 'Failed to get pipeline status' },
      { status: 500 }
    );
  }
}