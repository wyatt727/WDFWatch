import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// POST /api/prompts/init - Initialize prompts from filesystem
export async function POST(request: Request) {
  try {
    const fs = await import('fs/promises');
    const path = await import('path');
    
    const stages = ['classifier', 'moderator', 'responder', 'summarizer'];
    const initialized: any[] = [];
    const errors: any[] = [];
    
    for (const stage of stages) {
      try {
        const basePath = path.join(process.cwd(), '..', 'claude-pipeline', 'specialized', stage);
        const filePath = path.join(basePath, 'CLAUDE.md');
        const backupPath = path.join(basePath, 'CLAUDE.md.original');
        
        // Check if file exists
        const fileExists = await fs.access(filePath).then(() => true).catch(() => false);
        
        if (!fileExists) {
          errors.push({ stage, error: 'File not found' });
          continue;
        }
        
        // Read the current content
        const content = await fs.readFile(filePath, 'utf8');
        
        // Check if we already have a backup
        const existingOriginal = await prisma.promptOriginal.findUnique({
          where: { stage }
        });
        
        if (!existingOriginal) {
          // Create backup in database
          await prisma.promptOriginal.create({
            data: {
              stage,
              content,
              filePath: backupPath
            }
          });
          
          // Create physical backup file
          await fs.copyFile(filePath, backupPath);
          
          console.log(`Backed up original for ${stage}`);
        }
        
        // Check if we have an active prompt in database
        const existingPrompt = await prisma.promptTemplate.findFirst({
          where: { stage, isActive: true }
        });
        
        if (!existingPrompt) {
          // Create initial prompt in database
          const created = await prisma.promptTemplate.create({
            data: {
              key: `claude_${stage}`,
              stage,
              name: `CLAUDE.md for ${stage}`,
              description: `Prompt template for ${stage} stage`,
              template: content,
              version: 1,
              createdBy: 'system',
              isActive: true
            }
          });
          
          initialized.push({
            stage,
            status: 'created',
            version: created.version
          });
        } else {
          // Check if file content differs from database
          if (existingPrompt.template !== content) {
            // File has been modified outside of UI - sync to database
            await prisma.promptHistory.create({
              data: {
                promptId: existingPrompt.id,
                version: existingPrompt.version,
                template: existingPrompt.template,
                changedBy: 'system',
                changeNote: 'File system sync - external modification detected'
              }
            });
            
            const updated = await prisma.promptTemplate.update({
              where: { id: existingPrompt.id },
              data: {
                template: content,
                version: existingPrompt.version + 1,
                updatedAt: new Date()
              }
            });
            
            initialized.push({
              stage,
              status: 'synced',
              version: updated.version
            });
          } else {
            initialized.push({
              stage,
              status: 'unchanged',
              version: existingPrompt.version
            });
          }
        }
      } catch (error: any) {
        errors.push({ stage, error: error.message });
        console.error(`Error initializing ${stage}:`, error);
      }
    }
    
    return NextResponse.json({
      success: true,
      initialized,
      errors
    });
  } catch (error) {
    console.error('Error initializing prompts:', error);
    return NextResponse.json(
      { error: 'Failed to initialize prompts' },
      { status: 500 }
    );
  }
}