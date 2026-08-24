import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, type LiveEngineStatus, type LiveUpdate } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';

type LiveData = {
  isConnected: boolean;
  events: LiveUpdate[];
  latestUpdate: LiveUpdate | null;
  activeAlerts: LiveUpdate[];
  status: LiveEngineStatus | null;
  statusError: string | null;
  refreshStatus: () => Promise<void>;
  clearEvents: () => void;
};

const LiveDataContext = createContext<LiveData | null>(null);

export function LiveDataProvider({ children }: { children: ReactNode }) {
  const socket = useWebSocket();
  const [history, setHistory] = useState<LiveUpdate[]>([]);
  const [status, setStatus] = useState<LiveEngineStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const refreshStatus = async () => {
    try {
      const next = await api.getLiveStatus();
      setStatus(next);
      setStatusError(null);
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : 'Live engine unavailable');
    }
  };

  useEffect(() => {
    api.getEventStream(50).then((result) => setHistory(result.events)).catch(() => undefined);
    refreshStatus();
    const timer = window.setInterval(refreshStatus, 12000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (socket.latestUpdate) refreshStatus();
  }, [socket.latestUpdate]);

  const eventMap = new Map<string, LiveUpdate>();
  [...socket.events, ...history].forEach((event) => eventMap.set(event.event_id, event));
  const events = Array.from(eventMap.values()).sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  const clearEvents = () => {
    setHistory([]);
    socket.clearEvents();
  };

  return <LiveDataContext.Provider value={{ ...socket, events, clearEvents, status, statusError, refreshStatus }}>{children}</LiveDataContext.Provider>;
}

export function useLiveData() {
  const value = useContext(LiveDataContext);
  if (!value) throw new Error('useLiveData must be used within LiveDataProvider');
  return value;
}
