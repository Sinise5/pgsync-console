import { createSignal, onMount, Show, For } from 'solid-js';
import { A, useLocation, useNavigate, useParams } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';

interface DashboardWidget {
  id: number;
  title: string;
  widget_type: string;
  config: Record<string, unknown>;
}

interface Dashboard {
  id: number;
  name: string;
  description?: string;
  created_at?: string;
  is_shared: boolean;
  share_token?: string;
  widgets?: DashboardWidget[];
}

export default function DashboardDetailPage() {
  const params = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const editing = () => location.pathname.endsWith('/edit');
  const [dashboard, setDashboard] = createSignal<Dashboard | null>(null);
  const [name, setName] = createSignal('');
  const [description, setDescription] = createSignal('');
  const [isShared, setIsShared] = createSignal(false);
  const [loading, setLoading] = createSignal(true);
  const [saving, setSaving] = createSignal(false);
  const [error, setError] = createSignal('');
  const [widgetTitle, setWidgetTitle] = createSignal('');
  const [widgetType, setWidgetType] = createSignal('metric');
  const [widgetConfig, setWidgetConfig] = createSignal('{}');
  const [savingWidget, setSavingWidget] = createSignal(false);

  const loadDashboard = async () => {
    try {
      const response = await apiClient.getDashboard(Number(params.id));
      const item = response.data as Dashboard;
      setDashboard(item);
      setName(item.name || '');
      setDescription(item.description || '');
      setIsShared(Boolean(item.is_shared));
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Unable to load dashboard.');
    } finally {
      setLoading(false);
    }
  };

  onMount(loadDashboard);

  const addWidget = async (event: SubmitEvent) => {
    event.preventDefault();
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(widgetConfig());
      if (!config || Array.isArray(config) || typeof config !== 'object') throw new Error();
    } catch {
      setError('Widget configuration must be a valid JSON object.');
      return;
    }
    try {
      setSavingWidget(true);
      setError('');
      await apiClient.addWidget(Number(params.id), {
        title: widgetTitle().trim(), widget_type: widgetType(), config,
      });
      setWidgetTitle('');
      setWidgetConfig('{}');
      await loadDashboard();
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Unable to add widget.');
    } finally {
      setSavingWidget(false);
    }
  };

  const removeWidget = async (widgetId: number) => {
    try {
      setError('');
      await apiClient.deleteWidget(Number(params.id), widgetId);
      await loadDashboard();
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Unable to remove widget.');
    }
  };

  const save = async (event: SubmitEvent) => {
    event.preventDefault();
    if (!name().trim()) {
      setError('Dashboard name is required.');
      return;
    }
    try {
      setSaving(true);
      setError('');
      await apiClient.updateDashboard(Number(params.id), {
        name: name().trim(), description: description().trim(), is_shared: isShared(),
      });
      navigate(`/dashboards/${params.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Unable to save dashboard.');
    } finally {
      setSaving(false);
    }
  };

  return <section class="page-stack">
    <div class="page-heading">
      <div><p class="page-eyebrow"><A href="/dashboards">Dashboards</A> / {editing() ? 'Edit' : 'Overview'}</p>
        <h1>{dashboard()?.name || 'Dashboard'}</h1>
        <p class="page-description">{editing() ? 'Update dashboard details and sharing preferences.' : 'Dashboard details and available widgets.'}</p>
      </div>
      <div class="page-heading__actions">
        <A href="/dashboards" class="button button--secondary">Back to dashboards</A>
        <Show when={!editing() && dashboard()}><A href={`/dashboards/${params.id}/edit`} class="button button--primary">Edit dashboard</A></Show>
      </div>
    </div>
    <Show when={error()}><div class="notice notice--error" role="alert">{error()}</div></Show>
    <Show when={loading()}><div class="surface-card surface-card--empty">Loading dashboard…</div></Show>
    <Show when={!loading() && !dashboard() && !error()}><div class="surface-card surface-card--empty">Dashboard not found.</div></Show>
    <Show when={!loading() && dashboard()}>
      <Show when={editing()} fallback={<div class="dashboard-detail-grid">
        <article class="surface-card dashboard-summary">
          <h2>Overview</h2>
          <p>{dashboard()?.description || 'No description has been added.'}</p>
          <dl><div><dt>Widgets</dt><dd>{dashboard()?.widgets?.length || 0}</dd></div>
            <div><dt>Sharing</dt><dd>{dashboard()?.is_shared ? 'Shared' : 'Private'}</dd></div>
            <div><dt>Created</dt><dd>{dashboard()?.created_at ? new Date(dashboard()!.created_at!).toLocaleDateString() : '—'}</dd></div></dl>
        </article>
        <article class="surface-card"><div class="section-heading"><div><h2>Widgets</h2><p>Panels configured for this dashboard.</p></div></div>
          <Show when={(dashboard()?.widgets?.length || 0) > 0} fallback={<div class="empty-state">No widgets have been added yet.</div>}>
            <div class="widget-list"><For each={dashboard()?.widgets}>{(widget) => <div class="widget-row"><div><strong>{widget.title}</strong><span>{widget.widget_type}</span></div><button class="button button--secondary" type="button" onClick={() => removeWidget(widget.id)}>Remove</button></div>}</For></div>
          </Show>
          <form class="dashboard-form widget-form" onSubmit={addWidget}>
            <h3>Add a widget</h3>
            <label>Title<input value={widgetTitle()} onInput={(e) => setWidgetTitle(e.currentTarget.value)} required maxlength="120" /></label>
            <label>Widget type<select value={widgetType()} onChange={(e) => setWidgetType(e.currentTarget.value)}>
              <option value="metric">Metric</option><option value="chart">Chart</option><option value="table">Table</option><option value="gauge">Gauge</option><option value="kpi">KPI</option>
            </select></label>
            <label>Configuration (JSON)<textarea value={widgetConfig()} onInput={(e) => setWidgetConfig(e.currentTarget.value)} rows="3" spellcheck={false} /></label>
            <button class="button button--primary" type="submit" disabled={savingWidget() || !widgetTitle().trim()}>{savingWidget() ? 'Adding…' : 'Add widget'}</button>
          </form>
        </article>
      </div>}>
        <form class="surface-card dashboard-form" onSubmit={save}>
          <label>Dashboard name<input value={name()} onInput={(e) => setName(e.currentTarget.value)} required maxlength="120" /></label>
          <label>Description<textarea value={description()} onInput={(e) => setDescription(e.currentTarget.value)} rows="4" maxlength="1000" /></label>
          <label class="checkbox-field"><input type="checkbox" checked={isShared()} onChange={(e) => setIsShared(e.currentTarget.checked)} />Allow sharing</label>
          <div class="form-actions"><A href={`/dashboards/${params.id}`} class="button button--secondary">Cancel</A><button class="button button--primary" type="submit" disabled={saving()}>{saving() ? 'Saving…' : 'Save changes'}</button></div>
        </form>
      </Show>
    </Show>
  </section>;
}
