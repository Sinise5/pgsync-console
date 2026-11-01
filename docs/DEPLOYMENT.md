# Docker Deployment

## Local stack

Requirements: Docker Engine and either `docker compose` or `docker-compose`.

1. Copy `.env.example` to `.env`, then set the PostgreSQL and OpenSearch connection values.
2. Set `ENCRYPTION_KEY`, `JWT_SECRET`, `AUTH_ADMIN_USERNAME`, and `AUTH_ADMIN_PASSWORD`. The backend refuses to start with missing auth values. Generate keys with the commands in the root README.
   Set `DEMO_LOGIN_CREDENTIALS=true` only for a local demo; it displays the configured admin password on the login page. The default is `false`.
3. Start the Admin stack:

   ```bash
   make admin-up
   ```

   Or use Compose directly:

   ```bash
   docker-compose -f docker-compose.yml up -d --build
   ```

4. Open `http://localhost:3507` and sign in with the configured admin account. The API is also available at `http://localhost:3505`; both ports bind to loopback only.

The frontend and backend run in Compose. PostgreSQL and OpenSearch are external services configured through `.env`. ClickHouse is also external and optional for the local Admin UI; Docker connects to `host.docker.internal` by default. Set `ADMIN_CLICKHOUSE_HOST` if ClickHouse is hosted elsewhere.

Search API is a separate Compose project:

```bash
make search-up
```

It is exposed at `http://localhost:18080` by default and requires a reachable OpenSearch instance and `OPENSEARCH_PASSWORD`.

`make up` starts Search API and PGSync Admin. The checked-in Compose files do not currently define a PGSync CDC service, so CDC is not started by that command.

## Operate

```bash
docker-compose -f docker-compose.yml ps
docker-compose -f docker-compose.yml logs -f backend frontend
make admin-down
make search-down
```

The Admin SQLite database persists in the named `backend-data` volume. Removing containers with `down` keeps that volume. To intentionally delete local Admin data, use `docker-compose -f docker-compose.yml down -v`.

## Production notes

- Use unique production secrets and rotate credentials that have appeared in Git history.
- Put the UI behind HTTPS and keep the API ports private to the reverse proxy or trusted network.
- Back up the `backend-data` volume and test restore procedures.
- Supply a trusted OpenSearch CA when certificate verification is enabled. Disabling verification is intended only for isolated development.
