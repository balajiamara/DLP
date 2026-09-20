import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getAccessToken } from '../lib/auth';

export interface DoubtWebSocketMessage {
  event_type: 'doubt_created' | 'reply_created' | 'answer_accepted' | string;
  classroom_id: number;
  data: any;
}

/**
 * Custom React hook establishing a real-time WebSocket connection to FastAPI's
 * /ws/classrooms/{classroomId}/doubts endpoint (Step 36).
 *
 * Automatically invalidates relevant TanStack Query caches whenever doubt_created,
 * reply_created, or answer_accepted events are broadcast from Django.
 */
export function useDoubtWebSocket(classroomId: number, selectedDoubtId?: number | null) {
  const queryClient = useQueryClient();
  const selectedDoubtIdRef = useRef(selectedDoubtId);
  selectedDoubtIdRef.current = selectedDoubtId;

  useEffect(() => {
    if (!classroomId || isNaN(classroomId)) return;

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
        console.debug('[DoubtWS] No access token found; skipping WebSocket connection.');
        return;
      }

      const rawWsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';
      const wsBase = rawWsUrl
        .replace(/^http:/, 'ws:')
        .replace(/^https:/, 'wss:')
        .replace(/\/+$/, '');
      const endpoint = `${wsBase}/ws/classrooms/${classroomId}/doubts?token=${encodeURIComponent(token)}`;

      try {
        ws = new WebSocket(endpoint);

        ws.onopen = () => {
          console.log(`[DoubtWS] Connected to classroom ${classroomId} doubt room.`);
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

            console.log(`[DoubtWS] Received event '${message.event_type}' for classroom ${message.classroom_id}`, message.data);

            // 1. Invalidate doubt list cache for this classroom
            queryClient.invalidateQueries({ queryKey: ['doubts', classroomId] });

            // 2. Invalidate doubt detail cache if currently open
            // For reply_created and answer_accepted, message.data.doubt is the parent doubt ID
            // For doubt_created, message.data.id is the doubt ID
            const targetDoubtId = message.data?.doubt ?? message.data?.id;

            if (targetDoubtId) {
              queryClient.invalidateQueries({
                queryKey: ['doubt-detail', classroomId, Number(targetDoubtId)],
              });
            } else {
              queryClient.invalidateQueries({
                queryKey: ['doubt-detail', classroomId],
              });
            }
          } catch (parseError) {
            console.warn('[DoubtWS] Failed to parse incoming WebSocket message:', parseError);
          }
        };

        ws.onerror = (error) => {
          console.warn('[DoubtWS] WebSocket encountered an error:', error);
        };

        ws.onclose = (event) => {
          clearHeartbeat();
          console.log(`[DoubtWS] Connection closed (code: ${event.code}, reason: '${event.reason}')`);

          if (isUnmounted || event.code === 1000) {
            return; // Clean intentional unmount or closure
          }

          // Per Step 36 design: 4003 or 403 is Unauthorized/Forbidden (not in classroom) -> do NOT loop retry
          if (
            event.code === 4003 ||
            event.code === 403 ||
            (event.code === 1008 && event.reason?.toLowerCase().includes('forbidden'))
          ) {
            console.warn('[DoubtWS] Authorization denied. Will not attempt reconnect.');
            return;
          }

          // Exponential backoff: 2s, 4s, 8s, 16s, capped at 30s
          const delayMs = Math.min(2000 * Math.pow(2, reconnectAttempts), 30000);
          reconnectAttempts++;
          console.log(
            `[DoubtWS] Scheduling reconnect attempt ${reconnectAttempts} in ${delayMs / 1000}s...`
          );
          reconnectTimer = setTimeout(() => {
            if (!isUnmounted) {
              connect();
            }
          }, delayMs);
        };
      } catch (initError) {
        console.warn('[DoubtWS] Failed to initialize WebSocket:', initError);
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
        console.log(`[DoubtWS] Cleaning up WebSocket for classroom ${classroomId}`);
        ws.close(1000, 'Component unmounted');
      }
    };
  }, [classroomId, queryClient]);
}
