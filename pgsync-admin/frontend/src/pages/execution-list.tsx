import { createSignal, For, Show, onMount, onCleanup } from 'solid-js';
import { A } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';
import { apiErrorMessage } from '@/lib/api-client';
import { Card, Badge, Button } from '@/components/ui';

interface ExecutionListPageProps {}

interface Execution {
  id: number;
  config_id: number;
  config_name: string;
  type: 'batch' | 'cdc';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  pid: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  rows_processed: number;
}

export function ExecutionListPage(props: ExecutionListPageProps) {
  const [executions, setExecutions] = createSignal<Execution[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [busyId, setBusyId] = createSignal<number | null>(null);

  onMount(() => {
    void loadExecutions();
    const interval = setInterval(() => void loadExecutions(), 5000);
    onCleanup(() => clearInterval(interval));
  });

  const loadExecutions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.listExecutions();
      setExecutions(response.data.executions || []);
    } catch (err: any) {
      setError(apiErrorMessage(err, 'Failed to load executions.'));
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async (execution_id: number) => {
    if (!confirm('Stop this execution?')) return;
    setBusyId(execution_id);
    try {
      await apiClient.stopExecution(execution_id);
      await loadExecutions();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to stop execution.'));
    } finally {
      setBusyId(null);
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
      <div>
        <h1 class="text-3xl font-bold">Executions</h1>
        <p class="text-gray-600 mt-1">Monitor batch migrations and CDC processes</p>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error()}
        </div>
      </Show>

      <Show
        when={!loading() && executions().length > 0}
        fallback={
          <Card>
            <div class="text-center text-gray-500 py-8">
              {loading() ? 'Loading executions...' : 'No executions found'}
            </div>
          </Card>
        }
      >
        <div class="grid gap-4">
          <For each={executions()}>
            {(exec) => (
              <Card>
                <div class="flex justify-between items-start">
                  <div class="flex-1">
                    <div class="flex items-center gap-3">
                      <h3 class="text-lg font-semibold">{exec.config_name}</h3>
                      <Badge variant={statusColor(exec.status)}>
                        {exec.status}
                      </Badge>
                      <span class="text-xs bg-gray-200 px-2 py-1 rounded">
                        {exec.type}
                      </span>
                    </div>
                    <div class="text-sm text-gray-600 mt-2">
                      Started: {new Date(exec.started_at).toLocaleString()}
                      {exec.pid && ` • PID: ${exec.pid}`}
                    </div>
                    <div class="text-sm text-gray-600">
                      Rows processed: <span class="font-mono">{exec.rows_processed}</span>
                    </div>
                    {exec.error_message && (
                      <div class="text-sm text-red-600 mt-2">Error: {exec.error_message}</div>
                    )}
                  </div>
                  <div class="flex gap-2">
                    <A href={`/execution/${exec.id}`} class="button button--secondary">
                      Monitor
                    </A>
                    {(exec.status === 'running' || exec.status === 'pending') && (
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={busyId() === exec.id}
                        onClick={() => handleStop(exec.id)}
                      >
                        Stop
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}
