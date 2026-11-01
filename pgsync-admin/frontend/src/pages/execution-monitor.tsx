import { createSignal, onMount, onCleanup, Show } from 'solid-js';
import { A, useParams } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';
import { apiErrorMessage } from '@/lib/api-client';
import { useLiveLogsWebSocket } from '@/hooks/use-live-logs';
import { Card, Badge } from '@/components/ui';
import { LogViewer } from '@/components/log-viewer';
import { MetricsDisplay } from '@/components/metrics-display';

interface ExecutionMonitorPageProps {}

interface ExecutionStatus {
  id: number;
  config_name: string;
  type: string;
  status: string;
  pid: number | null;
  started_at: string;
  completed_at: string | null;
  rows_processed: number;
  cpu_percent: number;
  memory_mb: number;
  error_message: string | null;
}

interface Metrics {
  table_name: string;
  rows_synced: number;
  rows_failed: number;
  latency_ms: number;
}

export function ExecutionMonitorPage(props: ExecutionMonitorPageProps) {
  const params = useParams();
  const executionId = () => parseInt(params.id ?? '', 10);

  const [execution, setExecution] = createSignal<ExecutionStatus | null>(null);
  const [metrics, setMetrics] = createSignal<Metrics[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  const { logs, connected, connect, disconnect } = useLiveLogsWebSocket();

  onMount(() => {
    const id = executionId();
    if (!Number.isInteger(id) || id < 1) {
      setError('Invalid execution ID.');
      return;
    }
    void loadStatus();
    void loadMetrics();
    connect(id);
    const interval = setInterval(() => {
      void loadStatus();
      void loadMetrics();
    }, 3000);
    onCleanup(() => {
      clearInterval(interval);
      disconnect();
    });
  });

  const loadStatus = async () => {
    try {
      const response = await apiClient.getExecutionStatus(executionId());
      setExecution(response.data.execution);
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Failed to load execution status.'));
    }
  };

  const loadMetrics = async () => {
    try {
      const response = await apiClient.getMetrics(executionId());
      setMetrics(response.data.metrics || []);
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Failed to load execution metrics.'));
    }
  };

  const statusColor = (status: string) => {
    const colors: any = {
      pending: 'info',
      running: 'info',
      completed: 'success',
      failed: 'error',
      stopped: 'warning',
    };
    return colors[status] || 'info';
  };

  return (
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold">Execution Monitor</h1>
          <Show when={connected()}>
            <p class="text-sm text-green-600 mt-1">🔴 Live — Connected</p>
          </Show>
          <Show when={!connected()}>
            <p class="text-sm text-gray-600 mt-1">⚪ Offline</p>
          </Show>
        </div>
        <A href="/execution" class="text-blue-600 hover:underline text-sm">
          ← Back to List
        </A>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error()}
        </div>
      </Show>

      <Show when={execution()}>
        {(exec) => (
          <Card title="Execution Status">
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p class="text-sm text-gray-600">Config</p>
                <p class="font-semibold">{exec().config_name}</p>
              </div>
              <div>
                <p class="text-sm text-gray-600">Status</p>
                <Badge variant={statusColor(exec().status)}>
                  {exec().status}
                </Badge>
              </div>
              <div>
                <p class="text-sm text-gray-600">Type</p>
                <p class="font-mono text-sm">{exec().type}</p>
              </div>
              <div>
                <p class="text-sm text-gray-600">Rows Processed</p>
                <p class="font-mono text-sm">{exec().rows_processed}</p>
              </div>
              <div>
                <p class="text-sm text-gray-600">CPU / Memory</p>
                <p class="font-mono text-sm">
                  {exec().cpu_percent.toFixed(1)}% / {exec().memory_mb}MB
                </p>
              </div>
              <div>
                <p class="text-sm text-gray-600">PID</p>
                <p class="font-mono text-sm">{exec().pid || 'N/A'}</p>
              </div>
            </div>
          </Card>
        )}
      </Show>
      <Show when={!execution() && error()}><Card><div class="py-8 text-center text-gray-600">Execution details are unavailable. Return to the execution list or retry after checking the API.</div></Card></Show>

      <MetricsDisplay metrics={metrics()} />

      <Card title="Live Logs">
        <LogViewer logs={logs} loading={loading()} maxHeight="600px" />
      </Card>
    </div>
  );
}
