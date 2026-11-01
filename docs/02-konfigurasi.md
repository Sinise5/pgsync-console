# Konfigurasi

## Environment aplikasi

Buat `.env` lokal dari template. Jangan commit `.env` atau file environment per deployment.

```sh
cp .env.example .env
```

Admin API membutuhkan nilai berikut:

- `ENCRYPTION_KEY`: Fernet key untuk mengenkripsi kredensial yang disimpan.
- `JWT_SECRET`: secret untuk menandatangani token login.
- `AUTH_ADMIN_USERNAME` dan `AUTH_ADMIN_PASSWORD`: akun Admin. Password minimal 16 karakter.
- `DEMO_LOGIN_CREDENTIALS`: biarkan `false`, kecuali demo lokal terisolasi.

Buat dua key dengan Python standard library, lalu salin hasilnya ke `.env`:

```sh
python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

`.env.example` memuat placeholder koneksi untuk tool yang menggunakan environment bersama. Ganti host, database, user, password, TLS, dan port sesuai layanan Anda. Untuk konfigurasi yang disimpan melalui UI, gunakan host yang dapat dijangkau dari container backend.

## Koneksi database pada form Configure

Setiap konfigurasi menyimpan sumber, tujuan, tipe pipeline, dan schema mapping. Gunakan tombol tes koneksi sebelum menyimpan. Schema Builder memakai foreign key yang ditemukan untuk menghubungkan tabel; periksa relasi sebelum memulai sinkronisasi.

Port umum:

| Layanan | Port default |
| --- | ---: |
| PostgreSQL | 5432 |
| MySQL / MariaDB | 3306 |
| OpenSearch / Elasticsearch | 9200 |
| ClickHouse HTTP | 8123 |

Untuk PostgreSQL replication, sumber harus mengaktifkan `wal_level=logical` dan user pipeline memerlukan hak membuat publication. Untuk salin PostgreSQL, database tujuan harus sudah ada. Lihat [persyaratan pipeline](../pgsync-admin/backend/README.md#configure-pipeline-types).

## Koneksi lokal demo

Profil demo memberi nama service Docker `demo-postgres` dan `demo-opensearch`. Gunakan nama tersebut sebagai host dari backend container. Rincian seed, port host, serta smoke test tersedia di [panduan demo](../pgsync-admin/demo/README.md).
