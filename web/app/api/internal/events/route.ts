/**
 * Internal API route for emitting SSE events
 * Used by Python pipeline bridge to send real-time updates
 * Protected by API key authentication
 */

import { NextRequest, NextResponse } from "next/server"
import { eventEmitter } from "@/lib/event-emitter"

const INTERNAL_API_KEY = process.env.WEB_API_KEY || "development-internal-api-key"

export async function POST(request: NextRequest) {
  try {
    // Verify API key
    const apiKey = request.headers.get("X-API-Key")
    if (apiKey !== INTERNAL_API_KEY) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      )
    }

    // Get event from request body
    const event = await request.json()

    // Validate event has required type field
    if (!event.type) {
      return NextResponse.json(
        { error: "Event type is required" },
        { status: 400 }
      )
    }

    // Emit the event to all connected SSE clients
    await eventEmitter.broadcast(event)

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Failed to emit event:", error)
    return NextResponse.json(
      { error: "Failed to emit event" },
      { status: 500 }
    )
  }
}