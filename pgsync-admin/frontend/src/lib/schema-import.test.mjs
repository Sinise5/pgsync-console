import assert from 'node:assert/strict';
import test from 'node:test';
import { parseSchemaImport } from './schema-import.mjs';

const tables = [
  { name: 'orders', columns: [{ column_name: 'id' }, { column_name: 'total' }] },
  { name: 'order_items', columns: [{ column_name: 'id' }, { column_name: 'order_id' }] },
  { name: 'users', columns: [{ column_name: 'id' }] },
];
const relationships = [{ source_table: 'order_items', target_table: 'orders' }];
const schema = { index: 'order-search', main_table: 'orders', main_columns: ['id'], children: [{ table: 'order_items', fields: ['order_id'] }] };

test('imports an exported Search schema and keeps selected columns', () => {
  const result = parseSchemaImport(JSON.stringify({ format: 'pgsync-admin-schema', version: 1, pipeline_type: 'pg_search', schema }), 'pg_search', tables, relationships);
  assert.deepEqual(result, { tableNames: ['orders', 'order_items'], columns: { orders: ['id'], order_items: ['order_id'] }, index: 'order-search' });
});

test('accepts legacy nodes schema and defaults to every column', () => {
  const result = parseSchemaImport(JSON.stringify({ index: 'orders', nodes: { table: 'orders', columns: ['id'] } }), 'pg_search', tables, relationships);
  assert.deepEqual(result, { tableNames: ['orders'], columns: { orders: ['id'] }, index: 'orders' });
});

test('rejects a different pipeline type', () => {
  assert.throws(() => parseSchemaImport(JSON.stringify({ format: 'pgsync-admin-schema', version: 1, pipeline_type: 'pg_copy', schema }), 'pg_search', tables, relationships), /pipeline/);
});

test('rejects unknown tables and columns', () => {
  assert.throws(() => parseSchemaImport(JSON.stringify({ ...schema, main_table: 'missing' }), 'pg_search', tables, relationships), /tidak ditemukan/);
  assert.throws(() => parseSchemaImport(JSON.stringify({ ...schema, main_columns: ['secret'] }), 'pg_search', tables, relationships), /kolom/);
});

test('rejects Search children without a direct foreign key to the main table', () => {
  const invalid = { ...schema, children: [{ table: 'users', fields: ['id'] }] };
  assert.throws(() => parseSchemaImport(JSON.stringify(invalid), 'pg_search', tables, relationships), /foreign key/);
});

test('rejects multiple tables for ClickHouse and defaults copy to full columns', () => {
  assert.throws(() => parseSchemaImport(JSON.stringify(schema), 'pg_clickhouse', tables, relationships), /satu tabel/);
  const copied = parseSchemaImport(JSON.stringify(schema), 'pg_copy', tables, relationships);
  assert.deepEqual(copied.columns, { orders: ['id', 'total'], order_items: ['id', 'order_id'] });
});
