/**
 * Server-Sent Events (SSE) endpoint for real-time updates
 * Implements event streaming for tweet status changes, drafts, and quota updates
 * Interacts with: useTweets hook, Python pipeline via web bridge
 */

import { NextRequest } from "next/server"
import { eventEmitter } from "@/lib/event-emitter"

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  // Generate unique client ID
  const clientId = Math.random().toString(36).substring(7)

  // Create a TransformStream for SSE
  const stream = new TransformStream()
  const writer = stream.writable.getWriter()

  // Add client to emitter
  eventEmitter.addClient(clientId, writer)

  // Send initial connection message
  const encoder = new TextEncoder()
  writer.write(encoder.encode(`: connected\n\n`))

  // Set up heartbeat to keep connection alive
  const heartbeatInterval = setInterval(async () => {
    const heartbeat = ": heartbeat\n\n"
    const encoder = new TextEncoder()
    try {
      await writer.write(encoder.encode(heartbeat))
    } catch (error) {
      clearInterval(heartbeatInterval)
      eventEmitter.removeClient(clientId)
    }
  }, 30000) // Every 30 seconds

  // Clean up on disconnect
  request.signal.addEventListener("abort", () => {
    clearInterval(heartbeatInterval)
    eventEmitter.removeClient(clientId)
    writer.close()
  })

  // Return SSE response
  return new Response(stream.readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no", // Disable Nginx buffering
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  })
}

