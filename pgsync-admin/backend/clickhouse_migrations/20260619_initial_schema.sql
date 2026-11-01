-- Initial ClickHouse schema
-- Version: 20260619_initial
-- Migration for core telemetry tables

CREATE TABLE IF NOT EXISTS pgsync_logs (
    timestamp DateTime,
    execution_id UInt32,
    level String,
    process String,
    table_name String,
    message String,
    context String
) ENGINE = MergeTree()
ORDER BY (execution_id, timestamp);

CREATE TABLE IF NOT EXISTS pgsync_metrics (
    timestamp DateTime,
    execution_id UInt32,
    metric_name String,
    metric_value Float64,
    unit String
) ENGINE = MergeTree()
ORDER BY (execution_id, timestamp);

CREATE TABLE IF NOT EXISTS sync_logs (
    execution_id UInt32,
    timestamp DateTime,
    level String,
    message String,
    metadata String
) ENGINE = MergeTree()
ORDER BY (execution_id, timestamp);

CREATE TABLE IF NOT EXISTS sync_metrics (
    execution_id UInt32,
    metric_name String,
    metric_value Float64,
    timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (execution_id, timestamp);

CREATE TABLE IF NOT EXISTS execution_history (
    execution_id UInt32,
    config_id UInt32,
    status String,
    started_at DateTime,
    completed_at DateTime,
    total_docs UInt32,
    synced_docs UInt32,
    error_message String
) ENGINE = MergeTree()
ORDER BY started_at;

CREATE TABLE IF NOT EXISTS schema_changes (
    change_id UInt32,
    table_name String,
    column_name String,
    change_type String,
    detected_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY detected_at;

CREATE TABLE IF NOT EXISTS query_performance (
    query_id String,
    execution_time Float64,
    rows_processed UInt32,
    timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY timestamp;

CREATE TABLE IF NOT EXISTS anomaly_events (
    event_id UInt32,
    execution_id UInt32,
    anomaly_type String,
    severity String,
    description String,
    detected_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY detected_at;

CREATE TABLE IF NOT EXISTS alert_history (
    alert_id UInt32,
    rule_id UInt32,
    triggered_at DateTime,
    resolved_at Nullable(DateTime),
    severity String,
    message String
) ENGINE = MergeTree()
ORDER BY triggered_at;

CREATE TABLE IF NOT EXISTS lineage_graph (
    source_table String,
    target_table String,
    relationship_type String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (source_table, target_table);
