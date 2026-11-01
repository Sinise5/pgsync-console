"""Migration API routes for batch data sync."""

import json
import logging
from datetime import datetime
from typing import Optional
from robyn import Request, Response

from backend.db import db
from backend.models import Migration, MigrationStatus, Configuration
from backend.services.migration_service import migration_service

logger = logging.getLogger(__name__)


def migration_routes(app):
    """Register batch migration management routes."""

    @app.post("/api/migrations")
    async def create_migration(request: Request) -> Response:
        """Create and start a migration."""
        try:
            body = json.loads(request.body) if request.body else {}
            config_id = body.get("config_id")
            if not config_id:
                return Response(status_code=400, body=json.dumps({"error": "config_id required"}))

            migration = await migration_service.create_migration(
                config_id=config_id,
                name=body.get("name", f"Migration-{config_id}"),
                frequency=body.get("frequency", "daily"),
                date_column=body.get("date_column"),
                date_from=body.get("date_from"),
                date_to=body.get("date_to"),
                limit=body.get("limit"),
            )

            # Start migration in background
            await migration_service.start_migration(migration.id)

            return Response(
                status_code=201,
                body=json.dumps({"migration": migration.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Failed to create migration: {e}", exc_info=True)
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/migrations")
    async def list_migrations(request: Request) -> Response:
        """List all migrations with config names."""
        try:
            config_id = request.query_params.get("config_id", None)

            with db.get_session() as session:
                query = session.query(Migration, Configuration.name).join(
                    Configuration, Migration.config_id == Configuration.id
                )

                if config_id:
                    query = query.filter(Migration.config_id == int(config_id))

                results = query.order_by(Migration.created_at.desc()).all()

                migrations = []
                for migration, config_name in results:
                    migration_dict = migration.to_dict()
                    migration_dict['config_name'] = config_name
                    migrations.append(migration_dict)

            return Response(
                status_code=200,
                body=json.dumps({
                    "migrations": migrations,
                    "total": len(migrations),
                }),
            )
        except Exception as e:
            logger.error(f"Failed to list migrations: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/migrations/:migration_id")
    async def get_migration(request: Request) -> Response:
        """Get migration status and details."""
        try:
            migration_id = int(request.path_params.get("migration_id", 0))
            migration = migration_service.get_migration(migration_id)
            if not migration:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Migration not found"}),
                )
            return Response(
                status_code=200,
                body=json.dumps({"migration": migration.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Failed to get migration: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/migrations/:migration_id/cancel")
    async def cancel_migration(request: Request) -> Response:
        """Cancel a running migration."""
        try:
            migration_id = int(request.path_params.get("migration_id", 0))

            # Update status
            with db.get_session() as session:
                migration = session.query(Migration).filter_by(id=migration_id).first()
                if not migration:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Migration not found"}),
                    )
                if migration.status != MigrationStatus.RUNNING:
                    return Response(
                        status_code=400,
                        body=json.dumps({"error": "Migration is not running"}),
                    )
                migration.status = MigrationStatus.CANCELLED
                migration.completed_at = datetime.utcnow()
                session.commit()

            # Kill background task if running
            if migration_id in migration_service.running_migrations:
                migration_service.running_migrations[migration_id].cancel()
                del migration_service.running_migrations[migration_id]

            return Response(
                status_code=200,
                body=json.dumps({"message": "Migration cancelled", "id": migration_id}),
            )
        except Exception as e:
            logger.error(f"Failed to cancel migration: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/migrations/:migration_id/errors")
    async def get_migration_errors(request: Request) -> Response:
        """Get migration error details."""
        try:
            migration_id = int(request.path_params.get("migration_id", 0))
            migration = migration_service.get_migration(migration_id)
            if not migration:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Migration not found"}),
                )
            return Response(
                status_code=200,
                body=json.dumps({
                    "migration_id": migration_id,
                    "failed_docs": migration.failed_docs,
                    "error_message": migration.error_message,
                    "error_details": migration.error_details or [],
                }),
            )
        except Exception as e:
            logger.error(f"Failed to get migration errors: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.delete("/api/migrations/:migration_id")
    async def delete_migration(request: Request) -> Response:
        """Delete a migration record."""
        try:
            migration_id = int(request.path_params.get("migration_id", 0))

            with db.get_session() as session:
                migration = session.query(Migration).filter_by(id=migration_id).first()
                if not migration:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Migration not found"}),
                    )

                session.delete(migration)
                session.commit()

            return Response(
                status_code=200,
                body=json.dumps({"message": "Migration deleted", "id": migration_id}),
            )
        except Exception as e:
            logger.error(f"Failed to delete migration: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/migrations/preview-schema")
    async def preview_migration_schema(request: Request) -> Response:
        """Preview the OpenSearch index schema/mapping before migration."""
        try:
            body = json.loads(request.body) if request.body else {}
            config_id = body.get("config_id")

            if not config_id:
                return Response(status_code=400, body=json.dumps({"error": "config_id required"}))

            with db.get_session() as session:
                config = session.query(Configuration).filter_by(id=config_id).first()
                if not config:
                    return Response(status_code=404, body=json.dumps({"error": "Config not found"}))

                schema_config = json.loads(config.schema_config) if isinstance(config.schema_config, str) else config.schema_config

                if not schema_config or not schema_config.get('nodes'):
                    return Response(status_code=400, body=json.dumps({"error": "No schema configured"}))

                root = schema_config.get('nodes') or schema_config
                index_name = schema_config.get('index') or schema_config.get(
                    'main_table', root.get('table', 'index')
                ).lower()
                columns = schema_config.get('main_columns', root.get('columns', []))

                # Build preview mapping
                properties = {}
                for col in columns:
                    if col:
                        properties[col] = {"type": "keyword"}

                preview = {
                    "index_name": index_name,
                    "field_count": len(properties),
                    "mappings": {
                        "properties": properties
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    }
                }

                return Response(status_code=200, body=json.dumps(preview, default=str))
        except Exception as e:
            logger.error(f"Failed to preview schema: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))
