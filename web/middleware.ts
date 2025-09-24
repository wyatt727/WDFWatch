/**
 * Combined Middleware for Authentication & Audit Logging
 * 
 * 1. Protects routes with NextAuth authentication
 * 2. Logs all API actions to the audit_logs table
 * Integrates with: NextAuth, Database, all routes
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// API routes that modify data and should be logged
const AUDITED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];

// Extract entity information from URL
function extractEntityInfo(pathname: string): { entityType: string; entityId?: string } {
  const parts = pathname.split('/').filter(Boolean);
  
  // Remove 'api' prefix
  if (parts[0] === 'api') {
    parts.shift();
  }
  
  // Common patterns
  if (parts[0] === 'tweets' && parts[1]) {
    return { entityType: 'tweet', entityId: parts[1] };
  }
  if (parts[0] === 'drafts' && parts[1]) {
    return { entityType: 'draft_reply', entityId: parts[1] };
  }
  if (parts[0] === 'episodes' && parts[1]) {
    return { entityType: 'episode', entityId: parts[1] };
  }
  
  // Default to the first part as entity type
  return { entityType: parts[0] || 'unknown' };
}

// Extract action from method and path
function extractAction(method: string, pathname: string): string {
  const parts = pathname.split('/').filter(Boolean);
  const lastPart = parts[parts.length - 1];
  
  // Special actions
  if (lastPart === 'approve') return 'approved';
  if (lastPart === 'reject') return 'rejected';
  if (lastPart === 'process') return 'processing_started';
  
  // Standard CRUD actions
  switch (method) {
    case 'POST':
      return 'created';
    case 'PUT':
    case 'PATCH':
      return 'updated';
    case 'DELETE':
      return 'deleted';
    default:
      return 'unknown';
  }
}

export async function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  
  // Check authentication for protected routes
  const publicPaths = ['/login', '/api/auth', '/api/episodes'];
  const isPublicPath = publicPaths.some(path => pathname.startsWith(path));
  const isStaticFile = pathname.match(/\.(ico|png|jpg|jpeg|svg|css|js)$/);
  
  if (!isPublicPath && !isStaticFile && !pathname.startsWith('/_next')) {
    const token = await getToken({ 
      req: request,
      secret: process.env.NEXTAUTH_SECRET 
    });
    
    if (!token) {
      // Redirect to login if not authenticated
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('callbackUrl', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }
  
  // Continue with audit logging for API routes
  if (!pathname.startsWith('/api/')) {
    return NextResponse.next();
  }
  
  // Skip internal routes from audit logging
  if (pathname.startsWith('/api/internal/') || pathname.startsWith('/api/auth/')) {
    return NextResponse.next();
  }
  
  // Skip GET requests (read-only)
  if (!AUDITED_METHODS.includes(request.method)) {
    return NextResponse.next();
  }
  
  // Clone the request to read the body
  const requestClone = request.clone();
  let requestBody: any = null;
  
  try {
    if (requestClone.body) {
      const text = await requestClone.text();
      if (text) {
        requestBody = JSON.parse(text);
      }
    }
  } catch (error) {
    console.error('Failed to parse request body for audit:', error);
  }
  
  // Get the response
  const response = NextResponse.next();
  
  // Log the action asynchronously (don't block the response)
  if (response.status >= 200 && response.status < 400) {
    const { entityType, entityId } = extractEntityInfo(pathname);
    const action = extractAction(request.method, pathname);
    
    // Create audit log entry
    // Note: This is a simplified version. In production, you'd want to
    // queue this operation or use a more robust logging system
    fetch(`${request.nextUrl.origin}/api/internal/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.WEB_API_KEY || 'development',
      },
      body: JSON.stringify({
        action: `${entityType}_${action}`,
        entityType,
        entityId,
        userId: request.headers.get('x-user-id') || null,
        details: {
          method: request.method,
          path: pathname,
          query: Object.fromEntries(searchParams),
          body: requestBody,
          ip: request.headers.get('x-forwarded-for') || request.headers.get('x-real-ip'),
          userAgent: request.headers.get('user-agent'),
        },
      }),
    }).catch(error => {
      console.error('Failed to create audit log:', error);
    });
  }
  
  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};