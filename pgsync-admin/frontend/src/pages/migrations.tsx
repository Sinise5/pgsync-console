import { createSignal, createEffect, onMount, For, Show } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { apiClient } from '../lib/api-client';

interface Migration {
  id: number;
  config_id: number;
  config_name?: string;
  name: string;
  frequency: string;
  date_column?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  status: string;
  progress_percent: number;
  total_docs: number;
  synced_docs: number;
  failed_docs: number;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  error_message?: string;
}

interface Config {
  id: number;
  name: string;
  source_database: string;
}

export default function Migrations() {
  const [migrations, setMigrations] = createSignal<Migration[]>([]);
  const [configs, setConfigs] = createSignal<Config[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  // Form state
  const [showForm, setShowForm] = createSignal(false);
  const [selectedConfigId, setSelectedConfigId] = createSignal<number | null>(null);
  const [migrationName, setMigrationName] = createSignal('');
  const [frequency, setFrequency] = createSignal('daily');
  const [dateColumn, setDateColumn] = createSignal<string | null>(null);
  const [dateColumnOptions, setDateColumnOptions] = createSignal<string[]>([]);
  const [dateFrom, setDateFrom] = createSignal('');
  const [dateTo, setDateTo] = createSignal('');
  const [limit, setLimit] = createSignal<number | null>(null);
  const [formLoading, setFormLoading] = createSignal(false);

  // Preview schema state
  const [showPreview, setShowPreview] = createSignal(false);
  const [previewData, setPreviewData] = createSignal<any>(null);
  const [previewLoading, setPreviewLoading] = createSignal(false);

  onMount(async () => {
    await loadMigrations();
    await loadConfigs();
  });

  // Load date columns when config selected
  const [prevConfigId, setPrevConfigId] = createSignal<number | null>(null);

  const loadDateColumns = async (configId: number) => {
    try {
      const res = await apiClient.previewMigrationSchema(configId);
      if (res.data?.mappings?.properties) {
        const cols = Object.keys(res.data.mappings.properties);
        setDateColumnOptions(cols);
        setError(null);
      }
    } catch (err: any) {
      // Silent fail — user can still click Preview Schema manually
    }
  };

  // Watch selectedConfigId changes
  const checkConfigChange = () => {
    const id = selectedConfigId();
    if (id && id !== prevConfigId()) {
      setPrevConfigId(id);
      loadDateColumns(id);
    }
  };

  // Run check after every render
  createEffect(() => { configs(); checkConfigChange(); });

  const loadMigrations = async () => {
    try {
      setLoading(true);
      const res = await apiClient.listMigrations(); // calls /migrations (API_BASE = /api)
      setMigrations(res.data.migrations || []);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load migrations');
    } finally {
      setLoading(false);
    }
  };

  const loadConfigs = async () => {
    try {
      const res = await apiClient.listConfigs();
      setConfigs(res.data.configs || res.data || []);
    } catch (err: any) {
      console.error('Failed to load configs:', err);
    }
  };

  const handleStartMigration = async () => {
    if (!selectedConfigId()) {
      setError('Please select a configuration');
      return;
    }

    try {
      setFormLoading(true);
      setError(null);

      const payload = {
        config_id: selectedConfigId(),
        name: migrationName() || `Migration-${selectedConfigId()}`,
        frequency: frequency(),
        date_column: dateColumn() || null,
        date_from: dateFrom() || null,
        date_to: dateTo() || null,
        limit: limit() || null,
      };

      await apiClient.createMigration(payload);

      // Reset form
      setShowForm(false);
      setMigrationName('');
      setFrequency('daily');
      setDateColumn(null);
      setDateColumnOptions([]);
      setDateFrom('');
      setDateTo('');
      setLimit(null);
      setSelectedConfigId(null);

      // Reload migrations
      await loadMigrations();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start migration');
    } finally {
      setFormLoading(false);
    }
  };

  const handleCancelMigration = async (migrationId: number) => {
    if (!confirm('Cancel this migration?')) return;

    try {
      setError(null);
      await apiClient.cancelMigration(migrationId);
      await loadMigrations();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to cancel migration');
    }
  };

  const handleDeleteMigration = async (migrationId: number) => {
    if (!confirm('Delete this migration record? This cannot be undone.')) return;

    try {
      setError(null);
      await apiClient.deleteMigration(migrationId);
      await loadMigrations();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete migration');
    }
  };

  const handlePreviewSchema = async () => {
    if (!selectedConfigId()) {
      setError('Please select a configuration first');
      return;
    }

    try {
      setPreviewLoading(true);
      setError(null);
      const res = await apiClient.previewMigrationSchema(selectedConfigId()!);
      setPreviewData(res.data);
      setShowPreview(true);

      // Extract date columns from preview for dropdown
      if (res.data?.mappings?.properties) {
        setDateColumnOptions(Object.keys(res.data.mappings.properties));
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to preview schema');
    } finally {
      setPreviewLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <div class="p-6">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold">Migrations</h1>
        <button
          onClick={() => setShowForm(!showForm())}
          class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {showForm() ? 'Cancel' : 'Start Migration'}
        </button>
      </div>

      <Show when={error()}>
        <div class="mb-4 p-4 bg-red-100 text-red-700 rounded">
          {error()}
        </div>
      </Show>

      {/* Migration Form */}
      <Show when={showForm()}>
        <div class="mb-6 p-4 bg-gray-50 rounded border">
          <h2 class="text-xl font-semibold mb-4">Start New Migration</h2>

          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium mb-2">Configuration</label>
              <select
                value={selectedConfigId() || ''}
                onChange={(e) => setSelectedConfigId(Number(e.currentTarget.value) || null)}
                class="w-full px-3 py-2 border rounded"
              >
                <option value="">Select configuration...</option>
                <For each={configs()}>
                  {(config) => (
                    <option value={config.id}>
                      {config.name} ({config.source_database})
                    </option>
                  )}
                </For>
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">Migration Name</label>
              <input
                type="text"
                value={migrationName()}
                onChange={(e) => setMigrationName(e.currentTarget.value)}
                placeholder="Optional name"
                class="w-full px-3 py-2 border rounded"
              />
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">Frequency</label>
              <select
                value={frequency()}
                onChange={(e) => setFrequency(e.currentTarget.value)}
                class="w-full px-3 py-2 border rounded"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">Limit (docs)</label>
              <input
                type="number"
                value={limit() || ''}
                onChange={(e) => setLimit(e.currentTarget.value ? Number(e.currentTarget.value) : null)}
                placeholder="Leave empty for all"
                class="w-full px-3 py-2 border rounded"
              />
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">Date Column</label>
              <select
                value={dateColumn() || ''}
                onChange={(e) => setDateColumn(e.currentTarget.value || null)}
                class="w-full px-3 py-2 border rounded"
              >
                <option value="">No date filter</option>
                <For each={dateColumnOptions()}>
                  {(col) => <option value={col}>{col}</option>}
                </For>
              </select>
              <p class="text-xs text-gray-500 mt-1">Click "Preview Schema" first to load columns</p>
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">From Date</label>
              <input
                type="datetime-local"
                value={dateFrom()}
                onChange={(e) => setDateFrom(e.currentTarget.value)}
                class="w-full px-3 py-2 border rounded"
              />
            </div>

            <div>
              <label class="block text-sm font-medium mb-2">To Date</label>
              <input
                type="datetime-local"
                value={dateTo()}
                onChange={(e) => setDateTo(e.currentTarget.value)}
                class="w-full px-3 py-2 border rounded"
              />
            </div>
          </div>

          <div class="flex gap-2">
            <button
              onClick={handlePreviewSchema}
              disabled={previewLoading() || !selectedConfigId()}
              class="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
            >
              {previewLoading() ? 'Loading...' : 'Preview Schema'}
            </button>
            <button
              onClick={handleStartMigration}
              disabled={formLoading() || !selectedConfigId()}
              class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              {formLoading() ? 'Starting...' : 'Start Migration'}
            </button>
          </div>
        </div>
      </Show>

      {/* Migrations List */}
      <Show when={loading()}>
        <div class="text-center py-8">Loading migrations...</div>
      </Show>

      <Show when={!loading() && migrations().length === 0}>
        <div class="text-center py-8 text-gray-500">No migrations found</div>
      </Show>

      <Show when={!loading() && migrations().length > 0}>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-100">
                <th class="border px-4 py-2 text-left">ID</th>
                <th class="border px-4 py-2 text-left">Name</th>
                <th class="border px-4 py-2 text-left">Config</th>
                <th class="border px-4 py-2 text-left">Status</th>
                <th class="border px-4 py-2 text-center">Progress</th>
                <th class="border px-4 py-2 text-center">Synced / Total</th>
                <th class="border px-4 py-2 text-center">Failed</th>
                <th class="border px-4 py-2 text-left">Started</th>
                <th class="border px-4 py-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              <For each={migrations()}>
                {(migration) => (
                  <tr class="hover:bg-gray-50">
                    <td class="border px-4 py-2">{migration.id}</td>
                    <td class="border px-4 py-2">{migration.name}</td>
                    <td class="border px-4 py-2 text-sm text-gray-600">{migration.config_name || '-'}</td>
                    <td class="border px-4 py-2">
                      <span class={`px-2 py-1 rounded text-sm ${getStatusColor(migration.status)}`}>
                        {migration.status}
                      </span>
                    </td>
                    <td class="border px-4 py-2 text-center">
                      <div class="w-full bg-gray-200 rounded h-2">
                        <div
                          class="bg-blue-600 h-2 rounded"
                          style={{ width: `${migration.progress_percent}%` }}
                        />
                      </div>
                      <span class="text-xs">{migration.progress_percent.toFixed(1)}%</span>
                    </td>
                    <td class="border px-4 py-2 text-center">
                      {migration.synced_docs} / {migration.total_docs}
                    </td>
                    <td class="border px-4 py-2 text-center text-red-600">
                      {migration.failed_docs}
                    </td>
                    <td class="border px-4 py-2 text-sm">
                      {migration.started_at ? new Date(migration.started_at).toLocaleString() : '-'}
                    </td>
                    <td class="border px-4 py-2 text-center">
                      <div class="flex gap-2 justify-center">
                        <Show when={migration.status === 'running'}>
                          <button
                            onClick={() => handleCancelMigration(migration.id)}
                            class="text-red-600 hover:text-red-800 text-sm"
                          >
                            Cancel
                          </button>
                        </Show>
                        <Show when={migration.status === 'failed' && migration.error_message}>
                          <button
                            onClick={() => alert(migration.error_message)}
                            class="text-orange-600 hover:text-orange-800 text-sm"
                          >
                            View Error
                          </button>
                        </Show>
                        <button
                          onClick={() => handleDeleteMigration(migration.id)}
                          class="text-gray-600 hover:text-gray-800 text-sm"
                          title="Delete migration"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>

      {/* Preview Schema Modal */}
      <Show when={showPreview()}>
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-96 overflow-auto p-6">
            <div class="flex justify-between items-center mb-4">
              <h2 class="text-xl font-bold">Index Schema Preview</h2>
              <button
                onClick={() => setShowPreview(false)}
                class="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ×
              </button>
            </div>

            <Show when={previewData()}>
              <div class="space-y-4">
                <div>
                  <h3 class="font-semibold">Index Name</h3>
                  <p class="text-gray-700 font-mono text-sm">{previewData()?.index_name}</p>
                </div>

                <div>
                  <h3 class="font-semibold">Fields ({previewData()?.field_count})</h3>
                  <div class="bg-gray-50 rounded p-3 max-h-56 overflow-auto">
                    <div class="space-y-1 text-sm font-mono">
                      <For each={Object.keys(previewData()?.mappings?.properties || {})}>
                        {(field) => (
                          <div class="flex justify-between text-gray-700">
                            <span>{field}</span>
                            <span class="text-blue-600">
                              {previewData()?.mappings?.properties[field]?.type}
                            </span>
                          </div>
                        )}
                      </For>
                    </div>
                  </div>
                </div>

                <div class="text-xs text-gray-500">
                  <p>Shards: {previewData()?.settings?.number_of_shards}</p>
                  <p>Replicas: {previewData()?.settings?.number_of_replicas}</p>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </Show>
    </div>
  );
}
