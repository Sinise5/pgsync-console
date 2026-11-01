"""PostgreSQL schema discovery API routes."""

import json
import logging
import httpx
import psycopg
from typing import Dict, Any
from decimal import Decimal
from robyn import Request, Response

from backend.services import MySQLIntrospector, PGIntrospector

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types."""
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)


def discovery_routes(app: Any) -> None:
    """Register schema discovery routes."""

    @app.post("/api/discover/test")
    async def test_connection(request: Request) -> Response:
        """Test PostgreSQL connection.

        Request body:
        {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "user": "postgres",
            "password": "password"
        }
        """
        try:
            body = json.loads(request.body)

            conn_params = {
                "host": body.get("host", ""),
                "port": int(body.get("port", 5432)),
                "database": body.get("database", ""),
                "user": body.get("user", ""),
                "password": body.get("password", ""),
            }

            source_type = body.get("type", "postgres")
            if source_type not in {"postgres", "mysql", "mariadb"}:
                return Response(status_code=400, description=json.dumps({"error": "Unsupported source type"}))
            if source_type != "postgres" and conn_params["port"] == 5432:
                conn_params["port"] = 3306
            introspector = PGIntrospector(conn_params) if source_type == "postgres" else MySQLIntrospector(conn_params)

            try:
                result = await introspector.test_connection()

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "status": "connected",
                        "server": {
                            "version": result["server_version"].split(",")[0],
                            "database_size": result["database_size"],
                            "table_count": result["table_count"],
                        }
                    }, cls=DecimalEncoder)
                )
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"Connection test failed: {error_msg}")
                return Response(
                    status_code=503,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "status": "failed",
                        "error": error_msg,
                    })
                )
            finally:
                await introspector.disconnect()

        except json.JSONDecodeError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid JSON body"})
            )
        except ValueError as e:
            return Response(status_code=400, description=json.dumps({"error": str(e)}))

    @app.post("/api/discover/test-target")
    async def test_target_connection(request: Request) -> Response:
        """Test a PostgreSQL, ClickHouse, or search-engine destination."""
        try:
            body = json.loads(request.body)
            target_type = body.get("type")
            host = str(body.get("host", "")).strip()
            port = int(body.get("port", 0))
            if not host or not 1 <= port <= 65535:
                raise ValueError("A valid destination host and port are required")
            user = body.get("user") or None
            password = body.get("password") or None
            if target_type == "postgres":
                database = str(body.get("database") or "").strip()
                if not database:
                    raise ValueError("Destination database is required")
                with psycopg.connect(
                    host=host, port=port, dbname=database, user=user,
                    password=password, connect_timeout=8,
                ) as connection:
                    version = connection.execute("SELECT version()").fetchone()[0]
            elif target_type == "clickhouse":
                database = str(body.get("database") or "").strip()
                if not database:
                    raise ValueError("Destination database is required")
                scheme = "https" if body.get("secure") else "http"
                response = httpx.post(
                    f"{scheme}://{host}:{port}/", params={"database": database},
                    content="SELECT version()", auth=(user, password or "") if user else None,
                    verify=body.get("verify_certs", True), timeout=8,
                )
                response.raise_for_status()
                version = response.text.strip() or "ClickHouse"
            elif target_type in {"opensearch", "elasticsearch"}:
                from opensearchpy import OpenSearch
                client = OpenSearch(
                    hosts=[{"host": host, "port": port, "scheme": body.get("scheme", "http")}],
                    http_auth=(user, password) if user else None,
                    verify_certs=bool(body.get("verify_certs", True)),
                    ssl_show_warn=False,
                    timeout=8,
                )
                info = client.info()
                version = info.get("version", {}).get("number", target_type)
            else:
                raise ValueError("Unsupported destination type")
            return Response(status_code=200, headers={"Content-Type": "application/json"},
                            description=json.dumps({"status": "connected", "server": {"version": version}}))
        except ValueError as e:
            return Response(status_code=400, headers={"Content-Type": "application/json"},
                            description=json.dumps({"error": str(e)}))
        except Exception as e:
            logger.warning("Destination connection test failed: %s", e)
            return Response(status_code=503, headers={"Content-Type": "application/json"},
                            description=json.dumps({"status": "failed", "error": str(e)}))
    @app.post("/api/discover/schema")
    async def get_schema(request: Request) -> Response:
        """Get full schema with tables, columns, PKs, and relationships."""
        try:
            body = json.loads(request.body)

            required = ["host", "port", "database", "user", "password"]
            if not all(k in body for k in required):
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing required fields"})
                )

            conn_params = {
                "host": body["host"],
                "port": body["port"],
                "database": body["database"],
                "user": body["user"],
                "password": body["password"],
            }

            schema = body.get("schema", "public")
            source_type = body.get("type", "postgres")
            if source_type not in {"postgres", "mysql", "mariadb"}:
                return Response(status_code=400, description=json.dumps({"error": "Unsupported source type"}))
            introspector = PGIntrospector(conn_params) if source_type == "postgres" else MySQLIntrospector(conn_params)

            try:
                await introspector.connect()
                schema_data = await introspector.get_full_schema(schema)

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps(schema_data, cls=DecimalEncoder)
                )
            except Exception as e:
                error_msg = str(e).strip()
                logger.error(f"Schema discovery failed: {error_msg}")
                return Response(
                    status_code=503,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"status": "failed", "error": error_msg})
                )
            finally:
                await introspector.disconnect()

        except json.JSONDecodeError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid JSON body"})
            )
        except ValueError as e:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

    @app.post("/api/discover/tables")
    async def list_tables(request: Request) -> Response:
        """List all tables in schema.

        Request body:
        {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "user": "postgres",
            "password": "password",
            "schema": "public"
        }
        """
        try:
            body = json.loads(request.body)

            conn_params = {
                "host": body.get("host", ""),
                "port": int(body.get("port", 5432)),
                "database": body.get("database", ""),
                "user": body.get("user", ""),
                "password": body.get("password", ""),
            }
            schema = body.get("schema", "public")

            source_type = body.get("type", "postgres")
            if source_type not in {"postgres", "mysql", "mariadb"}:
                return Response(status_code=400, description=json.dumps({"error": "Unsupported source type"}))
            introspector = PGIntrospector(conn_params) if source_type == "postgres" else MySQLIntrospector(conn_params)

            try:
                await introspector.connect()
                tables = await introspector.discover_tables(schema)

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "schema": schema,
                        "total": len(tables),
                        "tables": tables,
                    }, cls=DecimalEncoder)
                )
            finally:
                await introspector.disconnect()

        except json.JSONDecodeError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid JSON body"})
            )
        except Exception as e:
            error_msg = str(e).strip()
            logger.error(f"Failed to list tables: {error_msg}")
            return Response(
                status_code=503,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": error_msg})
            )

    @app.post("/api/discover/relationships")
    async def detect_relationships(request: Request) -> Response:
        """Detect relationships for a table.

        Request body:
        {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "user": "postgres",
            "password": "password",
            "table": "users",
            "schema": "public"
        }
        """
        try:
            body = json.loads(request.body)

            conn_params = {
                "host": body.get("host", ""),
                "port": int(body.get("port", 5432)),
                "database": body.get("database", ""),
                "user": body.get("user", ""),
                "password": body.get("password", ""),
            }
            table = body.get("table", "")
            schema = body.get("schema", "public")

            if not table:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "table parameter required"})
                )

            source_type = body.get("type", "postgres")
            if source_type not in {"postgres", "mysql", "mariadb"}:
                return Response(status_code=400, description=json.dumps({"error": "Unsupported source type"}))
            introspector = PGIntrospector(conn_params) if source_type == "postgres" else MySQLIntrospector(conn_params)

            try:
                await introspector.connect()

                relationships = await introspector.get_foreign_keys(table, schema)
                pk = await introspector.get_primary_key(table, schema)
                columns = await introspector.get_table_columns(table, schema)

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "table": table,
                        "primary_key": pk,
                        "columns": columns,
                        "relationships": relationships,
                    })
                )
            finally:
                await introspector.disconnect()

        except json.JSONDecodeError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid JSON body"})
            )
        except Exception as e:
            error_msg = str(e).strip()
            logger.error(f"Failed to detect relationships: {error_msg}")
            return Response(
                status_code=503,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": error_msg})
            )
