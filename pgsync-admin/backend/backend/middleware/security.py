"""Security middleware for authentication and rate limiting."""

import logging
import os
from typing import Callable, Optional
from robyn import Identity, Request, Response

from backend.services.auth_service import auth_service, rate_limiter, InputValidator

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Security middleware for Robyn."""

    @staticmethod
    def auth_middleware(handler: Callable) -> Callable:
        """Authentication middleware - verify JWT token."""
        async def wrapper(request: Request) -> Response:
            # Skip auth for public endpoints
            public_paths = ["/api/health", "/api/auth/login"]
            if any(request.url.path.startswith(p) for p in public_paths):
                return await handler(request)

            # Get token from header
            auth_header = request.headers.get("Authorization") or ""
            if not auth_header.startswith("Bearer "):
                return Response(
                    status_code=401,
                    body='{"error": "Missing or invalid authorization header"}',
                    headers={"Content-Type": "application/json"},
                )

            token = auth_header[7:]  # Remove "Bearer " prefix
            payload = auth_service.verify_token(token)

            if not payload:
                return Response(
                    status_code=401,
                    body='{"error": "Invalid or expired token"}',
                    headers={"Content-Type": "application/json"},
                )

            # Attach user info to request
            request.identity = Identity(claims=payload)
            return await handler(request)

        return wrapper

    @staticmethod
    def rate_limit_middleware(handler: Callable) -> Callable:
        """Rate limiting middleware."""
        async def wrapper(request: Request) -> Response:
            # Get identifier (IP or user ID)
            identifier = request.headers.get("X-Forwarded-For") or request.ip_addr
            if request.identity:
                identifier = f"user:{request.identity.claims.get('user_id', identifier)}"

            allowed, remaining = rate_limiter.check_rate_limit(identifier)

            if not allowed:
                return Response(
                    status_code=429,
                    body='{"error": "Rate limit exceeded. Try again later."}',
                    headers={
                        "Content-Type": "application/json",
                        "X-RateLimit-Limit": str(rate_limiter.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(rate_limiter.window_seconds),
                    },
                )

            response = await handler(request)

            # Add rate limit headers
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
                response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        return wrapper

    @staticmethod
    def cors_middleware(handler: Callable) -> Callable:
        """CORS middleware."""
        allowed_origins = {
            origin.strip()
            for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
            if origin.strip()
        }

        async def wrapper(request: Request) -> Response:
            origin = request.headers.get("Origin") or ""
            cors_headers = {
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            } if origin in allowed_origins else {}

            # Handle preflight
            if request.method == "OPTIONS":
                return Response(
                    status_code=204,
                    headers={**cors_headers, "Access-Control-Max-Age": "86400"},
                )

            response = await handler(request)

            # Add CORS headers
            if cors_headers and hasattr(response, "headers"):
                response.headers.update(cors_headers)

            return response

        return wrapper

    @staticmethod
    def input_validation_middleware(handler: Callable) -> Callable:
        """Input validation middleware."""
        async def wrapper(request: Request) -> Response:
            # Validate URL parameters
            if hasattr(request, "query_params"):
                for key, value in request.query_params.items():
                    if isinstance(value, str) and len(value) > 1000:
                        return Response(
                            status_code=400,
                            body='{"error": "Query parameter too long"}',
                            headers={"Content-Type": "application/json"},
                        )

            return await handler(request)

        return wrapper
