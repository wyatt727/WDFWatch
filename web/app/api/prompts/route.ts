import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/prompts - Get all prompts or by stage
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const stage = searchParams.get('stage');
    const includeHistory = searchParams.get('includeHistory') === 'true';
    
    const where = stage ? { stage, isActive: true } : { isActive: true };
    
    const prompts = await prisma.promptTemplate.findMany({
      where,
      include: includeHistory ? {
        history: {
          orderBy: { createdAt: 'desc' },
          take: 10
        }
      } : undefined,
      orderBy: { createdAt: 'desc' }
    });
    
    // Also get originals if available
    const originals = await prisma.promptOriginal.findMany();
    
    return NextResponse.json({ 
      prompts,
      originals: originals.reduce((acc: any, orig) => {
        acc[orig.stage] = orig;
        return acc;
      }, {})
    });
  } catch (error) {
    console.error('Error fetching prompts:', error);
    return NextResponse.json(
      { error: 'Failed to fetch prompts' },
      { status: 500 }
    );
  }
}

// POST /api/prompts - Create new prompt or update existing
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { stage, template, notes, createdBy = 'system' } = body;
    
    if (!stage || !template) {
      return NextResponse.json(
        { error: 'Stage and template are required' },
        { status: 400 }
      );
    }
    
    // Check if prompt exists for this stage
    const existing = await prisma.promptTemplate.findFirst({
      where: { stage, isActive: true }
    });
    
    if (existing) {
      // Create new version
      const newVersion = existing.version + 1;
      
      // Create history entry for the old version
      await prisma.promptHistory.create({
        data: {
          promptId: existing.id,
          version: existing.version,
          template: existing.template,
          changedBy: createdBy,
          changeNote: notes
        }
      });
      
      // Update the prompt with new content
      const updated = await prisma.promptTemplate.update({
        where: { id: existing.id },
        data: {
          template,
          version: newVersion,
          createdBy,
          updatedAt: new Date()
        },
        include: {
          history: {
            orderBy: { createdAt: 'desc' },
            take: 5
          }
        }
      });
      
      // Sync to filesystem
      await syncPromptToFile(stage, template);
      
      return NextResponse.json(updated);
    } else {
      // Create new prompt
      const created = await prisma.promptTemplate.create({
        data: {
          key: `claude_${stage}`,
          stage,
          name: `CLAUDE.md for ${stage}`,
          description: `Prompt template for ${stage} stage`,
          template,
          version: 1,
          createdBy,
          isActive: true
        }
      });
      
      // Sync to filesystem
      await syncPromptToFile(stage, template);
      
      return NextResponse.json(created);
    }
  } catch (error) {
    console.error('Error saving prompt:', error);
    return NextResponse.json(
      { error: 'Failed to save prompt' },
      { status: 500 }
    );
  }
}

// Helper function to sync prompts to filesystem
async function syncPromptToFile(stage: string, content: string) {
  try {
    const fs = await import('fs/promises');
    const path = await import('path');
    
    const basePath = path.join(process.cwd(), '..', 'claude-pipeline', 'specialized', stage);
    const filePath = path.join(basePath, 'CLAUDE.md');
    
    // Ensure directory exists
    await fs.mkdir(basePath, { recursive: true });
    
    // Write the file
    await fs.writeFile(filePath, content, 'utf8');
    
    console.log(`Synced prompt for ${stage} to ${filePath}`);
  } catch (error) {
    console.error(`Failed to sync prompt to file:`, error);
    // Don't throw - we want the database update to succeed even if file sync fails
  }
}