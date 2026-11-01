import { createSignal, createEffect, onMount, onCleanup, For, Show } from 'solid-js';
import { A } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';
import { apiErrorMessage } from '@/lib/api-client';

interface CDCState {
  id: number;
  config_id: number;
  status: string;
  docs_synced: number;
  error_count: number;
  last_error?: string;
  last_sync_time?: string;
  started_at?: string;
}

interface Configuration {
  id: number;
  name: string;
  source_pg_host?: string;
  source_pg_port?: number;
  source_pg_database?: string;
  target_config?: string;
  source?: any;
  target?: any;
  schema?: any;
  pipeline_type?: string;
}

export function CDCPage() {
  const [configs, setConfigs] = createSignal<Configuration[]>([]);
  const [cdcStates, setCDCStates] = createSignal<any[]>([]);
  const [cdcLogs, setCDCLogs] = createSignal<Record<number, string[]>>({});
  const [showLogs, setShowLogs] = createSignal<Record<number, boolean>>({});
  const [loading, setLoading] = createSignal(true);
  const [syncing, setSyncing] = createSignal<Record<number, boolean>>({});
  const [stopping, setStopping] = createSignal<Record<number, boolean>>({});
  const [error, setError] = createSignal<string | null>(null);
  const pollers = new Map<number, ReturnType<typeof setInterval>>();

  const stopPolling = (configId: number) => {
    const timer = pollers.get(configId);
    if (timer) clearInterval(timer);
    pollers.delete(configId);
    setSyncing((current) => ({ ...current, [configId]: false }));
  };

  const startPolling = (configId: number) => {
    if (pollers.has(configId)) return;
    const timer = setInterval(async () => {
      try {
        const response = await apiClient.getCDCStatus(configId);
        const status = response.data?.status;
        if (status === 'stopped' || status === 'error') {
          stopPolling(configId);
          await loadCDCStates();
          await fetchLogs(configId);
        }
      } catch (err) {
        setError(apiErrorMessage(err, 'Could not refresh sync status.'));
      }
    }, 3000);
    pollers.set(configId, timer);
  };

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const res = await apiClient.listConfigs();
      const configList = res.data?.configs || [];

      // Fetch full details for each config
      const fullConfigs = await Promise.all(
        configList.map(async (c: any) => {
          try {
            const detail = await apiClient.get(`/config/${c.id}`);
            return detail.data || c;
          } catch {
            return c;
          }
        })
      );

      setConfigs(fullConfigs);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load configurations.'));
      setLoading(false);
    }
  };

  const loadCDCStates = async () => {
    try {
      const states = await Promise.all(configs().map(async (config) => {
        try {
          const response = await apiClient.getCDCStatus(config.id);
          const state = response.data || {};
          return {
            id: state.id, config_id: config.id,
            status: state.status === 'not_found' ? 'stopped' : state.status || 'stopped',
            docs_synced: state.docs_synced || 0, error_count: state.error_count || 0,
            last_error: state.last_error || null, last_sync_time: state.last_sync_time || null,
            started_at: state.started_at || null,
          };
        } catch (err) {
          return { config_id: config.id, status: 'unknown', docs_synced: 0, error_count: 0, last_error: apiErrorMessage(err, 'Status unavailable.') };
        }
      }));
      setCDCStates(states);
      const failed = states.find((state) => state.status === 'unknown');
      setError(failed ? `Could not refresh CDC status for configuration #${failed.config_id}.` : null);
      for (const state of states) {
        if (state.status === 'running' || state.status === 'stopping') startPolling(state.config_id);
        if (state.status === 'stopped' || state.status === 'error') {
          setStopping((current) => ({ ...current, [state.config_id]: false }));
        }
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load CDC status.'));
    } finally {
      setLoading(false);
    }
  };

  onMount(() => { void loadConfigs(); });

  createEffect(() => {
    const currentConfigs = configs();
    if (currentConfigs.length === 0) { setLoading(false); return; }
    void loadCDCStates();
    const interval = setInterval(() => void loadCDCStates(), 5000);
    onCleanup(() => clearInterval(interval));
  });

  onCleanup(() => { for (const configId of pollers.keys()) stopPolling(configId); });

  const handleSyncNow = async (config_id: number) => {
    setSyncing(prev => ({ ...prev, [config_id]: true }));
    try {
      const res = await apiClient.startCDC(config_id);
      const result = res.data || {};

      if (result.status === "started") {
        setError(null);
        stopPolling(config_id);
        setSyncing((current) => ({ ...current, [config_id]: true }));
        startPolling(config_id);

        // Fetch logs immediately
        await fetchLogs(config_id);
      } else if (result.status === "already_running") {
        setError("Sync already running for this config");
        setSyncing(prev => ({ ...prev, [config_id]: false }));
      } else {
        setError(result.error || "Unknown response from server");
        setSyncing(prev => ({ ...prev, [config_id]: false }));
      }

      await loadCDCStates();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to start sync.'));
      setSyncing(prev => ({ ...prev, [config_id]: false }));
    }
  };

  const fetchLogs = async (config_id: number) => {
    try {
      const res = await apiClient.getCDCLogs(config_id);
      setCDCLogs(prev => ({ ...prev, [config_id]: res.data?.logs || [] }));
    } catch (err) {
      setError(apiErrorMessage(err, `Failed to fetch logs for configuration #${config_id}.`));
    }
  };

  const handleToggleLogs = async (configId: number) => {
    const open = !showLogs()[configId];
    setShowLogs((current) => ({ ...current, [configId]: open }));
    if (open) await fetchLogs(configId);
  };

  const handleStopSync = async (config_id: number) => {
    setStopping((current) => ({ ...current, [config_id]: true }));
    try {
      const result = await apiClient.stopCDC(config_id);
      setError(null);
      if (result.data?.status === 'stopping') {
        setSyncing((current) => ({ ...current, [config_id]: true }));
      } else {
        stopPolling(config_id);
      }
      await loadCDCStates();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to stop sync.'));
      setStopping((current) => ({ ...current, [config_id]: false }));
    } finally {
      if (!pollers.has(config_id)) setStopping((current) => ({ ...current, [config_id]: false }));
    }
  };

  const getCDCState = (config_id: number): CDCState | undefined => {
    return cdcStates().find(s => s.config_id === config_id);
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      'running': 'bg-green-100 text-green-700',
      'stopped': 'bg-gray-100 text-gray-700',
      'error': 'bg-red-100 text-red-700',
      'starting': 'bg-blue-100 text-blue-700',
      'stopping': 'bg-yellow-100 text-yellow-800',
      'unknown': 'bg-yellow-100 text-yellow-800',
    };
    return colors[status] || colors['stopped'];
  };

  return (
    <section class="page-stack">
      <div class="page-heading"><div>
        <p class="page-eyebrow">Operations</p><h1>CDC sync</h1>
        <p class="page-description">Start and monitor continuous change streams. PostgreSQL copies run from the configuration page or a schedule.</p>
      </div></div>

      <Show when={error()}>
        <div class="notice notice--error" role="alert">{error()}</div>
      </Show>

      <Show when={loading()}>
        <div class="surface-card surface-card--empty" aria-live="polite">Loading CDC status…</div>
      </Show>

      <Show when={!loading() && configs().length === 0}>
        <article class="surface-card empty-state"><strong>No configurations yet</strong><p>Create a connection first, then configure its schema to enable syncing.</p><A href="/config/new" class="button button--primary">Create configuration</A></article>
      </Show>

      <Show when={!loading() && configs().length > 0}>
        <div class="space-y-4">
          <For each={configs()}>
            {(config) => {
              const state = getCDCState(config.id);
              const isRunning = state?.status === 'running' || syncing()[config.id];
              const schemaRoot = config.schema?.nodes || config.schema;
              const hasSchema = Boolean(schemaRoot?.table || config.schema?.main_table);
              const indexName = config.schema?.index || schemaRoot?.table || config.schema?.main_table || 'Not configured';
              const canStop = isRunning || state?.status === 'stopping';
              const supportsCDC = config.pipeline_type !== 'pg_copy';

              return (
                <article class="surface-card">
                  <div class="flex flex-wrap justify-between items-start gap-4 mb-4">
                    <div><h2>{config.name}</h2><p class="mt-1 text-xs text-gray-500">Configuration #{config.id}</p></div>
                    <div class="flex flex-wrap gap-2">
                      <Show when={supportsCDC}>
                        <button type="button" onClick={() => handleSyncNow(config.id)} disabled={!hasSchema || Boolean(syncing()[config.id]) || isRunning || loading()} class="button button--primary" title={!hasSchema ? 'Configure a schema first' : undefined}>
                          {syncing()[config.id] ? 'Starting…' : 'Start CDC'}
                        </button>
                      </Show>
                      <Show when={supportsCDC}>
                        <button type="button" onClick={() => handleStopSync(config.id)} disabled={!canStop || Boolean(stopping()[config.id])} class="button button--danger">
                          {stopping()[config.id] ? 'Stopping…' : state?.status === 'stopping' ? 'Stop requested' : 'Stop CDC'}
                        </button>
                        <button type="button" onClick={() => handleToggleLogs(config.id)} class="button button--secondary">
                          {showLogs()[config.id] ? 'Hide logs' : 'View logs'}
                        </button>
                      </Show>
                    </div>
                  </div>

                  <Show when={!hasSchema}><div class="notice notice--error mb-4">Schema not configured. <A class="underline" href={`/schema/${config.id}`}>Open Schema Builder</A> before starting this sync.</div></Show>

                  <Show when={supportsCDC} fallback={<div class="notice notice--info mb-4">This pipeline copies selected tables in a batch. <A class="underline" href={`/config/${config.id}`}>Open configuration</A> to run a one-time copy or set a schedule.</div>}>
                  <div class="cdc-pipeline">
                    <div><span>{config.source?.type || 'PostgreSQL'} source</span><strong>{config.source?.host}:{config.source?.port}</strong><small>{config.source?.database}</small></div>
                    <span class="cdc-pipeline__arrow" aria-hidden="true">→</span>
                    <div><span>{config.target?.type || 'Search destination'}</span><strong>{config.target?.host}:{config.target?.port}</strong><small>{config.target?.database ? `Database: ${config.target.database}` : `Index: ${indexName}`}</small></div>
                  </div>

                  <div class="cdc-metrics">
                    <div><span>Status</span><strong class={`inline-block px-2 py-1 rounded text-xs ${getStatusBadge(state?.status || 'stopped')}`}>{state?.status || 'stopped'}</strong></div>
                    <div><span>Documents synced</span><strong>{state?.docs_synced || 0}</strong></div>
                    <div><span>Errors</span><strong>{state?.error_count || 0}</strong></div>
                  </div>

                  <Show when={state?.last_error}><div class="notice notice--error mt-3">Last error: {state?.last_error}</div></Show>
                  <Show when={state?.last_sync_time}><p class="mt-3 text-xs text-gray-500">Last sync: {new Date(state!.last_sync_time!).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })}</p></Show>
                  <Show when={showLogs()[config.id]}>
                    <div class="mt-4 border-t pt-4"><h3 class="mb-2 text-sm font-semibold">Recent sync logs</h3>
                      <Show when={cdcLogs()[config.id]?.length} fallback={<p class="text-sm text-gray-500">No logs are available yet.</p>}>
                        <div class="max-h-64 overflow-auto rounded bg-gray-900 p-3 font-mono text-xs text-green-300"><For each={cdcLogs()[config.id] || []}>{(log) => <div class="whitespace-pre-wrap">{log}</div>}</For></div>
                      </Show>
                    </div>
                  </Show>
                  </Show>
                </article>
              );
            }}
          </For>
        </div>
      </Show>
    </section>
  );
}
