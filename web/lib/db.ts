/**
 * Prisma database client singleton
 * Ensures we don't create multiple database connections in development
 * Interacts with: All API routes and server components that need database access
 */

import { PrismaClient } from "@prisma/client"

declare global {
  var prisma: PrismaClient | undefined
}

export const prisma = global.prisma || new PrismaClient({
  log: process.env.NODE_ENV === "development" ? ["query", "error", "warn"] : ["error"],
})

if (process.env.NODE_ENV !== "production") {
  global.prisma = prisma
}

// Helper to handle database errors
export async function withDatabase<T>(
  operation: () => Promise<T>
): Promise<{ data?: T; error?: string }> {
  try {
    const data = await operation()
    return { data }
  } catch (error) {
    console.error("Database operation failed:", error)
    return { 
      error: error instanceof Error ? error.message : "Database operation failed" 
    }
  }
}