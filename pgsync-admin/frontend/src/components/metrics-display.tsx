import { For, Show } from 'solid-js';
import { Card } from '@/components/ui';

interface MetricsDisplayProps {
  metrics: Metric[];
}

interface Metric {
  table_name: string;
  rows_synced: number;
  rows_failed: number;
  latency_ms: number;
}

export function MetricsDisplay(props: MetricsDisplayProps) {
  const totalRows = () =>
    props.metrics.reduce((sum, m) => sum + m.rows_synced, 0);
  const totalFailed = () =>
    props.metrics.reduce((sum, m) => sum + m.rows_failed, 0);
  const avgLatency = () => {
    if (props.metrics.length === 0) return 0;
    const sum = props.metrics.reduce((s, m) => s + m.latency_ms, 0);
    return (sum / props.metrics.length).toFixed(2);
  };

  return (
    <Card title="Metrics by Table">
      <Show
        when={props.metrics.length > 0}
        fallback={<div class="text-gray-500">No metrics available</div>}
      >
        <div class="mb-4 grid grid-cols-3 gap-4 text-center">
          <div class="bg-blue-50 p-3 rounded">
            <p class="text-sm text-gray-600">Total Synced</p>
            <p class="text-2xl font-bold text-blue-600">{totalRows()}</p>
          </div>
          <div class="bg-red-50 p-3 rounded">
            <p class="text-sm text-gray-600">Total Failed</p>
            <p class="text-2xl font-bold text-red-600">{totalFailed()}</p>
          </div>
          <div class="bg-green-50 p-3 rounded">
            <p class="text-sm text-gray-600">Avg Latency</p>
            <p class="text-2xl font-bold text-green-600">{avgLatency()} ms</p>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-100 border-b">
              <tr>
                <th class="px-4 py-2 text-left font-semibold">Table</th>
                <th class="px-4 py-2 text-right font-semibold">Synced</th>
                <th class="px-4 py-2 text-right font-semibold">Failed</th>
                <th class="px-4 py-2 text-right font-semibold">Latency (ms)</th>
              </tr>
            </thead>
            <tbody>
              <For each={props.metrics}>
                {(metric) => (
                  <tr class="border-b hover:bg-gray-50">
                    <td class="px-4 py-2 font-mono">{metric.table_name}</td>
                    <td class="px-4 py-2 text-right">{metric.rows_synced}</td>
                    <td class="px-4 py-2 text-right text-red-600">
                      {metric.rows_failed}
                    </td>
                    <td class="px-4 py-2 text-right">{metric.latency_ms}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>
    </Card>
  );
}
