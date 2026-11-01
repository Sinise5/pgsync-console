import { createSignal, onMount, Show } from 'solid-js';
import { A, useParams, useNavigate } from '@solidjs/router';
import { apiClient, apiErrorMessage } from '../lib/api-client';

const pipelineLabels: Record<string, string> = {
  pg_search: 'Search sync',
  pg_clickhouse: 'ClickHouse analytics mirror',
  pg_replication: 'Continuous PostgreSQL replication',
  pg_copy: 'PostgreSQL table copy',
};

export default function ConfigDetail() {
  const params = useParams();
  const navigate = useNavigate();
  const [config, setConfig] = createSignal<any>(null);
  const [loading, setLoading] = createSignal(true);
  const [copying, setCopying] = createSignal(false);
  const [error, setError] = createSignal('');
  const [message, setMessage] = createSignal('');
  const [copyExecutionId, setCopyExecutionId] = createSignal<number | null>(null);

  onMount(async () => {
    try {
      const response = await apiClient.getConfig(Number(params.id));
      setConfig(response.data);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load this configuration.'));
    } finally {
      setLoading(false);
    }
  });

  const runCopy = async () => {
    const current = config();
    if (!current?.schema?.main_table) {
      setError('Select at least one table in Schema Builder before copying.');
      return;
    }
    if (!current.target?.allow_replace) {
      setError('Confirm destination replacement in Edit configuration before copying.');
      return;
    }
    const accepted = window.confirm(`Copy ${current.schema.main_table} and selected tables to ${current.target.database}? Existing matching destination tables can be replaced.`);
    if (!accepted) return;
    setCopying(true);
    setError('');
    setMessage('');
    try {
      const response = await apiClient.startBatchMigration(Number(params.id), {});
      setCopyExecutionId(response.data.execution_id);
      setMessage(`Copy started (execution #${response.data.execution_id}).`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not start the table copy.'));
    } finally {
      setCopying(false);
    }
  };

  return <section class="page-stack">
    <div class="page-heading">
      <div><p class="page-eyebrow"><A href="/config">Configurations</A> / Details</p>
        <h1>{config()?.name || 'Configuration details'}</h1>
        <p class="page-description">Connection details, pipeline mode, and selected source tables.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <A href={`/schema/${params.id}`} class="button button--secondary">Schema Builder</A>
        <A href={`/config/${params.id}/edit`} class="button button--secondary">Edit</A>
        <Show when={config()?.pipeline_type === 'pg_copy'}>
          <button type="button" class="button button--primary" onClick={runCopy} disabled={copying()}>
            {copying() ? 'Starting copy…' : 'Run one-time copy'}
          </button>
        </Show>
      </div>
    </div>

    <Show when={loading()}><div class="surface-card surface-card--empty">Loading configuration…</div></Show>
    <Show when={error()}><div class="notice notice--error" role="alert">{error()}</div></Show>
    <Show when={message()}><div class="notice notice--success" role="status">{message()} <Show when={copyExecutionId()}>{(id) => <A class="underline" href={`/execution/${id()}`}>View execution</A>}</Show></div></Show>
    <Show when={config()}>
      <article class="surface-card">
        <div class="page-heading page-heading--compact">
          <div><h2>Pipeline</h2><p class="page-description">{pipelineLabels[config().pipeline_type] || config().pipeline_type}</p></div>
          <span class={`status-badge ${config().is_active ? 'status-badge--success' : 'status-badge--muted'}`}>{config().is_active ? 'Active' : 'Inactive'}</span>
        </div>
        <div class="config-summary-grid">
          <div class="config-summary">
            <span>Source</span><strong>{config().source?.type} · {config().source?.database}</strong>
            <small>{config().source?.host}:{config().source?.port} · {config().source?.user}</small>
          </div>
          <div class="config-summary">
            <span>Destination</span><strong>{config().target?.type} · {config().target?.database || config().schema?.index || 'Search index'}</strong>
            <small>{config().target?.host}:{config().target?.port} · {config().target?.user || 'No username'}</small>
          </div>
          <div class="config-summary"><span>Schema version</span><strong>v{config().version}</strong><small>Updated {config().updated_at ? new Date(config().updated_at).toLocaleString('id-ID') : '—'}</small></div>
        </div>
      </article>
      <article class="surface-card">
        <div class="page-heading page-heading--compact"><div><h2>Selected tables</h2><p class="page-description">{config().schema?.main_table || 'No table selection yet'}</p></div></div>
        <Show when={config().schema?.main_table} fallback={<div class="empty-state"><p>Choose tables in Schema Builder before starting this pipeline.</p><A href={`/schema/${params.id}`} class="button button--primary">Select tables</A></div>}>
          <pre class="schema-preview">{JSON.stringify(config().schema, null, 2)}</pre>
        </Show>
      </article>
    </Show>
  </section>;
}
