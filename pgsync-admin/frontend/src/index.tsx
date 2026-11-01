import { createSignal, onCleanup, Show, For } from 'solid-js';
import { render } from 'solid-js/web';
import { A, Router, Route, useLocation } from '@solidjs/router';
import { ConfigListPage } from './pages/config-list';
import { ConfigFormPage } from './pages/config-form';
import ConfigDetail from './pages/config-detail';
import { ExecutionListPage } from './pages/execution-list';
import { ExecutionMonitorPage } from './pages/execution-monitor';
import SchemaBuilder from './pages/schema-builder';
import { JobsPage } from './pages/jobs';
import { ReportsPage } from './pages/reports';
import { DashboardsPage } from './pages/dashboards';
import DashboardDetailPage from './pages/dashboard-detail';
import { AlertsPage } from './pages/alerts';
import { CDCPage } from './pages/cdc';
import { LineagePage } from './pages/lineage';
import Migrations from './pages/migrations';
import { HelpPage } from './pages/help';
import { LoginPage } from './pages/login';
import './index.css';

const navGroups = [
  { label: 'Workspace', items: [{ label: 'Configurations', href: '/config', mark: 'CF' }] },
  { label: 'Operations', items: [
    { label: 'CDC', href: '/cdc', mark: 'CD' },
    { label: 'Executions', href: '/execution', mark: 'EX' },
    { label: 'Jobs', href: '/views/jobs', mark: 'JB' },
    { label: 'Migrations', href: '/migrations', mark: 'MG' },
  ] },
  { label: 'Insights', items: [
    { label: 'Dashboards', href: '/dashboards', mark: 'DB' },
    { label: 'Alerts', href: '/alerts', mark: 'AL' },
    { label: 'Lineage', href: '/lineage', mark: 'LN' },
    { label: 'Reports', href: '/reports', mark: 'RP' },
  ] },
  { label: 'Support', items: [{ label: 'Help center', href: '/help', mark: ' ? ' }] },
];

function AppShell(props: { children: any; onLogout: () => void }) {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = createSignal(false);
  const current = () => {
    const path = location.pathname;
    if (path.startsWith('/config') || path.startsWith('/schema')) return 'Configurations';
    if (path.startsWith('/execution')) return 'Executions';
    if (path.startsWith('/views/jobs')) return 'Jobs';
    if (path.startsWith('/dashboards')) return 'Dashboards';
    if (path.startsWith('/migrations')) return 'Migrations';
    if (path.startsWith('/alerts')) return 'Alerts';
    if (path.startsWith('/cdc')) return 'CDC';
    if (path.startsWith('/lineage')) return 'Lineage';
    if (path.startsWith('/reports')) return 'Reports';
    return 'Help center';
  };
  const closeMenu = () => setMenuOpen(false);

  return (
    <div class="admin-shell">
      <Show when={menuOpen()}>
        <button class="admin-backdrop" type="button" aria-label="Close navigation" onClick={closeMenu} />
      </Show>
      <aside class={`admin-sidebar${menuOpen() ? ' admin-sidebar--open' : ''}`} aria-label="Main navigation">
        <A href="/config" class="admin-brand" onClick={closeMenu}>
          <span class="admin-brand__mark">P</span>
          <span><strong>PGSync</strong><small>ADMIN CONSOLE</small></span>
        </A>
        <nav class="admin-nav" aria-label="Main menu">
          <For each={navGroups}>{(group) => <section class="admin-nav__group">
            <h2>{group.label}</h2>
            <For each={group.items}>{(item) => <A
              href={item.href}
              activeClass="nav-link--active"
              class="admin-nav__link"
              onClick={closeMenu}
            ><span class="admin-nav__mark" aria-hidden="true">{item.mark}</span><span>{item.label}</span></A>}</For>
          </section>}</For>
        </nav>
        <div class="admin-sidebar__footer">
          <span class="admin-status"><i /> Service console</span>
          <button type="button" class="admin-logout" onClick={props.onLogout}>Sign out</button>
        </div>
      </aside>
      <div class="admin-main">
        <header class="admin-topbar">
          <button type="button" class="admin-menu-toggle" aria-label="Open navigation" aria-expanded={menuOpen()} onClick={() => setMenuOpen(true)}>
            <span /><span /><span />
          </button>
          <div class="admin-topbar__context"><span>PGSYNC ADMIN</span><b>/</b><strong>{current()}</strong></div>
          <span class="admin-topbar__environment"><i /> Local environment</span>
        </header>
        <main class="admin-content">{props.children}</main>
      </div>
    </div>
  );
}

function App() {
  const [authenticated, setAuthenticated] = createSignal(Boolean(localStorage.getItem('pgsync_admin_token')));
  const expireSession = () => setAuthenticated(false);
  window.addEventListener('pgsync-auth-expired', expireSession);
  onCleanup(() => window.removeEventListener('pgsync-auth-expired', expireSession));
  const logout = () => {
    localStorage.removeItem('pgsync_admin_token');
    setAuthenticated(false);
  };

  return (
    <Router root={(props) => <Show when={authenticated()} fallback={<LoginPage onLogin={() => setAuthenticated(true)} />}>
      <AppShell onLogout={logout}>{props.children}</AppShell>
    </Show>}>
      <Route path="/" component={ConfigListPage} />
      <Route path="/config" component={ConfigListPage} />
      <Route path="/config/new" component={ConfigFormPage} />
      <Route path="/config/:id" component={ConfigDetail} />
      <Route path="/config/:id/edit" component={ConfigFormPage} />
      <Route path="/schema/:config_id" component={SchemaBuilder} />
      <Route path="/migrations" component={Migrations} />
      <Route path="/execution" component={ExecutionListPage} />
      <Route path="/execution/:id" component={ExecutionMonitorPage} />
      <Route path="/views/jobs" component={JobsPage} />
      <Route path="/dashboards" component={DashboardsPage} />
      <Route path="/dashboards/:id/edit" component={DashboardDetailPage} />
      <Route path="/dashboards/:id" component={DashboardDetailPage} />
      <Route path="/alerts" component={AlertsPage} />
      <Route path="/cdc" component={CDCPage} />
      <Route path="/lineage" component={LineagePage} />
      <Route path="/reports" component={ReportsPage} />
      <Route path="/help" component={HelpPage} />
    </Router>
  );
}

render(() => <App />, document.getElementById('root') as HTMLElement);
