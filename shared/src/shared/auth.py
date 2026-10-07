"""Service trust primitives for inter-service authentication.

Provides a shared-secret token model where all services validate
incoming requests via the X-Service-Token header.
"""

import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

SERVICE_TOKEN_HEADER = "x-service-token"
DEFAULT_TOKEN = "dev-token-ai-librarian"
PUBLIC_PATH_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


def get_service_token() -> str:
    """Return the service auth token from env, falling back to dev default."""
    return os.environ.get("SERVICE_AUTH_TOKEN", DEFAULT_TOKEN)


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    """Validate X-Service-Token header on incoming requests.

    Requests to public paths (health, docs) are exempt.
    """

    def __init__(
        self,
        app,
        public_prefixes: tuple[str, ...] = PUBLIC_PATH_PREFIXES,
        token_resolver: Callable[[], str] = get_service_token,
    ):
        super().__init__(app)
        self.public_prefixes = public_prefixes
        self.token_resolver = token_resolver

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.public_prefixes):
            return await call_next(request)

        token = request.headers.get(SERVICE_TOKEN_HEADER)
        expected = self.token_resolver()
        if not token or token != expected:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid service token"},
            )

        return await call_next(request)
