/**
 * Server-Sent Events Hook
 * 
 * Custom React hook for real-time updates via SSE.
 * Features:
 * - Auto-reconnection
 * - Error handling
 * - Event type filtering
 * - Cleanup on unmount
 */

import { useEffect, useRef, useCallback } from 'react'

interface SSEOptions {
  onMessage?: (event: any) => void
  onError?: (error: any) => void
  onOpen?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useSSE(url: string, options: SSEOptions = {}) {
  const {
    onMessage,
    onError,
    onOpen,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5
  } = options

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    try {
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        console.log('SSE connection opened')
        reconnectAttemptsRef.current = 0
        onOpen?.()
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (e) {
          console.error('Failed to parse SSE message:', e)
        }
      }

      eventSource.onerror = (error) => {
        console.error('SSE error:', error)
        onError?.(error)

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(`Reconnecting SSE (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        } else {
          console.error('Max SSE reconnection attempts reached')
        }
      }

      // Add custom event listeners if needed
      eventSource.addEventListener('tweet_queue_updated', (event: any) => {
        const data = JSON.parse(event.data)
        onMessage?.({ type: 'tweet_queue_updated', data })
      })

      eventSource.addEventListener('alert_triggered', (event: any) => {
        const data = JSON.parse(event.data)
        onMessage?.({ type: 'alert_triggered', data })
      })

      eventSource.addEventListener('single_tweet_response_generated', (event: any) => {
        const data = JSON.parse(event.data)
        onMessage?.({ type: 'single_tweet_response_generated', data })
      })

      eventSource.addEventListener('single_tweet_response_failed', (event: any) => {
        const data = JSON.parse(event.data)
        onMessage?.({ type: 'single_tweet_response_failed', data })
      })

    } catch (error) {
      console.error('Failed to create SSE connection:', error)
      onError?.(error)
    }
  }, [url, onMessage, onError, onOpen, reconnectInterval, maxReconnectAttempts])

  useEffect(() => {
    connect()

    // Cleanup
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [connect])

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