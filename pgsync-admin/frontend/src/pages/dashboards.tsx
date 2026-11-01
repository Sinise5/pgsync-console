import { createSignal, createEffect, For, Show } from 'solid-js';
import { A } from '@solidjs/router';
import { apiClient } from '@/lib/api-client';

interface Dashboard {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  is_shared: boolean;
  share_token?: string;
  widgets?: Widget[];
}

interface Widget {
  id: number;
  dashboard_id: number;
  widget_type: string;
  title: string;
  config: any;
  position: number;
}

export function DashboardsPage() {
  const [dashboards, setDashboards] = createSignal<Dashboard[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [showNewDialog, setShowNewDialog] = createSignal(false);
  const [newDashboardName, setNewDashboardName] = createSignal('');
  const [newDashboardDesc, setNewDashboardDesc] = createSignal('');

  const loadDashboards = async () => {
    try {
      setLoading(true);
      const res = await apiClient.listDashboards();
      setDashboards(res.data.dashboards || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboards');
    } finally {
      setLoading(false);
    }
  };

  createEffect(() => {
    loadDashboards();
  });

  const handleCreateDashboard = async () => {
    if (!newDashboardName().trim()) {
      alert('Dashboard name is required');
      return;
    }

    try {
      await apiClient.createDashboard({
        name: newDashboardName(),
        description: newDashboardDesc(),
      });
      setNewDashboardName('');
      setNewDashboardDesc('');
      setShowNewDialog(false);
      await loadDashboards();
    } catch (err: any) {
      alert(`Failed to create dashboard: ${err.message}`);
    }
  };

  const handleDeleteDashboard = async (id: number) => {
    if (!confirm('Are you sure you want to delete this dashboard?')) return;

    try {
      await apiClient.deleteDashboard(id);
      await loadDashboards();
    } catch (err: any) {
      alert(`Failed to delete dashboard: ${err.message}`);
    }
  };

  return (
    <div class="p-6">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">Custom Dashboards</h1>
        <button
          onClick={() => setShowNewDialog(true)}
          class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          + New Dashboard
        </button>
      </div>

      <Show when={loading()}>
        <div class="text-center py-8">Loading dashboards...</div>
      </Show>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error()}
        </div>
      </Show>

      <Show when={!loading() && dashboards().length === 0}>
        <div class="text-center py-12 bg-gray-50 rounded-lg">
          <p class="text-gray-600 mb-4">No dashboards yet</p>
          <button
            onClick={() => setShowNewDialog(true)}
            class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Create Your First Dashboard
          </button>
        </div>
      </Show>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <For each={dashboards()}>
          {(dashboard) => (
            <div class="border border-gray-200 rounded-lg p-4 hover:shadow-lg transition-shadow">
              <div class="flex justify-between items-start mb-2">
                <h3 class="text-lg font-semibold">{dashboard.name}</h3>
                <button
                  onClick={() => handleDeleteDashboard(dashboard.id)}
                  class="text-red-500 hover:text-red-700"
                >
                  ×
                </button>
              </div>

              <Show when={dashboard.description}>
                <p class="text-sm text-gray-600 mb-3">{dashboard.description}</p>
              </Show>

              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>
                  {dashboard.widgets?.length || 0} widget{dashboard.widgets?.length !== 1 ? 's' : ''}
                </span>
                <span>{new Date(dashboard.created_at).toLocaleDateString()}</span>
              </div>

              <div class="mt-4 flex gap-2">
                <A
                  href={`/dashboards/${dashboard.id}`}
                  class="flex-1 text-center px-3 py-2 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                >
                  View
                </A>
                <A
                  href={`/dashboards/${dashboard.id}/edit`}
                  class="flex-1 text-center px-3 py-2 bg-gray-50 text-gray-600 rounded hover:bg-gray-100"
                >
                  Edit
                </A>
              </div>

              <Show when={dashboard.is_shared}>
                <div class="mt-2 text-xs text-green-600">
                  🔗 Shared
                </div>
              </Show>
            </div>
          )}
        </For>
      </div>

      {/* New Dashboard Dialog */}
      <Show when={showNewDialog()}>
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 class="text-xl font-bold mb-4">Create New Dashboard</h2>

            <div class="mb-4">
              <label class="block text-sm font-medium mb-1">Dashboard Name</label>
              <input
                type="text"
                value={newDashboardName()}
                onInput={(e) => setNewDashboardName(e.currentTarget.value)}
                class="w-full px-3 py-2 border border-gray-300 rounded"
                placeholder="My Custom Dashboard"
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium mb-1">Description (optional)</label>
              <textarea
                value={newDashboardDesc()}
                onInput={(e) => setNewDashboardDesc(e.currentTarget.value)}
                class="w-full px-3 py-2 border border-gray-300 rounded"
                rows="3"
                placeholder="Dashboard description..."
              />
            </div>

            <div class="flex gap-2 justify-end">
              <button
                onClick={() => setShowNewDialog(false)}
                class="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDashboard}
                class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      </Show>
    </div>
  );
}
