import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// GET /api/settings/prompts/[id]/history - Get version history for a prompt
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const promptId = parseInt(params.id)
    
    if (isNaN(promptId)) {
      return NextResponse.json(
        { error: 'Invalid prompt ID' },
        { status: 400 }
      )
    }

    // Get current prompt
    const currentPrompt = await prisma.promptTemplate.findUnique({
      where: { id: promptId },
      select: { version: true, template: true, createdAt: true, createdBy: true }
    })

    if (!currentPrompt) {
      return NextResponse.json(
        { error: 'Prompt not found' },
        { status: 404 }
      )
    }

    // Get version history
    const historyEntries = await prisma.promptHistory.findMany({
      where: { promptId },
      orderBy: { version: 'desc' },
      select: {
        id: true,
        promptId: true,
        version: true,
        template: true,
        changedBy: true,
        changeNote: true,
        createdAt: true
      }
    })

    // Combine current version with history
    const history = [
      {
        id: 0, // Special ID for current version
        promptId,
        version: currentPrompt.version,
        template: currentPrompt.template,
        changedBy: currentPrompt.createdBy,
        changeNote: 'Current version',
        createdAt: currentPrompt.createdAt.toISOString(),
        isCurrent: true
      },
      ...historyEntries.map(entry => ({
        ...entry,
        createdAt: entry.createdAt.toISOString(),
        isCurrent: false
      }))
    ]

    return NextResponse.json({ history })
  } catch (error) {
    console.error('Failed to fetch prompt history:', error)
    return NextResponse.json({ error: 'Failed to fetch prompt history' }, { status: 500 })
  }
}

// POST /api/settings/prompts/[id]/history - Restore a version from history
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const promptId = parseInt(params.id)
    const body = await request.json()
    const { historyId, changeNote } = body
    
    if (isNaN(promptId) || !historyId) {
      return NextResponse.json(
        { error: 'Missing required fields: id, historyId' },
        { status: 400 }
      )
    }

    // Get the history entry to restore
    const historyEntry = await prisma.promptHistory.findUnique({
      where: { id: historyId }
    })

    if (!historyEntry || historyEntry.promptId !== promptId) {
      return NextResponse.json(
        { error: 'History entry not found' },
        { status: 404 }
      )
    }

    // Get current prompt
    const currentPrompt = await prisma.promptTemplate.findUnique({
      where: { id: promptId }
    })

    if (!currentPrompt) {
      return NextResponse.json(
        { error: 'Prompt not found' },
        { status: 404 }
      )
    }

    // Restore version in a transaction
    const result = await prisma.$transaction(async (tx) => {
      // Create history entry for current version
      await tx.promptHistory.create({
        data: {
          promptId,
          version: currentPrompt.version,
          template: currentPrompt.template,
          changedBy: 'system', // TODO: Use actual user from auth
          changeNote: `Before restoring to v${historyEntry.version}`
        }
      })

      // Update prompt with restored template
      const updatedPrompt = await tx.promptTemplate.update({
        where: { id: promptId },
        data: {
          template: historyEntry.template,
          version: currentPrompt.version + 1,
          updatedAt: new Date()
        }
      })

      // Create history entry for restoration
      await tx.promptHistory.create({
        data: {
          promptId,
          version: updatedPrompt.version,
          template: updatedPrompt.template,
          changedBy: 'system', // TODO: Use actual user from auth
          changeNote: changeNote || `Restored from v${historyEntry.version}`
        }
      })

      return updatedPrompt
    })

    return NextResponse.json({ prompt: result })
  } catch (error) {
    console.error('Failed to restore prompt version:', error)
    return NextResponse.json({ error: 'Failed to restore prompt version' }, { status: 500 })
  }
}