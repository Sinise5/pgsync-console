import { createSignal, For, Show, onMount } from 'solid-js';
import { useParams, useNavigate } from '@solidjs/router';
import { apiClient } from '../lib/api-client';
import { parseSchemaImport } from '../lib/schema-import.mjs';

interface Column {
  column_name: string;
  data_type: string;
  is_nullable: string;
  column_default?: any;
  ordinal_position?: number;
}

interface Table {
  name: string;
  columns: Column[];
  primary_key: string[];
  row_count: number;
  selected?: boolean;
}

interface SchemaData {
  tables: Table[];
  relationships: Array<{
    source_table: string;
    source_column: string;
    target_table: string;
    target_column: string;
  }>;
  schema: string;
}

interface ConfigSource {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
}

type PipelineType = 'pg_search' | 'pg_clickhouse' | 'pg_replication' | 'pg_copy';
type SchemaConfig = {
  index: string;
  main_table: string;
  main_columns: string[];
  children: Array<Record<string, any>>;
  fk_mappings: Record<string, unknown>;
};

export default function SchemaBuilder() {
  const params = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [importMessage, setImportMessage] = createSignal('');
  const [schemaData, setSchemaData] = createSignal<SchemaData | null>(null);
  const [selectedTables, setSelectedTables] = createSignal<string[]>([]);
  const [selectedColumns, setSelectedColumns] = createSignal<Record<string, string[]>>({});
  const [searchQuery, setSearchQuery] = createSignal('');
  const [indexName, setIndexName] = createSignal('');
  const [configSource, setConfigSource] = createSignal<ConfigSource | null>(null);
  const [pipelineType, setPipelineType] = createSignal<PipelineType>('pg_search');
  let schemaFileInput: HTMLInputElement | undefined;

  onMount(async () => {
    // If config_id provided, load schema from that config
    if (params.config_id) {
      await loadSchemaFromConfig(parseInt(params.config_id));
    }
  });

  const loadSchemaFromConfig = async (configId: number) => {
    setLoading(true);
    setError(null);

    try {
      // Get config details first
      const res = await apiClient.getConfig(configId);
      const c = res.data;
      setPipelineType(c.pipeline_type || 'pg_search');

      const source: ConfigSource = {
        host: c.source?.host,
        port: c.source?.port,
        database: c.source?.database,
        user: c.source?.user,
        password: '', // Not needed, server-side decrypt
      };

      setConfigSource(source);

      // Pre-load existing schema if present
      if (c.schema && Object.keys(c.schema).length > 0) {
        const existingSchema = c.schema;
        setIndexName(existingSchema.index || '');

        // Extract selected tables from existing schema
        const root = existingSchema.nodes || existingSchema;
        const mainTable = existingSchema.main_table || root.table;
        const childTables = existingSchema.children?.map((child: any) => child.table)
          || root.children?.map((child: any) => child.table) || [];
        if (mainTable) {
          setSelectedTables([mainTable, ...childTables]);
          setSelectedColumns({
            [mainTable]: existingSchema.main_columns || root.columns || [],
            ...Object.fromEntries((existingSchema.children || root.children || []).map((child: any) => [
              child.table, child.fields || child.columns || [],
            ])),
          });
        }
      }

      // Load fresh schema from DB
      const response = await apiClient.client.post(`/config/${configId}/discover/schema`, {});
      setSchemaData(response.data);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to load schema');
    } finally {
      setLoading(false);
    }
  };

  const toggleTable = (tableName: string) => {
    if (pipelineType() === 'pg_clickhouse' && !selectedTables().includes(tableName)) {
      const tableData = schemaData()?.tables.find(t => t.name === tableName);
      setSelectedTables([tableName]);
      setSelectedColumns(tableData ? { [tableName]: tableData.columns.map(c => c.column_name) } : {});
      return;
    }
    if (pipelineType() === 'pg_search' && selectedTables()[0] === tableName) {
      setSelectedTables([]);
      setSelectedColumns({});
      return;
    }
    setSelectedTables(prev => {
      if (prev.includes(tableName)) {
        // Deselect table — remove columns too
        setSelectedColumns(cols => {
          const updated = {...cols};
          delete updated[tableName];
          return updated;
        });
        return prev.filter(t => t !== tableName);
      } else {
        // Select table — auto-select all columns
        const tableData = schemaData()?.tables.find(t => t.name === tableName);
        if (tableData) {
          setSelectedColumns(cols => ({
            ...cols,
            [tableName]: tableData.columns.map(c => c.column_name)
          }));
        }
        return [...prev, tableName];
      }
    });
  };

  const toggleColumn = (tableName: string, columnName: string) => {
    setSelectedColumns(cols => {
      const tableCols = cols[tableName] || [];
      if (tableCols.includes(columnName)) {
        return {
          ...cols,
          [tableName]: tableCols.filter(c => c !== columnName)
        };
      } else {
        return {
          ...cols,
          [tableName]: [...tableCols, columnName]
        };
      }
    });
  };

  const toggleAllTables = () => {
    const filtered = filteredTables();
    if (pipelineType() === 'pg_clickhouse') {
      if (filtered.some(t => selectedTables().includes(t.name))) {
        setSelectedTables([]);
        setSelectedColumns({});
      } else if (filtered[0]) {
        setSelectedTables([filtered[0].name]);
        setSelectedColumns({ [filtered[0].name]: filtered[0].columns.map(c => c.column_name) });
      }
      return;
    }
    if (pipelineType() !== 'pg_search') {
      const allSelected = filtered.every(table => selectedTables().includes(table.name));
      if (allSelected) setSelectedTables(prev => prev.filter(name => !filtered.some(table => table.name === name)));
      else setSelectedTables(prev => [...new Set([...prev, ...filtered.map(table => table.name)])]);
      return;
    }
    const mainTable = selectedTables()[0];
    if (!mainTable) return;
    const visibleRelated = relatedTables(mainTable).filter(name => filtered.some(table => table.name === name));
    const allSelected = visibleRelated.length > 0 && visibleRelated.every(name => selectedTables().includes(name));
    if (allSelected) {
      setSelectedTables(prev => [mainTable, ...prev.slice(1).filter(name => !visibleRelated.includes(name))]);
      setSelectedColumns(prev => Object.fromEntries(Object.entries(prev).filter(([name]) => name === mainTable || !visibleRelated.includes(name))));
    } else {
      const tables = schemaData()?.tables || [];
      setSelectedTables(prev => [...new Set([mainTable, ...prev.slice(1), ...visibleRelated])]);
      setSelectedColumns(prev => ({ ...prev, ...Object.fromEntries(visibleRelated.map(name => [name, tables.find(table => table.name === name)?.columns.map(column => column.column_name) || []])) }));
    }
  };

  const relatedTables = (mainTable: string) => {
    const data = schemaData();
    if (!data) return [];
    return [...new Set(data.relationships.filter(item => item.target_table === mainTable).map(item => item.source_table))];
  };

  const visibleRelatedTables = () => selectedTables()[0]
    ? relatedTables(selectedTables()[0]).filter(name => filteredTables().some(table => table.name === name))
    : [];

  const isRelatedToMain = (tableName: string) => !selectedTables()[0]
    || selectedTables()[0] === tableName || relatedTables(selectedTables()[0]).includes(tableName);

  const changeMainTable = (tableName: string) => {
    const previousTables = selectedTables();
    const validChildren = previousTables.slice(1).filter(name => relatedTables(tableName).includes(name));
    const retained = [tableName, ...validChildren];
    setSelectedTables(retained);
    setSelectedColumns(columns => Object.fromEntries(retained.map(name => [name, columns[name] || schemaData()?.tables.find(table => table.name === name)?.columns.map(column => column.column_name) || []])));
  };

  const filteredTables = () => {
    const data = schemaData();
    if (!data) return [];

    const query = searchQuery().toLowerCase();
    if (!query) return data.tables;

    return data.tables.filter(t =>
      t.name.toLowerCase().includes(query) ||
      t.columns.some(c => c.column_name.toLowerCase().includes(query))
    );
  };

  const buildSchema = (): { schema?: SchemaConfig; error?: string } => {
    const selected = pipelineType() === 'pg_clickhouse' ? selectedTables().slice(0, 1) : selectedTables();
    const data = schemaData();
    if (!data) return { error: 'Schema tabel belum dimuat dari database.' };
    if (selected.length === 0) return { error: 'Pilih minimal satu tabel.' };
    const mainTable = selected[0];
    const mainTableData = data.tables.find(table => table.name === mainTable);
    if (!mainTableData) return { error: `Tabel "${mainTable}" tidak tersedia lagi. Muat ulang schema dan pilih tabel lain.` };
    if (pipelineType() === 'pg_search' && selected.some(table => !(selectedColumns()[table]?.length))) {
      return { error: 'Pilih minimal satu kolom untuk setiap tabel Search yang dipilih.' };
    }

    const children: SchemaConfig['children'] = [];
    for (const childTable of selected.slice(1)) {
      const childData = data.tables.find(table => table.name === childTable);
      if (!childData) return { error: `Tabel "${childTable}" tidak tersedia lagi. Muat ulang schema dan pilih tabel lain.` };
      const selectedChild = { table: childTable, fields: selectedColumns()[childTable] || childData.columns.map(column => column.column_name) };
      if (pipelineType() === 'pg_copy' || pipelineType() === 'pg_replication') {
        children.push(selectedChild);
        continue;
      }
      const relationship = data.relationships.find(item => item.source_table === childTable && item.target_table === mainTable);
      if (!relationship) return { error: `Relasi foreign key dari "${childTable}" ke "${mainTable}" tidak ditemukan.` };
      children.push({
        ...selectedChild,
        relationship: {
          variant: 'object',
          type: 'one_to_many',
          foreign_key: { child: relationship.source_column, parent: relationship.target_column },
        },
      });
    }
    return { schema: {
      index: indexName().trim() || mainTable.toLowerCase(),
      main_table: mainTable,
      main_columns: selectedColumns()[mainTable] || mainTableData.columns.map(column => column.column_name),
      children,
      fk_mappings: {},
    } };
  };

  const importSchema = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    setError(null);
    setImportMessage('');
    if (file.size > 1_000_000) {
      setError('Berkas schema maksimal 1 MB.');
      return;
    }
    try {
      const available = schemaData();
      const imported = parseSchemaImport(await file.text(), pipelineType(), available?.tables || [], available?.relationships || []);
      setSelectedTables(imported.tableNames);
      setSelectedColumns(imported.columns);
      setIndexName(imported.index);
      setImportMessage(`Schema dari ${file.name} berhasil dimuat. Tinjau pilihan, lalu simpan untuk menerapkannya.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Schema gagal diimpor. Pastikan berkas JSON valid.');
    }
  };

  const exportSchema = () => {
    const { schema, error: validationError } = buildSchema();
    if (!schema) {
      setError(validationError || 'Schema belum siap diekspor.');
      return;
    }
    setError(null);
    setImportMessage('');
    const fileContent = JSON.stringify({ format: 'pgsync-admin-schema', version: 1, pipeline_type: pipelineType(), schema }, null, 2);
    const url = URL.createObjectURL(new Blob([fileContent], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${schema.main_table.replace(/[^a-z0-9_-]/gi, '_')}-schema.json`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const generateSchema = async () => {
    const { schema, error: validationError } = buildSchema();
    if (!schema) {
      setError(validationError || 'Schema belum siap disimpan.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Update config with generated schema
      if (params.config_id) {
        await apiClient.updateConfiguration(parseInt(params.config_id), {
          schema_config: JSON.stringify(schema, null, 2)
        });

        navigate(`/config/${params.config_id}`);
      } else {
        // Store in localStorage for new configs
        localStorage.setItem('pgsync_schema', JSON.stringify(schema, null, 2));
        navigate('/config/new');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to generate schema');
    } finally {
      setLoading(false);
    }
  };

  return <section class="page-stack schema-builder">
    <div class="page-heading">
      <div><p class="page-eyebrow">Configuration / Schema</p><h1>Schema Builder</h1>
        <p class="page-description">{pipelineType() === 'pg_search'
          ? 'Pilih tabel utama, tabel yang berelasi, dan kolom dokumen pencarian.'
          : pipelineType() === 'pg_clickhouse'
            ? 'Pilih satu tabel PostgreSQL untuk dicerminkan ke ClickHouse.'
            : 'Pilih tabel PostgreSQL yang akan dipindahkan. Semua kolom tabel ikut disalin.'}</p>
      </div>
      <Show when={params.config_id}><button type="button" class="button button--secondary" onClick={() => navigate(`/config/${params.config_id}`)}>Kembali ke konfigurasi</button></Show>
    </div>
    <Show when={error()}><div class="notice notice--error" role="alert">{error()}</div></Show>
    <Show when={loading() && !schemaData()}><div class="surface-card surface-card--empty" role="status">Memuat schema dari database…</div></Show>
    <Show when={schemaData()}>
      <div class="surface-card schema-builder__content">
        <Show when={importMessage()}><div class="notice notice--success" role="status">{importMessage()}</div></Show>
        <div class="schema-builder__controls">
          <input type="search" aria-label="Cari tabel atau kolom" placeholder="Cari tabel atau kolom…" class="schema-builder__input schema-builder__search" value={searchQuery()} onInput={(e) => setSearchQuery(e.currentTarget.value)} />
          <label class="schema-builder__index"><span>{pipelineType() === 'pg_clickhouse' ? 'Nama tabel ClickHouse' : 'Nama index Search'}</span>
            <input type="text" class="schema-builder__input" placeholder={pipelineType() === 'pg_clickhouse' ? 'clickhouse_table' : 'search_index'} value={indexName()} disabled={pipelineType() === 'pg_copy' || pipelineType() === 'pg_replication'} onInput={(e) => setIndexName(e.currentTarget.value)} />
            <small>{pipelineType() === 'pg_copy' || pipelineType() === 'pg_replication' ? 'Nama tabel tujuan mengikuti sumber.' : `Default: ${selectedTables()[0]?.toLowerCase() || 'nama_tabel'}`}</small>
          </label>
          <div class="schema-builder__actions">
            <input ref={(element) => { schemaFileInput = element; }} class="schema-builder__file-input" type="file" accept="application/json,.json" onChange={(event) => void importSchema(event)} aria-label="Impor file schema JSON" />
            <button type="button" class="button button--secondary" onClick={() => schemaFileInput?.click()}>Impor schema</button>
            <button type="button" class="button button--secondary" onClick={exportSchema} disabled={selectedTables().length === 0}>Ekspor schema</button>
          </div>
          <button type="button" onClick={toggleAllTables} class="button button--secondary" disabled={pipelineType() === 'pg_search' && (!selectedTables()[0] || visibleRelatedTables().length === 0)}>
            {pipelineType() === 'pg_clickhouse' ? selectedTables().length ? 'Hapus pilihan' : 'Pilih satu tabel' : visibleRelatedTables().length > 0 && visibleRelatedTables().every(name => selectedTables().includes(name)) ? 'Hapus tabel terkait' : 'Pilih tabel terkait'}
          </button>
          <button type="button" onClick={generateSchema} disabled={selectedTables().length === 0 || loading()} class="button button--primary">
            {loading() ? 'Menyimpan…' : `Simpan pilihan (${selectedTables().length})`}
          </button>
        </div>
        <div class="schema-builder__stats" aria-live="polite">
          <div><strong>{schemaData()?.tables.length || 0}</strong><span>Total tabel</span></div>
          <div><strong>{selectedTables().length}</strong><span>Tabel dipilih</span></div>
          <div><strong>{filteredTables().length}</strong><span>Hasil pencarian</span><Show when={searchQuery()}><small>“{searchQuery()}”</small></Show></div>
        </div>
        <Show when={pipelineType() === 'pg_search'}>
          <p class="schema-builder__hint">Pilih tabel utama terlebih dahulu. Tabel tanpa relasi langsung akan dinonaktifkan agar konfigurasi bisa disimpan dengan benar.</p>
        </Show>
        <div class="schema-builder__tables">
          <For each={filteredTables()}>{(table) => {
            const selected = () => selectedTables().includes(table.name);
            const disabled = () => pipelineType() === 'pg_search' && selectedTables().length > 0 && !isRelatedToMain(table.name) && !selected();
            return <article class={`schema-table ${selected() ? 'schema-table--selected' : ''} ${disabled() ? 'schema-table--disabled' : ''}`}>
              <button type="button" class="schema-table__select" disabled={disabled()} onClick={() => toggleTable(table.name)} aria-pressed={selected()}>
                <span class="schema-table__checkbox" aria-hidden="true">{selected() ? '✓' : ''}</span>
                <span class="schema-table__identity"><strong>{table.name}</strong>
                  <Show when={selectedTables()[0] === table.name}><span class="schema-table__role">Utama</span></Show>
                  <Show when={selected() && selectedTables()[0] !== table.name}><span class="schema-table__role">Terkait</span></Show>
                  <Show when={table.primary_key.length > 0}><span class="schema-table__pk">PK: {table.primary_key.join(', ')}</span></Show>
                </span>
                <span class="schema-table__meta">{table.columns.length} kolom · {table.row_count.toLocaleString()} baris</span>
                <span class="schema-table__preview">{table.columns.slice(0, 3).map(c => c.column_name).join(', ')}{table.columns.length > 3 && ` +${table.columns.length - 3} lainnya`}</span>
              </button>
              <Show when={selected() && pipelineType() === 'pg_search'}>
                <div class="schema-table__columns">
                  <div class="schema-table__columns-heading"><span>Kolom dokumen</span><button type="button" class="schema-builder__text-button" onClick={() => setSelectedColumns(cols => ({ ...cols, [table.name]: cols[table.name]?.length === table.columns.length ? [] : table.columns.map(col => col.column_name) }))}>{selectedColumns()[table.name]?.length === table.columns.length ? 'Hapus semua' : 'Pilih semua'}</button></div>
                  <div class="schema-table__column-list"><For each={table.columns}>{(col) => <label title={`${col.column_name} (${col.data_type})`}>
                    <input type="checkbox" checked={selectedColumns()[table.name]?.includes(col.column_name) || false} onChange={() => toggleColumn(table.name, col.column_name)} />
                    <span>{col.column_name}<small>{col.data_type}</small></span>
                  </label>}</For></div>
                </div>
              </Show>
              <Show when={selected() && table.name !== selectedTables()[0] && pipelineType() === 'pg_search'}>
                <button type="button" class="schema-table__make-primary" onClick={() => changeMainTable(table.name)}>Jadikan tabel utama</button>
              </Show>
            </article>;
          }}</For>
          <Show when={filteredTables().length === 0}><div class="empty-state">Tidak ada tabel atau kolom yang cocok.</div></Show>
        </div>
      </div>
    </Show>
  </section>;
}
