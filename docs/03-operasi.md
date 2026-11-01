# Operasi

## Status dan log

```sh
docker-compose -f docker-compose.yml ps
docker-compose -f docker-compose.yml logs -f backend frontend
curl http://localhost:3505/health
```

Untuk demo PostgreSQL ke OpenSearch, sertakan overlay dan profile saat menjalankan perintah Compose. Lihat [Quick Start](../QUICKSTART.md).

## Menjalankan dan menghentikan

```sh
docker-compose -f docker-compose.yml up -d --build
docker-compose -f docker-compose.yml down
```

Perintah `down` menghentikan dan menghapus container serta network, tetapi mempertahankan volume. `down -v` juga menghapus database Admin dan seluruh data yang tersimpan di volume. Gunakan opsi itu hanya saat memang ingin menghapus data lokal.

## Backup

SQLite Admin disimpan di volume `backend-data`. Sebelum upgrade atau pemindahan host, hentikan layanan atau gunakan mekanisme backup volume yang konsisten, lalu uji pemulihan pada lingkungan terpisah. Konfigurasi koneksi database disimpan di Admin; jaga file backup seperti rahasia.

## Operasi pipeline

Mulai, hentikan, dan pantau pipeline dari UI. Batch synchronization melakukan salinan awal; CDC berkelanjutan membutuhkan logical replication dan izin yang sesuai pada database sumber. Untuk PostgreSQL replication, slot yang tidak aktif dapat menahan WAL. Hapus publication atau slot hanya setelah pipeline tersebut memang dihentikan permanen.

Search API berjalan sebagai Compose terpisah. Periksa [panduan Search API](../search-api/README.md) untuk health check dan log layanannya.
