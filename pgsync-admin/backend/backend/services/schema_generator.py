"""PGSync schema JSON generator service."""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """Generate PGSync schema JSON from configuration."""

    def generate(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete PGSync schema from config.

        Args:
            config_dict: Configuration dictionary with keys:
                - source_pg_*: source database connection details
                - source_type: postgres, mysql, or mariadb
                - target_type: Target storage type
                - target_config: Target storage config (JSON string)
                - schema_config: Schema configuration (JSON string)

        Returns:
            PGSync schema dictionary
        """
        schema_config = json.loads(config_dict["schema_config"])
        # Accept both the editor's {main_table, main_columns, children} format and
        # the PGSync-like {nodes: {table, columns, children}} format stored by older configs.
        root_config = schema_config.get("nodes") or schema_config
        main_table = schema_config.get("main_table") or root_config.get("table")
        if not main_table:
            raise ValueError("Schema configuration requires a main table")

        root_node = self._build_root_node(schema_config)
        if config_dict.get("source_type") in {"mysql", "mariadb"}:
            def set_mysql_schema(node: Dict[str, Any]) -> None:
                node["schema"] = config_dict["source_pg_database"]
                for child in node.get("children", []):
                    set_mysql_schema(child)

            set_mysql_schema(root_node)

        # Generate plugin name
        plugin_name = self._plugin_name(config_dict.get("name", "custom"))

        # Build complete schema
        pgsync_schema = {
            "database": config_dict["source_pg_database"],
            "index": schema_config.get("index") or main_table,
            "nodes": root_node,
            "plugins": [plugin_name] if schema_config.get("fk_mappings") else [],
            "setting": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "standard"
                        }
                    }
                }
            }
        }

        logger.info(f"Generated PGSync schema for table: {main_table}")
        return pgsync_schema

    def _build_root_node(self, schema_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build root node with children recursively."""
        root_config = schema_config.get("nodes") or schema_config
        root = {
            "table": schema_config.get("main_table") or root_config.get("table"),
            "schema": root_config.get("schema", "public"),
            "columns": schema_config.get("main_columns", root_config.get("columns", [])),
        }

        # Add children if present
        children = schema_config.get("children", root_config.get("children", []))
        if children:
            root["children"] = [self._build_child_node(child) for child in children]

        return root

    def _build_child_node(self, child_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build child node recursively."""
        node = {
            "table": child_config["table"],
            "schema": "public",
            "columns": child_config.get("fields", child_config.get("columns", [])),
            "relationship": {
                "type": child_config.get("relationship", {}).get("type", "one_to_many"),
                "variant": child_config.get("relationship", {}).get("variant", "object"),
            }
        }

        # Add foreign key relationship
        fk = child_config.get("relationship", {}).get("foreign_key")
        if fk:
            node["relationship"]["foreign_key"] = {
                "child": [fk.get("child", "")],
                "parent": [fk.get("parent", "id")]
            }

        # Nested children
        if "children" in child_config:
            node["children"] = [self._build_child_node(c) for c in child_config["children"]]

        return node

    def validate(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated schema.

        Args:
            schema: PGSync schema dictionary

        Returns:
            Validation result with errors/warnings
        """
        errors = []
        warnings = []

        # Check required keys
        required_keys = ["database", "index", "nodes"]
        for key in required_keys:
            if key not in schema:
                errors.append(f"Missing required key: {key}")

        # Check nodes structure
        if "nodes" in schema:
            nodes = schema["nodes"]
            if "table" not in nodes:
                errors.append("nodes.table is required")
            if "columns" not in nodes:
                warnings.append("nodes.columns is empty - will sync all columns")

        # Check children relationships
        if "nodes" in schema and "children" in schema["nodes"]:
            for child in schema["nodes"]["children"]:
                if "relationship" not in child:
                    errors.append(f"Child {child.get('table')} missing relationship")
                elif "foreign_key" not in child["relationship"]:
                    errors.append(f"Child {child.get('table')} missing foreign_key")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _plugin_name(self, config_name: str) -> str:
        """Generate plugin class name from config name."""
        # Convert kebab-case to PascalCase
        words = config_name.replace("_", "-").split("-")
        return "".join(word.capitalize() for word in words) + "Denormalize"


class PluginGenerator:
    """Generate PGSync plugin Python code."""

    def generate(self, config_dict: Dict[str, Any]) -> str:
        """Generate plugin code from configuration.

        Args:
            config_dict: Configuration dictionary

        Returns:
            Python plugin code as string
        """
        schema_config = json.loads(config_dict["schema_config"])
        fk_mappings = schema_config.get("fk_mappings", {})

        if not fk_mappings:
            return ""  # No denormalization needed

        class_name = self._plugin_name(config_dict.get("name", "custom"))

        # Generate code
        code_parts = []

        # Header
        code_parts.append('"""Auto-generated PGSync denormalization plugin."""\n')
        code_parts.append("from pgsync.plugin import Plugin\n")
        code_parts.append("from typing import Dict, Any, Optional\n\n")

        # Class definition
        code_parts.append(f"class {class_name}(Plugin):\n")
        code_parts.append(f'    """{class_name} denormalization plugin."""\n\n')
        code_parts.append(f'    name = "{class_name}"\n\n')

        # Lookup cache
        code_parts.append("    def __init__(self, *args: Any, **kwargs: Any) -> None:\n")
        code_parts.append("        super().__init__(*args, **kwargs)\n")
        code_parts.append("        self._lookup_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}\n\n")

        # Transform method
        code_parts.append("    def transform(self, doc: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:\n")
        code_parts.append('        """Transform document with denormalized lookups."""\n')

        # Generate lookup calls
        for fk_col, mapping in fk_mappings.items():
            table = mapping["table"]
            id_col = mapping.get("id_col", "id")
            name_col = mapping.get("name_col", "nama")

            code_parts.append(f"\n        # Denormalize {fk_col}\n")
            code_parts.append(f"        if '{fk_col}' in doc and doc['{fk_col}']:\n")
            code_parts.append(f"            lookup = self._fetch_lookup('{table}', doc['{fk_col}'], '{id_col}', '{name_col}')\n")
            code_parts.append(f"            if lookup:\n")
            code_parts.append(f"                doc['{fk_col}'] = lookup\n")

        code_parts.append("\n        return doc\n\n")

        # Fetch lookup helper
        code_parts.append("    def _fetch_lookup(self, table: str, lookup_id: int, id_col: str, name_col: str) -> Optional[Dict[str, Any]]:\n")
        code_parts.append('        """Fetch and cache lookup data."""\n')
        code_parts.append("        if table not in self._lookup_cache:\n")
        code_parts.append("            self._lookup_cache[table] = {}\n\n")
        code_parts.append("        if lookup_id in self._lookup_cache[table]:\n")
        code_parts.append("            return self._lookup_cache[table][lookup_id]\n\n")
        code_parts.append("        # Query database\n")
        code_parts.append("        query = f\"SELECT {id_col}, {name_col} FROM {table} WHERE {id_col} = %s\"\n")
        code_parts.append("        result = self.fetchone(query, (lookup_id,))\n\n")
        code_parts.append("        if result:\n")
        code_parts.append("            lookup_data = {id_col: result[0], name_col: result[1]}\n")
        code_parts.append("            self._lookup_cache[table][lookup_id] = lookup_data\n")
        code_parts.append("            return lookup_data\n\n")
        code_parts.append("        return None\n")

        code = "".join(code_parts)
        logger.info(f"Generated plugin: {class_name}")
        return code

    def _plugin_name(self, config_name: str) -> str:
        """Generate plugin class name from config name."""
        words = config_name.replace("_", "-").split("-")
        return "".join(word.capitalize() for word in words) + "Denormalize"


# Global singleton instance
schema_generator = SchemaGenerator()
