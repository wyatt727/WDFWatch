import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/prompts/[stage] - Get prompt for specific stage
export async function GET(
  request: Request,
  { params }: { params: { stage: string } }
) {
  try {
    const prompt = await prisma.promptTemplate.findFirst({
      where: { 
        stage: params.stage,
        isActive: true 
      },
      include: {
        history: {
          orderBy: { createdAt: 'desc' },
          take: 10
        }
      }
    });
    
    if (!prompt) {
      return NextResponse.json(
        { error: 'Prompt not found' },
        { status: 404 }
      );
    }
    
    // Check for original
    const original = await prisma.promptOriginal.findUnique({
      where: { stage: params.stage }
    });
    
    return NextResponse.json({ prompt, original });
  } catch (error) {
    console.error('Error fetching prompt:', error);
    return NextResponse.json(
      { error: 'Failed to fetch prompt' },
      { status: 500 }
    );
  }
}

// DELETE /api/prompts/[stage] - Delete/deactivate prompt
export async function DELETE(
  request: Request,
  { params }: { params: { stage: string } }
) {
  try {
    const prompt = await prisma.promptTemplate.updateMany({
      where: { 
        stage: params.stage,
        isActive: true 
      },
      data: {
        isActive: false
      }
    });
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting prompt:', error);
    return NextResponse.json(
      { error: 'Failed to delete prompt' },
      { status: 500 }
    );
  }
}