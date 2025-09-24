/**
 * Audit Logs API Route
 * 
 * Fetches audit log entries with pagination and filtering.
 * Integrates with: Database
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    // Get query parameters
    const searchParams = req.nextUrl.searchParams;
    const page = parseInt(searchParams.get('page') || '1');
    const pageSize = parseInt(searchParams.get('pageSize') || '20');
    const search = searchParams.get('search') || '';
    const entityType = searchParams.get('entityType');
    const action = searchParams.get('action');
    
    // Build where clause
    const where: any = {};
    
    if (search) {
      where.OR = [
        { resourceId: parseInt(search) || undefined },
        { userId: { contains: search, mode: 'insensitive' } },
      ];
    }
    
    if (entityType && entityType !== 'all') {
      where.resourceType = entityType;
    }
    
    if (action && action !== 'all') {
      where.action = { endsWith: action };
    }
    
    // Get total count
    const total = await prisma.auditLog.count({ where });
    
    // Get paginated results
    const items = await prisma.auditLog.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: pageSize,
      skip: (page - 1) * pageSize,
    });
    
    // Transform the data
    const transformedItems = items.map((item) => ({
      id: item.id,
      action: item.action,
      entityType: item.resourceType,
      entityId: item.resourceId,
      userId: item.userId,
      details: item.metadata,
      createdAt: item.createdAt.toISOString(),
    }));
    
    return NextResponse.json({
      items: transformedItems,
      total,
      page,
      pageSize,
    });
  } catch (error) {
    console.error('Failed to fetch audit logs:', error);
    return NextResponse.json(
      { error: 'Failed to fetch audit logs' },
      { status: 500 }
    );
  }
}
