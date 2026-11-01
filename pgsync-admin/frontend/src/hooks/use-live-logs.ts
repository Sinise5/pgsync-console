import { createSignal, onMount, onCleanup } from 'solid-js';

interface LogEntry {
  timestamp: string;
  level: string;
  process: string;
  table_name: string;
  message: string;
}

interface UseLogsResult {
  logs: () => LogEntry[];
  connected: () => boolean;
  connect: (executionId: number) => void;
  disconnect: () => void;
}

export function useLiveLogsWebSocket(): UseLogsResult {
  const [logs, setLogs] = createSignal<LogEntry[]>([]);
  const [connected, setConnected] = createSignal(false);
  let ws: WebSocket | null = null;

  const connect = (executionId: number) => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/logs/${executionId}/stream`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      const token = localStorage.getItem('pgsync_admin_token');
      if (!token) {
        ws?.close();
        setConnected(false);
        return;
      }
      ws?.send(`auth:${token}`);
    };

    ws.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data);
        setLogs((prev) => [entry, ...prev].slice(0, 100)); // Keep last 100
      } catch (e) {
        console.error('Failed to parse log entry:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };
  };

  const disconnect = () => {
    if (ws) {
      ws.close();
      ws = null;
      setConnected(false);
    }
  };

  onCleanup(() => {
    disconnect();
  });

  return {
    logs,
    connected,
    connect,
    disconnect,
  };
}
