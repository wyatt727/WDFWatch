/**
 * Event Emitter for Server-Sent Events
 * 
 * Singleton pattern for broadcasting real-time updates to connected clients
 * Used by: /api/events/route.ts, /api/internal/events/route.ts
 */

// Event emitter singleton for broadcasting events
export class EventEmitter {
  private static instance: EventEmitter
  private clients: Map<string, WritableStreamDefaultWriter> = new Map()

  static getInstance(): EventEmitter {
    if (!EventEmitter.instance) {
      EventEmitter.instance = new EventEmitter()
    }
    return EventEmitter.instance
  }

  addClient(clientId: string, writer: WritableStreamDefaultWriter) {
    this.clients.set(clientId, writer)
    console.log(`SSE client connected: ${clientId}`)
  }

  removeClient(clientId: string) {
    this.clients.delete(clientId)
    console.log(`SSE client disconnected: ${clientId}`)
  }

  async emit(event: string, data: any) {
    const message = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
    const encoder = new TextEncoder()
    const encoded = encoder.encode(message)

    // Send to all connected clients
    const clientEntries = Array.from(this.clients.entries())
    for (const [clientId, writer] of clientEntries) {
      try {
        await writer.write(encoded)
      } catch (error) {
        console.error(`Error writing to client ${clientId}:`, error)
        this.removeClient(clientId)
      }
    }
  }

  async broadcast(event: {
    type: string
    [key: string]: any
  }) {
    const eventData = {
      ...event,
      timestamp: new Date().toISOString(),
    }
    await this.emit(event.type, eventData)
  }
}

// Global singleton instance
export const eventEmitter = EventEmitter.getInstance()

// Helper function to emit SSE events
export async function emitSSEEvent(event: {
  type: 'tweet_scraped' | 'tweet_classified' | 'draft_created' | 'draft_approved' | 'quota_update' | 'error'
  [key: string]: any
}) {
  await eventEmitter.broadcast(event)
}