import { createSignal, For, Show } from 'solid-js';
import { apiClient, apiErrorMessage } from '@/lib/api-client';
import { Card, Badge, Button } from '@/components/ui';

interface CronBuilderProps {
  onCreated: () => void;
}

const PRESETS = [
  { label: 'Every hour', cron: '0 * * * *' },
  { label: 'Every 6 hours', cron: '0 */6 * * *' },
  { label: 'Daily at 2am', cron: '0 2 * * *' },
  { label: 'Weekly (Mon 8am)', cron: '0 8 * * 1' },
  { label: 'Weekly (Sun 3pm)', cron: '0 15 * * 0' },
  { label: 'Monthly 1st 3am', cron: '0 3 1 * *' },
];

const MINUTE_OPTS = Array.from({ length: 60 }, (_, i) => i);
const HOUR_OPTS = Array.from({ length: 24 }, (_, i) => i);
const DAY_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DAY_OF_MONTH = Array.from({ length: 31 }, (_, i) => i + 1);

export function CronBuilder(props: CronBuilderProps) {
  const [minute, setMinute] = createSignal(0);
  const [hour, setHour] = createSignal(2);
  const [dayOfMonth, setDayOfMonth] = createSignal<any>('*');
  const [month, setMonth] = createSignal('*');
  const [dayOfWeek, setDayOfWeek] = createSignal('*');
  const [name, setName] = createSignal('');
  const [configId, setConfigId] = createSignal<number | null>(null);
  const [configs, setConfigs] = createSignal<any[]>([]);
  const [configError, setConfigError] = createSignal('');
  const [loading, setLoading] = createSignal(false);
  const [customCron, setCustomCron] = createSignal(false);
  const [cronInput, setCronInput] = createSignal('0 */6 * * *');
  const [error, setError] = createSignal<string | null>(null);
  const [timezone, setTimezone] = createSignal(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [executionType, setExecutionType] = createSignal<'batch' | 'cdc'>('batch');
  const [retryOnFailure, setRetryOnFailure] = createSignal(true);
  const [maxRetries, setMaxRetries] = createSignal(3);
  const [timeoutSeconds, setTimeoutSeconds] = createSignal(3600);
  const [notifications, setNotifications] = createSignal<string[]>([]);
  const [notifyOnSuccess, setNotifyOnSuccess] = createSignal(false);
  const [notifyOnFailure, setNotifyOnFailure] = createSignal(true);
  const selectedConfig = () => configs().find((config) => config.id === configId());
  const allowsBatch = () => selectedConfig()?.pipeline_type !== 'pg_replication';
  const allowsCdc = () => selectedConfig()?.pipeline_type !== 'pg_copy';

  const cronExpr = () =>
    customCron() ? cronInput() : `${minute()} ${hour()} ${dayOfMonth()} ${month()} ${dayOfWeek()}`;

  const isValidCron = () => {
    const parts = cronExpr().trim().split(/\s+/);
    return parts.length === 5 && parts.every(Boolean);
  };

  const loadConfigs = async () => {
    try {
      const resp = await apiClient.getConfigurations();
      setConfigs(resp.data.configs || []);
      setConfigError('');
    } catch (err) {
      setConfigError(apiErrorMessage(err, 'Could not load configurations.'));
    }
  };

  loadConfigs();

  const handleSubmit = async () => {
    if (!name().trim() || configId() === null || configId() === 0) {
      setError('Name and config are required');
      return;
    }
    if (!isValidCron()) {
      setError('Invalid cron expression');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiClient.createJob({
        name: name().trim(),
        config_id: configId(),
        cron_expression: cronExpr(),
        timezone: timezone(),
        execution_type: executionType(),
        retry_on_failure: retryOnFailure(),
        max_retries: maxRetries(),
        timeout_seconds: timeoutSeconds(),
        notifications: notifications(),
        notify_on_success: notifyOnSuccess(),
        notify_on_failure: notifyOnFailure(),
      });
      props.onCreated();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the scheduled job.'));
    } finally {
      setLoading(false);
    }
  };

  const applyPreset = (cron: string) => {
    setCustomCron(true);
    setCronInput(cron);
  };

  return (
    <Card title="Create Scheduled Job">
      <div class="space-y-4">
        {/* Presets */}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Quick Presets</label>
          <div class="flex flex-wrap gap-2">
            <For each={PRESETS}>
              {(preset) => (
                <button
                  type="button"
                  class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                  onClick={() => applyPreset(preset.cron)}
                >
                  {preset.label}
                </button>
              )}
            </For>
          </div>
        </div>

        {/* Name */}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Job Name</label>
          <input
            type="text"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg"
            placeholder="e.g., Daily Postgres Sync"
            value={name()}
            onChange={(e) => setName(e.currentTarget.value)}
          />
        </div>

        {/* Config */}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Configuration</label>
          <select
            class="w-full px-4 py-2 border border-gray-300 rounded-lg bg-white"
            required
            value={configId() ?? ''}
            onChange={(e) => {
              const id = e.currentTarget.value ? Number(e.currentTarget.value) : null;
              setConfigId(id);
              const selected = configs().find((config) => config.id === id);
              if (selected?.pipeline_type === 'pg_replication') setExecutionType('cdc');
              if (selected?.pipeline_type === 'pg_copy') setExecutionType('batch');
            }}
          >
            <option value="">Select a config...</option>
            <For each={configs()}>
              {(config) => (
                <option value={config.id}>{config.name}</option>
              )}
            </For>
          </select>
          <Show when={configError()}><p class="text-sm text-red-700" role="alert">{configError()}</p></Show>
          <Show when={!configError() && configs().length === 0}><p class="text-sm text-gray-500">Create an active configuration before scheduling a job.</p></Show>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label class="block text-sm font-medium text-gray-700">Execution type
            <select class="mt-2 w-full rounded border border-gray-300 bg-white px-3 py-2" value={executionType()} onChange={(e) => setExecutionType(e.currentTarget.value as 'batch' | 'cdc')}>
              <Show when={allowsBatch()}><option value="batch">Batch sync</option></Show>
              <Show when={allowsCdc()}><option value="cdc">Continuous CDC</option></Show>
            </select>
          </label>
          <label class="block text-sm font-medium text-gray-700">Time zone
            <input class="mt-2 w-full rounded border border-gray-300 px-3 py-2" value={timezone()} onInput={(e) => setTimezone(e.currentTarget.value.trim())} required placeholder="Asia/Jakarta" />
          </label>
          <label class="block text-sm font-medium text-gray-700">Timeout (seconds)
            <input class="mt-2 w-full rounded border border-gray-300 px-3 py-2" type="number" min="1" max="86400" value={timeoutSeconds()} onInput={(e) => setTimeoutSeconds(e.currentTarget.valueAsNumber)} required />
          </label>
          <label class="block text-sm font-medium text-gray-700">Maximum retries
            <input class="mt-2 w-full rounded border border-gray-300 px-3 py-2" type="number" min="0" max="20" value={maxRetries()} onInput={(e) => setMaxRetries(e.currentTarget.valueAsNumber)} disabled={!retryOnFailure()} required />
          </label>
        </div>

        <fieldset class="grid gap-3 border-t pt-4">
          <legend class="text-sm font-semibold text-gray-700">Failure handling and notifications</legend>
          <label class="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={retryOnFailure()} onChange={(e) => setRetryOnFailure(e.currentTarget.checked)} />Retry after failures</label>
          <label class="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={notifyOnFailure()} onChange={(e) => setNotifyOnFailure(e.currentTarget.checked)} />Notify on failure</label>
          <label class="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={notifyOnSuccess()} onChange={(e) => setNotifyOnSuccess(e.currentTarget.checked)} />Notify on success</label>
          <div class="flex flex-wrap gap-4">
            <For each={['email', 'telegram', 'slack', 'webhook']}>{(channel) => <label class="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={notifications().includes(channel)} onChange={(e) => setNotifications((current) => e.currentTarget.checked ? [...current, channel] : current.filter((item) => item !== channel))} />{channel}</label>}</For>
          </div>
          <p class="text-xs text-gray-500">Channels must be configured on the server before notifications can be delivered.</p>
        </fieldset>

        {/* Cron Builder */}
        <div class="border-t pt-4">
          <label class="block text-sm font-medium text-gray-700 mb-3">
            <input
              type="checkbox"
              class="mr-2"
              checked={customCron()}
              onChange={() => setCustomCron(!customCron())}
            />
            Custom Cron Expression
          </label>

          <Show when={customCron()}>
            <input
              type="text"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg font-mono"
              placeholder="0 2 * * *"
              value={cronInput()}
              onChange={(e) => setCronInput(e.currentTarget.value)}
            />
            <p class="text-xs text-gray-500 mt-1">
              Format: minute hour day-of-month month day-of-week (0 2 * * * = daily 2am)
            </p>
          </Show>

          <Show when={!customCron()}>
            <div class="grid grid-cols-4 gap-4">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Minute</label>
                <select class="w-full px-2 py-2 border border-gray-300 rounded bg-white text-sm"
                  value={minute()} onChange={(e) => setMinute(parseInt(e.currentTarget.value))}>
                  <For each={MINUTE_OPTS}>{(m) => <option value={m}>{String(m).padStart(2, '0')}</option>}</For>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Hour</label>
                <select class="w-full px-2 py-2 border border-gray-300 rounded bg-white text-sm"
                  value={hour()} onChange={(e) => setHour(parseInt(e.currentTarget.value))}>
                  <For each={HOUR_OPTS}>{(h) => <option value={h}>{String(h).padStart(2, '0')}</option>}</For>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Day of Month</label>
                <select class="w-full px-2 py-2 border border-gray-300 rounded bg-white text-sm"
                  value={dayOfMonth()} onChange={(e) => setDayOfMonth(e.currentTarget.value)}>
                  <option value="*">Every Day</option>
                  <For each={DAY_OF_MONTH}>{(d) => <option value={d}>{d}</option>}</For>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Day of Week</label>
                <select class="w-full px-2 py-2 border border-gray-300 rounded bg-white text-sm"
                  value={dayOfWeek()} onChange={(e) => setDayOfWeek(e.currentTarget.value)}>
                  <option value="*">Every Day</option>
                  <For each={DAY_OF_WEEK}>{(d, i) => <option value={i()}>{d}</option>}</For>
                </select>
              </div>
            </div>
          </Show>
        </div>

        {/* Preview */}
        <div class="bg-gray-50 rounded p-3">
          <p class="text-sm">
            <span class="font-medium">Cron:</span>{' '}
            <code class="bg-gray-200 px-2 py-0.5 rounded font-mono text-sm">
              {cronExpr()}
            </code>
            <Show when={!isValidCron()}>
              <span class="text-red-500 ml-2 text-xs">Invalid</span>
            </Show>
          </p>
        </div>

        {/* Actions */}
        <Show when={error()}>
          <div class="bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">{error()}</div>
        </Show>

        <div class="flex gap-2">
          <Button onClick={handleSubmit} loading={loading()} disabled={!isValidCron() || configs().length === 0 || Boolean(configError()) || !timezone().trim()}>
            Create Job
          </Button>
        </div>
      </div>
    </Card>
  );
}
