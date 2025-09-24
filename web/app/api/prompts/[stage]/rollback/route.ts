import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// POST /api/prompts/[stage]/rollback - Rollback to specific version
export async function POST(
  request: Request,
  { params }: { params: { stage: string } }
) {
  try {
    const body = await request.json();
    const { version, changedBy = 'system' } = body;
    
    if (!version) {
      return NextResponse.json(
        { error: 'Version is required' },
        { status: 400 }
      );
    }
    
    // Find the current prompt
    const currentPrompt = await prisma.promptTemplate.findFirst({
      where: { stage: params.stage, isActive: true }
    });
    
    if (!currentPrompt) {
      return NextResponse.json(
        { error: 'Prompt not found' },
        { status: 404 }
      );
    }
    
    // Find the history entry for the requested version
    const historyEntry = await prisma.promptHistory.findFirst({
      where: {
        promptId: currentPrompt.id,
        version: version
      }
    });
    
    if (!historyEntry) {
      return NextResponse.json(
        { error: 'Version not found in history' },
        { status: 404 }
      );
    }
    
    // Create a new history entry for the current version
    await prisma.promptHistory.create({
      data: {
        promptId: currentPrompt.id,
        version: currentPrompt.version,
        template: currentPrompt.template,
        changedBy,
        changeNote: `Rollback from v${currentPrompt.version} to v${version}`
      }
    });
    
    // Update the prompt with the historical version
    const updated = await prisma.promptTemplate.update({
      where: { id: currentPrompt.id },
      data: {
        template: historyEntry.template,
        version: currentPrompt.version + 1,
        createdBy: changedBy,
        updatedAt: new Date()
      }
    });
    
    // Sync to filesystem
    await syncPromptToFile(params.stage, historyEntry.template);
    
    return NextResponse.json(updated);
  } catch (error) {
    console.error('Error rolling back prompt:', error);
    return NextResponse.json(
      { error: 'Failed to rollback prompt' },
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