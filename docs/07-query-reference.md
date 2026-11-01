# Query Reference — OpenSearch Laporan

Semua query dalam format **OpenSearch Query DSL** (REST API).
Cocok untuk Dashboard, analitik, atau integrasi langsung.

**Endpoint:** `POST /laporan/_search`
**Base:** `https://<host>:9200`

---

## Daftar Isi

1. [Full-Text Search](#1-full-text-search)
2. [Filter by Object Fields (FK)](#2-filter-by-object-fields-fk)
3. [Filter by Date Range](#3-filter-by-date-range)
4. [Filter by Scalar Fields](#4-filter-by-scalar-fields)
5. [Filter Nested (isi_list)](#5-filter-nested-isi_list)
6. [Filter Array Objects](#6-filter-array-objects)
7. [Boolean Combinations](#7-boolean-combinations)
8. [Aggregations](#8-aggregations)
9. [Pagination & Sorting](#9-pagination--sorting)
10. [Complete Dashboard Query](#10-complete-dashboard-query)

---

## 1. Full-Text Search

### 1a. Single Field

```json
// Cari di judul
POST /laporan/_search
{
  "query": {
    "match": { "judul": "keamanan jakarta" }
  }
}

// Cari di narasi
POST /laporan/_search
{
  "query": {
    "match": { "narasi": "situasi politik" }
  }
}

// Cari di catatan
POST /laporan/_search
{
  "query": {
    "match": { "catatan": "dokumen rahasia" }
  }
}

// Cari di komentar
POST /laporan/_search
{
  "query": {
    "match": { "komentar": "perlu ditindaklanjuti" }
  }
}

// Exact phrase
POST /laporan/_search
{
  "query": {
    "match_phrase": { "narasi": "situasi keamanan jakarta pusat" }
  }
}

// Prefix (autocomplete nomor)
POST /laporan/_search
{
  "query": {
    "prefix": { "nomor": "00886" }
  }
}
```

### 1b. Multi-Field (dengan boosting)

```json
// Search di judul + narasi + catatan. Judul dapat boost 3x
POST /laporan/_search
{
  "query": {
    "multi_match": {
      "query": "keamanan politik",
      "fields": ["judul^3", "narasi^2", "catatan", "komentar"],
      "type": "best_fields"
    }
  }
}
```

### 1c. Search di Semua Teks (termasuk isi_list)

> **Catatan:** `isi_list` adalah `nested` — perlu query khusus.

```json
POST /laporan/_search
{
  "query": {
    "bool": {
      "should": [
        { "multi_match": {
            "query": "patroli",
            "fields": ["judul^3", "narasi^2", "catatan"]
        }},
        { "nested": {
            "path": "isi_list",
            "query": { "multi_match": {
                "query": "patroli",
                "fields": ["isi_list.isi", "isi_list.apa", "isi_list.mengapa", "isi_list.bagaimana"]
            }},
            "score_mode": "max"
        }}
      ]
    }
  }
}
```

---

## 2. Filter by Object Fields (FK)

Semua FK terdenormalisasi jadi `{id, nama}`. Filter bisa via `id` atau `nama`.

### 2a. By ID (exact)

```json
// jenis_id = 8 (Laporan Intelijen)
POST /laporan/_search
{
  "query": {
    "term": { "jenis.id": 8 }
  }
}

// satuan_kerja_id = 286 (BINDA DKI JAKARTA)
POST /laporan/_search
{
  "query": {
    "term": { "satuan_kerja.id": 286 }
  }
}

// Multiple IDs
POST /laporan/_search
{
  "query": {
    "terms": { "jenis.id": [8, 9, 10] }
  }
}
```

### 2b. By Nama (keyword)

```json
POST /laporan/_search
{
  "query": {
    "term": { "jenis.nama": "Laporan Intelijen" }
  }
}

// Partial match (wildcard)
POST /laporan/_search
{
  "query": {
    "wildcard": { "satuan_kerja.nama": "BINDA*" }
  }
}
```

### 2c. Semua Filter Object yang Tersedia

| Filter Field | Sumber | Tipe ID | Contoh |
|-------------|--------|---------|--------|
| `jenis.id` / `jenis.nama` | referensi | integer | 8 |
| `klasifikasi.id` / `klasifikasi.nama` | referensi | integer | 4 |
| `urgensi.id` / `urgensi.nama` | referensi | integer | 1 |
| `created_by.id` / `created_by.nama` | user | integer | 1 |
| `updated_by.id` / `updated_by.nama` | user | integer | 5 |
| `pelapor.id` / `pelapor.nama` | pelapor | integer | 100 |
| `tujuan.id` / `tujuan.nama` | satuan_kerja | integer | 29 |
| `satuan_kerja.id` / `satuan_kerja.nama` | satuan_kerja | integer | 286 |
| `neraca_kebenaran.id` / `neraca_kebenaran.nama` | neraca_penilaian_kebenaran | integer | 1 |
| `neraca_kepercayaan.id` / `neraca_kepercayaan.nama` | neraca_penilaian_kepercayaan | integer | 1 |

---

## 3. Filter by Date Range

```json
// Tanggal laporan dalam rentang
POST /laporan/_search
{
  "query": {
    "range": {
      "tanggal_laporan": {
        "gte": "2025-01-01",
        "lte": "2025-06-30",
        "format": "yyyy-MM-dd"
      }
    }
  }
}

// Dibuat dalam 7 hari terakhir
POST /laporan/_search
{
  "query": {
    "range": {
      "created_date": {
        "gte": "now-7d/d",
        "lte": "now"
      }
    }
  }
}

// Belum pernah diupdate
POST /laporan/_search
{
  "query": {
    "bool": {
      "must_not": { "exists": { "field": "updated_date" } }
    }
  }
}

// Diupdate dalam 30 hari terakhir
POST /laporan/_search
{
  "query": {
    "range": {
      "updated_date": {
        "gte": "now-30d/d"
      }
    }
  }
}
```

---

## 4. Filter by Scalar Fields

```json
// Status exact
POST /laporan/_search
{
  "query": {
    "term": { "status": 1 }
  }
}

// Status multiple
POST /laporan/_search
{
  "query": {
    "terms": { "status": [0, 1, 2] }
  }
}

// Approve
POST /laporan/_search
{
  "query": {
    "term": { "approve": true }
  }
}

// Belum approve
POST /laporan/_search
{
  "query": {
    "term": { "approve": false }
  }
}

// status_pengajuan_penghapusan
POST /laporan/_search
{
  "query": {
    "term": { "status_pengajuan_penghapusan": "diajukan" }
  }
}

// unique_id exact
POST /laporan/_search
{
  "query": {
    "term": { "unique_id": "UUID-xxx" }
  }
}
```

---

## 5. Filter Nested (isi_list)

> **PENTING:** `isi_list` adalah `nested` type. Semua query ke field di dalamnya
> **WAJIB** pakai `nested` query dengan `path: "isi_list"`.

### 5a. Search di Isi

```json
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "match": { "isi_list.isi": "patroli keamanan" }
      }
    }
  }
}
```

### 5b. Search di Semua Field Isi

```json
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "multi_match": {
          "query": "patroli",
          "fields": ["isi_list.isi", "isi_list.apa", "isi_list.mengapa", "isi_list.bagaimana"]
        }
      }
    }
  }
}
```

### 5c. Filter by Lokasi dalam Isi

```json
// By ID
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "term": { "isi_list.lokasi.id": 50 }
      }
    }
  }
}

// By Nama
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "term": { "isi_list.lokasi.nama": "Jakarta Pusat" }
      }
    }
  }
}
```

### 5d. Filter by Tokoh dalam Isi

```json
// Laporan yang menyebut tokoh tertentu
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "nested": {
          "path": "isi_list.tokoh",
          "query": {
            "term": { "isi_list.tokoh.nama": "Nama Tokoh" }
          }
        }
      }
    }
  }
}
```

> **Catatan:** `tokoh` nested di dalam `isi_list` (nested-in-nested).
> Butuh 2 level `nested` query.

### 5e. Multiple Conditions dalam Isi

```json
// Isi mengandung "patroli" DAN lokasi = Jakarta Pusat
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "bool": {
          "must": [
            { "match": { "isi_list.isi": "patroli" } },
            { "term": { "isi_list.lokasi.id": 50 } }
          ]
        }
      }
    }
  }
}
```

### 5f. Filter by Kapan (Date di Isi)

```json
POST /laporan/_search
{
  "query": {
    "nested": {
      "path": "isi_list",
      "query": {
        "range": {
          "isi_list.kapan": {
            "gte": "2025-01-01",
            "lte": "2025-12-31"
          }
        }
      }
    }
  }
}
```

---

## 6. Filter Array Objects

### 6a. tembusan — Filter by Satuan Kerja

```json
// Laporan yang ditembuskan ke DEPUTI-II
POST /laporan/_search
{
  "query": {
    "term": { "tembusan.nama": "DEPUTI-II" }
  }
}

// Yang punya tembusan
POST /laporan/_search
{
  "query": {
    "exists": { "field": "tembusan" }
  }
}

// Yang TIDAK punya tembusan
POST /laporan/_search
{
  "query": {
    "bool": {
      "must_not": { "exists": { "field": "tembusan" } }
    }
  }
}
```

### 6b. aspek — Filter by Referensi

```json
// Laporan dengan aspek Ideologi
POST /laporan/_search
{
  "query": {
    "term": { "aspek.nama": "Ideologi" }
  }
}

// Multiple aspek
POST /laporan/_search
{
  "query": {
    "terms": { "aspek.id": [16, 17, 18] }
  }
}
```

### 6c. lampiran — Filter by Jenis File

```json
// Yang punya lampiran PDF
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        { "exists": { "field": "lampiran" } },
        { "term": { "lampiran.jenis": "PDF" } }
      ]
    }
  }
}

// Yang punya lampiran apapun
POST /laporan/_search
{
  "query": {
    "exists": { "field": "lampiran" }
  }
}
```

### 6d. laporan_masuk — Filter by Satuan Kerja

```json
// Laporan yang masuk ke DEPUTI-II
POST /laporan/_search
{
  "query": {
    "term": { "laporan_masuk.satuan_kerja.nama": "DEPUTI-II" }
  }
}
```

---

## 7. Boolean Combinations

Semua filter di atas bisa digabung pake `bool` query.

### 7a. Search + Multiple Filters

```json
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        { "multi_match": {
            "query": "keamanan",
            "fields": ["judul^3", "narasi^2"]
        }}
      ],
      "filter": [
        { "term": { "jenis.id": 8 } },
        { "term": { "klasifikasi.id": 4 } },
        { "range": {
            "tanggal_laporan": {
              "gte": "2025-01-01",
              "lte": "2025-12-31"
            }
        }},
        { "term": { "approve": true } },
        { "exists": { "field": "tembusan" } }
      ]
    }
  }
}
```

### 7b. OR Antar Filter

```json
// Search + (jenis = Intelijen ATAU klasifikasi = Rahasia)
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "judul": "keamanan" } }
      ],
      "filter": [
        { "bool": {
            "should": [
              { "term": { "jenis.id": 8 } },
              { "term": { "klasifikasi.id": 4 } }
            ],
            "minimum_should_match": 1
        }}
      ]
    }
  }
}
```

### 7c. Nested + Top-Level Filter

```json
// Search di judul + filter nested isi_list.lokasi
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "judul": "keamanan" } }
      ],
      "filter": [
        { "nested": {
            "path": "isi_list",
            "query": {
              "term": { "isi_list.lokasi.id": 50 }
            }
        }},
        { "terms": { "status": [1, 2] } },
        { "term": { "satuan_kerja.id": 286 } }
      ]
    }
  }
}
```

### 7d. Dashboard Query Lengkap

```json
// Pencarian lengkap dengan SEMUA filter umum
// Copy-paste ini, uncomment yang dipake
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        // Full-text search (aktifkan salah satu)
        //{ "multi_match": {
        //    "query": "keamanan",
        //    "fields": ["judul^3", "narasi^2", "catatan"]
        //}}
      ],
      "filter": [
        // ── Date Range ──
        //{ "range": { "tanggal_laporan": { "gte": "2025-01-01", "lte": "2025-12-31" } }},
        //{ "range": { "created_date": { "gte": "now-30d/d" } }},

        // ── Status & Approval ──
        //{ "term": { "status": 1 }},
        //{ "term": { "approve": true }},

        // ── FK Objects ──
        //{ "term": { "jenis.id": 8 }},
        //{ "term": { "klasifikasi.id": 4 }},
        //{ "term": { "urgensi.id": 1 }},
        //{ "term": { "satuan_kerja.id": 286 }},
        //{ "term": { "tujuan.id": 29 }},
        //{ "term": { "pelapor.id": 100 }},
        //{ "term": { "created_by.id": 1 }},
        //{ "term": { "neraca_kebenaran.id": 1 }},
        //{ "term": { "neraca_kepercayaan.id": 1 }},

        // ── Array Objects ──
        //{ "exists": { "field": "tembusan" }},
        //{ "term": { "tembusan.nama": "DEPUTI-II" }},
        //{ "term": { "aspek.nama": "Ideologi" }},
        //{ "exists": { "field": "lampiran" }},
        //{ "term": { "lampiran.jenis": "PDF" }},
        //{ "term": { "laporan_masuk.satuan_kerja.nama": "DEPUTI-II" }},

        // ── Nested (isi_list) ──
        //{ "nested": {
        //    "path": "isi_list",
        //    "query": { "match": { "isi_list.isi": "patroli" }}
        //}},
        //{ "nested": {
        //    "path": "isi_list",
        //    "query": { "term": { "isi_list.lokasi.id": 50 }}
        //}},
        //{ "nested": {
        //    "path": "isi_list",
        //    "query": { "nested": {
        //        "path": "isi_list.tokoh",
        //        "query": { "term": { "isi_list.tokoh.nama": "Nama Tokoh" }}
        //    }}
        //}}
      ]
    }
  },
  "sort": [
    { "_score": { "order": "desc" } },
    { "tanggal_laporan": { "order": "desc" } }
  ],
  "from": 0,
  "size": 20,
  "_source": {
    "excludes": ["narasi"]
  },
  "highlight": {
    "fields": {
      "judul": {},
      "narasi": { "fragment_size": 150 },
      "catatan": {}
    }
  }
}
```

---

## 8. Aggregations

### 8a. Count per Jenis

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_jenis": {
      "terms": { "field": "jenis.nama", "size": 30 }
    }
  }
}
```

### 8b. Count per Klasifikasi

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_klasifikasi": {
      "terms": { "field": "klasifikasi.nama", "size": 20 }
    }
  }
}
```

### 8c. Count per Satuan Kerja

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_satuan_kerja": {
      "terms": { "field": "satuan_kerja.nama", "size": 50 }
    }
  }
}
```

### 8d. Count per Tahun

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_tahun": {
      "date_histogram": {
        "field": "tanggal_laporan",
        "calendar_interval": "year",
        "format": "yyyy",
        "min_doc_count": 1
      }
    }
  }
}
```

### 8e. Nested Aggregation — Aspek per Jenis

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_jenis": {
      "terms": { "field": "jenis.nama", "size": 20 },
      "aggs": {
        "per_aspek": {
          "terms": { "field": "aspek.nama", "size": 10 }
        }
      }
    }
  }
}
```

### 8f. Status Summary

```json
POST /laporan/_search
{
  "size": 0,
  "aggs": {
    "per_status": {
      "terms": { "field": "status" }
    },
    "approve_count": {
      "terms": { "field": "approve" }
    }
  }
}
```

### 8g. Date Histogram + Filter

```json
// Trend bulanan untuk jenis tertentu
POST /laporan/_search
{
  "size": 0,
  "query": {
    "term": { "jenis.id": 8 }
  },
  "aggs": {
    "trend_bulanan": {
      "date_histogram": {
        "field": "tanggal_laporan",
        "calendar_interval": "month",
        "format": "yyyy-MM",
        "min_doc_count": 1
      }
    }
  }
}
```

---

## 9. Pagination & Sorting

```json
// Halaman 3, 50 items per halaman, sorted by tanggal terbaru
POST /laporan/_search
{
  "from": 100,
  "size": 50,
  "query": { "match_all": {} },
  "sort": [
    { "tanggal_laporan": { "order": "desc" } }
  ]
}

// Sorted by relevance then tanggal
POST /laporan/_search
{
  "query": {
    "match": { "judul": "keamanan" }
  },
  "sort": [
    { "_score": { "order": "desc" } },
    { "tanggal_laporan": { "order": "desc" } }
  ]
}
```

---

## 10. Complete Dashboard Query

Contoh query siap pakai untuk endpoint dashboard FastAPI.
Semua params opsional — hanya yang diisi yang jadi filter.

```json
// Template query yang bisa dipanggil dari Python/FastAPI
POST /laporan/_search
{
  "query": {
    "bool": {
      "must": [
        // ── Search ──
        // $q → multi_match di judul^3, narasi^2, catatan
        // $q_isi → nested match di isi_list.isi, apa, mengapa, bagaimana
      ],
      "filter": [
        // $jenis_id, $klasifikasi_id, $urgensi_id
        // $satuan_kerja_id, $tujuan_id, $pelapor_id
        // $status, $approve
        // $tanggal_from, $tanggal_to
        // $aspek_nama, $tembusan_nama, $lokasi_id
        // $tokoh_nama
        // $has_lampiran (exists)
      ]
    }
  },
  "sort": [ /* $sort_by, $sort_order */ ],
  "from": 0,
  "size": 20,
  "aggs": {
    // $aggs → aggregasi sidebar
  },
  "highlight": {
    "fields": {
      "judul": {},
      "narasi": { "fragment_size": 200 }
    }
  }
}
```

Lihat `scripts/search_laporan.py` untuk implementasi Python lengkap.
