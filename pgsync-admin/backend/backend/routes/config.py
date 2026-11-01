"""Configuration management API routes."""

import json
import logging
from typing import Dict, Any
from decimal import Decimal
from robyn import Request, Response
from sqlalchemy.exc import IntegrityError

from backend.db import db
from backend.models import Configuration, ConfigurationHistory
from backend.utils import crypto_service, validate_db_connection_params, validate_config_name
from backend.services import SchemaGenerator, PluginGenerator
from backend.routes.discovery import DecimalEncoder

logger = logging.getLogger(__name__)

PIPELINE_TARGETS = {
    "pg_search": ({"postgres", "mysql", "mariadb"}, {"opensearch", "elasticsearch"}),
    "pg_clickhouse": ({"postgres"}, {"clickhouse"}),
    "pg_replication": ({"postgres"}, {"postgres"}),
    "pg_copy": ({"postgres"}, {"postgres"}),
}


def validate_pipeline(source_type: str, pipeline_type: str, target_type: str) -> None:
    """Reject source and destination combinations without an execution backend."""
    allowed = PIPELINE_TARGETS.get(pipeline_type)
    if not allowed:
        raise ValueError("Unsupported pipeline type")
    if source_type not in allowed[0] or target_type not in allowed[1]:
        raise ValueError("Source and destination do not match the selected pipeline")


def validate_target(pipeline_type: str, target: Dict[str, Any]) -> None:
    """Validate destination fields required by the selected runner."""
    if not str(target.get("host") or "").strip():
        raise ValueError("Destination host is required")
    default_ports = {"pg_search": 9200, "pg_clickhouse": 8123, "pg_replication": 5432, "pg_copy": 5432}
    try:
        port = int(target.get("port") or default_ports[pipeline_type])
    except (TypeError, ValueError) as exc:
        raise ValueError("Destination port must be a valid integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Destination port must be between 1 and 65535")
    target["port"] = port
    if pipeline_type != "pg_search" and not str(target.get("database") or "").strip():
        raise ValueError("Destination database is required")
    if pipeline_type in {"pg_replication", "pg_copy"}:
        if not str(target.get("user") or "").strip() or not target.get("password"):
            raise ValueError("PostgreSQL destination username and password are required")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal to int/float."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def config_routes(app: Any) -> None:
    """Register configuration management routes."""

    @app.post("/api/config/new")
    async def create_config(request: Request) -> Response:
        """Create new configuration.

        Request body:
        {
            "name": "config-name",
            "description": "Optional description",
            "source": {
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "postgres",
                "password": "password"
            },
            "target": {
                "type": "opensearch",
                "host": "localhost",
                "port": 9200,
                "user": "admin",
                "password": "admin",
                "use_ssl": true
            },
            "schema": {
                "main_table": "users",
                "main_columns": ["id", "name", "email"],
                "children": [],
                "fk_mappings": {}
            }
        }
        """
        try:
            body = json.loads(request.body)

            # Validate name
            name = validate_config_name(body["name"])

            pipeline_type = body.get("pipeline_type", "pg_search")
            source_type = body.get("source", {}).get("type", "postgres")
            # Validate source connection params
            source = validate_db_connection_params(body["source"])
            target_data = body["target"].copy()
            target_kind = target_data.get("type", "opensearch")
            validate_pipeline(source_type, pipeline_type, target_kind)
            validate_target(pipeline_type, target_data)

            # Encrypt password
            encrypted_password = crypto_service.encrypt(source["password"])

            # Create configuration
            session = db.get_session()

            try:
                # Build target config with user/password if provided
                # Encrypt target password if provided
                if "password" in target_data and target_data["password"]:
                    target_data["password"] = crypto_service.encrypt(target_data["password"])

                # Check jika config dengan nama ini sudah ada (inactive) → reactivate
                existing = session.query(Configuration).filter(
                    Configuration.name == name
                ).first()

                if existing:
                    if not existing.is_active:
                        # Reactivate existing config
                        existing.description = body.get("description")
                        existing.source_pg_host = source["host"]
                        existing.source_pg_port = source["port"]
                        existing.source_pg_database = source["database"]
                        existing.source_pg_user = source["user"]
                        existing.source_pg_password = encrypted_password
                        existing.source_type = source_type
                        existing.pipeline_type = pipeline_type
                        existing.target_type = target_kind if target_kind in {"opensearch", "elasticsearch"} else "opensearch"
                        existing.target_config = json.dumps(target_data)
                        existing.schema_config = json.dumps(body.get("schema", {}))
                        existing.is_active = True
                        existing.version = 1
                        session.commit()
                        session.refresh(existing)

                        logger.info(f"Reactivated configuration: {name} (id={existing.id})")

                        return Response(
                            status_code=201,
                            headers={"Content-Type": "application/json"},
                            description=json.dumps({
                                "id": existing.id,
                                "name": existing.name,
                                "version": existing.version,
                                "created_at": existing.created_at.isoformat(),
                                "message": "Configuration reactivated"
                            })
                        )
                    else:
                        # Already active → error
                        session.close()
                        return Response(
                            status_code=409,
                            headers={"Content-Type": "application/json"},
                            description=json.dumps({"error": f"Configuration name '{name}' already exists. Please choose a different name."})
                        )

                # Create new config
                config = Configuration(
                    name=name,
                    description=body.get("description"),
                    source_pg_host=source["host"],
                    source_pg_port=source["port"],
                    source_pg_database=source["database"],
                    source_pg_user=source["user"],
                    source_pg_password=encrypted_password,
                    source_type=source_type,
                    pipeline_type=pipeline_type,
                    target_type=target_kind if target_kind in {"opensearch", "elasticsearch"} else "opensearch",
                    target_config=json.dumps(target_data),
                    schema_config=json.dumps(body.get("schema", {})),
                    version=1,
                )

                session.add(config)
                session.commit()
                session.refresh(config)

                # Create history entry
                history = ConfigurationHistory(
                    config_id=config.id,
                    version=1,
                    schema_config=config.schema_config,
                    change_description="Initial configuration",
                )
                session.add(history)
                session.commit()

                logger.info(f"Created configuration: {name} (id={config.id})")

                return Response(
                    status_code=201,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "id": config.id,
                        "name": config.name,
                        "version": config.version,
                        "created_at": config.created_at.isoformat(),
                    })
                )
            except IntegrityError as e:
                session.rollback()
                error_msg = str(e)
                if "UNIQUE constraint failed: configurations.name" in error_msg or "unique" in error_msg.lower():
                    msg = f"Configuration name '{name}' already exists. Please choose a different name."
                else:
                    msg = f"Database constraint error: {error_msg}"
                logger.warning(f"IntegrityError creating config: {msg}")
                return Response(
                    status_code=409,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": msg})
                )
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )
        except Exception as e:
            logger.error(f"Failed to create config: {type(e).__name__}: {e}", exc_info=True)
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

    @app.get("/api/config/list")
    async def list_configs(request: Request) -> Response:
        """List all configurations."""
        try:
            session = db.get_session()

            try:
                configs = session.query(Configuration).filter(
                    Configuration.is_active == True
                ).order_by(Configuration.created_at.desc()).all()

                result = {
                    "total": len(configs),
                    "configs": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "description": c.description,
                            "source_database": c.source_pg_database,
                            "target_type": json.loads(c.target_config).get("type", c.target_type),
                            "pipeline_type": c.pipeline_type,
                            "source_type": c.source_type,
                            "is_active": c.is_active,
                            "version": c.version,
                            "created_at": c.created_at.isoformat(),
                            "updated_at": c.updated_at.isoformat(),
                        }
                        for c in configs
                    ]
                }

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps(result)
                )
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to list configs: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Internal server error"})
            )

    @app.get("/api/config/:config_id")
    async def get_config(request: Request) -> Response:
        """Get configuration by ID."""
        try:
            config_id = int(request.path_params["config_id"])
            session = db.get_session()

            try:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id
                ).first()

                if not config:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"error": "Configuration not found"})
                    )

                target_data = json.loads(config.target_config) if config.target_config else {}
                if target_data.get("password"):
                    target_data["password"] = "***"

                # Decrypt password for display (masked)
                result = {
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "pipeline_type": config.pipeline_type,
                    "source": {
                        "type": config.source_type,
                        "host": config.source_pg_host,
                        "port": config.source_pg_port,
                        "database": config.source_pg_database,
                        "user": config.source_pg_user,
                        "password": "***"  # Masked
                    },
                    "target": target_data,
                    "schema": json.loads(config.schema_config),
                    "version": config.version,
                    "created_at": config.created_at.isoformat(),
                    "updated_at": config.updated_at.isoformat(),
                    "is_active": config.is_active,
                }

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps(result)
                )
            finally:
                session.close()

        except ValueError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid config_id"})
            )
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Internal server error"})
            )

    @app.post("/api/config/:config_id/generate")
    async def generate_schema(request: Request) -> Response:
        """Generate PGSync schema JSON + plugin code."""
        try:
            config_id = int(request.path_params["config_id"])
            session = db.get_session()

            try:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id
                ).first()

                if not config:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"error": "Configuration not found"})
                    )

                # Prepare config dict for generators
                config_dict = {
                    "name": config.name,
                    "source_pg_database": config.source_pg_database,
                    "source_type": config.source_type,
                    "target_config": config.target_config,
                    "schema_config": config.schema_config,
                }

                # Generate schema
                if config.pipeline_type in {"pg_replication", "pg_copy"}:
                    pgsync_schema = json.loads(config.schema_config or "{}")
                    validation = {"is_valid": bool(pgsync_schema), "errors": [], "warnings": []}
                    plugin_code = ""
                else:
                    schema_gen = SchemaGenerator()
                    pgsync_schema = schema_gen.generate(config_dict)
                    validation = schema_gen.validate(pgsync_schema)
                    plugin_code = PluginGenerator().generate(config_dict)

                # Update configuration
                config.pgsync_schema_json = json.dumps(pgsync_schema, indent=2)
                config.plugin_code = plugin_code
                session.commit()

                logger.info(f"Generated schema for config: {config.name}")

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "pgsync_schema": pgsync_schema,
                        "plugin_code": plugin_code,
                        "validation": validation,
                    })
                )
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

        except ValueError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid config_id"})
            )
        except Exception as e:
            logger.error(f"Failed to generate schema: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

    @app.put("/api/config/:config_id")
    async def update_config(request: Request) -> Response:
        """Update configuration (partial update support)."""
        try:
            config_id = int(request.path_params["config_id"])
            body = json.loads(request.body)
            session = db.get_session()

            try:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id
                ).first()

                if not config:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"error": "Configuration not found"})
                    )

                # Track if schema changed for version increment
                schema_changed = False

                # Update source if provided
                if "source" in body:
                    src = body["source"]
                    if "host" in src:
                        config.source_pg_host = src["host"]
                    if "port" in src:
                        config.source_pg_port = src["port"]
                    if "database" in src:
                        config.source_pg_database = src["database"]
                    if "user" in src:
                        config.source_pg_user = src["user"]
                    # Only update password if provided and not empty
                    if "password" in src and src["password"] and src["password"] != "***":
                        config.source_pg_password = crypto_service.encrypt(src["password"])
                    if "type" in src:
                        config.source_type = src["type"]

                # Update target if provided
                if "target" in body:
                    tgt = dict(body["target"])
                    current_target = json.loads(config.target_config) if config.target_config else {}

                    # Encrypt password if provided and not masked
                    if "password" in tgt and tgt["password"] and tgt["password"] != "***":
                        tgt["password"] = crypto_service.encrypt(tgt["password"])
                    elif "password" in tgt:
                        # A blank or masked value means keep the existing credential.
                        tgt.pop("password")

                    # Merge with existing target config
                    current_target.update(tgt)
                    config.target_config = json.dumps(current_target)
                    if "type" in tgt:
                        config.target_type = tgt["type"] if tgt["type"] in {"opensearch", "elasticsearch"} else "opensearch"

                if "pipeline_type" in body:
                    if body["pipeline_type"] != config.pipeline_type:
                        return Response(
                            status_code=400,
                            headers={"Content-Type": "application/json"},
                            description=json.dumps({"error": "Pipeline type cannot be changed after creation"}),
                        )
                source_type = body.get("source", {}).get("type", config.source_type)
                target = json.loads(config.target_config) if config.target_config else {}
                validate_pipeline(source_type, config.pipeline_type, target.get("type", config.target_type))
                validate_target(config.pipeline_type, target)

                # Update schema_config if provided
                if "schema_config" in body:
                    new_schema = body["schema_config"]
                    if isinstance(new_schema, str):
                        config.schema_config = new_schema
                    else:
                        config.schema_config = json.dumps(new_schema)
                    schema_changed = True

                # Update other optional fields
                if "name" in body:
                    config.name = validate_config_name(body["name"])
                if "description" in body:
                    config.description = body["description"]
                if "is_active" in body:
                    config.is_active = body["is_active"]

                # Increment version if schema changed
                if schema_changed:
                    config.version += 1

                    # Create history entry
                    history = ConfigurationHistory(
                        config_id=config.id,
                        version=config.version,
                        schema_config=config.schema_config,
                        change_description=body.get("change_description", "Schema updated via API"),
                    )
                    session.add(history)

                session.commit()
                session.refresh(config)

                logger.info(f"Updated configuration: {config.name} (id={config.id}, version={config.version})")

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({
                        "id": config.id,
                        "name": config.name,
                        "version": config.version,
                        "message": "Configuration updated successfully"
                    }, cls=DecimalEncoder)
                )
            finally:
                session.close()

        except ValueError as e:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

    @app.delete("/api/config/:config_id")
    async def delete_config(request: Request) -> Response:
        """Delete (deactivate) configuration."""
        try:
            config_id = int(request.path_params["config_id"])
            session = db.get_session()

            try:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id
                ).first()

                if not config:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"error": "Configuration not found"})
                    )

                config.is_active = False
                session.commit()

                logger.info(f"Deactivated configuration: {config.name}")

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"message": "Configuration deactivated"})
                )
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

        except ValueError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid config_id"})
            )
        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Internal server error"})
            )

    @app.post("/api/config/:config_id/discover/schema")
    async def discover_config_schema(request: Request) -> Response:
        """Discover schema using config's stored credentials (server-side decrypt)."""
        try:
            config_id = int(request.path_params["config_id"])
            session = db.get_session()

            try:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id
                ).first()

                if not config:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"error": "Configuration not found"})
                    )

                decrypted_password = crypto_service.decrypt(config.source_pg_password)

                from backend.services import MySQLIntrospector, PGIntrospector
                connection = {
                    "host": config.source_pg_host,
                    "port": config.source_pg_port,
                    "database": config.source_pg_database,
                    "user": config.source_pg_user,
                    "password": decrypted_password,
                }
                introspector = (
                    PGIntrospector(connection)
                    if config.source_type == "postgres"
                    else MySQLIntrospector(connection)
                )

                try:
                    await introspector.connect()
                    schema_data = await introspector.get_full_schema(
                        "public" if config.source_type == "postgres" else config.source_pg_database
                    )
                    return Response(
                        status_code=200,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps(schema_data, cls=DecimalEncoder)
                    )
                except Exception as e:
                    return Response(
                        status_code=503,
                        headers={"Content-Type": "application/json"},
                        description=json.dumps({"status": "failed", "error": str(e).strip()})
                    )
                finally:
                    await introspector.disconnect()
            finally:
                session.close()
        except ValueError:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid config_id"})
            )
        except Exception as e:
            logger.error(f"Failed to discover schema for config {config_id}: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )
