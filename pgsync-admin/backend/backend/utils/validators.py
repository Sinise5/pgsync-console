"""Input validation utilities."""

import re
from typing import Dict, Any


def validate_db_connection_params(params: Dict[str, Any]) -> Dict[str, str]:
    """Validate PostgreSQL connection parameters.

    Args:
        params: Connection parameters dict

    Returns:
        Validated params

    Raises:
        ValueError: If validation fails
    """
    required = ["host", "port", "database", "user", "password"]
    for field in required:
        if field not in params:
            raise ValueError(f"Missing required field: {field}")

    # Validate host
    host = params.get("host", "").strip()
    if not host or len(host) > 256:
        raise ValueError("Invalid host")

    # Validate port
    try:
        port = int(params.get("port", 5432))
        if port <= 0 or port >= 65536:
            raise ValueError("Port must be between 1 and 65535")
    except (TypeError, ValueError):
        raise ValueError("Port must be a valid integer")

    # Validate database
    db = params.get("database", "").strip()
    if not db or len(db) > 128:
        raise ValueError("Invalid database name")

    # Validate user
    user = params.get("user", "").strip()
    if not user or len(user) > 128:
        raise ValueError("Invalid user")

    # Validate password
    password = params.get("password", "")
    if len(password) > 512:
        raise ValueError("Password too long")

    return {
        "host": host,
        "port": port,
        "database": db,
        "user": user,
        "password": password,
    }


def validate_config_name(name: str) -> str:
    """Validate configuration name.

    Args:
        name: Config name

    Returns:
        Validated name

    Raises:
        ValueError: If validation fails
    """
    if not name or len(name) > 128:
        raise ValueError("Config name must be between 1 and 128 characters")

    # Allow alphanumeric, hyphen, underscore
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError("Config name can only contain alphanumeric characters, hyphens, and underscores")

    return name
