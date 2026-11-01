export type PipelineType = 'pg_search' | 'pg_clickhouse' | 'pg_replication' | 'pg_copy';
export interface SchemaTable {
  name: string;
  columns: Array<{ column_name: string }>;
}
export interface SchemaRelationship {
  source_table: string;
  target_table: string;
}
export interface ImportedSchemaSelection {
  tableNames: string[];
  columns: Record<string, string[]>;
  index: string;
}
export function parseSchemaImport(
  content: string,
  pipelineType: PipelineType,
  availableTables: SchemaTable[],
  relationships: SchemaRelationship[],
): ImportedSchemaSelection;
