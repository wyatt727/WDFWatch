/**
 * Internal Audit API Route
 * 
 * Creates audit log entries. Only accessible internally.
 * Integrates with: Database, middleware.ts
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';

// Schema for audit log entry
const auditLogSchema = z.object({
  action: z.string(),
  entityType: z.string(),
  entityId: z.string().optional(),
  userId: z.string().nullable().optional(),
  details: z.record(z.any()).optional(),
});

// Verify internal API key
function verifyApiKey(request: NextRequest): boolean {
  const apiKey = request.headers.get('X-API-Key');
  const expectedKey = process.env.WEB_API_KEY || 'development';
  return apiKey === expectedKey;
}

export async function POST(req: NextRequest) {
  // Verify this is an internal request
  if (!verifyApiKey(req)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }
  
  try {
    const body = await req.json();
    
    // Validate input
    const validatedData = auditLogSchema.parse(body);
    
    // Create audit log entry
    const auditLog = await prisma.auditLog.create({
      data: {
        action: validatedData.action,
        resourceType: validatedData.entityType,
        resourceId: validatedData.entityId ? parseInt(validatedData.entityId) : null,
        userId: validatedData.userId,
        metadata: validatedData.details || {},
      },
    });
    
    return NextResponse.json({
      id: auditLog.id,
      createdAt: auditLog.createdAt.toISOString(),
    });
  } catch (error) {
    console.error('Failed to create audit log:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to create audit log' },
      { status: 500 }
    );
  }
}