# Quick start: PostgreSQL to OpenSearch

This guide runs the Admin UI, a seeded PostgreSQL source, and OpenSearch locally in Docker. It does not connect to an external database.

## Requirements

- Docker Engine with Docker Compose
- Python 3 to generate local application secrets

## Start the demo

1. Create a local environment file:

   ```sh
   cp .env.example .env
   ```

2. Generate an encryption key and a JWT secret. Paste each result into `.env`, then set `AUTH_ADMIN_USERNAME` and a unique `AUTH_ADMIN_PASSWORD` of at least 16 characters. Keep `DEMO_LOGIN_CREDENTIALS=false` unless the demo is isolated.

   ```sh
   python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```

3. Build and start the services:

   ```sh
   docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test up -d --build
   docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test ps
   ```

4. Open [http://localhost:3507](http://localhost:3507) and sign in with the Admin account from `.env`.

## Verify the pipeline

Run the end-to-end smoke test:

```sh
docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test exec -T backend /app/.venv/bin/python -m backend.scripts.local_pg_opensearch_smoke
```

It checks the connection handlers, schema discovery, configuration save/readback, a PGSync batch run, and documents in OpenSearch. The sample configuration appears in the UI as `local_pg_to_opensearch_demo`.

OpenSearch security is disabled in this demo and the service only binds to localhost. Do not expose it to a network. For ports, sample data, and reset commands, see the [demo guide](pgsync-admin/demo/README.md).

## Stop

```sh
docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test down
```

This preserves volumes. Add `-v` only when you intend to delete the Admin database and demo data. See the [root README](README.md) for other install and development options.
