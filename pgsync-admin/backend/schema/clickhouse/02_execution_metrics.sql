-- PGSync Admin - ClickHouse execution_metrics table
CREATE TABLE IF NOT EXISTS pgsync_admin.execution_metrics (
    execution_id UInt64,
    timestamp DateTime,
    metric_name String,
    metric_value Float64
) ENGINE = MergeTree()
ORDER BY (execution_id, timestamp);
