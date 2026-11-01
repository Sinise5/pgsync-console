export function parseSchemaImport(content, pipelineType, availableTables, relationships) {
  const parsed = JSON.parse(content);
  const envelope = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  const schema = envelope?.format === 'pgsync-admin-schema' ? envelope.schema : parsed;
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) throw new Error('Format JSON schema tidak valid.');
  if (envelope?.format === 'pgsync-admin-schema' && envelope.version !== 1) throw new Error('Versi file schema tidak didukung. Ekspor ulang dari versi aplikasi ini.');
  if (envelope?.format === 'pgsync-admin-schema' && envelope.pipeline_type !== pipelineType) {
    throw new Error(`Schema ini untuk pipeline "${envelope.pipeline_type}"; konfigurasi ini memakai "${pipelineType}".`);
  }
  if (schema.index !== undefined && (typeof schema.index !== 'string' || schema.index.length > 255)) throw new Error('Nama index atau tabel tujuan tidak valid.');

  const root = schema.nodes || schema;
  const mainTable = schema.main_table || root.table;
  if (typeof mainTable !== 'string' || !mainTable) throw new Error('Schema tidak memiliki main_table atau nodes.table.');
  const children = schema.children || root.children || [];
  if (!Array.isArray(children)) throw new Error('Daftar children harus berupa array.');
  const tableNames = [mainTable, ...children.map(child => child?.table)];
  if (tableNames.some(name => typeof name !== 'string' || !name) || new Set(tableNames).size !== tableNames.length) {
    throw new Error('Nama tabel schema tidak valid atau berulang.');
  }
  if (pipelineType === 'pg_clickhouse' && tableNames.length !== 1) throw new Error('Pipeline ClickHouse hanya dapat mengimpor satu tabel.');

  const columns = {};
  for (const name of tableNames) {
    const table = availableTables.find(item => item.name === name);
    if (!table) throw new Error(`Tabel "${name}" tidak ditemukan pada database sumber konfigurasi ini.`);
    const child = children.find(item => item.table === name);
    const chosenColumns = name === mainTable ? schema.main_columns ?? root.columns : child?.fields ?? child?.columns;
    if (pipelineType === 'pg_search' && chosenColumns !== undefined && (!Array.isArray(chosenColumns)
      || chosenColumns.some(column => typeof column !== 'string' || !table.columns.some(item => item.column_name === column)))) {
      throw new Error(`Daftar kolom untuk tabel "${name}" tidak cocok dengan database sumber.`);
    }
    if (pipelineType === 'pg_search' && chosenColumns !== undefined && chosenColumns.length === 0) {
      throw new Error(`Tabel Search "${name}" harus memiliki minimal satu kolom terpilih.`);
    }
    columns[name] = pipelineType === 'pg_search' && chosenColumns
      ? chosenColumns
      : table.columns.map(column => column.column_name);
  }

  if (pipelineType === 'pg_search') {
    for (const child of children) {
      if (!relationships.some(item => item.source_table === child.table && item.target_table === mainTable)) {
        throw new Error(`Relasi foreign key dari "${child.table}" ke "${mainTable}" tidak ditemukan pada database sumber.`);
      }
    }
  }

  return { tableNames, columns, index: schema.index || '' };
}
