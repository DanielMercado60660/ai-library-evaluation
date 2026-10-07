"""Service discovery and registry for inter-service communication.

This module provides centralized service URL management, supporting both
Docker Compose networking and local development.
"""

import os
from typing import Literal

ServiceName = Literal["catalog", "circulation", "ill", "registry"]


class ServiceRegistry:
    """Registry for service discovery.

    Supports both environment variables (Docker) and default local URLs.
    """

    # Default URLs for local development
    DEFAULT_URLS = {
        "catalog": "http://localhost:8001",
        "circulation": "http://localhost:8002",
        "ill": "http://localhost:8003",
        "registry": "http://localhost:8004",
    }

    # Environment variable names for service URLs
    ENV_VARS = {
        "catalog": "CATALOG_SERVICE_URL",
        "circulation": "CIRCULATION_SERVICE_URL",
        "ill": "ILL_SERVICE_URL",
        "registry": "REGISTRY_SERVICE_URL",
    }

    @classmethod
    def get_url(cls, service: ServiceName) -> str:
        """Get the base URL for a service.

        Checks environment variables first (for Docker), then falls back
        to default local URLs.

        Args:
            service: Name of the service (catalog, circulation, ill)

        Returns:
            Base URL for the service (e.g., "http://localhost:8001")

        Raises:
            ValueError: If service name is invalid
        """
        if service not in cls.DEFAULT_URLS:
            raise ValueError(
                f"Unknown service: {service}. "
                f"Valid services: {list(cls.DEFAULT_URLS.keys())}"
            )

        # Check environment variable first (Docker Compose sets these)
        env_var = cls.ENV_VARS[service]
        url = os.getenv(env_var)

        if url:
            return url.rstrip("/")

        # Fall back to default local URL
        return cls.DEFAULT_URLS[service]

    @classmethod
    def get_catalog_url(cls) -> str:
        """Get the Catalog service URL."""
        return cls.get_url("catalog")

    @classmethod
    def get_circulation_url(cls) -> str:
        """Get the Circulation service URL."""
        return cls.get_url("circulation")

    @classmethod
    def get_ill_url(cls) -> str:
        """Get the ILL service URL."""
        return cls.get_url("ill")

    @classmethod
    def get_registry_url(cls) -> str:
        """Get the Registry service URL."""
        return cls.get_url("registry")


# Convenience function
def get_service_url(service: ServiceName) -> str:
    """Get the base URL for a service.

    Args:
        service: Name of the service

    Returns:
        Base URL for the service
    """
    return ServiceRegistry.get_url(service)
