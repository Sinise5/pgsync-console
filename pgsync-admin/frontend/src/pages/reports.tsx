import { createSignal, createEffect, For, Show } from 'solid-js';
import { apiClient } from '@/lib/api-client';
import { Card, Badge, Button } from '@/components/ui';

interface ReportsPageProps {}

interface DailyMetric {
  date: string;
  total_logs: number;
  errors: number;
  warnings: number;
  info: number;
  active_executions: number;
}

interface TableStat {
  table_name: string;
  executions: number;
  total_ops: number;
  inserts: number;
  updates: number;
  deletes: number;
  avg_latency_ms: number;
  total_rows: number;
  total_errors: number;
}

export function ReportsPage(props: ReportsPageProps) {
  const [dailyData, setDailyData] = createSignal<DailyMetric[]>([]);
  const [tableStats, setTableStats] = createSignal<TableStat[]>([]);
  const [days, setDays] = createSignal(7);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  createEffect(() => {
    loadReports();
  });

  const loadReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dailyResp, statsResp] = await Promise.all([
        apiClient.getDailyReport(days()),
        apiClient.getTableStats(),
      ]);
      setDailyData(dailyResp.data.data || []);
      setTableStats(statsResp.data.tables || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const response = await apiClient.exportReport(format, days());
      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${new Date().toISOString().split('T')[0]}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to export report');
    }
  };

  return (
    <div class="space-y-6">
      <div class="flex justify-between items-center">
        <div>
          <h1 class="text-3xl font-bold">Reports & Analytics</h1>
          <p class="text-gray-600 mt-1">PGSync performance metrics and trends</p>
        </div>
        <div class="flex gap-2">
          <select
            class="px-4 py-2 border border-gray-300 rounded bg-white"
            value={days()}
            onChange={(e) => setDays(parseInt(e.currentTarget.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <Button variant="secondary" size="sm" onClick={() => handleExport('csv')}>
            📥 CSV
          </Button>
          <Button variant="secondary" size="sm" onClick={() => handleExport('json')}>
            📥 JSON
          </Button>
        </div>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error()}
        </div>
      </Show>

      {/* Daily Metrics Chart */}
      <Card title="Daily Activity">
        <Show when={!loading() && dailyData().length > 0}>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-100 border-b">
                <tr>
                  <th class="px-4 py-2 text-left font-semibold">Date</th>
                  <th class="px-4 py-2 text-right font-semibold">Total Logs</th>
                  <th class="px-4 py-2 text-right font-semibold">Errors</th>
                  <th class="px-4 py-2 text-right font-semibold">Warnings</th>
                  <th class="px-4 py-2 text-right font-semibold">Info</th>
                  <th class="px-4 py-2 text-right font-semibold">Executions</th>
                </tr>
              </thead>
              <tbody>
                <For each={dailyData()}>
                  {(metric) => (
                    <tr class="border-b hover:bg-gray-50">
                      <td class="px-4 py-2 font-mono">{metric.date}</td>
                      <td class="px-4 py-2 text-right">{metric.total_logs}</td>
                      <td class="px-4 py-2 text-right text-red-600">{metric.errors}</td>
                      <td class="px-4 py-2 text-right text-yellow-600">{metric.warnings}</td>
                      <td class="px-4 py-2 text-right text-green-600">{metric.info}</td>
                      <td class="px-4 py-2 text-right">{metric.active_executions}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
        <Show when={loading()}>
          <div class="text-center text-gray-500 py-8">Loading daily metrics...</div>
        </Show>
      </Card>

      {/* Table Statistics */}
      <Card title="Table Statistics (Lifetime)">
        <Show when={!loading() && tableStats().length > 0}>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-100 border-b">
                <tr>
                  <th class="px-4 py-2 text-left font-semibold">Table</th>
                  <th class="px-4 py-2 text-right font-semibold">Execs</th>
                  <th class="px-4 py-2 text-right font-semibold">Total Ops</th>
                  <th class="px-4 py-2 text-right font-semibold">INSERT</th>
                  <th class="px-4 py-2 text-right font-semibold">UPDATE</th>
                  <th class="px-4 py-2 text-right font-semibold">DELETE</th>
                  <th class="px-4 py-2 text-right font-semibold">Avg Lat (ms)</th>
                  <th class="px-4 py-2 text-right font-semibold">Rows</th>
                  <th class="px-4 py-2 text-right font-semibold">Errors</th>
                </tr>
              </thead>
              <tbody>
                <For each={tableStats()}>
                  {(stat) => (
                    <tr class="border-b hover:bg-gray-50">
                      <td class="px-4 py-2 font-mono text-xs">{stat.table_name}</td>
                      <td class="px-4 py-2 text-right text-sm">{stat.executions}</td>
                      <td class="px-4 py-2 text-right text-sm">{stat.total_ops}</td>
                      <td class="px-4 py-2 text-right text-green-600 text-sm">{stat.inserts}</td>
                      <td class="px-4 py-2 text-right text-blue-600 text-sm">{stat.updates}</td>
                      <td class="px-4 py-2 text-right text-red-600 text-sm">{stat.deletes}</td>
                      <td class="px-4 py-2 text-right text-sm">{stat.avg_latency_ms}</td>
                      <td class="px-4 py-2 text-right font-mono text-sm">{stat.total_rows}</td>
                      <td class="px-4 py-2 text-right text-red-600 text-sm">{stat.total_errors}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
        <Show when={loading()}>
          <div class="text-center text-gray-500 py-8">Loading table statistics...</div>
        </Show>
      </Card>
    </div>
  );
}
