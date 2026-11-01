"""Data lineage discovery and tracking service."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.db import db
from backend.models import Configuration, DataLineage

logger = logging.getLogger(__name__)


class LineageTracker:
    """Discover and track data lineage for CDC pipelines."""

    def discover_lineage(self, config_id: int) -> Optional[Dict[str, Any]]:
        """Discover lineage from a configuration."""
        try:
            with db.get_session() as session:
                config = session.query(Configuration).filter_by(id=config_id).first()
                if not config:
                    return None

                # Parse source and target from config
                source_info = self._parse_source(config)
                target_info = self._parse_target(config)

                # Extract transformations
                transforms = self._extract_transforms(config)

                # Detect dependencies
                dependencies = self._detect_dependencies(config)

                # Store or update lineage
                lineage = session.query(DataLineage).filter_by(config_id=config_id).first()
                if lineage:
                    lineage.source_type = source_info["type"]
                    lineage.source_name = source_info["name"]
                    lineage.source_columns = source_info["columns"]
                    lineage.target_type = target_info["type"]
                    lineage.target_name = target_info["name"]
                    lineage.target_fields = target_info["fields"]
                    lineage.transform_rules = transforms
                    lineage.dependencies = dependencies
                    lineage.last_updated = datetime.utcnow()
                else:
                    lineage = DataLineage(
                        config_id=config_id,
                        source_type=source_info["type"],
                        source_name=source_info["name"],
                        source_columns=source_info["columns"],
                        target_type=target_info["type"],
                        target_name=target_info["name"],
                        target_fields=target_info["fields"],
                        transform_rules=transforms,
                        dependencies=dependencies,
                    )
                    session.add(lineage)

                session.commit()
                session.refresh(lineage)
                return lineage.to_dict()

        except Exception as e:
            logger.error(f"Failed to discover lineage for config {config_id}: {e}")
            return None

    def _parse_source(self, config: Configuration) -> Dict[str, Any]:
        """Extract source info from config."""
        source = config.source_config or {}
        tables = source.get("tables", [])

        db_name = source.get("database", "unknown")
        schema = source.get("schema", "public")

        if tables:
            table_name = tables[0] if isinstance(tables, list) else tables
            source_name = f"{db_name}.{schema}.{table_name}"
        else:
            source_name = f"{db_name}.{schema}"

        # Extract columns
        columns = []
        if isinstance(tables, list) and len(tables) > 0:
            table_obj = tables[0]
            if isinstance(table_obj, dict):
                columns = table_obj.get("columns", [])

        return {
            "type": "postgresql",
            "name": source_name,
            "columns": columns if isinstance(columns, list) else [],
        }

    def _parse_target(self, config: Configuration) -> Dict[str, Any]:
        """Extract target info from config."""
        target = config.target_config or {}
        index_name = target.get("index", config.name.lower().replace(" ", "_"))

        # Extract field mappings
        fields = []
        if "mapping" in target:
            mapping = target["mapping"]
            if isinstance(mapping, dict):
                fields = list(mapping.keys())

        target_type = config.target_config.get("type", "elasticsearch")

        return {
            "type": target_type,
            "name": index_name,
            "fields": fields,
        }

    def _extract_transforms(self, config: Configuration) -> List[Dict[str, Any]]:
        """Extract transformation rules from config."""
        transforms = []
        target = config.target_config or {}

        # Check for field transformations
        if "transform" in target:
            transform_rules = target["transform"]
            if isinstance(transform_rules, dict):
                for field, rule in transform_rules.items():
                    transforms.append({
                        "field": field,
                        "type": "transform",
                        "rule": rule,
                    })

        # Check for plugins
        if "plugins" in target:
            plugins = target["plugins"]
            if isinstance(plugins, list):
                for plugin in plugins:
                    transforms.append({
                        "type": "plugin",
                        "name": plugin,
                    })

        return transforms

    def _detect_dependencies(self, config: Configuration) -> List[str]:
        """Detect upstream table dependencies."""
        dependencies = []
        source = config.source_config or {}

        # Check for foreign key relationships (if available)
        tables = source.get("tables", [])
        if isinstance(tables, list):
            for table in tables:
                if isinstance(table, dict):
                    fkeys = table.get("foreign_keys", [])
                    for fk in fkeys:
                        if isinstance(fk, dict):
                            ref_table = fk.get("referenced_table")
                            if ref_table:
                                dependencies.append(ref_table)

        return dependencies

    def get_lineage_graph(self) -> Dict[str, Any]:
        """Get complete lineage graph for visualization."""
        try:
            with db.get_session() as session:
                lineages = session.query(DataLineage).all()
                configs = session.query(Configuration).all()

                nodes = []
                edges = []

                # Add source nodes
                sources = set()
                for lineage in lineages:
                    if lineage.source_name not in sources:
                        sources.add(lineage.source_name)
                        nodes.append({
                            "id": f"source_{lineage.source_name}",
                            "label": lineage.source_name,
                            "type": "source",
                            "nodeType": lineage.source_type,
                        })

                # Add config nodes
                for config in configs:
                    nodes.append({
                        "id": f"config_{config.id}",
                        "label": config.name,
                        "type": "pipeline",
                        "status": "active" if config.is_active else "inactive",
                    })

                # Add target nodes
                targets = set()
                for lineage in lineages:
                    if lineage.target_name not in targets:
                        targets.add(lineage.target_name)
                        nodes.append({
                            "id": f"target_{lineage.target_name}",
                            "label": lineage.target_name,
                            "type": "target",
                            "nodeType": lineage.target_type,
                        })

                # Add edges
                for lineage in lineages:
                    # Source -> Config
                    edges.append({
                        "source": f"source_{lineage.source_name}",
                        "target": f"config_{lineage.config_id}",
                        "label": "reads",
                    })

                    # Config -> Target
                    edges.append({
                        "source": f"config_{lineage.config_id}",
                        "target": f"target_{lineage.target_name}",
                        "label": "writes",
                    })

                    # Dependencies
                    for dep in lineage.dependencies:
                        edges.append({
                            "source": f"source_{dep}",
                            "target": f"source_{lineage.source_name}",
                            "label": "depends on",
                            "style": "dashed",
                        })

                return {
                    "nodes": nodes,
                    "edges": edges,
                }

        except Exception as e:
            logger.error(f"Failed to get lineage graph: {e}")
            return {"nodes": [], "edges": []}


lineage_tracker = LineageTracker()
