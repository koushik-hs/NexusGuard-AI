import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_URL } from '../api/client';
import type { LiveUpdate } from '../api/client';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [events, setEvents] = useState<LiveUpdate[]>([]);
  const [latestUpdate, setLatestUpdate] = useState<LiveUpdate | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<LiveUpdate[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[WebSocket] Connected to NexusGuard AI live stream');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'keepalive' || data.type === 'pong' || data.type === 'connected') {
            return;
          }

          const update = data as LiveUpdate;
          setLatestUpdate(update);
          setEvents((prev) => [update, ...prev.slice(0, 99)]);

          if (update.alert_triggered) {
            setActiveAlerts((prev) => [update, ...prev.slice(0, 19)]);
          }
        } catch (err) {
          console.error('[WebSocket] Message parse error:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('[WebSocket] Disconnected. Attempting reconnect in 2s...');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      ws.onerror = (err) => {
        console.warn('[WebSocket] Connection error:', err);
        ws.close();
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('[WebSocket] Setup error:', e);
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    isConnected,
    events,
    latestUpdate,
    activeAlerts,
    clearEvents,
  };
}
