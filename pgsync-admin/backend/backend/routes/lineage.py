"""Data lineage API routes."""

import json
import logging
from robyn import Request, Response

from backend.db import db
from backend.models import DataLineage
from backend.services.lineage_tracker import lineage_tracker

logger = logging.getLogger(__name__)


def lineage_routes(app):
    """Register lineage routes."""

    @app.get("/api/lineage/graph")
    async def get_lineage_graph(request: Request) -> Response:
        """Get complete lineage graph."""
        try:
            graph = lineage_tracker.get_lineage_graph()
            return Response(
                status_code=200,
                body=json.dumps(graph),
            )
        except Exception as e:
            logger.error(f"Failed to get lineage graph: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/lineage/:config_id")
    async def get_config_lineage(request: Request) -> Response:
        """Get lineage for a specific config."""
        try:
            config_id = int(request.path_params.get("config_id"))

            with db.get_session() as session:
                lineage = session.query(DataLineage).filter_by(config_id=config_id).first()

                if not lineage:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Lineage not found"}),
                    )

                return Response(
                    status_code=200,
                    body=json.dumps(lineage.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to get config lineage: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/lineage/:config_id/discover")
    async def discover_config_lineage(request: Request) -> Response:
        """Discover and store lineage for a config."""
        try:
            config_id = int(request.path_params.get("config_id"))

            lineage = lineage_tracker.discover_lineage(config_id)

            if not lineage:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Configuration not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps(lineage),
            )
        except Exception as e:
            logger.error(f"Failed to discover lineage: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/lineage/discover-all")
    async def discover_all_lineage(request: Request) -> Response:
        """Discover lineage for all configurations."""
        try:
            from backend.models import Configuration

            with db.get_session() as session:
                configs = session.query(Configuration).all()

                results = []
                for config in configs:
                    lineage = lineage_tracker.discover_lineage(config.id)
                    if lineage:
                        results.append(lineage)

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "discovered": len(results),
                        "lineages": results,
                    }),
                )
        except Exception as e:
            logger.error(f"Failed to discover all lineage: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/lineage")
    async def list_lineages(request: Request) -> Response:
        """List all lineage records."""
        try:
            with db.get_session() as session:
                lineages = session.query(DataLineage).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"lineages": [l.to_dict() for l in lineages]}),
                )
        except Exception as e:
            logger.error(f"Failed to list lineages: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))
