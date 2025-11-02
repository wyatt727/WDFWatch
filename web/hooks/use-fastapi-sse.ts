/**
 * Hook for FastAPI Server-Sent Events
 * 
 * Provides real-time event streaming from FastAPI backend for pipeline updates.
 * Can be used as an alternative or complement to Next.js SSE events.
 * 
 * Related files:
 * - /backend/api/app/routes/events.py (FastAPI SSE endpoint)
 * - FastAPI SSE endpoints (`/events/...`) for pipeline + queue updates
 */

import { useEffect, useRef, useCallback } from 'react'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface FastAPISSEOptions {
  episodeId?: string
  path?: string
  onMessage?: (event: any) => void
  onError?: (error: any) => void
  onOpen?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
  enabled?: boolean
}

export function useFastAPISSE(options: FastAPISSEOptions) {
  const {
    episodeId,
    path,
    onMessage,
    onError,
    onOpen,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5,
    enabled = true,
  } = options

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    const endpoint = path ?? (episodeId ? `/events/${episodeId}` : null)
    if (!enabled || !endpoint) return

    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    try {
      const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
      const eventSource = new EventSource(`${API_BASE_URL}${normalizedEndpoint}`)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        console.log('FastAPI SSE connection opened')
        reconnectAttemptsRef.current = 0
        onOpen?.()
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (e) {
          console.error('Failed to parse FastAPI SSE message:', e)
        }
      }

      // Handle specific event types from FastAPI backend
      eventSource.addEventListener('pipeline.started', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.({ type: 'pipeline_stage_started', ...data })
        } catch (e) {
          console.error('Failed to parse pipeline.started event:', e)
        }
      })

      eventSource.addEventListener('pipeline.completed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.({ type: 'pipeline_stage_completed', ...data })
        } catch (e) {
          console.error('Failed to parse pipeline.completed event:', e)
        }
      })

      eventSource.addEventListener('job.started', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.({ type: 'job_started', ...data })
        } catch (e) {
          console.error('Failed to parse job.started event:', e)
        }
      })

      eventSource.addEventListener('job.completed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.({ type: 'job_completed', ...data })
        } catch (e) {
          console.error('Failed to parse job.completed event:', e)
        }
      })

      eventSource.addEventListener('job.failed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.({ type: 'job_failed', ...data })
        } catch (e) {
          console.error('Failed to parse job.failed event:', e)
        }
      })

      eventSource.onerror = (error) => {
        console.error('FastAPI SSE error:', error)
        onError?.(error)

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(`Reconnecting FastAPI SSE (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        } else {
          console.error('Max FastAPI SSE reconnection attempts reached')
        }
      }

    } catch (error) {
      console.error('Failed to create FastAPI SSE connection:', error)
      onError?.(error)
    }
  }, [episodeId, path, onMessage, onError, onOpen, reconnectInterval, maxReconnectAttempts, enabled])

  useEffect(() => {
    if (!enabled) {
      return () => undefined
    }

    const endpoint = path ?? (episodeId ? `/events/${episodeId}` : null)
    if (endpoint) {
      connect()
    }

    // Cleanup
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [connect, enabled, episodeId, path])

  return {
    reconnect: connect,
    disconnect: () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }
}
