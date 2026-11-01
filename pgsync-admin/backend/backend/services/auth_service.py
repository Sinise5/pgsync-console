"""Authentication and authorization service."""

import logging
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from backend.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and authorization management."""

    def __init__(self, secret_key: str, token_expiry: int = 3600):
        self.secret_key = secret_key
        self.token_expiry = token_expiry  # seconds
        self.sessions: Dict[str, Dict[str, Any]] = {}  # In-memory session store

    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash password with salt."""
        if not salt:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hashed.hex(), salt

    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """Verify password against hash."""
        computed_hash, _ = self.hash_password(password, salt)
        return secrets.compare_digest(computed_hash, hashed)

    def generate_token(self, user_id: int, username: str, roles: list[str]) -> str:
        """Generate JWT token."""
        payload = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": datetime.utcnow() + timedelta(seconds=self.token_expiry),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def create_session(self, user_id: int, username: str, roles: list[str]) -> str:
        """Create session and return session ID."""
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "created_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session = self.sessions.get(session_id)
        if session:
            session["last_accessed"] = datetime.utcnow()
        return session

    def revoke_session(self, session_id: str) -> bool:
        """Revoke session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self, max_age: int = 3600):
        """Cleanup sessions older than max_age seconds."""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self.sessions.items()
            if (now - session["last_accessed"]).total_seconds() > max_age
        ]
        for sid in expired:
            del self.sessions[sid]
        logger.info(f"Cleaned up {len(expired)} expired sessions")


class RateLimiter:
    """Rate limiting for API endpoints."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list[datetime]] = {}

    def check_rate_limit(self, identifier: str) -> tuple[bool, int]:
        """Check if request is within rate limit. Returns (allowed, remaining)."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                ts for ts in self.requests[identifier] if ts > cutoff
            ]
        else:
            self.requests[identifier] = []

        # Check limit
        current_count = len(self.requests[identifier])
        if current_count >= self.max_requests:
            return False, 0

        # Record request
        self.requests[identifier].append(now)
        remaining = self.max_requests - current_count - 1
        return True, remaining

    def reset(self, identifier: str):
        """Reset rate limit for identifier."""
        if identifier in self.requests:
            del self.requests[identifier]


class InputValidator:
    """Input validation and sanitization."""

    @staticmethod
    def sanitize_sql_input(value: str) -> str:
        """Basic SQL injection prevention."""
        dangerous = ["--", ";", "/*", "*/", "xp_", "sp_", "DROP", "DELETE", "INSERT", "UPDATE"]
        for pattern in dangerous:
            if pattern.lower() in value.lower():
                raise ValueError(f"Potentially dangerous input detected: {pattern}")
        return value

    @staticmethod
    def validate_cron_expression(expr: str) -> bool:
        """Validate a five-field cron expression with APScheduler's parser."""
        from apscheduler.triggers.cron import CronTrigger

        try:
            CronTrigger.from_crontab(expr.strip())
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        if not url.startswith(("http://", "https://")):
            return False
        return True


# Global instances
auth_service = AuthService(
    secret_key=settings.jwt_secret,
    token_expiry=settings.jwt_expiry_hours * 3600,
)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
