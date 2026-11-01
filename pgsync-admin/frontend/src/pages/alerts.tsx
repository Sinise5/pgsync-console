import { createSignal, createEffect, For, Show } from 'solid-js';
import { apiClient } from '@/lib/api-client';
import { apiErrorMessage } from '@/lib/api-client';

interface AlertRule {
  id: number;
  name: string;
  description?: string;
  metric: string;
  condition: string;
  threshold: number;
  severity: string;
  enabled: boolean;
  duration_seconds?: number;
  cooldown_seconds?: number;
  config_ids?: number[];
  notification_channels?: string[];
}

interface AlertTemplate {
  name: string;
  metric: string;
  condition: string;
  threshold: number;
  severity: string;
  description: string;
}

export function AlertsPage() {
  const [rules, setRules] = createSignal<AlertRule[]>([]);
  const [templates, setTemplates] = createSignal<AlertTemplate[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [configs, setConfigs] = createSignal<Array<{ id: number; name: string }>>([]);
  const [history, setHistory] = createSignal<any[]>([]);
  const [error, setError] = createSignal('');
  const [saving, setSaving] = createSignal(false);
  const [busyRuleId, setBusyRuleId] = createSignal<number | null>(null);
  const [testResult, setTestResult] = createSignal<Record<number, string>>({});
  const [showNewDialog, setShowNewDialog] = createSignal(false);
  const [formData, setFormData] = createSignal<Partial<AlertRule>>({
    name: '', description: '',
    metric: 'latency',
    condition: 'gt',
    threshold: 5000,
    severity: 'warning',
    enabled: true,
    duration_seconds: 300,
    cooldown_seconds: 900,
    config_ids: [],
    notification_channels: [],
  });

  const loadRules = async () => {
    try {
      setLoading(true);
      const res = await apiClient.listAlertRules();
      setRules(res.data?.rules || []);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load alert rules.'));
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const res = await apiClient.listAlertTemplates();
      setTemplates(res.data?.templates || []);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load alert templates.'));
    }
  };

  const loadSupportingData = async () => {
    const [configResult, historyResult] = await Promise.allSettled([
      apiClient.listConfigs(), apiClient.listAlertHistory(),
    ]);
    if (configResult.status === 'fulfilled') setConfigs(configResult.value.data?.configs || []);
    else setError(apiErrorMessage(configResult.reason, 'Could not load configurations.'));
    if (historyResult.status === 'fulfilled') setHistory(historyResult.value.data?.evaluations || []);
    else setError(apiErrorMessage(historyResult.reason, 'Could not load alert history.'));
  };

  createEffect(() => {
    loadRules();
    loadTemplates();
    loadSupportingData();
  });

  const resetForm = () => setFormData({
    name: '', description: '', metric: 'latency', condition: 'gt', threshold: 5000,
    severity: 'warning', enabled: true, duration_seconds: 300, cooldown_seconds: 900,
    config_ids: [], notification_channels: [],
  });

  const handleCreateRule = async (event: SubmitEvent) => {
    event.preventDefault();
    if (!formData().name?.trim()) {
      setError('Rule name is required.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      await apiClient.createAlertRule({ ...formData(), name: formData().name!.trim() });
      setShowNewDialog(false);
      resetForm();
      await loadRules();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to create the alert rule.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRule = async (id: number) => {
    if (!confirm('Delete this alert rule?')) return;
    setError('');
    try {
      await apiClient.deleteAlertRule(id);
      await loadRules();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete rule.'));
    }
  };

  const handleToggleRule = async (rule: AlertRule) => {
    setBusyRuleId(rule.id);
    setError('');
    try {
      await apiClient.updateAlertRule(rule.id, { enabled: !rule.enabled });
      await loadRules();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to update rule status.'));
    } finally {
      setBusyRuleId(null);
    }
  };

  const handleTestRule = async (rule: AlertRule) => {
    setBusyRuleId(rule.id);
    setError('');
    try {
      const result = (await apiClient.testAlertRule(rule.id)).data;
      setTestResult((current) => ({ ...current, [rule.id]: result.message || (result.triggered ? 'Rule triggered.' : 'No alert triggered.') }));
      const latest = await apiClient.listAlertHistory();
      setHistory(latest.data?.evaluations || []);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not test this alert rule.'));
    } finally {
      setBusyRuleId(null);
    }
  };

  const handleSuppress = async (evaluationId: number) => {
    try {
      setError('');
      await apiClient.suppressAlert(evaluationId, 24);
      const result = await apiClient.listAlertHistory();
      setHistory(result.data?.evaluations || []);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not suppress this alert.'));
    }
  };

  const handleApplyTemplate = (template: AlertTemplate) => {
    setFormData({
      name: `${template.name} - New Rule`,
      description: template.description,
      metric: template.metric,
      condition: template.condition,
      threshold: template.threshold,
      severity: template.severity,
      enabled: true,
      duration_seconds: 300,
      cooldown_seconds: 900,
      config_ids: [],
      notification_channels: [],
    });
    setError('');
    setShowNewDialog(true);
  };

  return (
    <section class="page-stack alerts-page">
      <div class="page-heading">
        <div><p class="page-eyebrow">Monitoring</p><h1>Alert rules</h1><p class="page-description">Define thresholds, test rules against current metrics, and review recent evaluations.</p></div>
        <button
          type="button" onClick={() => { resetForm(); setError(''); setShowNewDialog(true); }}
          class="button button--primary"
        >
          Create alert rule
        </button>
      </div>

      <Show when={error()}><div class="notice notice--error" role="alert">{error()}</div></Show>

      <Show when={loading()}>
        <div class="surface-card surface-card--empty" aria-live="polite">Loading alert rules…</div>
      </Show>

      {/* Alert Rules List */}
      <Show when={!loading() && rules().length > 0}>
        <article class="surface-card">
          <div class="section-heading"><h2>Rules <span class="count-badge">{rules().length}</span></h2><p>Enabled rules are eligible for evaluation by the alert service.</p></div>
          <div class="alert-rule-list">
            <For each={rules()}>
              {(rule) => (
                <div class="alert-rule-row">
                  <div class="alert-rule-row__summary">
                    <div class="alert-rule-row__title"><strong>{rule.name}</strong><span class={`severity-pill severity-pill--${rule.severity}`}>{rule.severity}</span><span class={`status-pill ${rule.enabled ? '' : 'status-pill--muted'}`}>{rule.enabled ? 'Enabled' : 'Paused'}</span></div>
                    <p>{rule.description || `${rule.metric} ${rule.condition} ${rule.threshold}`}</p>
                    <small>{rule.metric} · {rule.condition} · threshold {rule.threshold} · evaluation {rule.duration_seconds ?? 300}s · cooldown {rule.cooldown_seconds ?? 900}s</small>
                    <Show when={testResult()[rule.id]}><span class="alert-test-result" role="status">{testResult()[rule.id]}</span></Show>
                  </div>
                  <div class="alert-rule-row__actions">
                    <button class="button button--secondary" type="button" disabled={busyRuleId() === rule.id} onClick={() => handleTestRule(rule)}>{busyRuleId() === rule.id ? 'Working…' : 'Test now'}</button>
                    <button class="button button--secondary" type="button" disabled={busyRuleId() === rule.id} onClick={() => handleToggleRule(rule)}>{rule.enabled ? 'Pause' : 'Enable'}</button>
                    <button class="button button--danger" type="button" onClick={() => handleDeleteRule(rule.id)}>Delete</button>
                  </div>
                </div>
              )}
            </For>
          </div>
        </article>
      </Show>
      <Show when={!loading() && rules().length === 0}><article class="surface-card empty-state"><strong>No alert rules yet</strong><p>Create a rule or start from a template below.</p><button class="button button--primary" type="button" onClick={() => { resetForm(); setShowNewDialog(true); }}>Create your first rule</button></article></Show>

      {/* Templates */}
      <Show when={templates().length > 0}>
        <article class="surface-card">
          <div class="section-heading"><h2>Templates</h2><p>Start with a sensible threshold, then tailor it to your workload.</p></div>
          <div class="alert-template-list">
            <For each={templates()}>
              {(template) => (
                <div class="border border-gray-200 rounded p-4 hover:shadow-lg transition-shadow">
                  <h3 class="font-semibold">{template.name}</h3>
                  <p class="text-sm text-gray-600 my-2">{template.description}</p>
                  <p class="text-xs text-gray-500 mb-3">
                    {template.metric} {template.condition} {template.threshold}
                  </p>
                  <button
                    type="button"
                    onClick={() => handleApplyTemplate(template)}
                    class="w-full px-3 py-2 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 text-sm"
                  >
                    Use Template
                  </button>
                </div>
              )}
            </For>
          </div>
        </article>
      </Show>

      <article class="surface-card">
        <div class="section-heading"><h2>Recent evaluations</h2><p>Latest evaluations recorded by the alert service.</p></div>
        <Show when={history().length > 0} fallback={<div class="empty-state">No alert evaluations have been recorded.</div>}>
          <div class="alert-history-list"><For each={history()}>{(evaluation) => <div class="alert-history-row">
            <div><strong>{evaluation.message || `${evaluation.metric || 'Metric'} evaluation`}</strong><small>{evaluation.evaluated_at ? new Date(evaluation.evaluated_at).toLocaleString() : 'Time unavailable'} · {evaluation.actual_value ?? 'No data'} / {evaluation.threshold ?? '—'}</small></div>
            <div class="alert-history-row__actions"><span class={`status-pill ${evaluation.triggered ? 'status-pill--alert' : ''}`}>{evaluation.triggered ? 'Triggered' : 'No trigger'}</span>{evaluation.triggered && !evaluation.suppressed && <button class="button button--secondary" type="button" onClick={() => handleSuppress(evaluation.id)}>Mute 24h</button>}{evaluation.suppressed && <span class="status-pill status-pill--muted">Muted</span>}</div>
          </div>}</For></div>
        </Show>
      </article>

      {/* New Rule Dialog */}
      <Show when={showNewDialog()}>
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <form class="surface-card alert-dialog" onSubmit={handleCreateRule}>
            <h2 class="text-xl font-bold mb-4">Create alert rule</h2>

            <div class="alert-form-grid">
              <div>
                <label class="block text-sm font-medium mb-1">Rule name <b>*</b></label>
                <input
                  type="text"
                  value={formData().name || ''}
                  onInput={(e) => setFormData({...formData(), name: e.currentTarget.value})}
                  class="w-full px-3 py-2 border border-gray-300 rounded"
                  placeholder="e.g. High replication lag" required maxlength="120"
                />
              </div>

              <label class="block text-sm font-medium">Description<textarea value={formData().description || ''} onInput={(e) => setFormData({...formData(), description: e.currentTarget.value})} class="mt-1 w-full rounded border border-gray-300 px-3 py-2" rows="2" maxlength="500" placeholder="What should operators do when this triggers?" /></label>

              <div>
                <label class="block text-sm font-medium mb-1">Metric</label>
                <select
                  value={formData().metric || 'latency'}
                  onChange={(e) => setFormData({...formData(), metric: e.currentTarget.value})}
                  class="w-full px-3 py-2 border border-gray-300 rounded"
                >
                  <option value="latency">Latency (ms)</option>
                  <option value="throughput">Throughput (docs/sec)</option>
                  <option value="error_rate">Error Rate (%)</option>
                  <option value="batch_duration">Batch Duration (sec)</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium mb-1">Condition</label>
                <select
                  value={formData().condition || 'gt'}
                  onChange={(e) => setFormData({...formData(), condition: e.currentTarget.value})}
                  class="w-full px-3 py-2 border border-gray-300 rounded"
                >
                  <option value="gt">Greater than</option>
                  <option value="gte">Greater or equal</option>
                  <option value="lt">Less than</option>
                  <option value="lte">Less or equal</option>
                  <option value="eq">Equal</option>
                  <option value="anomaly">Anomaly Detection</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium mb-1">Threshold</label>
                <input
                  type="number"
                  value={formData().threshold ?? 0}
                  onInput={(e) => setFormData({...formData(), threshold: e.currentTarget.valueAsNumber})}
                  class="w-full px-3 py-2 border border-gray-300 rounded"
                  step="any" required
                />
              </div>

              <label class="block text-sm font-medium">Evaluation window (seconds)<input type="number" min="0" max="86400" value={formData().duration_seconds ?? 300} onInput={(e) => setFormData({...formData(), duration_seconds: e.currentTarget.valueAsNumber})} class="mt-1 w-full rounded border border-gray-300 px-3 py-2" required /></label>
              <label class="block text-sm font-medium">Cooldown (seconds)<input type="number" min="0" max="604800" value={formData().cooldown_seconds ?? 900} onInput={(e) => setFormData({...formData(), cooldown_seconds: e.currentTarget.valueAsNumber})} class="mt-1 w-full rounded border border-gray-300 px-3 py-2" required /></label>

              <div>
                <label class="block text-sm font-medium mb-1">Severity</label>
                <select
                  value={formData().severity || 'warning'}
                  onChange={(e) => setFormData({...formData(), severity: e.currentTarget.value})}
                  class="w-full px-3 py-2 border border-gray-300 rounded"
                >
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <label class="block text-sm font-medium">Configurations
                <select multiple value={(formData().config_ids || []).map(String)} onChange={(e) => setFormData({...formData(), config_ids: Array.from(e.currentTarget.selectedOptions, (option) => Number(option.value))})} class="mt-1 min-h-24 w-full rounded border border-gray-300 px-3 py-2">
                  <For each={configs()}>{(config) => <option value={config.id}>{config.name}</option>}</For>
                </select><small class="mt-1 block font-normal text-gray-500">Leave unselected to apply to all configurations.</small>
              </label>
              <fieldset class="rounded border border-gray-200 p-3"><legend class="px-1 text-sm font-medium">Notification channels</legend><div class="flex flex-wrap gap-3"><For each={['email', 'telegram', 'slack', 'webhook']}>{(channel) => <label class="flex items-center gap-2 text-sm font-normal"><input type="checkbox" checked={(formData().notification_channels || []).includes(channel)} onChange={(e) => setFormData({...formData(), notification_channels: e.currentTarget.checked ? [...(formData().notification_channels || []), channel] : (formData().notification_channels || []).filter((item) => item !== channel)})} />{channel}</label>}</For></div><small class="mt-2 block text-gray-500">Channels need server-side credentials before delivery can work.</small></fieldset>
              <label class="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={formData().enabled !== false} onChange={(e) => setFormData({...formData(), enabled: e.currentTarget.checked})} />Enable this rule after creation</label>
            </div>

            <Show when={error()}><div class="notice notice--error mt-4" role="alert">{error()}</div></Show>
            <div class="flex gap-2 justify-end mt-6">
              <button
                type="button"
                onClick={() => setShowNewDialog(false)}
                class="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit" disabled={saving()}
                class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                {saving() ? 'Saving…' : 'Create Rule'}
              </button>
            </div>
          </form>
        </div>
      </Show>
    </section>
  );
}
