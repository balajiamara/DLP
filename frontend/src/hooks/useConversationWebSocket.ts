import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getAccessToken } from '../lib/auth';
import type { Message } from '../types/conversations';

export interface ConversationWebSocketMessage {
  event_type: 'message_created' | string;
  conversation_id: number;
  data: Message;
}

interface UseConversationWebSocketOptions {
  onNewMessage?: (message: Message) => void;
}

/**
 * Custom React hook establishing a real-time WebSocket connection to FastAPI's
 * /ws/conversations/{conversationId} endpoint (Step 45).
 *
 * Automatically invalidates relevant TanStack Query caches whenever message_created
 * events are broadcast from Django.
 */
export function useConversationWebSocket(
  conversationId?: number | null,
  options?: UseConversationWebSocketOptions
) {
  const queryClient = useQueryClient();
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    if (!conversationId || isNaN(conversationId)) return;

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
    let isUnmounted = false;
    let reconnectAttempts = 0;

    const clearHeartbeat = () => {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };

    const connect = () => {
      if (isUnmounted) return;

      const token = getAccessToken();
      if (!token) {
        console.debug('[ConversationWS] No access token found; skipping WebSocket connection.');
        return;
      }

      const rawWsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';
      const wsBase = rawWsUrl
        .replace(/^http:/, 'ws:')
        .replace(/^https:/, 'wss:')
        .replace(/\/+$/, '');
      const endpoint = `${wsBase}/ws/conversations/${conversationId}?token=${encodeURIComponent(token)}`;

      try {
        ws = new WebSocket(endpoint);

        ws.onopen = () => {
          console.log(`[ConversationWS] Connected to conversation ${conversationId} room.`);
          reconnectAttempts = 0;
          clearHeartbeat();
          heartbeatTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }));
            }
          }, 30000);
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'pong') {
              return; // Handled heartbeat response
            }

            console.log(
              `[ConversationWS] Received event '${message.event_type}' for conversation ${message.conversation_id}`,
              message.data
            );

            if (message.event_type === 'message_created' && message.data) {
              // 1. Trigger optional callback (e.g. for auto-scroll check)
              optionsRef.current?.onNewMessage?.(message.data);

              // 2. Invalidate conversation messages cache so fresh list is loaded
              queryClient.invalidateQueries({
                queryKey: ['conversation-messages', conversationId],
              });

              // 3. Invalidate conversation inbox query to update last_message
              queryClient.invalidateQueries({
                queryKey: ['conversations'],
              });
            }
          } catch (parseError) {
            console.warn('[ConversationWS] Failed to parse incoming WebSocket message:', parseError);
          }
        };

        ws.onerror = (error) => {
          console.warn('[ConversationWS] WebSocket encountered an error:', error);
        };

        ws.onclose = (event) => {
          clearHeartbeat();
          console.log(`[ConversationWS] Connection closed (code: ${event.code}, reason: '${event.reason}')`);

          if (isUnmounted || event.code === 1000) {
            return; // Clean intentional unmount or closure
          }

          // 4003, 403, or Forbidden: Unauthorized / not authorized for conversation -> do NOT loop retry
          if (
            event.code === 4003 ||
            event.code === 403 ||
            (event.code === 1008 && event.reason?.toLowerCase().includes('forbidden'))
          ) {
            console.warn('[ConversationWS] Authorization denied. Will not attempt reconnect.');
            return;
          }

          // Exponential backoff: 2s, 4s, 8s, 16s, capped at 30s
          const delayMs = Math.min(2000 * Math.pow(2, reconnectAttempts), 30000);
          reconnectAttempts++;
          console.log(
            `[ConversationWS] Scheduling reconnect attempt ${reconnectAttempts} in ${delayMs / 1000}s...`
          );
          reconnectTimer = setTimeout(() => {
            if (!isUnmounted) {
              connect();
            }
          }, delayMs);
        };
      } catch (initError) {
        console.warn('[ConversationWS] Failed to initialize WebSocket:', initError);
      }
    };

    connect();

    return () => {
      isUnmounted = true;
      clearHeartbeat();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (ws) {
        console.log(`[ConversationWS] Cleaning up WebSocket for conversation ${conversationId}`);
        ws.close(1000, 'Component unmounted');
      }
    };
  }, [conversationId, queryClient]);
}
