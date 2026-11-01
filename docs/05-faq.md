# FAQ & Troubleshooting

---

## Q: Project ini buat apa?

**A:** Sinkronisasi ~4,4 juta data laporan intelijen dari PostgreSQL ke OpenSearch.
Dashboard bisa search cepat, filter denormalized, aggregasi.

---

## Q: Min PostgreSQL berapa? Min OpenSearch berapa?

**Min PostgreSQL:** 9.4 (CDC `wal_level=logical`)
**Min OpenSearch:** 1.x (atau Elasticsearch 7.x)

**Production saat ini:**
- PostgreSQL 15.14 (Debian)
- OpenSearch 3.3.0 (prod) / 3.6.0 (dev)
- PGSync 7.0.5
- Python 3.12, deps via pip (Docker) atau uv (bare metal)

---

## Q: Bagaimana dengan relasi baru — tembusan, aspek, lampiran, laporan_masuk, tokoh?

**A:** Semua relasi ini **sudah diimplementasikan**. Detail:

| Relasi | Tabel PG | Denormalisasi di OS | Mulai ada data |
|--------|----------|-------------------|----------------|
| `tembusan` | laporan_tembusan → satuan_kerja | `tembusan: [{id, nama}]` | 2001+ |
| `aspek` | laporan_aspek → referensi | `aspek: [{id, nama}]` | 2001+ |
| `lampiran` | laporan_lampiran | `lampiran: [{id, jenis, file, ...}]` | ~2018+ |
| `laporan_masuk` | laporan_masuk → satuan_kerja | `laporan_masuk: [{id, satuan_kerja:{...}}]` | 2001+ |
| `tokoh` | laporan_isi_tokoh → tokoh | `isi_list[].tokoh: [{id, nama}]` | Data kosong di DB |

---

## Q: Ganti PG/OS ke server lain gimana?

Edit file `.env`:
- `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DATABASE`
- `ELASTICSEARCH_HOST`, `ELASTICSEARCH_PORT`, `ELASTICSEARCH_USER`, `ELASTICSEARCH_PASSWORD`

Rebuild index + sync ulang:
```bash
make docker-index
make docker-sync-all
```

---

## Q: Semua FK jadi `{id, nama}` — kenapa?

**A:** Denormalisasi = simpan hasil JOIN langsung di dokumen.
Filter by ID: `jenis.id: 8`. Filter by nama: `jenis.nama: "Laporan Intelijen"`.
Storage lebih besar, query 1000x lebih cepat.

---

## Q: Data di PG berubah, gimana update di OS?

- **CDC (real-time)** — WAL detect perubahan → index dalam detik
- **Re-sync (manual)** — `make docker-sync-resume`

---

## Q: Sync --all berhenti di tengah?

**A:** `make docker-sync-resume` — baca checkpoint → lanjut.

Manual: `cat /tmp/laporan-sync-checkpoint.txt`

---

## Q: Error `collation version mismatch`?

**A:** Warning harmless. Fix: `ALTER DATABASE example_db REFRESH COLLATION VERSION;`

---

## Q: SSL warning `InsecureRequestWarning`?

**A:** Self-signed cert. Supress: `export PYTHONWARNINGS=ignore`

---

## Q: Tabel `laporan` partitioned table. PGSync handle?

**A:** Yes. PGSync detect inheritance (partition) otomatis.
PostgreSQL logical replication handle partitioned tables tanpa konfigurasi tambahan.

---

## Q: Password mengandung karakter spesial (`!`, `$`, dll)?

**A:** Gunakan heredoc:
```bash
# Bukan: export PG_PASSWORD='pass!word'
# Tapi:
python3 <<'PYEOF'
import os
os.environ['ELASTICSEARCH_PASSWORD'] = 'pass_anda_disini'
# ... script logic
PYEOF
```

Atau load via `.env` file — script batch auto-load `.env`.

---

## Q: Reset dari awal?

```bash
rm -f /tmp/laporan-sync-checkpoint.txt
make docker-index        # Hapus & buat ulang index
make docker-sync-all     # Sync dari 2001
```

---

## Q: Offset bug — kok bulk empty terus?

**A:** v1.0.0 punya bug `offset += page_limit`. Udah fix — sekarang `offset += len(rows)`.
Kalau masih empty, cek apakah bulan yang di-sync beneran ada data.

---

## Q: `--tail` tidak ada di PGSync 7.0.5?

**A:** Betul. `--tail` dihapus setelah PGSync 6.x.
Ganti dengan:
- `--wal` — untuk consume WAL real-time (CDC)
- `--bootstrap` — untuk bikin replication slot (sebelum `--wal`)

---

## Q: CDC idle — log cuma periodic info, tidak sync data?

**A:** Ini terjadi kalau replication slot tidak ada atau corrupt.

**Penyebab:**
1. **Slot tidak ada** — PGSync `--wal` butuh slot
2. **Slot corrupt** — mismatch plugin (`test_decoding` vs `pgoutput`)
3. **Slot inactive** — container mati/direstart tanpa `--bootstrap`

**Diagnosis:**
```bash
# Cek slot di PG
PGPASSWORD=*** psql -h $PG_HOST -U postgres -d postgres \
  -c "SELECT slot_name, plugin, active FROM pg_replication_slots WHERE slot_type='logical'"
```

**Fix:**
```bash
# Drop semua logical slot
PGPASSWORD=*** psql -h $PG_HOST -U postgres -d postgres \
  -c "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_type='logical'"

# Restart CDC — --bootstrap bikin slot baru
podman compose up -d --force-recreate laporan-cdc

# Verifikasi: harus ada "Starting logical replication stream..."
podman compose logs -f laporan-cdc
```

---

## Q: CDC crash — KeyError: 'type' atau 'variant'?

**A:** PGSync 7.0.5 mewajibkan setiap relationship node di schema JSON punya:
```json
{
  "type": "one_to_many",
  "variant": "nested"
}
```

Cek semua `children` node di `config/schema-laporan-plugin.json` — pastikan
setiap node punya kedua field ini.

---

## Q: CDC crash — kolom `xxx_id` tidak ada?

**A:** PG tables **tidak punya foreign key constraint**. PGSync auto-detect gagal.
Tiap child node butuh `foreign_key` explicit:

```json
{
  "children": [{
    "table": "laporan_isi",
    "foreign_key": {
      "parent": "id",
      "child": "laporan_id"
    },
    ...
  }]
}
```

Juga perhatikan **nama kolom eksak** di PG. Ada yang `satuankerja_id`, ada yang `satuan_kerja_id`.
Cek `\d table_name` di psql dulu.

---

## Q: Container restart loop?

**A:** Biasanya karena Python startup error. Cek:
```bash
podman compose logs -f laporan-cdc
```

Penyebab umum:
1. **Schema JSON error** — validasi gagal di startup
2. **Env missing** — koneksi PG/OS gagal
3. **Index sudah ada tapi mapping beda** — run `make docker-index`

**Fix sementara:**
```bash
podman compose up -d --force-recreate laporan-cdc
```

---

## Q: CDC langsung sync semua data lama setelah start?

**A:** Normal. Ini initial sync dari replication slot baru. PGSync replay WAL dari
posisi awal slot — semua perubahan yang belum di-consume. Tapi karena slot baru,
dia mulai dari current position, bukan dari awal database.

Kalau mau **skip initial sync** — tidak bisa di PGSync 7.0.5 (`--tail` sudah dihapus).
Data lama harus di-sync via batch dulu, baru CDC jalan untuk perubahan baru.

---

## Q: `sudo -E` — kenapa perlu untuk `docker run psql`?

**A:** Kalo PG di remote host, `docker run --rm postgres:16 psql` butuh koneksi.
`sudo` reset environment variables → `$PG_HOST`, `$PG_USER`, dll jadi kosong.
Gunakan `sudo -E` untuk preserve env vars, atau pass langsung:
```bash
sudo docker run --rm --network host postgres:16 psql \
  "host=$PG_HOST dbname=postgres user=postgres password=***"
```

---

## Q: Drop replication slot — container harus mati dulu?

**A:** Tidak. Replication slot bisa di-drop kapanpun via `pg_drop_replication_slot()`.
Slot aktif (`active=t`) akan langsung di-terminate. Container CDC akan
restart otomatis (karena `restart: unless-stopped`).

Tapi setelah slot di-drop, PGSync di container perlu `--bootstrap` lagi untuk
bikin slot baru. Pastikan `docker-compose.yml` punya `--bootstrap` di command.

---

## Q: Bagaimana cara drop slot via container kalo PSQL gak ada di host?

```bash
source .env
sudo docker run --rm --network host postgres:16 \
  psql "host=$PG_HOST dbname=postgres user=$PG_USER password=$PG_PASSWORD" \
  -c "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_type='logical'"
```
