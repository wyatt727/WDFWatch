import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import os from 'os';

const prisma = new PrismaClient();

/**
 * POST /api/episodes/[id]/claude-pipeline/run
 * ULTRA SIMPLE Claude pipeline trigger - saves transcript to file, runs orchestrator
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
    
    // Save transcript to temp file FIRST
    const tempDir = os.tmpdir();
    const transcriptPath = path.join(tempDir, `transcript_${episodeId}_${Date.now()}.txt`);
    await fs.writeFile(transcriptPath, episode.transcriptText);
    
    console.log(`Saved transcript to: ${transcriptPath}`);
    
    // Run the ULTRA SIMPLE bridge script
    const scriptPath = path.join(process.cwd(), 'web', 'scripts', 'claude_pipeline_ultra_simple.py');
    
    // Build command - EXACTLY like the CLI that works
    const args = [
      scriptPath,
      '--episode-id', episodeIdentifier,
      '--stages', stages,
      '--transcript', transcriptPath,  // Pass the file path!
      '-d'  // Always use debug mode
    ];
    
    // Add video URL if available
    if (episode.videoUrl) {
      args.push('--video-url', episode.videoUrl);
    }
    
    const command = `python3 ${args.join(' ')}`;
    console.log(`Running EXACT command: ${command}`);
    
    // Spawn the process
    const pythonProcess = spawn('python3', args, {
      cwd: process.cwd(),
      env: process.env
    });
    
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
      
      // Clean up temp transcript file
      try {
        await fs.unlink(transcriptPath);
        console.log(`Cleaned up temp transcript: ${transcriptPath}`);
      } catch (e) {
        console.warn(`Could not delete temp file: ${e}`);
      }
      
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
      transcriptPath,
      message: 'Claude pipeline started',
      command: command
    });
    
  } catch (error) {
    console.error('Failed to start Claude pipeline:', error);
    return NextResponse.json(
      { error: 'Failed to start Claude pipeline' },
      { status: 500 }
    );
  }
}