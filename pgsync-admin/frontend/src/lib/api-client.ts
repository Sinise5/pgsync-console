import axios, { AxiosInstance } from 'axios';

export function apiErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as { error?: unknown; detail?: unknown; message?: unknown } | undefined;
    const message = payload?.error ?? payload?.detail ?? payload?.message;
    if (typeof message === 'string' && message.trim()) return message;
    if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
    if (!error.response) return 'Unable to reach the server. Check your connection and try again.';
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

const API_BASE = '/api';

export class ApiClient {
  public client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('pgsync_admin_token');
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401 && !error.config?.url?.endsWith('/auth/login')) {
          localStorage.removeItem('pgsync_admin_token');
          window.dispatchEvent(new Event('pgsync-auth-expired'));
        }
        return Promise.reject(error);
      },
    );
  }

  async login(username: string, password: string) {
    return this.client.post('/auth/login', { username, password });
  }

  async getDemoCredentials() {
    return this.client.get('/auth/demo-credentials');
  }

  // Config endpoints
  async createConfig(config: any) {
    return this.client.post('/config/new', config);
  }

  async createConfiguration(config: any) {
    return this.createConfig(config);
  }

  async listConfigs() {
    return this.client.get('/config/list');
  }

  async getConfig(id: number) {
    return this.client.get(`/config/${id}`);
  }

  async updateConfig(id: number, config: any) {
    return this.client.put(`/config/${id}`, config);
  }

  async updateConfiguration(id: number, config: any) {
    return this.updateConfig(id, config);
  }

  async deleteConfig(id: number) {
    return this.client.delete(`/config/${id}`);
  }

  // Discovery endpoints
  async testConnection(params: any) {
    return this.client.post('/discover/test', params);
  }

  async testTargetConnection(params: any) {
    return this.client.post('/discover/test-target', params);
  }

  async getTables(params: any) {
    return this.client.post('/discover/tables', params);
  }

  async getSchema(params: any) {
    return this.client.post('/discover/schema', params);
  }

  // Execution endpoints
  async listExecutions() {
    return this.client.get('/execution');
  }

  async startBatchMigration(config_id: number, pgsync_schema: any) {
    return this.client.post('/execution/batch', {
      config_id,
      pgsync_schema,
    });
  }

  async startExecutionCDC(config_id: number, pgsync_schema: any) {
    return this.client.post('/execution/cdc', {
      config_id,
      pgsync_schema,
    });
  }

  async stopExecution(execution_id: number) {
    return this.client.post(`/execution/${execution_id}/stop`);
  }

  async getExecutionStatus(execution_id: number) {
    return this.client.get(`/execution/${execution_id}/status`);
  }

  // Logs endpoints
  async getLogs(execution_id: number, limit = 100, level?: string) {
    const params: any = { limit };
    if (level) params.level = level;
    return this.client.get(`/logs/${execution_id}`, { params });
  }

  async getMetrics(execution_id: number, table_name?: string) {
    const params: any = {};
    if (table_name) params.table_name = table_name;
    return this.client.get(`/metrics/${execution_id}`, { params });
  }

  async getSummary(execution_id: number) {
    return this.client.get(`/summary/${execution_id}`);
  }

  async getDailyReport(days: number = 7) {
    return this.client.get('/reports/daily', { params: { days } });
  }

  async getWeeklyReport(weeks: number = 4) {
    return this.client.get('/reports/weekly', { params: { weeks } });
  }

  async getTableStats(config_id?: string) {
    const params: any = {};
    if (config_id) params.config_id = config_id;
    return this.client.get('/reports/table-stats', { params });
  }

  async exportReport(format: 'csv' | 'json', days: number = 7) {
    return this.client.get(`/reports/export/${format}`, { params: { days } });
  }

  // Dashboard management
  async listDashboards() {
    return this.client.get('/dashboards');
  }

  async getDashboard(id: number) {
    return this.client.get(`/dashboards/${id}`);
  }

  async createDashboard(data: { name: string; description?: string; is_shared?: boolean }) {
    return this.client.post('/dashboards', data);
  }

  async updateDashboard(id: number, data: any) {
    return this.client.put(`/dashboards/${id}`, data);
  }

  async deleteDashboard(id: number) {
    return this.client.delete(`/dashboards/${id}`);
  }

  async addWidget(dashboardId: number, widget: any) {
    return this.client.post(`/dashboards/${dashboardId}/widgets`, widget);
  }

  async updateWidget(dashboardId: number, widgetId: number, data: any) {
    return this.client.put(`/dashboards/${dashboardId}/widgets/${widgetId}`, data);
  }

  async deleteWidget(dashboardId: number, widgetId: number) {
    return this.client.delete(`/dashboards/${dashboardId}/widgets/${widgetId}`);
  }

  // Alert management
  async listAlertRules() {
    return this.client.get('/alerts/rules');
  }

  async createAlertRule(data: any) {
    return this.client.post('/alerts/rules', data);
  }

  async updateAlertRule(id: number, data: any) {
    return this.client.put(`/alerts/rules/${id}`, data);
  }

  async deleteAlertRule(id: number) {
    return this.client.delete(`/alerts/rules/${id}`);
  }

  async testAlertRule(id: number) {
    return this.client.post(`/alerts/rules/${id}/test`, {});
  }

  async listAlertHistory() {
    return this.client.get('/alerts/history');
  }

  async suppressAlert(id: number, hours: number = 24) {
    return this.client.post(`/alerts/${id}/suppress`, { hours });
  }

  async listAlertTemplates() {
    return this.client.get('/alerts/templates');
  }

  // Lineage management
  async getLineageGraph() {
    return this.client.get('/lineage/graph');
  }

  async getConfigLineage(configId: number) {
    return this.client.get(`/lineage/${configId}`);
  }

  async discoverConfigLineage(configId: number) {
    return this.client.post(`/lineage/${configId}/discover`, {});
  }

  async discoverAllLineage() {
    return this.client.post('/lineage/discover-all', {});
  }

  // Job management
  async listJobs() {
    return this.client.get('/jobs');
  }

  async createJob(data: any) {
    return this.client.post('/jobs', data);
  }

  async updateJob(jobId: number, data: any) {
    return this.client.patch(`/jobs/${jobId}`, data);
  }

  async deleteJob(jobId: number) {
    return this.client.delete(`/jobs/${jobId}`);
  }

  async pauseJob(jobId: number) {
    return this.client.post(`/jobs/${jobId}/pause`);
  }

  async resumeJob(jobId: number) {
    return this.client.post(`/jobs/${jobId}/resume`);
  }

  async triggerJob(jobId: number) {
    return this.client.post(`/jobs/${jobId}/run`);
  }

  async getConfigurations() {
    return this.listConfigs();
  }

  // Migration endpoints
  async listMigrations() {
    return this.client.get('/migrations');
  }

  async createMigration(data: any) {
    return this.client.post('/migrations', data);
  }

  async getMigration(id: number) {
    return this.client.get(`/migrations/${id}`);
  }

  async cancelMigration(id: number) {
    return this.client.post(`/migrations/${id}/cancel`);
  }

  async getMigrationErrors(id: number) {
    return this.client.get(`/migrations/${id}/errors`);
  }

  async deleteMigration(id: number) {
    return this.client.delete(`/migrations/${id}`);
  }

  async previewMigrationSchema(configId: number) {
    return this.client.post(`/migrations/preview-schema`, { config_id: configId });
  }

  // Generic get method for direct API calls
  async get(url: string) {
    return this.client.get(url);
  }

  // CDC endpoints
  async startCDC(config_id: number) {
    return this.client.post(`/cdc/${config_id}/start`, {});
  }

  async stopCDC(config_id: number) {
    return this.client.post(`/cdc/${config_id}/stop`, {});
  }

  async getCDCStatus(config_id: number) {
    return this.client.get(`/cdc/${config_id}/status`);
  }

  async getCDCLogs(config_id: number) {
    return this.client.get(`/cdc/${config_id}/logs`);
  }
}

export const apiClient = new ApiClient();
