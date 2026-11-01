# Schema Dokumen OpenSearch — Laporan

Setiap dokumen di index `laporan` berbentuk seperti ini:

## Contoh Dokumen Lengkap

```json
{
  "_index": "laporan",
  "_id": "3412991",
  "_source": {
    "id": 3412991,
    "nomor": "00886/LAPINTEL/BINDADKI/I/2001",
    "judul": "Laporan situasi keamanan Jakarta Pusat",
    "narasi": "Berdasarkan hasil pemantauan pada tanggal 28 Januari 2001...",
    "catatan": null,
    "komentar": null,
    "status": 1,
    "approve": true,
    "tanggal_laporan": "2001-01-28T04:14:04+07:00",
    "created_date": "2022-04-04T14:22:53.953913+07:00",
    "updated_date": null,
    "unique_id": null,
    "status_pengajuan_penghapusan": null,

    "jenis":            { "id": 8,  "nama": "Laporan Intelijen" },
    "klasifikasi":      { "id": 4,  "nama": "Rahasia" },
    "urgensi":          null,
    "created_by":       { "id": 1,  "nama": "Administrator" },
    "updated_by":       null,
    "pelapor":          null,
    "tujuan":           { "id": 29, "nama": "DEPUTI-II" },
    "satuan_kerja":     { "id": 286, "nama": "BINDA DKI JAKARTA" },
    "neraca_kebenaran": null,
    "neraca_kepercayaan": null,

    "isi_list": [
      {
        "isi": "Situasi keamanan terkendali",
        "apa": "Pemantauan rutin",
        "mengapa": "Deteksi dini potensi gangguan",
        "bagaimana": "Patroli dan koordinasi dengan aparat setempat",
        "kapan": "2001-01-28T10:00:00+07:00",
        "lokasi": { "id": 50, "nama": "Jakarta Pusat" },
        "tokoh": []
      }
    ],

    "tembusan": [
      { "id": 29, "nama": "DEPUTI-II" },
      { "id": 52, "nama": "DIREKTORAT-52" }
    ],

    "aspek": [
      { "id": 16, "nama": "Ideologi" },
      { "id": 17, "nama": "Politik" },
      { "id": 18, "nama": "Ekonomi" }
    ],

    "lampiran": [
      {
        "id": 3,
        "jenis": "PDF",
        "file": "lampiran.pdf",
        "catatan": "Dokumen pendukung",
        "realfile": "/path/to/file",
        "created_date": "2024-01-15"
      }
    ],

    "laporan_masuk": [
      { "id": 20554, "satuan_kerja": { "id": 29, "nama": "DEPUTI-II" } }
    ]
  }
}
```

## Field Reference

| Field | Type | Sumber | Query |
|-------|------|--------|-------|
| `id` | integer | laporan.id | `_id` or `id` |
| `nomor` | keyword | laporan.nomor | `nomor: "00886/..."` |
| `judul` | text | laporan.judul | `match: {judul: "..."}` |
| `narasi` | text | laporan.narasi | `match: {narasi: "..."}` |
| `jenis` | object | referensi via jenis_id | `jenis.nama: "Laporan Intelijen"` |
| `klasifikasi` | object | referensi via klasifikasi_id | `klasifikasi.nama: "Rahasia"` |
| `tujuan` | object | satuan_kerja via tujuan_id | `tujuan.nama: "DEPUTI-II"` |
| `satuan_kerja` | object | satuan_kerja via satuan_kerja_id | `satuan_kerja.nama: "BINDA DKI"` |
| `isi_list` | nested[] | laporan_isi child | `nested path: isi_list` |
| `isi_list[].tokoh` | object[] | laporan_isi_tokoh → tokoh | `nested path: isi_list` |
| `tembusan` | object[] | laporan_tembusan → satuan_kerja | `exists: tembusan` |
| `aspek` | object[] | laporan_aspek → referensi | `exists: aspek` |
| `lampiran` | object[] | laporan_lampiran direct | `exists: lampiran` |
| `laporan_masuk` | object[] | laporan_masuk → satuan_kerja | `exists: laporan_masuk` |

## Cara Query

### Full-text Search

```json
// Cari di judul
GET laporan/_search
{ "query": { "match": { "judul": "keamanan jakarta" } } }

// Multi-field
GET laporan/_search
{
  "query": {
    "multi_match": {
      "query": "keamanan",
      "fields": ["judul", "narasi"]
    }
  }
}
```

### Filter Relasi Baru

```json
// Cari laporan yang punya tembusan
GET laporan/_search
{ "query": { "exists": { "field": "tembusan" } } }

// Cari berdasarkan aspek tertentu
GET laporan/_search
{
  "query": {
    "term": { "aspek.nama": "Ideologi" }
  }
}

// Cari berdasarkan laporan_masuk
GET laporan/_search
{
  "query": {
    "term": { "laporan_masuk.satuan_kerja.nama": "DEPUTI-II" }
  }
}
```

### Filter Nested (isi_list)

```json
// Cari laporan yang isi_list-nya menyebut keyword
GET laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": { "match": { "isi_list.isi": "patroli" } }
    }
  }
}

// Filter lokasi dalam isi_list
GET laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": { "term": { "isi_list.lokasi.nama": "Jakarta Pusat" } }
    }
  }
}
```

### Aggregasi

```json
// Hitung per aspek
GET laporan/_search
{
  "size": 0,
  "aggs": {
    "per_aspek": {
      "terms": { "field": "aspek.nama", "size": 20 }
    }
  }
}

// Hitung per jenis + sub-aggregasi klasifikasi
GET laporan/_search
{
  "size": 0,
  "aggs": {
    "per_jenis": {
      "terms": { "field": "jenis.nama", "size": 20 },
      "aggs": {
        "per_klasifikasi": {
          "terms": { "field": "klasifikasi.nama" }
        }
      }
    }
  }
}
```

## Null Handling

Field yang bisa `null`:
- `catatan`, `komentar`, `updated_date`, `unique_id`
- `urgensi`, `updated_by`, `pelapor`
- `neraca_kebenaran`, `neraca_kepercayaan`
- `isi_list` (array, bisa kosong `[]`)
- `lampiran` (array, bisa kosong `[]` — data mulai 2018)

Query `exists` untuk cek keberadaan:
```json
// Cek laporan yang punya lampiran
GET laporan/_search
{ "query": { "exists": { "field": "lampiran" } } }

// Cek laporan yang punya tembusan
GET laporan/_search
{ "query": { "exists": { "field": "tembusan" } } }
```
