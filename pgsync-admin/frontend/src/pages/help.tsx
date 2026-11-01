import { Component, createSignal, Show } from 'solid-js';

type Section = 'overview' | 'config' | 'schema' | 'migration' | 'cdc' | 'job' | 'exec' | 'dash' | 'alert' | 'report' | 'lineage';

export const HelpPage: Component = () => {
  const [section, setSection] = createSignal<Section>('overview');

  const nav: { id: Section; label: string }[] = [
    { id: 'overview', label: '📖 Overview' },
    { id: 'config', label: '🗄️ Configurations' },
    { id: 'schema', label: '🧩 Schema Builder' },
    { id: 'migration', label: '🔁 Migrations' },
    { id: 'cdc', label: '⚡ CDC' },
    { id: 'job', label: '⏰ Jobs' },
    { id: 'exec', label: '📊 Executions' },
    { id: 'dash', label: '📈 Dashboards' },
    { id: 'alert', label: '🚨 Alerts' },
    { id: 'report', label: '📋 Reports' },
    { id: 'lineage', label: '🔗 Lineage' },
  ];

  return (
    <div class="space-y-6">
      <div>
        <h1 class="text-3xl font-bold">📖 Help Guide</h1>
        <p class="text-gray-600 mt-1">Complete guide to PGSync Admin — all features, examples, and setup</p>
      </div>

      {/* Side navigation */}
      <div class="flex flex-nowrap gap-2 overflow-x-auto pb-2 border-b">
        {nav.map((item) => (
          <button
            class={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap ${
              section() === item.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div class="prose max-w-none">
        <Show when={section() === 'overview'}>{OverviewSection()}</Show>
        <Show when={section() === 'config'}>{ConfigSection()}</Show>
        <Show when={section() === 'schema'}>{SchemaSection()}</Show>
        <Show when={section() === 'migration'}>{MigrationSection()}</Show>
        <Show when={section() === 'cdc'}>{CDCSection()}</Show>
        <Show when={section() === 'job'}>{JobSection()}</Show>
        <Show when={section() === 'exec'}>{ExecSection()}</Show>
        <Show when={section() === 'dash'}>{DashSection()}</Show>
        <Show when={section() === 'alert'}>{AlertSection()}</Show>
        <Show when={section() === 'report'}>{ReportSection()}</Show>
        <Show when={section() === 'lineage'}>{LineageSection()}</Show>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────
// Sections
// ──────────────────────────────────────────

function Section(props: { title: string; children: any }) {
  return <div class="bg-white rounded-xl border p-6 space-y-4">{props.children}</div>;
}

function Tip(props: { children: any; type?: 'tip' | 'warn' | 'critical' }) {
  const colors = { tip: '#2196F3', warn: '#FF9800', critical: '#F44336' };
  const icons = { tip: '💡', warn: '⚠️', critical: '🔴' };
  const c = (props.type || 'tip') as keyof typeof colors;
  return (
    <div class="bg-gray-50 p-3 rounded-lg border-l-4 text-sm" style={`border-left-color: ${colors[c]};`}>
      <strong>{icons[c]} {props.type === 'warn' ? 'Warning' : props.type === 'critical' ? 'Critical' : 'Tip'}:</strong> {props.children}
    </div>
  );
}

function Code({ children }: any) {
  return <code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>;
}

// ─── Overview ────────────────────────────────

function OverviewSection() {
  return (
    <Section title="📖 Overview">
      <h2 class="text-xl font-bold">What is PGSync Admin?</h2>
      <p>
        PGSync Admin is a visual workspace for configuring and monitoring database pipelines. It uses <a href="https://pgsync.com" class="text-blue-600 underline" target="_blank" rel="noreferrer">PGSync</a> for search and ClickHouse sync, and PostgreSQL logical replication or pg_dump/pg_restore for PostgreSQL transfers.
      </p>

      <h3 class="text-lg font-semibold mt-4">Key Features</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          ['🗄️ Configuration Manager', 'Configure PostgreSQL, MySQL, MariaDB, OpenSearch, Elasticsearch, and ClickHouse connections'],
          ['🧩 Schema Builder', 'Select search document relationships or tables to mirror and transfer'],
          ['🔁 Batch Migrations', 'Run one-time or scheduled copies between PostgreSQL databases'],
          ['⚡ Real-time CDC', 'Stream PostgreSQL changes to search, ClickHouse, or another PostgreSQL database'],
          ['⏰ Scheduled Jobs', 'Cron-based recurring sync with visual builder'],
          ['📊 Execution Monitor', 'Real-time progress, logs, and metrics per sync run'],
          ['📈 Custom Dashboards', 'Widget-based monitoring dashboards with KPIs'],
          ['🚨 Alert Rules', 'Email/Telegram/Webhook notifications on failures'],
          ['📋 Reports', 'Daily/weekly summaries with CSV/JSON export'],
          ['🔗 Data Lineage', 'Track data flow from source tables to OpenSearch'],
        ].map(([emoji, text]) => (
          <div class="bg-gray-50 rounded-lg p-3 text-sm">{emoji} {text}</div>
        ))}
      </div>

      <h3 class="text-lg font-semibold mt-4">Configure modes</h3>
      <ul class="list-disc space-y-1 pl-5 text-sm">
        <li>Search sync accepts PostgreSQL, MySQL, or MariaDB sources and OpenSearch or Elasticsearch destinations.</li>
        <li>ClickHouse analytics mirrors one PostgreSQL table to one ClickHouse table. Wide relational denormalization requires the separate Pro connector.</li>
        <li>Continuous PostgreSQL replication uses a source publication and target subscription. Create compatible target tables and configure PostgreSQL logical replication first.</li>
        <li>PostgreSQL table copy transfers complete selected tables once or on a batch schedule. Existing destination tables can be replaced, so the form asks for explicit acknowledgement.</li>
      </ul>

      <h3 class="text-lg font-semibold mt-4">Architecture</h3>
      <div class="bg-gray-100 rounded-lg p-4 font-mono text-xs leading-relaxed">
{`┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ PostgreSQL  │────▶│  PGSync Engine   │────▶│  OpenSearch  │
│ (source)    │     │  (CDC/Batch)     │     │  (target)    │
└─────────────┘     └──────────────────┘     └──────────────┘
                           │
                    ┌──────┴──────┐
                    │ PGSync Admin│
                    │ Dashboard   │
                    └─────────────┘`}</div>
    </Section>
  );
}

// ─── Config ──────────────────────────────────

function ConfigSection() {
  return (
    <Section title="🗄️ Configurations">
      <h2 class="text-xl font-bold">Managing PGSync Configurations</h2>
      <p>Each configuration defines a sync pipeline: <strong>which PostgreSQL database to read from</strong> and <strong>which OpenSearch index to write to</strong>.</p>

      <h3 class="text-lg font-semibold mt-4">Create a Configuration</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Go to <strong>Configurations</strong> → click <strong>"+ New Config"</strong></li>
        <li>Fill in the form:</li>
      </ol>

      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1 font-mono overflow-x-auto">
{`Field            │ Example Value              │ Description
─────────────────┼────────────────────────────┼──────────────────
name             │ production-postgres-01     │ Unique config name
source_host      │ localhost               │ PostgreSQL host
source_port      │ 5432                       │ PostgreSQL port
source_db        │ source_db                 │ Source database name
source_user      │ pgsync_user                │ PostgreSQL user
source_password  │ ********                   │ PostgreSQL password
target_host      │ localhost               │ OpenSearch host
target_port      │ 9200                       │ OpenSearch port
target_user      │ admin                      │ OpenSearch username
target_password  │ ********                   │ OpenSearch password
tables           │ users, orders, products    │ Tables to sync
batch_size       │ 1000                       │ Docs per batch
cdc_enabled      │ ✅ (checked)               │ Enable real-time CDC`}</div>

      <h3 class="text-lg font-semibold mt-4">Test Connection</h3>
      <p>After filling connection details, use <strong>"Test Connection"</strong> button to verify both source (PostgreSQL) and target (OpenSearch) are reachable.</p>

      <h3 class="text-lg font-semibold mt-4">Actions Available</h3>
      <table class="w-full text-sm border-collapse">
        <tbody>
        <tr class="bg-gray-100"><td class="p-2 font-medium">📝 Edit</td><td class="p-2">Modify any field</td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">🗑 Delete</td><td class="p-2">Remove configuration</td></tr>
        <tr class="bg-gray-100"><td class="p-2 font-medium">🧩 Schema</td><td class="p-2">Open schema builder to map tables → documents</td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">▶ Run</td><td class="p-2">Start batch sync or CDC immediately</td></tr>
        </tbody>
      </table>

      <Tip>Start with one table (e.g. <Code>public.users</Code>) to verify the pipeline works before adding more tables.</Tip>
    </Section>
  );
}

// ─── Schema ──────────────────────────────────

function SchemaSection() {
  return (
    <Section title="🧩 Schema Builder">
      <h2 class="text-xl font-bold">Pilih tabel untuk pipeline</h2>
      <p>Schema Builder menyesuaikan langkah dengan jenis pipeline. Mulai dengan mencari nama tabel, lalu pilih tabel yang ingin dipakai.</p>

      <h3 class="text-lg font-semibold mt-4">Search ke OpenSearch atau Elasticsearch</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Pilih satu tabel sebagai <strong>tabel utama</strong>.</li>
        <li>Pilih tabel terkait yang memiliki foreign key langsung ke tabel utama. Gunakan <strong>Pilih tabel terkait</strong> untuk memilih semua relasi langsung yang terlihat.</li>
        <li>Centang kolom yang ingin dimasukkan ke dokumen. Kolom dimulai dalam keadaan terpilih; gunakan <strong>Pilih semua</strong> atau <strong>Hapus semua</strong> untuk mengubahnya sekaligus.</li>
        <li>Opsional: ubah nama index, lalu simpan pilihan.</li>
      </ol>
      <p class="mt-3">Gunakan <strong>Ekspor schema</strong> untuk mengunduh file JSON mapping. Untuk memakai mapping yang sudah ada, pilih <strong>Impor schema</strong>; file akan diperiksa terhadap pipeline, tabel, kolom, dan relasi database ini. Simpan pilihan untuk menerapkan hasil impor.</p>
      <Tip type="warn">Jangan sertakan kolom rahasia seperti kata sandi atau API key. Tabel terkait harus menjadi anak dari tabel utama melalui foreign key langsung.</Tip>

      <h3 class="text-lg font-semibold mt-4">ClickHouse, PostgreSQL replication, dan PostgreSQL copy</h3>
      <ul class="list-disc ml-5 space-y-2">
        <li><strong>ClickHouse:</strong> pilih satu tabel; seluruh kolom tabel dipakai.</li>
        <li><strong>Replication dan copy:</strong> pilih satu atau beberapa tabel; seluruh kolom disalin dan tidak perlu mapping relasi atau kolom.</li>
        <li>Gunakan pencarian untuk menemukan tabel. Jumlah tabel dipilih selalu terlihat sebelum disimpan.</li>
      </ul>
    </Section>
  );
}

// ─── Migration ───────────────────────────────

function MigrationSection() {
  return (
    <Section title="🔁 Migrations">
      <h2 class="text-xl font-bold">Batch Data Migration</h2>
      <p>Migrations let you perform <strong>one-time bulk sync</strong> from PostgreSQL to OpenSearch. Useful for initial data load or full re-index.</p>

      <h3 class="text-lg font-semibold mt-4">Create a Migration</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Go to <strong>Migrations</strong> → click <strong>"+ New Migration"</strong></li>
        <li>Select a configuration (pre-created from Configurations page)</li>
        <li>Set parameters:</li>
      </ol>

      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1">
{`• Name: e.g. "orders-initial-load"
• Frequency: Daily / Weekly / Monthly (for recurring)
• Date Column: which column to filter by (e.g. updated_at)
• Date From: start of data range (e.g. 2026-01-01)
• Date To: end of range (2026-06-23)
• Limit: max documents (leave empty for all)`}</div>

      <h3 class="text-lg font-semibold mt-4">Monitor Progress</h3>
      <p>After starting, the Migrations page shows:</p>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-center text-sm">
        {[
          ['Progress %', 'How far along'],
          ['Synced Docs', 'Total documents synced'],
          ['Failed Docs', 'Errors encountered'],
          ['Time Elapsed', 'Duration (seconds)'],
        ].map(([label, desc]) => (
          <div class="bg-gray-50 rounded p-2">
            <div class="font-semibold">{label}</div>
            <div class="text-gray-500 text-xs">{desc}</div>
          </div>
        ))}
      </div>

      <Tip>Use <strong>Preview Schema</strong> before running to verify field mappings are correct.</Tip>
    </Section>
  );
}

// ─── CDC ─────────────────────────────────────

function CDCSection() {
  return (
    <Section title="⚡ CDC (Change Data Capture)">
      <h2 class="text-xl font-bold">Real-Time Change Data Capture</h2>
      <p>CDC syncs changes from PostgreSQL to OpenSearch <strong>in real-time</strong> using PostgreSQL replication slots. Every INSERT, UPDATE, DELETE on tracked tables is reflected in OpenSearch within seconds.</p>

      <h3 class="text-lg font-semibold mt-4">Prerequisites</h3>
      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1">
{`1. PostgreSQL must have wal_level = logical
2. Source database must have a replication slot (auto-created by PGSync)
3. Tables should have PRIMARY KEY defined
4. CDC must be enabled in the Configuration form`}</div>

      <h3 class="text-lg font-semibold mt-4">How to Start CDC</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Create a Configuration with <strong>cdc_enabled = true</strong></li>
        <li>Go to <strong>CDC</strong> tab → find your configuration</li>
        <li>Click <strong>"Start CDC"</strong> to begin replication</li>
        <li>Monitor:</li>
      </ol>

      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1">
{`• Status: Running / Stopped / Error
• Docs Synced: Total documents replicated
• Throughput: Documents per second
• Lag: Seconds behind the source
• Last Sync: Timestamp of last successful sync`}</div>

      <h3 class="text-lg font-semibold mt-4">Example CDC Logs</h3>
      <div class="bg-gray-100 rounded p-3 text-xs font-mono leading-relaxed">
{`[2026-06-23 08:15:01] INFO  Starting CDC for config #3 (production-orders)
[2026-06-23 08:15:02] INFO  Created replication slot: pgsync_orders
[2026-06-23 08:15:03] INFO  Initial sync: 1,234 docs synced
[2026-06-23 08:15:04] INFO  Live streaming started, lag: 0.5s
[2026-06-23 08:15:05] INFO  INSERT → orders/789 synced
[2026-06-23 08:15:06] INFO  UPDATE → orders/456 synced`}</div>

      <Tip type="warn">Always stop CDC before deleting a configuration. Active replication slots can grow PostgreSQL WAL logs indefinitely.</Tip>

      <Tip>CDC throughput depends on network latency and document size. Expected: 500-5000 docs/sec for typical OLTP schemas.</Tip>
    </Section>
  );
}

// ─── Job ─────────────────────────────────────

function JobSection() {
  return (
    <Section title="⏰ Scheduled Jobs">
      <h2 class="text-xl font-bold">Recurring Sync Jobs with Cron</h2>
      <p>Jobs let you schedule PGSync execution at specific intervals using cron expressions. Built-in visual builder makes scheduling easy without remembering cron syntax.</p>

      <h3 class="text-lg font-semibold mt-4">Create a Job</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Go to <strong>Jobs</strong> → click <strong>"+ New Job"</strong></li>
        <li>Fill in:</li>
      </ol>

      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1 font-mono">
{`Field        │ Example                      │ Description
─────────────┼──────────────────────────────┼──────────────────────
Job Name     │ Daily Order Sync             │ Human-readable name
Config       │ (select from dropdown)       │ Which pipeline to run
Cron         │ 0 2 * * *                   │ Use presets or build`}</div>

      <h3 class="text-lg font-semibold mt-4">Cron Presets</h3>
      <table class="w-full text-sm border-collapse">
        <tbody>
        <tr class="bg-gray-100"><td class="p-2 font-medium">Every hour</td><td class="p-2"><Code>0 * * * *</Code></td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">Every 6 hours</td><td class="p-2"><Code>0 */6 * * *</Code></td></tr>
        <tr class="bg-gray-100"><td class="p-2 font-medium">Daily at 2am</td><td class="p-2"><Code>0 2 * * *</Code></td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">Weekly Mon 8am</td><td class="p-2"><Code>0 8 * * 1</Code></td></tr>
        <tr class="bg-gray-100"><td class="p-2 font-medium">Monthly 1st 3am</td><td class="p-2"><Code>0 3 1 * *</Code></td></tr>
        </tbody>
      </table>

      <h3 class="text-lg font-semibold mt-4">Job Actions</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
        {[
          ['▶ Run', 'Triggers execution immediately'],
          ['⏸ Pause', 'Temporarily stops scheduled runs'],
          ['▶ Resume', 'Re-enables after pause'],
          ['🗑 Delete', 'Removes job permanently'],
        ].map(([action, desc]) => (
          <div class="bg-gray-50 rounded p-2">
            <div class="font-semibold">{action}</div>
            <div class="text-gray-500 text-xs">{desc}</div>
          </div>
        ))}
      </div>

      <Tip>Use the <strong>Quick Presets</strong> in the cron builder — they cover 90% of scheduling needs. Custom mode available for advanced cron patterns.</Tip>
    </Section>
  );
}

// ─── Execution ───────────────────────────────

function ExecSection() {
  return (
    <Section title="📊 Execution Monitor">
      <h2 class="text-xl font-bold">Monitoring Sync Executions</h2>
      <p>The Execution tab shows <strong>every sync run</strong> — whether triggered manually, by a job, or by CDC. Monitor real-time progress, view logs, and analyze performance.</p>

      <h3 class="text-lg font-semibold mt-4">Execution List</h3>
      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1">
{`• Status: Running / Completed / Failed / Cancelled
• Config: Which pipeline was executed
• Type: batch / cdc
• Duration: Total execution time
• Progress: Documents synced vs total
• Started: Timestamp of execution start`}</div>

      <h3 class="text-lg font-semibold mt-4">Drill Down — Execution Detail</h3>
      <p>Click any execution to see full details:</p>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2">
        {[
          ['📋 Live Logs', 'Real-time streaming output from PGSync engine. Filter by log level (INFO, WARN, ERROR).'],
          ['📈 Metrics', 'Per-table stats: docs synced, failed, throughput. Useful for identifying slow tables.'],
          ['📄 Summary', 'Overall execution report: total docs, failures, batches, duration.'],
        ].map(([title, desc]) => (
          <div class="bg-gray-50 rounded-lg p-3 text-sm">
            <div class="font-semibold">{title}</div>
            <p class="text-gray-600 text-xs mt-1">{desc}</p>
          </div>
        ))}
      </div>

      <h3 class="text-lg font-semibold mt-4">Actions</h3>
      <div class="bg-gray-50 rounded-lg p-3 text-sm">
        • <strong>Stop Execution</strong> — Cancel a running sync immediately
        • <strong>Retry Failed</strong> — Re-run failed migrations
        • <strong>Acknowledge</strong> — Mark failure as reviewed (clears from alert view)
      </div>

      <Tip>Use logs with <strong>level=ERROR</strong> filter to quickly find root cause of failed executions.</Tip>
    </Section>
  );
}

// ─── Dashboard ───────────────────────────────

function DashSection() {
  return (
    <Section title="📈 Dashboards">
      <h2 class="text-xl font-bold">Custom Monitoring Dashboards</h2>
      <p>Dashboards provide a <strong>visual overview</strong> of your PGSync pipeline health. Create custom dashboards with widget-based layouts.</p>

      <h3 class="text-lg font-semibold mt-4">Create a Dashboard</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Go to <strong>Dashboards</strong> → click <strong>"+ New Dashboard"</strong></li>
        <li>Enter name and optional description</li>
        <li>Click <strong>Save</strong></li>
        <li>Add widgets to display metrics</li>
      </ol>

      <h3 class="text-lg font-semibold mt-4">Widget Types</h3>
      <table class="w-full text-sm border-collapse">
        <tbody>
        <tr class="bg-gray-100"><td class="p-2 font-medium">📊 Total Docs Synced</td><td class="p-2">Sum of all synced documents across all configs</td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">🟢 Active CDC</td><td class="p-2">Number of currently running CDC streams</td></tr>
        <tr class="bg-gray-100"><td class="p-2 font-medium">🔴 Failures</td><td class="p-2">Count of failed executions in the last 24h</td></tr>
        <tr class="bg-gray-50"><td class="p-2 font-medium">⚠️ Alerts Triggered</td><td class="p-2">Number of active alerts</td></tr>
        <tr class="bg-gray-100"><td class="p-2 font-medium">📈 Throughput</td><td class="p-2">Documents per second (rolling 1h avg)</td></tr>
        </tbody>
      </table>

      <h3 class="text-lg font-semibold mt-4">Example Dashboard Layout</h3>
      <div class="bg-gray-100 rounded p-3 text-xs font-mono">
{`┌─────────────────────────────────────────────────────┐
│  📈 Production Pipeline Dashboard                    │
├────────────┬────────────┬────────────┬───────────────┤
│Total Synced│Active CDC  │Failures 24h│Alerts Active  │
│  1,234,567 │     3      │     2      │      1        │
├────────────┴────────────┴────────────┴───────────────┤
│  📉 Throughput Over Time (line chart)                │
│  ████████████████░░░░░░░░░░░░░░  1,200 docs/s       │
└─────────────────────────────────────────────────────┘`}</div>

      <Tip>Create separate dashboards for production vs staging to keep metrics organized.</Tip>
    </Section>
  );
}

// ─── Alerts ──────────────────────────────────

function AlertSection() {
  return (
    <Section title="🚨 Alerts & Notifications">
      <h2 class="text-xl font-bold">Alert Rules & Notification Channels</h2>
      <p>Configure alerts to be notified when sync operations fail or exceed thresholds. Supports multiple notification channels.</p>

      <h3 class="text-lg font-semibold mt-4">Create an Alert Rule</h3>
      <ol class="list-decimal ml-5 space-y-2">
        <li>Go to <strong>Alerts</strong> → click <strong>"+ New Rule"</strong></li>
        <li>Configure:</li>
      </ol>

      <div class="bg-gray-50 rounded-lg p-4 text-sm space-y-1 font-mono">
{`Field            │ Example                      │ Description
─────────────────┼──────────────────────────────┼──────────────────
Rule Name        │ CDC Failure Alert             │ Identifier
Condition        │ failure_count > 5             │ Trigger threshold
Severity         │ critical / warning / info     │ Alert level
Channel          │ Telegram / Webhook            │ Notification target
Cooldown (min)   │ 30                            │ Min gap between alerts`}</div>

      <h3 class="text-lg font-semibold mt-4">Notification Channels</h3>
      <table class="w-full text-sm border-collapse">
        <tbody>
        <tr class="bg-gray-100">
          <td class="p-2 font-medium">📱 Telegram</td>
          <td class="p-2">Send alerts to a Telegram chat. Get chat ID from <Code>@userinfobot</Code>.</td>
        </tr>
        <tr class="bg-gray-50">
          <td class="p-2 font-medium">🔗 Webhook</td>
          <td class="p-2">POST JSON payload to any HTTP URL. Supports custom headers.</td>
        </tr>
        <tr class="bg-gray-100">
          <td class="p-2 font-medium">📧 Email (coming)</td>
          <td class="p-2">SMTP-based email delivery (planned).</td>
        </tr>
        </tbody>
      </table>

      <h3 class="text-lg font-semibold mt-4">Example: Telegram Alert Setup</h3>
      <ol class="list-decimal ml-5 space-y-1 text-sm">
        <li>Message <Code>@userinfobot</Code> on Telegram → get your chat ID</li>
        <li>In PGSync Admin: Alerts → <strong>"Setup Notification Provider"</strong></li>
        <li>Choose <strong>Telegram</strong>, enter bot token and chat ID</li>
        <li>Click <strong>"Test"</strong> to verify delivery</li>
        <li>Create alert rules that use this channel</li>
      </ol>

      <h3 class="text-lg font-semibold mt-4">Alert History & Actions</h3>
      <div class="bg-gray-50 rounded-lg p-3 text-sm space-y-1">
{`• 🔔 History: View all triggered alerts with timestamps
• 🔇 Suppress: Mute alert for N hours (e.g., during maintenance)
• ✅ Acknowledge: Mark alert as reviewed
• 🔄 Retry: Re-run failed execution from alert`}</div>

      <Tip type="warn">Always test notification channels after setup. A misconfigured channel means silent failures!</Tip>
    </Section>
  );
}

// ─── Reports ─────────────────────────────────

function ReportSection() {
  return (
    <Section title="📋 Reports">
      <h2 class="text-xl font-bold">Sync Reports & Analytics</h2>
      <p>Reports provide <strong>aggregated views</strong> of sync performance across all configurations. Export to CSV or JSON for external analysis.</p>

      <h3 class="text-lg font-semibold mt-4">Available Reports</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          ['📅 Daily Report', 'Last N days (default: 7). Total synced docs, failures, throughput per day.'],
          ['📅 Weekly Report', 'Last N weeks (default: 4). Weekly aggregation with trend comparison.'],
          ['📊 Table Stats', 'Per-table sync stats: documents, failures, update frequency.'],
        ].map(([title, desc]) => (
          <div class="bg-gray-50 rounded-lg p-3 text-sm">
            <div class="font-semibold">{title}</div>
            <p class="text-gray-600 text-xs mt-1">{desc}</p>
          </div>
        ))}
      </div>

      <h3 class="text-lg font-semibold mt-4">Export</h3>
      <div class="bg-gray-50 rounded-lg p-3 text-sm">
{`• CSV Export: Download report in CSV format (Excel-compatible)
• JSON Export: Raw JSON format for programmatic analysis
• Filter: You can filter by config_id to narrow down results`}</div>

      <h3 class="text-lg font-semibold mt-4">Example: Daily Report</h3>
      <div class="bg-gray-100 rounded p-3 text-xs font-mono">
{`📅 Daily Sync Report (Last 7 days)

Date        │ Synced  │ Failed │ Throughput │ Avg Duration
────────────┼─────────┼────────┼────────────┼─────────────
Jun-17      │ 125,430 │     2  │   1,450/s  │     12.3s
Jun-18      │ 132,100 │     0  │   1,520/s  │     10.1s
Jun-19      │ 118,200 │     5  │   1,300/s  │     15.7s
Jun-20      │    —    │    —   │     —      │      —   (outage)
Jun-21      │  98,400 │     1  │   1,100/s  │     11.4s
Jun-22      │ 105,300 │     0  │   1,200/s  │     10.8s
Jun-23      │  45,200 │     0  │   1,280/s  │     11.2s`}</div>

      <Tip>Export weekly reports to CSV for external dashboarding (Excel, Google Sheets, Metabase integration).</Tip>
    </Section>
  );
}

// ─── Lineage ─────────────────────────────────

function LineageSection() {
  return (
    <Section title="🔗 Data Lineage">
      <h2 class="text-xl font-bold">Data Flow Tracking</h2>
      <p>Lineage shows the <strong>end-to-end data flow</strong> from source PostgreSQL tables to destination OpenSearch indices. Visualize dependencies and impact analysis.</p>

      <h3 class="text-lg font-semibold mt-4">Features</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          ['🔗 Global Graph', 'Full dependency graph of all configs and their source/target relationships'],
          ['🔍 Per-Config View', 'Show lineage for a single configuration in isolation'],
          ['✨ Auto-Discover', 'Automatically detect table dependencies from PGSync schema config'],
          ['🔄 Re-discover', 'Refresh lineage after configuration changes'],
        ].map(([title, desc]) => (
          <div class="bg-gray-50 rounded-lg p-3 text-sm">
            <div class="font-semibold">{title}</div>
            <p class="text-gray-600 text-xs">{desc}</p>
          </div>
        ))}
      </div>

      <h3 class="text-lg font-semibold mt-4">Example Lineage Graph</h3>
      <div class="bg-gray-100 rounded p-3 text-xs font-mono leading-relaxed">
{`┌─────────────────┐           ┌─────────────────┐
│ PostgreSQL:     │           │ OpenSearch:     │
│ source_db      │           │ pgsync-orders   │
│                 │──────────▶│                 │
│  ├─ users       │           │  ├─ user        │
│  ├─ orders      │ Sync      │  ├─ order       │
│  └─ order_items │  #3       │  └─ order_item  │
└─────────────────┘           └─────────────────┘
        │
        │ Shared
        │ source
        ▼
┌─────────────────┐           ┌─────────────────┐
│ PostgreSQL:     │           │ OpenSearch:     │
│ legacy (10.7.0.5)│           │ legacy-products  │
│                 │──────────▶│                 │
│  └─ products    │ Sync      │  └─ product     │
│  └─ categories  │  #7       │  └─ category    │
└─────────────────┘           └─────────────────┘`}</div>

      <h3 class="text-lg font-semibold mt-4">Use Cases</h3>
      <ol class="list-decimal ml-5 space-y-1 text-sm">
        <li><strong>Impact Analysis</strong>: Before modifying a source table, check which OpenSearch indices depend on it</li>
        <li><strong>Audit Trail</strong>: Document data flow for compliance requirements</li>
        <li><strong>Troubleshooting</strong>: When a sync fails, trace which upstream source caused it</li>
      </ol>

      <Tip>Click <strong>"Discover All"</strong> to auto-generate lineage for all configurations. Run it after any config change to keep lineage up to date.</Tip>
    </Section>
  );
}
