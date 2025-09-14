import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// GET /api/settings/prompts - List all prompt templates
export async function GET() {
  try {
    const prompts = await prisma.promptTemplate.findMany({
      where: { isActive: true },
      orderBy: { key: 'asc' },
      include: {
        _count: {
          select: { history: true }
        }
      }
    })

    return NextResponse.json({
      prompts: prompts.map(prompt => ({
        ...prompt,
        variables: prompt.variables || [],
        historyCount: prompt._count.history
      }))
    })
  } catch (error) {
    console.error('Failed to fetch prompts:', error)
    return NextResponse.json({ error: 'Failed to fetch prompts' }, { status: 500 })
  }
}

// POST /api/settings/prompts - Create a new prompt template
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { key, name, description, template, variables } = body

    // Validate required fields
    if (!key || !name || !template) {
      return NextResponse.json(
        { error: 'Missing required fields: key, name, template' },
        { status: 400 }
      )
    }

    // Check if key already exists
    const existing = await prisma.promptTemplate.findUnique({
      where: { key }
    })

    if (existing) {
      return NextResponse.json(
        { error: `Prompt with key "${key}" already exists` },
        { status: 409 }
      )
    }

    // Create the prompt
    const prompt = await prisma.promptTemplate.create({
      data: {
        key,
        name,
        description,
        template,
        variables: variables || [],
        createdBy: 'system' // TODO: Use actual user from auth
      }
    })

    return NextResponse.json({ prompt }, { status: 201 })
  } catch (error) {
    console.error('Failed to create prompt:', error)
    return NextResponse.json({ error: 'Failed to create prompt' }, { status: 500 })
  }
}

// PUT /api/settings/prompts - Update a prompt template
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const { id, template, description, changeNote } = body

    if (!id || !template) {
      return NextResponse.json(
        { error: 'Missing required fields: id, template' },
        { status: 400 }
      )
    }

    // Get current prompt
    const currentPrompt = await prisma.promptTemplate.findUnique({
      where: { id }
    })

    if (!currentPrompt) {
      return NextResponse.json(
        { error: 'Prompt not found' },
        { status: 404 }
      )
    }

    // Start transaction to update prompt and create history
    const result = await prisma.$transaction(async (tx) => {
      // Create history entry
      await tx.promptHistory.create({
        data: {
          promptId: id,
          version: currentPrompt.version,
          template: currentPrompt.template,
          changedBy: 'system', // TODO: Use actual user from auth
          changeNote: changeNote || 'Updated template'
        }
      })

      // Update prompt
      const updatedPrompt = await tx.promptTemplate.update({
        where: { id },
        data: {
          template,
          description: description !== undefined ? description : currentPrompt.description,
          version: currentPrompt.version + 1,
          updatedAt: new Date()
        }
      })

      return updatedPrompt
    })

    return NextResponse.json({ prompt: result })
  } catch (error) {
    console.error('Failed to update prompt:', error)
    return NextResponse.json({ error: 'Failed to update prompt' }, { status: 500 })
  }
}

// DELETE /api/settings/prompts/:id - Deactivate a prompt template
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const id = searchParams.get('id')

    if (!id) {
      return NextResponse.json(
        { error: 'Missing prompt ID' },
        { status: 400 }
      )
    }

    // Soft delete by setting isActive to false
    const prompt = await prisma.promptTemplate.update({
      where: { id: parseInt(id) },
      data: { isActive: false }
    })

    return NextResponse.json({ prompt })
  } catch (error) {
    console.error('Failed to delete prompt:', error)
    return NextResponse.json({ error: 'Failed to delete prompt' }, { status: 500 })
  }
}