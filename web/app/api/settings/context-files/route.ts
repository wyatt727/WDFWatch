import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// GET /api/settings/context-files - List all context files
export async function GET() {
  try {
    const contextFiles = await prisma.contextFile.findMany({
      where: { isActive: true },
      orderBy: { key: 'asc' }
    })

    return NextResponse.json({ contextFiles })
  } catch (error) {
    console.error('Failed to fetch context files:', error)
    return NextResponse.json({ error: 'Failed to fetch context files' }, { status: 500 })
  }
}

// POST /api/settings/context-files - Create a new context file
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { key, name, description, content } = body

    // Validate required fields
    if (!key || !name || !content) {
      return NextResponse.json(
        { error: 'Missing required fields: key, name, content' },
        { status: 400 }
      )
    }

    // Check if key already exists
    const existing = await prisma.contextFile.findUnique({
      where: { key }
    })

    if (existing) {
      return NextResponse.json(
        { error: `Context file with key "${key}" already exists` },
        { status: 409 }
      )
    }

    // Create the context file
    const contextFile = await prisma.contextFile.create({
      data: {
        key,
        name,
        description,
        content,
        updatedBy: 'system' // TODO: Use actual user from auth
      }
    })

    return NextResponse.json({ contextFile }, { status: 201 })
  } catch (error) {
    console.error('Failed to create context file:', error)
    return NextResponse.json({ error: 'Failed to create context file' }, { status: 500 })
  }
}

// PUT /api/settings/context-files - Update a context file
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const { id, content, description } = body

    if (!id || content === undefined) {
      return NextResponse.json(
        { error: 'Missing required fields: id, content' },
        { status: 400 }
      )
    }

    // Update context file
    const contextFile = await prisma.contextFile.update({
      where: { id },
      data: {
        content,
        description: description !== undefined ? description : undefined,
        updatedBy: 'system', // TODO: Use actual user from auth
        updatedAt: new Date()
      }
    })

    return NextResponse.json({ contextFile })
  } catch (error) {
    console.error('Failed to update context file:', error)
    return NextResponse.json({ error: 'Failed to update context file' }, { status: 500 })
  }
}

// DELETE /api/settings/context-files/:id - Deactivate a context file
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const id = searchParams.get('id')

    if (!id) {
      return NextResponse.json(
        { error: 'Missing context file ID' },
        { status: 400 }
      )
    }

    // Soft delete by setting isActive to false
    const contextFile = await prisma.contextFile.update({
      where: { id: parseInt(id) },
      data: { isActive: false }
    })

    return NextResponse.json({ contextFile })
  } catch (error) {
    console.error('Failed to delete context file:', error)
    return NextResponse.json({ error: 'Failed to delete context file' }, { status: 500 })
  }
}