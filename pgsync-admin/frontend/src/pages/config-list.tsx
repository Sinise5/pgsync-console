import { createSignal, createEffect, For, Show } from 'solid-js';
import { A } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';
import { Card, Badge, Button } from '@/components/ui';

interface ConfigListPageProps {}

const sourceLabels: Record<string, string> = { postgres: 'PostgreSQL', mysql: 'MySQL', mariadb: 'MariaDB' };
const pipelineLabels: Record<string, string> = {
  pg_search: 'Search index', pg_clickhouse: 'ClickHouse analytics',
  pg_replication: 'PostgreSQL continuous replication', pg_copy: 'PostgreSQL table copy',
};

interface Config {
  id: number;
  name: string;
  description?: string;
  source_database: string;
  target_type: string;
  source_type: string;
  pipeline_type: string;
  is_active: boolean;
  created_at: string;
  version: number;
}

export function ConfigListPage(props: ConfigListPageProps) {
  const [configs, setConfigs] = createSignal<Config[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  createEffect(() => {
    loadConfigs();
  });

  const loadConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.listConfigs();
      setConfigs(response.data.configs || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load configurations');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this configuration?')) return;

    try {
      await apiClient.deleteConfig(id);
      setConfigs((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      setError(err.message || 'Failed to delete configuration');
    }
  };

  return (
    <div class="space-y-6">
      <div class="flex justify-between items-center">
        <div>
          <h1 class="text-3xl font-bold">Configurations</h1>
          <p class="text-gray-600 mt-1">Manage PGSync configurations</p>
        </div>
        <A href="/config/new" class="button button--primary">
          + New Configuration
        </A>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error()}
        </div>
      </Show>

      <Show
        when={!loading() && configs().length > 0}
        fallback={
          <Card>
            <div class="text-center text-gray-500 py-8">
              {loading() ? 'Loading configurations...' : 'No configurations found'}
            </div>
          </Card>
        }
      >
        <div class="grid gap-4">
          <For each={configs()}>
            {(config) => (
              <Card>
                <div class="flex justify-between items-start">
                  <div class="flex-1">
                    <h3 class="text-lg font-semibold">{config.name}</h3>
                    {config.description && <p class="text-gray-600 text-sm mt-1">{config.description}</p>}
                    <div class="flex gap-2 mt-3">
                      <Badge variant={config.is_active ? 'success' : 'error'}>
                        {config.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      <span class="text-xs text-gray-500">v{config.version}</span>
                      <span class="text-xs text-gray-500">{sourceLabels[config.source_type] || 'PostgreSQL'} → {pipelineLabels[config.pipeline_type] || config.target_type}</span>
                    </div>
                    <div class="text-sm text-gray-500 mt-2">
                      Source: <span class="font-mono">{config.source_database}</span>
                    </div>
                  </div>
                  <div class="flex gap-2">
                    <A href={`/schema/${config.id}`} class="button button--primary">Schema Builder</A>
                    <A href={`/config/${config.id}/edit`} class="button button--secondary">Edit</A>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => handleDelete(config.id)}
                    >
                      Delete
                    </Button>
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
