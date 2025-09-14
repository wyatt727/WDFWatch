import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import fs from 'fs/promises';
import path from 'path';

const prisma = new PrismaClient();

/**
 * GET /api/episodes/[id]/context
 * Get episode context for Claude pipeline
 */
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const { searchParams } = new URL(req.url);
    const contextType = searchParams.get('type') || 'episode_specific';
    const claudeMode = searchParams.get('mode');
    
    // Get context from database
    const context = await prisma.episodeContext.findFirst({
      where: {
        episodeId,
        contextType,
        ...(claudeMode ? { claudeMode } : {}),
        isActive: true
      },
      orderBy: {
        version: 'desc'
      }
    });
    
    if (!context) {
      // Try to load from file if exists
      const episode = await prisma.podcastEpisode.findUnique({
        where: { id: episodeId },
        select: { claudeEpisodeDir: true }
      });
      
      if (episode?.claudeEpisodeDir) {
        const contextPath = path.join(
          process.cwd(),
          episode.claudeEpisodeDir,
          'EPISODE_CONTEXT.md'
        );
        
        try {
          const fileContent = await fs.readFile(contextPath, 'utf-8');
          return NextResponse.json({
            contextContent: fileContent,
            contextType: 'episode_specific',
            source: 'file',
            version: 1
          });
        } catch (fileError) {
          // File doesn't exist
        }
      }
      
      return NextResponse.json(
        { error: 'Context not found' },
        { status: 404 }
      );
    }
    
    return NextResponse.json({
      contextContent: context.contextContent,
      contextType: context.contextType,
      claudeMode: context.claudeMode,
      version: context.version,
      source: 'database',
      updatedAt: context.updatedAt
    });
    
  } catch (error) {
    console.error('Failed to get episode context:', error);
    return NextResponse.json(
      { error: 'Failed to get episode context' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/episodes/[id]/context
 * Create or update episode context
 */
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const body = await req.json();
    const {
      contextContent,
      contextType = 'episode_specific',
      claudeMode
    } = body;
    
    if (!contextContent) {
      return NextResponse.json(
        { error: 'Context content is required' },
        { status: 400 }
      );
    }
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId }
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Check if context exists
    const existingContext = await prisma.episodeContext.findFirst({
      where: {
        episodeId,
        contextType,
        ...(claudeMode ? { claudeMode } : { claudeMode: null })
      }
    });
    
    let context;
    if (existingContext) {
      // Update existing context
      context = await prisma.episodeContext.update({
        where: { id: existingContext.id },
        data: {
          contextContent,
          version: existingContext.version + 1,
          isActive: true
        }
      });
    } else {
      // Create new context
      context = await prisma.episodeContext.create({
        data: {
          episodeId,
          contextType,
          contextContent,
          claudeMode,
          version: 1,
          isActive: true
        }
      });
    }
    
    // Update episode to indicate context is generated
    await prisma.podcastEpisode.update({
      where: { id: episodeId },
      data: {
        claudeContextGenerated: true
      }
    });
    
    // If episode has a Claude directory, also save to file
    if (episode.claudeEpisodeDir) {
      const contextPath = path.join(
        process.cwd(),
        episode.claudeEpisodeDir,
        'EPISODE_CONTEXT.md'
      );
      
      try {
        await fs.mkdir(path.dirname(contextPath), { recursive: true });
        await fs.writeFile(contextPath, contextContent, 'utf-8');
      } catch (fileError) {
        console.error('Failed to write context file:', fileError);
        // Continue - database write succeeded
      }
    }
    
    return NextResponse.json({
      success: true,
      contextId: context.id,
      version: context.version,
      message: 'Context saved successfully'
    });
    
  } catch (error) {
    console.error('Failed to save episode context:', error);
    return NextResponse.json(
      { error: 'Failed to save episode context' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/episodes/[id]/context
 * Deactivate episode context
 */
export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const { searchParams } = new URL(req.url);
    const contextType = searchParams.get('type') || 'episode_specific';
    const claudeMode = searchParams.get('mode');
    
    // Deactivate context
    await prisma.episodeContext.updateMany({
      where: {
        episodeId,
        contextType,
        ...(claudeMode ? { claudeMode } : {}),
        isActive: true
      },
      data: {
        isActive: false
      }
    });
    
    return NextResponse.json({
      success: true,
      message: 'Context deactivated'
    });
    
  } catch (error) {
    console.error('Failed to deactivate context:', error);
    return NextResponse.json(
      { error: 'Failed to deactivate context' },
      { status: 500 }
    );
  }
}