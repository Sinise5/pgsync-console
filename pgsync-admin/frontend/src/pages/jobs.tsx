import { createSignal, createEffect, For, Show } from 'solid-js';
import { apiClient } from '@/lib/api-client';
import { apiErrorMessage } from '@/lib/api-client';
import { Card, Badge, Button } from '@/components/ui';
import { CronBuilder } from '@/components/cron-builder';

export function JobsPage() {
  const [jobs, setJobs] = createSignal<any[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [showForm, setShowForm] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [busyJobId, setBusyJobId] = createSignal<number | null>(null);

  createEffect(() => loadJobs());

  async function loadJobs() {
    setLoading(true);
    try {
      const resp = await apiClient.listJobs();
      setJobs(resp.data.jobs || []);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load scheduled jobs.'));
    } finally {
      setLoading(false);
    }
  }

  async function handlePauseResume(job: any) {
    setBusyJobId(job.id);
    setError(null);
    try {
      if (job.enabled) {
        await apiClient.pauseJob(job.id);
      } else {
        await apiClient.resumeJob(job.id);
      }
      await loadJobs();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not update this job.'));
    } finally {
      setBusyJobId(null);
    }
  }

  async function handleDelete(jobId: number) {
    if (!confirm('Delete this job?')) return;
    setBusyJobId(jobId);
    setError(null);
    try {
      await apiClient.deleteJob(jobId);
      await loadJobs();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not delete this job.'));
    } finally {
      setBusyJobId(null);
    }
  }

  async function handleTrigger(jobId: number) {
    setBusyJobId(jobId);
    setError(null);
    try {
      await apiClient.triggerJob(jobId);
      await loadJobs();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not start this job.'));
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <div class="space-y-6">
      <div class="flex justify-between items-center">
        <div>
          <h1 class="text-3xl font-bold">Scheduled Jobs</h1>
          <p class="text-gray-600 mt-1">Manage recurring sync jobs</p>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm())}>
          {showForm() ? 'Close' : '+ New Job'}
        </Button>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">{error()}</div>
      </Show>

      <Show when={showForm()}>
        <CronBuilder onCreated={() => { setShowForm(false); loadJobs(); }} />
      </Show>

      <Show when={loading()}>
        <div class="text-center text-gray-500 py-8">Loading jobs...</div>
      </Show>

      <Card title={`Scheduled Jobs (${jobs().length})`}>
        <Show when={jobs().length === 0 && !loading()}>
          <div class="text-center text-gray-500 py-8">No jobs configured yet</div>
        </Show>
        <div class="space-y-3">
          <For each={jobs()}>
            {(job) => (
              <div class="border rounded-lg p-4 hover:bg-gray-50">
                <div class="flex justify-between items-start">
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <Badge variant={job.enabled ? 'default' : 'secondary'}>
                        {job.enabled ? 'Active' : 'Paused'}
                      </Badge>
                      <span class="font-semibold">{job.name}</span>
                      <span class="text-xs text-gray-500">#{job.id}</span>
                    </div>
                    <div class="mt-2 space-y-1 text-sm text-gray-600">
                      <p>Cron: <code class="bg-gray-100 px-1 rounded">{job.cron_expression}</code></p>
                      <p>Config: #{job.config_id} | Type: {job.execution_type}</p>
                      <p>Runs: {job.run_count} | Failures: {job.failure_count} | Retries: {job.max_retries}</p>
                      <Show when={job.next_run}>
                        <p>Next: {new Date(job.next_run).toLocaleString()}</p>
                      </Show>
                    </div>
                  </div>
                  <div class="flex gap-2 ml-4">
                    <Button size="sm" variant="secondary" disabled={busyJobId() === job.id} onClick={() => handleTrigger(job.id)}>
                      ▶ Run
                    </Button>
                    <Button size="sm" variant="secondary" disabled={busyJobId() === job.id} onClick={() => handlePauseResume(job)}>
                      {job.enabled ? '⏸ Pause' : '▶ Resume'}
                    </Button>
                    <Button size="sm" variant="danger" disabled={busyJobId() === job.id} onClick={() => handleDelete(job.id)}>
                      🗑
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </For>
        </div>
      </Card>
    </div>
  );
}
