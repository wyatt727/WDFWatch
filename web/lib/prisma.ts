/**
 * Prisma Client Singleton
 * 
 * Ensures a single Prisma instance across the application
 * Prevents creating multiple connections in development
 * 
 * Related files:
 * - /web/prisma/schema.prisma (Database schema)
 * - /web/lib/db.ts (Database utilities)
 */

import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const prisma = globalForPrisma.prisma ?? new PrismaClient()

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma