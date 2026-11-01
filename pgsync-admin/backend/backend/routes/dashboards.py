"""Dashboard management routes."""

import json
import logging
import secrets
from robyn import Request, Response

from backend.db import db
from backend.models import Dashboard, DashboardWidget

logger = logging.getLogger(__name__)


def dashboard_routes(app):
    """Register dashboard routes."""

    @app.get("/api/dashboards")
    async def list_dashboards(request: Request) -> Response:
        """List all dashboards."""
        try:
            with db.get_session() as session:
                dashboards = session.query(Dashboard).order_by(Dashboard.created_at.desc()).all()
                results = []
                for dashboard in dashboards:
                    item = dashboard.to_dict()
                    item["widgets"] = [widget.to_dict() for widget in session.query(DashboardWidget)
                        .filter_by(dashboard_id=dashboard.id).order_by(DashboardWidget.position).all()]
                    results.append(item)
                return Response(
                    status_code=200,
                    body=json.dumps({"dashboards": results}),
                )
        except Exception as e:
            logger.error(f"Failed to list dashboards: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/dashboards/:id")
    async def get_dashboard(request: Request) -> Response:
        """Get dashboard with widgets."""
        try:
            dashboard_id = int(request.path_params.get("id"))

            with db.get_session() as session:
                dashboard = session.query(Dashboard).filter_by(id=dashboard_id).first()

                if not dashboard:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Dashboard not found"}),
                    )

                widgets = session.query(DashboardWidget).filter_by(
                    dashboard_id=dashboard_id
                ).order_by(DashboardWidget.position).all()

                result = dashboard.to_dict()
                result["widgets"] = [w.to_dict() for w in widgets]

                return Response(
                    status_code=200,
                    body=json.dumps(result),
                )
        except Exception as e:
            logger.error(f"Failed to get dashboard: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/dashboards")
    async def create_dashboard(request: Request) -> Response:
        """Create new dashboard."""
        try:
            body = json.loads(request.body)
            name = body.get("name")
            description = body.get("description", "")
            is_shared = body.get("is_shared", False)

            if not isinstance(name, str) or not name.strip():
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Name is required"}),
                )

            with db.get_session() as session:
                dashboard = Dashboard(
                    name=name.strip(),
                    description=description,
                    created_by=1,  # Authentication currently has a single admin identity.
                    is_shared=is_shared,
                    share_token=secrets.token_urlsafe(16) if is_shared else None,
                )
                session.add(dashboard)
                session.commit()
                session.refresh(dashboard)

                return Response(
                    status_code=201,
                    body=json.dumps(dashboard.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to create dashboard: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.put("/api/dashboards/:id")
    async def update_dashboard(request: Request) -> Response:
        """Update dashboard."""
        try:
            dashboard_id = int(request.path_params.get("id"))
            body = json.loads(request.body)

            with db.get_session() as session:
                dashboard = session.query(Dashboard).filter_by(id=dashboard_id).first()

                if not dashboard:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Dashboard not found"}),
                    )

                if "name" in body:
                    dashboard.name = body["name"]
                if "description" in body:
                    dashboard.description = body["description"]
                if "is_shared" in body:
                    dashboard.is_shared = body["is_shared"]
                    if body["is_shared"] and not dashboard.share_token:
                        dashboard.share_token = secrets.token_urlsafe(16)
                if "layout_config" in body:
                    dashboard.layout_config = body["layout_config"]

                session.commit()
                session.refresh(dashboard)

                return Response(
                    status_code=200,
                    body=json.dumps(dashboard.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to update dashboard: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.delete("/api/dashboards/:id")
    async def delete_dashboard(request: Request) -> Response:
        """Delete dashboard and its widgets."""
        try:
            dashboard_id = int(request.path_params.get("id"))

            with db.get_session() as session:
                dashboard = session.query(Dashboard).filter_by(id=dashboard_id).first()

                if not dashboard:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Dashboard not found"}),
                    )

                # Delete widgets first
                session.query(DashboardWidget).filter_by(dashboard_id=dashboard_id).delete()

                # Delete dashboard
                session.delete(dashboard)
                session.commit()

                return Response(
                    status_code=200,
                    body=json.dumps({"message": "Dashboard deleted successfully"}),
                )
        except Exception as e:
            logger.error(f"Failed to delete dashboard: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/dashboards/:id/widgets")
    async def add_widget(request: Request) -> Response:
        """Add widget to dashboard."""
        try:
            dashboard_id = int(request.path_params.get("id"))
            body = json.loads(request.body)

            widget_type = body.get("widget_type")
            title = body.get("title")
            config = body.get("config", {})

            if not widget_type or not title:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "widget_type and title are required"}),
                )

            with db.get_session() as session:
                # Get max position
                max_position = session.query(DashboardWidget).filter_by(
                    dashboard_id=dashboard_id
                ).count()

                widget = DashboardWidget(
                    dashboard_id=dashboard_id,
                    widget_type=widget_type,
                    title=title,
                    config=config,
                    position=max_position,
                )
                session.add(widget)
                session.commit()
                session.refresh(widget)

                return Response(
                    status_code=201,
                    body=json.dumps(widget.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to add widget: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.put("/api/dashboards/:id/widgets/:widget_id")
    async def update_widget(request: Request) -> Response:
        """Update widget configuration."""
        try:
            widget_id = int(request.path_params.get("widget_id"))
            body = json.loads(request.body)

            with db.get_session() as session:
                widget = session.query(DashboardWidget).filter_by(id=widget_id).first()

                if not widget:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Widget not found"}),
                    )

                if "title" in body:
                    widget.title = body["title"]
                if "config" in body:
                    widget.config = body["config"]
                if "position" in body:
                    widget.position = body["position"]

                session.commit()
                session.refresh(widget)

                return Response(
                    status_code=200,
                    body=json.dumps(widget.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to update widget: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.delete("/api/dashboards/:id/widgets/:widget_id")
    async def delete_widget(request: Request) -> Response:
        """Delete widget from dashboard."""
        try:
            widget_id = int(request.path_params.get("widget_id"))

            with db.get_session() as session:
                widget = session.query(DashboardWidget).filter_by(id=widget_id).first()

                if not widget:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Widget not found"}),
                    )

                session.delete(widget)
                session.commit()

                return Response(
                    status_code=200,
                    body=json.dumps({"message": "Widget deleted successfully"}),
                )
        except Exception as e:
            logger.error(f"Failed to delete widget: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
