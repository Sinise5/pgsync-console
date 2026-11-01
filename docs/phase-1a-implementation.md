# Phase 1a: Backend Setup + Config Management (continued)

---

## API Endpoints Specification (continued)

### 3. Schema Generation

#### `POST /api/generate/schema`

Generate PGSync schema JSON + plugin code from config.

**Request:**
```json
{
  "config_id": 1
}
```

**Response (200):**
```json
{
  "pgsync_schema": {
    "database": "siitpartisi",
    "index": "laporan",
    "nodes": {
      "table": "laporan",
      "schema": "public",
      "columns": ["id", "nomor", "judul"],
      "children": [
        {
          "table": "laporan_isi",
          "schema": "public",
          "columns": ["id", "laporan_id", "isi", "apa", "mengapa"],
          "relationship": {
            "type": "one_to_many",
            "variant": "object",
            "foreign_key": {"parent": "id", "child": "laporan_id"}
          }
        }
      ]
    },
    "plugins": ["LaporanDenormalize"],
    "enable_logical_replication": true
  },
  "plugin_code": "class LaporanDenormalize(Plugin):\n    name = \"LaporanDenormalize\"\n    ...",
  "validation": {
    "is_valid": true,
    "warnings": ["Large table (4.4M rows) — batch migration recommended"]
  }
}
```

**Error (400):**
```json
{
  "error": "Invalid schema",
  "details": "Missing foreign key relationship for laporan_isi"
}
```

---

## Implementation Details

### Service: `pg_introspector.py`

PostgreSQL schema discovery service.

**Key Methods:**

```python
class PGIntrospector:
    """Discover PostgreSQL schema metadata."""

    def __init__(self, connection_params: dict):
        self.conn = psycopg2.connect(**connection_params)

    def test_connection(self) -> dict:
        """Test connection and return server info."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.execute("""
            SELECT sum(pg_database_size(datname))
            FROM pg_database;
        """)
        db_size = cursor.fetchone()[0]

        cursor.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'public';
        """)
        table_count = cursor.fetchone()[0]

        cursor.close()

        return {
            "server_version": version,
            "database_size": db_size,
            "table_count": table_count
        }

    def list_tables(self, schema: str = "public") -> list[dict]:
        """List all tables with metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
              t.tablename,
              pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
              (SELECT count(*) FROM information_schema.table_constraints
               WHERE table_name = t.tablename AND constraint_type = 'PRIMARY KEY') > 0 as has_pk,
              n_live_tup as row_count
            FROM pg_tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.tablename
            WHERE t.schemaname = %s
            ORDER BY t.tablename;
        """, (schema,))

        tables = []
        for row in cursor.fetchall():
            tablename, size, has_pk, row_count = row
            columns = self.get_table_columns(tablename, schema)
            tables.append({
                "name": tablename,
                "schema": schema,
                "size": size,
                "has_primary_key": has_pk,
                "row_count": row_count or 0,
                "columns": columns
            })

        cursor.close()
        return tables

    def get_table_columns(self, table: str, schema: str = "public") -> list[dict]:
        """Get table columns with metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
              c.column_name,
              c.data_type,
              c.is_nullable = 'YES' as nullable,
              (tc.constraint_type = 'PRIMARY KEY') as is_pk,
              ccu.table_name is not null as is_fk
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu
              ON c.table_name = kcu.table_name
              AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
              AND tc.constraint_type = 'PRIMARY KEY'
            LEFT JOIN information_schema.constraint_column_usage ccu
              ON kcu.constraint_name = ccu.constraint_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position;
        """, (schema, table))

        columns = []
        for row in cursor.fetchall():
            col_name, col_type, nullable, is_pk, is_fk = row
            columns.append({
                "name": col_name,
                "type": col_type,
                "nullable": nullable,
                "is_pk": is_pk,
                "is_fk": is_fk
            })

        cursor.close()
        return columns

    def detect_relationships(self, table: str, schema: str = "public") -> list[dict]:
        """Detect FK relationships + child tables."""
        cursor = self.conn.cursor()

        # Explicit FK constraints
        cursor.execute("""
            SELECT
              rc.constraint_name,
              kcu1.column_name as fk_column,
              ccu.table_name as referenced_table,
              ccu.column_name as referenced_column
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu1
              ON rc.constraint_name = kcu1.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON rc.unique_constraint_name = ccu.constraint_name
            WHERE kcu1.table_name = %s AND kcu1.table_schema = %s;
        """, (table, schema))

        relationships = []
        for row in cursor.fetchall():
            constraint_name, fk_col, ref_table, ref_col = row
            relationships.append({
                "type": "explicit",
                "fk_column": fk_col,
                "referenced_table": ref_table,
                "referenced_column": ref_col
            })

        # Heuristic: columns ending with _id
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND table_schema = %s
            AND column_name LIKE '%%_id'
            AND column_name NOT IN (SELECT fk_column FROM (
              SELECT kcu1.column_name as fk_column
              FROM information_schema.referential_constraints rc
              JOIN information_schema.key_column_usage kcu1
                ON rc.constraint_name = kcu1.constraint_name
            ) t);
        """, (table, schema))

        for row in cursor.fetchall():
            col_name = row[0]
            relationships.append({
                "type": "heuristic",
                "fk_column": col_name,
                "hint": "Column name ends with _id but no constraint"
            })

        cursor.close()
        return relationships

    def detect_children(self, table: str, pk_column: str = "id", schema: str = "public") -> list[dict]:
        """Find child tables referencing this table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
              kcu2.table_name as child_table,
              kcu1.column_name as parent_column,
              kcu2.column_name as child_column
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu1
              ON rc.constraint_name = kcu1.constraint_name
            JOIN information_schema.key_column_usage kcu2
              ON rc.unique_constraint_name = kcu2.constraint_name
            WHERE kcu1.table_name = %s
            AND kcu1.table_schema = %s
            AND kcu1.column_name = %s;
        """, (table, schema, pk_column))

        children = []
        for row in cursor.fetchall():
            child_table, parent_col, child_col = row
            child_schema = self.get_table_schema(child_table, schema)
            children.append({
                "table": child_table,
                "foreign_key": {"parent": parent_col, "child": child_col},
                "columns": [c["name"] for c in child_schema["columns"]],
                "row_count": child_schema["row_count"]
            })

        cursor.close()
        return children
```

---

### Service: `schema_generator.py`

Auto-generate PGSync JSON schema from config.

```python
class SchemaGenerator:
    """Generate PGSync schema JSON from configuration."""

    def generate(self, config: Configuration) -> dict:
        """Generate complete PGSync schema."""
        schema_config = json.loads(config.schema_config)

        # Build root node
        root_node = {
            "table": schema_config["main_table"],
            "schema": "public",
            "columns": schema_config.get("main_columns", []),
            "children": []
        }

        # Build child nodes recursively
        for child in schema_config.get("children", []):
            child_node = self._build_child_node(child)
            root_node["children"].append(child_node)

        # Wrap in PGSync format
        return {
            "database": config.source_pg_database,
            "index": schema_config["main_table"],
            "nodes": root_node,
            "plugins": [self._plugin_name(config.name)],
            "enable_logical_replication": True,
            "enable_dynamic_settings": True,
            "database_url": f"postgresql://{config.source_pg_user}:***@{config.source_pg_host}:{config.source_pg_port}/{config.source_pg_database}",
            "opensearch": {
                "host": json.loads(config.target_config).get("host"),
                "port": json.loads(config.target_config).get("port"),
                "user": "${ELASTICSEARCH_USER}",
                "password": "${ELASTICSEARCH_PASSWORD}",
                "use_ssl": json.loads(config.target_config).get("use_ssl", True),
                "verify_certs": json.loads(config.target_config).get("verify_certs", False)
            }
        }

    def _build_child_node(self, child_config: dict) -> dict:
        """Recursively build child node."""
        node = {
            "table": child_config["table"],
            "schema": "public",
            "columns": child_config.get("fields", []),
            "relationship": {
                "type": child_config.get("relationship", {}).get("type", "one_to_many"),
                "variant": child_config.get("relationship", {}).get("variant", "object"),
                "foreign_key": child_config.get("relationship", {}).get("foreign_key", {})
            }
        }

        # Nested children
        if "children" in child_config:
            node["children"] = [self._build_child_node(c) for c in child_config["children"]]

        return node

    def validate(self, schema: dict) -> dict:
        """Validate generated schema."""
        warnings = []
        errors = []

        # TODO: Implement validation
        # - Check all tables exist
        # - Check all columns exist
        # - Check FK relationships valid
        # - Check no circular dependencies

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _plugin_name(self, config_name: str) -> str:
        """Generate plugin class name from config name."""
        return ''.join(word.capitalize() for word in config_name.split('-')) + "Denormalize"
```

---

### Service: `plugin_generator.py`

Auto-generate PGSync plugin Python code.

```python
from jinja2 import Environment, FileSystemLoader

class PluginGenerator:
    """Generate PGSync plugin code from configuration."""

    def __init__(self):
        self.env = Environment(loader=FileSystemLoader("backend/templates"))

    def generate(self, config: Configuration) -> str:
        """Generate plugin code."""
        schema_config = json.loads(config.schema_config)
        fk_mappings = schema_config.get("fk_mappings", {})

        template = self.env.get_template("plugin_template.jinja2")

        code = template.render(
            class_name=self._plugin_name(config.name),
            lookup_tables=self._extract_lookup_tables(fk_mappings),
            fk_map=fk_mappings,
            child_fetchers=self._generate_child_fetchers(
                schema_config.get("children", [])
            )
        )

        return code

    def _extract_lookup_tables(self, fk_mappings: dict) -> list:
        """Extract unique lookup tables."""
        tables = {}
        for fk_col, mapping in fk_mappings.items():
            table = mapping["table"]
            if table not in tables:
                tables[table] = {
                    "table": table,
                    "id_col": mapping.get("id_col", "id"),
                    "name_col": mapping.get("name_col", "nama")
                }
        return list(tables.values())

    def _generate_child_fetchers(self, children: list) -> list:
        """Generate fetch methods for child tables."""
        fetchers = []
        for child in children:
            fetchers.append({
                "method_name": f"_fetch_{child['table']}",
                "table": child["table"],
                "fields": child.get("fields", []),
                "foreign_key": child.get("relationship", {}).get("foreign_key", {})
            })
        return fetchers

    def _plugin_name(self, config_name: str) -> str:
        """Generate plugin class name."""
        return ''.join(word.capitalize() for word in config_name.split('-')) + "Denormalize"
```

---

## Security Considerations

### 1. Password Encryption

**Storage:** Encrypt passwords with Fernet (symmetric encryption).

```python
from cryptography.fernet import Fernet
import os

class CryptoService:
    """Encrypt/decrypt sensitive data."""

    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
        self.cipher = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext to ciphertext."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext to plaintext."""
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

**Setup:**
```bash
# Generate key once (in CI/CD or secure setup):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# .env
ENCRYPTION_KEY=your-base64-encoded-key-here
```

### 2. API Authentication (Phase 2)

MVP: No auth (internal network only)
Phase 2: JWT bearer tokens

### 3. SQL Injection Prevention

Always use parameterized queries:

```python
# ✅ Safe
cursor.execute("SELECT * FROM tables WHERE name = %s", (table_name,))

# ❌ Unsafe — Never!
cursor.execute(f"SELECT * FROM tables WHERE name = '{table_name}'")
```

### 4. Secrets Never Logged

```python
# ✅ Safe — no sensitive data
logger.info(f"Connected to {host}:{port} as {user}")

# ❌ Unsafe — password exposed
logger.info(f"Connection string: postgresql://{user}:{password}@{host}/{db}")
```

---

## Testing Strategy

### Unit Tests (`tests/unit/`)

```python
# test_pg_introspector.py
import pytest
from backend.services import PGIntrospector

@pytest.fixture
def introspector():
    return PGIntrospector({
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "postgres",
        "password": "postgres"
    })

def test_test_connection(introspector):
    result = introspector.test_connection()
    assert "server_version" in result
    assert result["table_count"] > 0

def test_list_tables(introspector):
    tables = introspector.list_tables()
    assert len(tables) > 0
    assert any(t["name"] == "laporan" for t in tables)

def test_get_table_columns(introspector):
    columns = introspector.get_table_columns("laporan")
    assert len(columns) > 0
    assert any(c["name"] == "id" for c in columns)
```

```python
# test_schema_generator.py
from backend.models import Configuration
from backend.services import SchemaGenerator
import json

def test_generate_simple_schema():
    config = Configuration(
        name="test",
        source_pg_database="test_db",
        schema_config=json.dumps({
            "main_table": "laporan",
            "main_columns": ["id", "nomor", "judul"],
            "children": []
        })
    )

    generator = SchemaGenerator()
    schema = generator.generate(config)

    assert schema["database"] == "test_db"
    assert schema["nodes"]["table"] == "laporan"
    assert len(schema["nodes"]["children"]) == 0

def test_generate_schema_with_children():
    config = Configuration(
        name="test",
        source_pg_database="test_db",
        schema_config=json.dumps({
            "main_table": "laporan",
            "children": [
                {
                    "table": "laporan_isi",
                    "fields": ["isi", "apa"],
                    "relationship": {
                        "type": "one_to_many",
                        "variant": "object",
                        "foreign_key": {"parent": "id", "child": "laporan_id"}
                    }
                }
            ]
        })
    )

    generator = SchemaGenerator()
    schema = generator.generate(config)

    assert len(schema["nodes"]["children"]) == 1
    assert schema["nodes"]["children"][0]["table"] == "laporan_isi"
```

### Integration Tests (`tests/integration/`)

```python
# test_config_api.py
import pytest
from robyn import Robyn
import json

@pytest.fixture
def client():
    app = Robyn(__file__)
    return app.test_client()

def test_create_config(client):
    response = client.post("/api/config/new", json={
        "name": "test-config",
        "description": "Test configuration",
        "source": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "postgres",
            "password": "postgres"
        },
        "target": {
            "type": "opensearch",
            "host": "localhost",
            "port": 9200
        },
        "schema": {
            "main_table": "laporan",
            "children": []
        }
    })

    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["name"] == "test-config"
    assert body["version"] == 1

def test_get_config(client):
    # First create
    create_resp = client.post("/api/config/new", json={...})
    config_id = json.loads(create_resp.body)["id"]

    # Then get
    get_resp = client.get(f"/api/config/{config_id}")
    assert get_resp.status_code == 200
    body = json.loads(get_resp.body)
    assert body["id"] == config_id

def test_list_configs(client):
    response = client.get("/api/config/list")
    assert response.status_code == 200
    body = json.loads(response.body)
    assert "configs" in body
    assert "total" in body
```

### Coverage Target

- Unit tests: **80%** code coverage
- Integration tests: Critical paths (CRUD, discovery, generation)
- Command: `pytest --cov=backend --cov-report=html`

---

## Development Workflow

### 1. Initial Setup

```bash
cd /Volumes/Sinise/work/qti/pgsync-production
git checkout dev

# Create workspace structure
mkdir -p pgsync-admin/{backend,frontend}
cd pgsync-admin/backend

# Init Python project
uv init --python 3.12
uv add robyn sqlalchemy psycopg2-binary cryptography jinja2
uv add --dev pytest pytest-cov black ruff mypy
```

### 2. Run Backend (Dev Mode)

```bash
cd pgsync-admin/backend
uv run python main.py

# Or with auto-reload
uv run watchfiles "python main.py" .
```

### 3. Test

```bash
# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=backend --cov-report=html

# Single test file
uv run pytest tests/unit/test_pg_introspector.py

# Specific test
uv run pytest tests/unit/test_pg_introspector.py::test_list_tables
```

### 4. Code Quality

```bash
# Format code
uv run black backend/

# Lint
uv run ruff check backend/ --fix

# Type checking
uv run mypy backend/
```

---

## Deliverables Checklist

- [ ] Project structure created (`pgsync-admin/backend/`)
- [ ] SQLite schema implemented + migrations
- [ ] Config CRUD API endpoints (5/5)
- [ ] PG introspection service
- [ ] Schema generation service
- [ ] Plugin code generation
- [ ] Password encryption (Fernet)
- [ ] OpenAPI/Swagger documentation
- [ ] Unit tests (80% coverage)
- [ ] Integration tests (critical paths)
- [ ] README.md for backend setup
- [ ] Commit + PR to `dev` branch

---

## Next Phase (1b)

After Phase 1a:
1. ✅ Config CRUD API working
2. ✅ PG schema introspection complete
3. ✅ Auto-generation of PGSync JSON + plugin code
4. ✅ 80% test coverage

Phase 1b will add:
- Batch migration orchestrator (Docker)
- CDC daemon manager (subprocess)
- ClickHouse integration (logs + metrics)
- Background task scheduler

---

**Last Updated:** 2026-06-19
**Branch:** `dev`
**Assignee:** Development Team
