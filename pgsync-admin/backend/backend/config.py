"""Configuration settings loaded from environment variables."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root (../../.env relative to backend/)
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent  # /Volumes/.../pgsync-production/
dotenv_path = PROJECT_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)


class Settings(BaseModel):
    """Application settings."""

    # Encryption
    encryption_key: str = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""),
        description="Fernet encryption key for password storage",
    )

    # Database
    sqlite_db_path: str = Field(
        default_factory=lambda: os.getenv("SQLITE_DB_PATH", "./pgsync_admin.db"),
        description="SQLite database file path",
    )

    # ClickHouse
    clickhouse_host: str = Field(
        default_factory=lambda: os.getenv("CLICKHOUSE_HOST", "localhost"),
        description="ClickHouse host",
    )
    clickhouse_port: int = Field(
        default_factory=lambda: int(os.getenv("CLICKHOUSE_PORT", "9000")),
        description="ClickHouse native TCP port",
    )
    clickhouse_user: str = Field(
        default_factory=lambda: os.getenv("CLICKHOUSE_USER", ""),
        description="ClickHouse username",
    )
    clickhouse_password: str = Field(
        default_factory=lambda: os.getenv("CLICKHOUSE_PASSWORD", ""),
        description="ClickHouse password",
    )
    clickhouse_database: str = Field(
        default_factory=lambda: os.getenv("CLICKHOUSE_DATABASE", "pgsync_admin"),
        description="ClickHouse database name",
    )

    # API
    api_host: str = Field(
        default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"),
        description="API server host",
    )
    api_port: int = Field(
        default_factory=lambda: int(os.getenv("API_PORT", "3505")),
        description="API server port",
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level",
    )
    jwt_secret: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_expiry_hours: int = Field(default_factory=lambda: int(os.getenv("JWT_EXPIRY_HOURS", "24")))
    auth_admin_username: str = Field(default_factory=lambda: os.getenv("AUTH_ADMIN_USERNAME", ""))
    auth_admin_password: str = Field(default_factory=lambda: os.getenv("AUTH_ADMIN_PASSWORD", ""))
    demo_login_credentials: bool = Field(
        default_factory=lambda: os.getenv("DEMO_LOGIN_CREDENTIALS", "false").lower() == "true"
    )

    def validate_encryption_key(self) -> None:
        """Validate encryption key is set."""
        if not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not set. Generate with: "
                "python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )

    def validate_auth_config(self) -> None:
        """Reject missing or example-only credentials before serving requests."""
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("your_"):
            raise ValueError("Set JWT_SECRET to a random value with at least 32 characters")
        if not self.auth_admin_username or len(self.auth_admin_password) < 16 or self.auth_admin_password.startswith(("your_", "replace_")):
            raise ValueError("Set AUTH_ADMIN_USERNAME and a unique AUTH_ADMIN_PASSWORD with at least 16 characters")


# Global settings instance
settings = Settings()
