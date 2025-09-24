import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// POST /api/prompts/[stage]/reset - Reset to original
export async function POST(
  request: Request,
  { params }: { params: { stage: string } }
) {
  try {
    const body = await request.json();
    const { changedBy = 'system' } = body;
    
    // Find the original
    const original = await prisma.promptOriginal.findUnique({
      where: { stage: params.stage }
    });
    
    if (!original) {
      return NextResponse.json(
        { error: 'Original prompt not found' },
        { status: 404 }
      );
    }
    
    // Find the current prompt
    const currentPrompt = await prisma.promptTemplate.findFirst({
      where: { stage: params.stage, isActive: true }
    });
    
    if (currentPrompt) {
      // Create history entry for current version
      await prisma.promptHistory.create({
        data: {
          promptId: currentPrompt.id,
          version: currentPrompt.version,
          template: currentPrompt.template,
          changedBy,
          changeNote: 'Reset to original'
        }
      });
      
      // Update with original content
      const updated = await prisma.promptTemplate.update({
        where: { id: currentPrompt.id },
        data: {
          template: original.content,
          version: currentPrompt.version + 1,
          createdBy: changedBy,
          updatedAt: new Date()
        }
      });
      
      // Sync to filesystem
      await syncPromptToFile(params.stage, original.content);
      
      return NextResponse.json(updated);
    } else {
      // Create new prompt from original
      const created = await prisma.promptTemplate.create({
        data: {
          key: `claude_${params.stage}`,
          stage: params.stage,
          name: `CLAUDE.md for ${params.stage}`,
          description: `Prompt template for ${params.stage} stage`,
          template: original.content,
          version: 1,
          createdBy: changedBy,
          isActive: true
        }
      });
      
      // Sync to filesystem
      await syncPromptToFile(params.stage, original.content);
      
      return NextResponse.json(created);
    }
  } catch (error) {
    console.error('Error resetting prompt:', error);
    return NextResponse.json(
      { error: 'Failed to reset prompt' },
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
  }
}