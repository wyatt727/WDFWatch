import { NextRequest, NextResponse } from 'next/server'

// File upload system temporarily disabled during schema migration
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return NextResponse.json({ 
    error: 'File upload system under migration - use new episode upload instead' 
  }, { status: 501 })
}