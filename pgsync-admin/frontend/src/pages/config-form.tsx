import { createSignal, onMount, Show } from 'solid-js';
import { A, useNavigate, useParams } from '@solidjs/router';
import { apiClient, apiErrorMessage } from '@/lib/api-client';

interface ConfigurationForm {
  name: string;
  description: string;
  pipeline_type: 'pg_search' | 'pg_clickhouse' | 'pg_replication' | 'pg_copy';
  source_type: 'postgres' | 'mysql' | 'mariadb';
  source_host: string;
  source_port: number;
  source_database: string;
  source_user: string;
  source_password: string;
  target_type: 'opensearch' | 'elasticsearch' | 'clickhouse' | 'postgres';
  target_database: string;
  target_host: string;
  target_port: number;
  target_user: string;
  target_password: string;
  target_tls: boolean;
  target_verify_certs: boolean;
  target_overwrite: boolean;
}

const initialForm: ConfigurationForm = {
  name: '', description: '', pipeline_type: 'pg_search', source_type: 'postgres', source_host: 'localhost', source_port: 5432,
  source_database: '', source_user: '', source_password: '',
  target_type: 'opensearch', target_database: '', target_host: 'localhost', target_port: 9200,
  target_user: '', target_password: '', target_tls: true, target_verify_certs: true, target_overwrite: false,
};

export function ConfigFormPage() {
  const params = useParams();
  const navigate = useNavigate();
  const isEdit = () => params.id !== undefined;
  const [form, setForm] = createSignal<ConfigurationForm>({ ...initialForm });
  const [loading, setLoading] = createSignal(false);
  const [testing, setTesting] = createSignal(false);
  const [error, setError] = createSignal('');
  const [connection, setConnection] = createSignal<{ status: 'success' | 'failure'; message: string } | null>(null);
  const [targetConnection, setTargetConnection] = createSignal<{ status: 'success' | 'failure'; message: string } | null>(null);
  const [showSourcePassword, setShowSourcePassword] = createSignal(false);
  const [showTargetPassword, setShowTargetPassword] = createSignal(false);
  const [hasSavedTargetPassword, setHasSavedTargetPassword] = createSignal(false);

  onMount(async () => {
    if (!isEdit()) return;
    setLoading(true);
    try {
      const response = await apiClient.getConfig(Number(params.id));
      const config = response.data;
      setHasSavedTargetPassword(config.target?.password === '***');
      setForm({
        name: config.name || '', description: config.description || '',
        pipeline_type: config.pipeline_type || 'pg_search',
        source_type: config.source?.type || 'postgres',
        source_host: config.source?.host || 'localhost', source_port: Number(config.source?.port) || 5432,
        source_database: config.source?.database || '', source_user: config.source?.user || '', source_password: '',
        target_type: config.target?.type || 'opensearch', target_database: config.target?.database || '',
        target_host: config.target?.host || 'localhost', target_port: Number(config.target?.port) || 9200,
        target_user: config.target?.user || '', target_password: '',
        target_tls: (config.target?.scheme || 'https') === 'https',
        target_verify_certs: config.target?.verify_certs !== false,
        target_overwrite: config.target?.allow_replace === true,
      });
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load this configuration.'));
    } finally {
      setLoading(false);
    }
  });

  const update = <K extends keyof ConfigurationForm>(key: K, value: ConfigurationForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setConnection(null);
  };

  const canTestConnection = () => Boolean(
    form().source_host.trim() && form().source_database.trim() && form().source_user.trim()
      && Number.isInteger(form().source_port) && form().source_port > 0 && form().source_port <= 65535
      && (!isEdit() || form().source_password.length > 0),
  );

  const testSourceConnection = async () => {
    if (!canTestConnection()) return;
    setTesting(true);
    setConnection(null);
    setError('');
    try {
      const response = await apiClient.testConnection({
        type: form().source_type,
        host: form().source_host.trim(), port: form().source_port,
        database: form().source_database.trim(), user: form().source_user.trim(),
        password: form().source_password,
      });
      const server = response.data.server;
      setConnection({
        status: 'success',
        message: `Connected${server?.version ? ` to ${server.version}` : ''}${server?.table_count !== undefined ? ` · ${server.table_count} tables` : ''}.`,
      });
    } catch (err) {
      setConnection({ status: 'failure', message: apiErrorMessage(err, 'Connection test failed.') });
    } finally {
      setTesting(false);
    }
  };

  const canTestTarget = () => Boolean(
    form().target_host.trim() && Number.isInteger(form().target_port) && form().target_port > 0
      && form().target_port <= 65535
      && (form().pipeline_type === 'pg_search' || form().target_database.trim())
      && (!['pg_replication', 'pg_copy'].includes(form().pipeline_type)
        || (form().target_user.trim() && (form().target_password || hasSavedTargetPassword())))
      && (!isEdit() || !hasSavedTargetPassword() || form().target_password.length > 0),
  );

  const targetIsPostgres = () => form().pipeline_type === 'pg_replication' || form().pipeline_type === 'pg_copy';

  const testTargetConnection = async () => {
    if (!canTestTarget()) return;
    setTesting(true);
    setTargetConnection(null);
    try {
      const values = form();
      const type = values.pipeline_type === 'pg_search' ? values.target_type
        : values.pipeline_type === 'pg_clickhouse' ? 'clickhouse' : 'postgres';
      const response = await apiClient.testTargetConnection({
        type, host: values.target_host.trim(), port: values.target_port,
        database: values.target_database.trim(), user: values.target_user.trim(), password: values.target_password,
        scheme: values.target_tls ? 'https' : 'http', secure: values.target_tls,
        verify_certs: values.target_tls && values.target_verify_certs,
      });
      setTargetConnection({ status: 'success', message: `Connected${response.data?.server?.version ? ` to ${response.data.server.version}` : ''}.` });
    } catch (err) {
      setTargetConnection({ status: 'failure', message: apiErrorMessage(err, 'Destination connection test failed.') });
    } finally {
      setTesting(false);
    }
  };

  const submit = async (event: SubmitEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    const values = form();
    const hasTargetPassword = Boolean(values.target_password) || hasSavedTargetPassword();
    const targetIsPostgres = values.pipeline_type === 'pg_replication' || values.pipeline_type === 'pg_copy';
    if (targetIsPostgres && (!values.target_user.trim() || !hasTargetPassword)) {
      setError('PostgreSQL destination username and password are required.');
      setLoading(false);
      return;
    }
    const targetPort = Number.isInteger(values.target_port) ? values.target_port : 0;
    const payload = {
      name: values.name.trim(), description: values.description.trim(),
      pipeline_type: values.pipeline_type,
      source: {
        type: values.source_type,
        host: values.source_host.trim(), port: values.source_port,
        database: values.source_database.trim(), user: values.source_user.trim(),
        password: values.source_password,
      },
      target: {
        type: values.pipeline_type === 'pg_search' ? values.target_type : values.pipeline_type === 'pg_clickhouse' ? 'clickhouse' : 'postgres',
        host: values.target_host.trim(), port: targetPort, database: values.target_database.trim(),
        user: values.target_user.trim(), password: values.target_password,
        scheme: values.target_tls ? 'https' : 'http', verify_certs: values.target_tls && values.target_verify_certs,
        sslmode: values.target_tls ? 'require' : 'prefer', allow_replace: values.target_overwrite,
      },
      ...(!isEdit() ? { schema: {} } : {}),
    };

    try {
      const response = isEdit()
        ? await apiClient.updateConfiguration(Number(params.id), payload)
        : await apiClient.createConfiguration(payload);
      const id = Number(params.id || response.data?.id);
      if (Number.isFinite(id) && id > 0) navigate(`/config/${id}`);
      else navigate('/config');
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save the configuration. Check the fields and try again.'));
    } finally {
      setLoading(false);
    }
  };

  return <section class="page-stack config-form-page">
    <div class="page-heading">
      <div><p class="page-eyebrow"><A href="/config">Configurations</A> / {isEdit() ? 'Edit' : 'New'}</p>
        <h1>{isEdit() ? 'Edit configuration' : 'Connect your data sources'}</h1>
        <p class="page-description">Choose a source, destination, and sync mode. Saved credentials stay masked.</p>
      </div>
      <A href="/config" class="button button--secondary">Cancel</A>
    </div>

    <Show when={error()}><div class="notice notice--error" role="alert">{error()}</div></Show>
    <Show when={loading() && isEdit()}><div class="surface-card surface-card--empty">Loading configuration…</div></Show>
    <Show when={!loading() || !isEdit()}>
      <form class="config-form" onSubmit={submit}>
        <article class="surface-card config-form__section">
          <div class="config-form__section-title"><span>01</span><div><h2>General</h2><p>Give this pipeline a clear name for your team.</p></div></div>
          <div class="config-form__fields">
            <label class="field"><span>Configuration name <b>*</b></span><input value={form().name} onInput={(e) => update('name', e.currentTarget.value)} maxlength="128" required placeholder="e.g. Customer data sync" /></label>
            <label class="field"><span>Description</span><textarea value={form().description} onInput={(e) => update('description', e.currentTarget.value)} rows="3" maxlength="1000" placeholder="What data does this pipeline synchronize?" /></label>
            <label class="field"><span>Pipeline type <b>*</b></span><select value={form().pipeline_type} disabled={isEdit()} onChange={(e) => {
              const type = e.currentTarget.value as ConfigurationForm['pipeline_type'];
              const defaults = type === 'pg_clickhouse' ? { source_type: 'postgres' as const, source_port: 5432, target_type: 'clickhouse' as const, target_port: 8123, target_tls: false }
                : type === 'pg_replication' || type === 'pg_copy' ? { source_type: 'postgres' as const, source_port: 5432, target_type: 'postgres' as const, target_port: 5432, target_tls: false }
                  : { target_type: 'opensearch' as const, target_port: 9200, target_tls: true };
              setForm(current => ({ ...current, pipeline_type: type, ...defaults }));
            }}>
              <option value="pg_search">Search — PostgreSQL, MySQL, or MariaDB to OpenSearch/Elasticsearch</option>
              <option value="pg_clickhouse">Analytics — PostgreSQL to ClickHouse</option>
              <option value="pg_replication">Continuous replication — PostgreSQL to PostgreSQL</option>
              <option value="pg_copy">Database copy — PostgreSQL to PostgreSQL, manual or scheduled</option>
            </select><span class="field-hint">{isEdit() ? 'Pipeline type is fixed after creation. Create another configuration to change it.' : 'The selected mode controls which connection fields and execution options are used.'}</span></label>
          </div>
        </article>

        <article class="surface-card config-form__section">
          <div class="config-form__section-title"><span>02</span><div><h2>{form().source_type === 'postgres' ? 'PostgreSQL source' : form().source_type === 'mysql' ? 'MySQL source' : 'MariaDB source'}</h2><p>Read access to the database you want to synchronize.</p></div></div>
          <div class="config-form__fields config-form__fields--two">
            <Show when={form().pipeline_type === 'pg_search'}><label class="field"><span>Database engine <b>*</b></span><select value={form().source_type} onChange={(e) => { const type = e.currentTarget.value as ConfigurationForm['source_type']; setForm(current => ({ ...current, source_type: type, source_port: type === 'postgres' ? 5432 : 3306 })); setConnection(null); }}><option value="postgres">PostgreSQL</option><option value="mysql">MySQL</option><option value="mariadb">MariaDB</option></select></label></Show>
            <label class="field"><span>Host <b>*</b></span><input value={form().source_host} onInput={(e) => update('source_host', e.currentTarget.value)} required autocomplete="off" placeholder="db.example.com" /></label>
            <label class="field"><span>Port <b>*</b></span><input type="number" min="1" max="65535" step="1" value={form().source_port} onInput={(e) => update('source_port', e.currentTarget.valueAsNumber)} required /></label>
            <label class="field"><span>Database <b>*</b></span><input value={form().source_database} onInput={(e) => update('source_database', e.currentTarget.value)} required autocomplete="off" /></label>
            <label class="field"><span>Username <b>*</b></span><input value={form().source_user} onInput={(e) => update('source_user', e.currentTarget.value)} required autocomplete="username" /></label>
            <label class="field"><span>Password {isEdit() ? '' : <b>*</b>}</span><span class="field__secret"><input type={showSourcePassword() ? 'text' : 'password'} value={form().source_password} onInput={(e) => update('source_password', e.currentTarget.value)} required={!isEdit()} autocomplete={isEdit() ? 'new-password' : 'current-password'} placeholder={isEdit() ? 'Leave blank to keep saved password' : 'Database password'} /><button type="button" onClick={() => setShowSourcePassword((visible) => !visible)} aria-pressed={showSourcePassword()}>{showSourcePassword() ? 'Hide' : 'Show'}</button></span></label>
          </div>
          <div class="config-form__connection">
            <button class="button button--secondary" type="button" onClick={testSourceConnection} disabled={!canTestConnection() || testing()}>{testing() ? 'Testing…' : 'Test connection'}</button>
            <Show when={isEdit() && !form().source_password}><span class="field-hint">Enter the source password to test it. Leave it blank to keep the saved password.</span></Show>
            <Show when={connection()}>{(state) => <span class={`connection-result connection-result--${state().status}`} role="status">{state().message}</span>}</Show>
          </div>
        </article>

        <article class="surface-card config-form__section">
          <div class="config-form__section-title"><span>03</span><div><h2>{form().pipeline_type === 'pg_search' ? 'Search destination' : form().pipeline_type === 'pg_clickhouse' ? 'ClickHouse destination' : 'PostgreSQL destination'}</h2><p>{form().pipeline_type === 'pg_search' ? 'Where PGSync writes synchronized search documents.' : form().pipeline_type === 'pg_clickhouse' ? 'Where the analytics mirror table will be written.' : 'The destination database receives data from the PostgreSQL source.'}</p></div></div>
          <div class="config-form__fields config-form__fields--two">
            <Show when={form().pipeline_type === 'pg_search'}><label class="field"><span>Engine <b>*</b></span><select value={form().target_type} onChange={(e) => update('target_type', e.currentTarget.value as ConfigurationForm['target_type'])}><option value="opensearch">OpenSearch</option><option value="elasticsearch">Elasticsearch</option></select></label></Show>
            <label class="field"><span>Host <b>*</b></span><input value={form().target_host} onInput={(e) => update('target_host', e.currentTarget.value)} required placeholder="search.example.com" /></label>
            <label class="field"><span>Port <b>*</b></span><input type="number" min="1" max="65535" step="1" value={form().target_port} onInput={(e) => update('target_port', e.currentTarget.valueAsNumber)} required /></label>
            <Show when={form().pipeline_type !== 'pg_search'}><label class="field"><span>Database <b>*</b></span><input value={form().target_database} onInput={(e) => update('target_database', e.currentTarget.value)} required autocomplete="off" placeholder="analytics" /></label></Show>
            <label class="field"><span>Username {targetIsPostgres() && <b>*</b>}</span><input value={form().target_user} onInput={(e) => update('target_user', e.currentTarget.value)} autocomplete="username" required={targetIsPostgres()} /></label>
            <label class="field"><span>Password {targetIsPostgres() && !hasSavedTargetPassword() && <b>*</b>}</span><span class="field__secret"><input type={showTargetPassword() ? 'text' : 'password'} value={form().target_password} onInput={(e) => update('target_password', e.currentTarget.value)} autocomplete="new-password" placeholder={isEdit() ? 'Leave blank to keep saved password' : targetIsPostgres() ? 'Required for PostgreSQL destination' : 'Optional'} required={targetIsPostgres() && !hasSavedTargetPassword()} /><button type="button" onClick={() => setShowTargetPassword((visible) => !visible)} aria-pressed={showTargetPassword()}>{showTargetPassword() ? 'Hide' : 'Show'}</button></span></label>
            <div class="field__options">
              <Show when={form().pipeline_type === 'pg_search'}><label class="field field--checkbox"><input type="checkbox" checked={form().target_tls} onChange={(e) => { update('target_tls', e.currentTarget.checked); if (!e.currentTarget.checked) update('target_verify_certs', false); }} /><span>Use HTTPS</span></label><label class="field field--checkbox"><input type="checkbox" checked={form().target_verify_certs} disabled={!form().target_tls} onChange={(e) => update('target_verify_certs', e.currentTarget.checked)} /><span>Verify TLS certificate</span></label><p class="field-hint">Use certificate verification in production. Disable it only for a trusted local development certificate.</p></Show>
              <Show when={form().pipeline_type === 'pg_clickhouse'}><label class="field field--checkbox"><input type="checkbox" checked={form().target_tls} onChange={(e) => { update('target_tls', e.currentTarget.checked); if (!e.currentTarget.checked) update('target_verify_certs', false); }} /><span>Use HTTPS</span></label><label class="field field--checkbox"><input type="checkbox" checked={form().target_verify_certs} disabled={!form().target_tls} onChange={(e) => update('target_verify_certs', e.currentTarget.checked)} /><span>Verify TLS certificate</span></label></Show>
              <Show when={form().pipeline_type === 'pg_replication' || form().pipeline_type === 'pg_copy'}><label class="field field--checkbox"><input type="checkbox" checked={form().target_tls} onChange={(e) => update('target_tls', e.currentTarget.checked)} /><span>Require TLS for PostgreSQL destination</span></label></Show>
              <Show when={form().pipeline_type === 'pg_copy'}><label class="field field--checkbox"><input type="checkbox" checked={form().target_overwrite} onChange={(e) => update('target_overwrite', e.currentTarget.checked)} /><span>I understand matching objects at the destination can be replaced</span></label><p class="field-hint">Required before a copy can run. Review the destination database before starting.</p></Show>
            </div>
            <div class="config-form__connection"><button class="button button--secondary" type="button" onClick={testTargetConnection} disabled={!canTestTarget() || testing()}>{testing() ? 'Testing…' : 'Test destination'}</button><Show when={isEdit() && hasSavedTargetPassword() && !form().target_password}><span class="field-hint">Enter the destination password to test it; leave blank to keep the saved password.</span></Show><Show when={targetConnection()}>{(state) => <span class={`connection-result connection-result--${state().status}`} role="status">{state().message}</span>}</Show></div>
          </div>
        </article>

        <div class="config-form__next-step"><strong>Next: choose tables and columns</strong><span>{form().pipeline_type === 'pg_search' ? `Schema Builder will discover ${form().source_type} tables and let you define search documents.` : form().pipeline_type === 'pg_clickhouse' ? 'Choose one source table to mirror into ClickHouse. Relational denormalization requires the separate PGSync ClickHouse Pro package.' : form().pipeline_type === 'pg_replication' ? 'Choose the tables to publish. Target tables must exist with matching names and compatible columns; leave them empty for the initial copy.' : 'Choose tables to copy. For recurring copies, create a scheduled batch job after saving.'}</span></div>
        <div class="form-actions"><A href="/config" class="button button--secondary">Cancel</A><button class="button button--primary" type="submit" disabled={loading()}>{loading() ? 'Saving…' : isEdit() ? 'Save configuration' : 'Save and continue'}</button></div>
      </form>
    </Show>
  </section>;
}
