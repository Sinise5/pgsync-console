# PGSync Admin - Frontend

**Version:** 0.6.0 (see `package.json`)
**Framework:** SolidJS + Tailwind CSS
**Dev port:** 5173 | **Docker port:** 3507

---

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

Frontend: http://localhost:5173
API Proxy: http://localhost:3505

### 3. Build for Production

```bash
npm run build
```

---

## Project Structure

```
frontend/
├── src/
│   ├── components/       # Reusable UI components
│   │   ├── ui/          # Local UI primitives (Button, Card, Badge)
│   │   ├── log-viewer.tsx
│   │   └── cron-builder.tsx
│   ├── pages/           # Page components
│   │   ├── config-list.tsx
│   │   ├── config-form.tsx
│   │   ├── config-detail.tsx
│   │   ├── schema-builder.tsx
│   │   ├── cdc.tsx
│   │   ├── execution-list.tsx
│   │   ├── execution-monitor.tsx
│   │   ├── jobs.tsx
│   │   ├── migrations.tsx
│   │   ├── dashboards.tsx
│   │   ├── alerts.tsx
│   │   ├── reports.tsx
│   │   ├── lineage.tsx
│   │   └── help.tsx
│   ├── lib/             # Utilities
│   │   └── api-client.ts
│   ├── hooks/           # Custom hooks
│   │   └── use-live-logs.ts
│   ├── index.tsx        # App entry point + router
│   └── index.css        # Global styles
├── index.html           # HTML template
├── nginx.conf           # Production nginx config (static + SPA)
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## Available Scripts

- `npm run dev` — Start development server
- `npm run build` — Build for production
- `npm run preview` — Preview production build
- `npm run type-check` — TypeScript type checking

---

## Pages & Features (v0.9.2)

| Page | Route | Description |
|------|-------|-------------|
| **Configurations** | `/` | List, create, edit, delete PGSync configs |
| **Config Detail** | `/config/:id` | View config details + schema + lineage access |
| **Schema Builder** | `/schema/:config_id` | Select tables and Search columns; import or export portable JSON schema mappings |
| **Migrations** | `/migrations` | Batch data migration from Postgres to OpenSearch |
| **CDC** | `/cdc` | Real-time CDC monitoring (status, lag, throughput) |
| **Jobs** | `/views/jobs` | Cron-based scheduled sync jobs |
| **Executions** | `/execution` | Monitor sync runs (progress, logs, metrics) |
| **Dashboards** | `/dashboards` | Custom KPI dashboards with widgets |
| **Alerts** | `/alerts` | Alert rules + Telegram/webhook notifications |
| **Reports** | `/reports` | Daily/weekly reports + CSV/JSON export |
| **Lineage** | `/lineage` | Data flow graph (Postgres tables → OpenSearch indices) |
| **Help** | `/help` | Complete guide with examples for all features |

The app requires an admin login. Configure `AUTH_ADMIN_USERNAME`, `AUTH_ADMIN_PASSWORD`, and `JWT_SECRET` in the repository root `.env` before starting the backend.

---

## Key Technical Details

- **Router:** `@solidjs/router` with hash-free SPA routing
- **API client:** Axios wrapper via `/api` proxy (dev: Vite proxy → :3505, prod: nginx reverse proxy)
- **Styling:** Tailwind CSS 3.4, processed by PostCSS and Autoprefixer
- **Build output:** Static `dist/` served by nginx in Docker
- **Docker port:** 3507 (mapped from nginx :80)
- **nginx:** SPA fallback (`try_files $uri /index.html`), API reverse proxy to backend :3505

---

## Dependencies

- solid-js ^1.9
- @solidjs/router ^0.15
- axios ^1.7
- tailwindcss ^3.4

---

**Maintainer:** QTI Research

## License

This component is covered by the repository [MIT License](../../LICENSE).
