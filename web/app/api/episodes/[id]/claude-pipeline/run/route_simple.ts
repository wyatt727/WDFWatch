import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';
import path from 'path';

const prisma = new PrismaClient();

/**
 * POST /api/episodes/[id]/claude-pipeline/run
 * Simplified Claude pipeline trigger - just runs the CLI command that works
 */
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Get episode from database
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        transcriptText: true,
        videoUrl: true,
        claudeEpisodeDir: true
      }
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    if (!episode.transcriptText) {
      return NextResponse.json(
        { error: 'Episode has no transcript' },
        { status: 400 }
      );
    }
    
    // Get request options
    const body = await req.json();
    const { stages = 'summarize' } = body;
    
    // Use episode directory name or create one based on ID
    const episodeIdentifier = episode.claudeEpisodeDir || `episode_${episodeId}`;
    
    // Run the simplified bridge script
    const scriptPath = path.join(process.cwd(), 'web', 'scripts', 'claude_pipeline_simple.py');
    
    // Build command - exactly like the CLI that works
    const args = [
      scriptPath,
      '--episode-id', episodeIdentifier,
      '--stages', stages,
      '-d'  // Always use debug mode
    ];
    
    // Add video URL if available
    if (episode.videoUrl) {
      args.push('--video-url', episode.videoUrl);
    }
    
    console.log(`Running Claude pipeline: python3 ${args.join(' ')}`);
    
    // Spawn the process
    const pythonProcess = spawn('python3', args, {
      cwd: process.cwd(),
      env: {
        ...process.env,
        // Pass the transcript via stdin or save to temp file
        TRANSCRIPT_TEXT: episode.transcriptText
      }
    });
    
    // Write transcript to stdin if needed
    pythonProcess.stdin.write(episode.transcriptText);
    pythonProcess.stdin.end();
    
    let output = '';
    let errorOutput = '';
    
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
      console.log(`Pipeline output: ${data}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
      errorOutput += data.toString();
      console.error(`Pipeline error: ${data}`);
    });
    
    pythonProcess.on('close', async (code) => {
      const success = code === 0;
      
      // Update episode status
      await prisma.podcastEpisode.update({
        where: { id: episodeId },
        data: {
          claudePipelineStatus: success ? 'completed' : 'failed',
          claudeEpisodeDir: episodeIdentifier
        }
      });
      
      console.log(`Pipeline finished with code ${code}`);
    });
    
    // Return immediately - pipeline runs in background
    return NextResponse.json({
      success: true,
      episodeId,
      episodeIdentifier,
      stages,
      message: 'Claude pipeline started',
      command: `orchestrator.py --episode-id ${episodeIdentifier} --stages ${stages} --video-url ${episode.videoUrl || 'N/A'} -d`
    });
    
  } catch (error) {
    console.error('Failed to start Claude pipeline:', error);
    return NextResponse.json(
      { error: 'Failed to start Claude pipeline' },
      { status: 500 }
    );
  }
}