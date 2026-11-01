-- PGSync Admin - ClickHouse executions table
CREATE TABLE IF NOT EXISTS pgsync_admin.executions (
    id UInt64,
    configuration_id UInt64,
    status String,
    started_at DateTime,
    finished_at Nullable(DateTime),
    records_synced UInt64,
    error_message Nullable(String),
    execution_time_ms Nullable(UInt64)
) ENGINE = MergeTree()
ORDER BY (started_at, id);
