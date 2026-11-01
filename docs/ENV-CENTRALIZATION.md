# Centralized Environment Configuration — Migration Guide

## 📁 New Structure (Opsi B — Multi-env di Root)

```
pgsync-production/
├── .env.example         ← Template (commit ke git)
├── .env.development     ← Dev config (commit)
├── .env.staging         ← Staging config (commit)
├── .env.production      ← Production config (gitignore)
├── .env                 ← Active config (gitignore, symlink/copy dari salah satu)
├── pgsync-admin/backend/
│   └── .env             ← DEPRECATED (akan dihapus)
├── search-api/
│   └── .env             ← DEPRECATED (akan dihapus)
└── laporan/
    └── .env             ← DEPRECATED (akan dihapus)
```

---

## 🎯 Benefits

✅ **Single Source of Truth** — satu file untuk semua services
✅ **Environment-specific** — dev/staging/prod terpisah tapi struktur sama
✅ **No Duplication** — shared vars (PG_*, OPENSEARCH_*) cuma ditulis 1x
✅ **Docker-compose ready** — `env_file: .env` otomatis load semua vars
✅ **Easy CI/CD** — `cp .env.production .env && docker-compose up`

---

## 🚀 Migration Steps

### Step 1: Copy Current Values

```bash
# Backup old env files
cp pgsync-admin/backend/.env pgsync-admin/backend/.env.backup
cp search-api/.env search-api/.env.backup
cp .env .env.backup

# Copy template
cp .env.example .env
```

### Step 2: Fill in Actual Values

Edit `.env` dan isi:

```bash
# From pgsync-admin/backend/.env.backup
ENCRYPTION_KEY=4510HbyGasbwOw_oUUNha-WJxi7hPOM84TDHexgoxbE=

# From search-api/.env.backup (sudah di SHARED section)
OPENSEARCH_PASSWORD=***

# From root .env.backup
PG_PASSWORD=***
```

### Step 3: Update docker-compose.yml

```yaml
services:
  backend:
    env_file: .env    # Load from root
    # Remove individual environment: entries

  frontend:
    env_file: .env

  search-api:
    env_file: .env
```

### Step 4: Update Python Services

**pgsync-admin/backend/backend/config.py:**
```python
# Old way (masih baca dari pgsync-admin/backend/.env)
load_dotenv()

# New way (baca dari root)
load_dotenv(find_dotenv())  # Auto-find .env di parent dirs
```

**search-api/main.py:**
```python
# Old
env_path = Path(__file__).parent / ".env"

# New
from dotenv import find_dotenv
load_dotenv(find_dotenv())  # Auto-find dari root
```

### Step 5: Test

```bash
# Test load env vars
cd pgsync-production
python -c "from dotenv import load_dotenv, find_dotenv; load_dotenv(find_dotenv()); import os; print(f'PG_HOST={os.getenv(\"PG_HOST\")}')"

# Test services
make admin-backend-run
make admin-test-quick
```

### Step 6: Cleanup (setelah verified working)

```bash
# Remove old env files
rm pgsync-admin/backend/.env
rm search-api/.env
rm laporan/.env

# Keep backups for rollback
# Commit new structure
git add .env.example .env.development .env.staging
git add .gitignore  # tambah .env ke gitignore
git commit -m "feat(env): Centralized environment configuration"
```

---

## 📋 Environment Files Explained

| File | Purpose | Git | Usage |
|------|---------|-----|-------|
| `.env.example` | Template + docs | ✅ Commit | Copy → fill values |
| `.env.development` | Local dev preset | ✅ Commit | `cp .env.development .env` |
| `.env.staging` | Staging preset | ✅ Commit | `cp .env.staging .env` |
| `.env.production` | Prod preset (NO SECRETS) | ✅ Commit | `cp .env.production .env` then fill secrets |
| `.env` | Active config | ❌ Gitignore | Copy from above + secrets |

---

## 🔐 Security Note

**JANGAN commit `.env` dengan secrets!**

```bash
# .gitignore
.env
*.env.local
.env.*.local
```

Commit `.env.production` tapi **TANPA** isi password/key — cuma struktur:

```bash
# .env.production (safe to commit)
PG_PASSWORD=          # Fill on deploy
ENCRYPTION_KEY=       # Fill on deploy
JWT_SECRET=           # Fill on deploy
```

---

## 🛠️ Commands

```bash
# Development
cp .env.development .env
docker-compose up

# Staging
cp .env.staging .env
docker-compose up

# Production
cp .env.production .env
nano .env  # Fill secrets
docker-compose up -d

# Or use env_file override
docker-compose --env-file .env.production up -d
```

---

## 🔄 Rollback Plan

Jika ada masalah:

```bash
# Restore old structure
cp pgsync-admin/backend/.env.backup pgsync-admin/backend/.env
cp search-api/.env.backup search-api/.env
cp .env.backup .env

# Services will work as before
```

---

## ✅ Verification Checklist

- [ ] `.env.example` created
- [ ] `.env.development` created
- [ ] `.env.staging` created
- [ ] `.env.production` created (no secrets)
- [ ] `.env` created from template + secrets filled
- [ ] docker-compose.yml updated with `env_file: .env`
- [ ] Python services updated to use `find_dotenv()`
- [ ] All services start successfully
- [ ] All tests pass
- [ ] Old .env files backed up
- [ ] `.gitignore` updated

---

## 📞 Support

Jika ada issue:

1. Check `.env` file exists: `ls -la .env`
2. Check vars loaded: `docker-compose config | grep PG_HOST`
3. Check service logs: `docker-compose logs backend`
4. Rollback: `cp .env.backup .env`
