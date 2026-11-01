# Docker

## Compose utama

`docker-compose.yml` membangun dan menjalankan Admin API serta UI:

```sh
cp .env.example .env
# Isi kredensial Admin dan key aplikasi pada .env.
docker-compose -f docker-compose.yml up -d --build
docker-compose -f docker-compose.yml ps
```

UI tersedia di `http://localhost:3507`, API di `http://localhost:3505`. Keduanya hanya dipublikasikan pada loopback. Database sumber dan tujuan tidak disertakan pada Compose utama.

## Demo PostgreSQL → OpenSearch

`docker-compose.local-test.yml` menambahkan PostgreSQL berisi data contoh dan OpenSearch single-node:

```sh
docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test up -d --build
```

Jalankan pemeriksaan end-to-end:

```sh
docker-compose -f docker-compose.yml -f docker-compose.local-test.yml --profile local-test exec -T backend /app/.venv/bin/python -m backend.scripts.local_pg_opensearch_smoke
```

OpenSearch demo berjalan tanpa security plugin dan hanya bind ke localhost. Jangan gunakan konfigurasi tersebut di server bersama atau production. Baca [panduan demo](../pgsync-admin/demo/README.md) sebelum menghapus volume.

## Search API

Search API menggunakan Compose terpisah dan koneksi OpenSearch TLS:

```sh
docker-compose --env-file .env -f search-api/docker-compose.yml up -d --build
```

Atur `OPENSEARCH_HOST`, `OPENSEARCH_PASSWORD`, `OPENSEARCH_INDEX`, dan `SEARCH_API_PORT` di `.env`. Panduan endpoint tersedia di [Search API README](../search-api/README.md).

## Data container

Volume `backend-data` menyimpan database SQLite Admin. Compose demo juga memakai `demo-postgres-data` dan `demo-opensearch-data`. Perintah `down` mempertahankan data; `down -v` menghapus volume dalam project tersebut.
