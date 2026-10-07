"""MCP Connection Manager - Async lifecycle management for MCP toolsets.

Provides centralized management of MCP server connections with:
- Async context managers for proper resource cleanup
- Centralized service configurations
- Connection pooling and reuse
- Graceful error handling
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)


# Centralized MCP service configurations
MCP_SERVICE_CONFIGS = {
    "catalog": {
        "server_params": StdioServerParameters(
            command="python",
            args=["-m", "catalog.mcp_server"],
            env={
                "DATABASE_URL": os.getenv("CATALOG_DB_URL", "sqlite:///./db/catalog.db"),
                "PYTHONPATH": os.getenv("CATALOG_PYTHONPATH", "/app/services/catalog/src:/app/shared/src"),
            },
        ),
        "tool_filter": [
            "search_books",
            "get_book_details",
            "check_availability",
            "reserve_instance",
            "get_books_by_stratum",
        ],
    },
    "circulation": {
        "server_params": StdioServerParameters(
            command="python",
            args=["-m", "circulation.mcp_server"],
            env={
                "DATABASE_URL": os.getenv("CIRCULATION_DB_URL", "sqlite:///./db/circulation.db"),
                "PYTHONPATH": os.getenv("CIRCULATION_PYTHONPATH", "/app/services/circulation/src:/app/shared/src"),
            },
        ),
        "tool_filter": [
            "check_patron_eligibility",
            "calculate_patron_fines",
            "checkout_item",
            "return_item",
            "renew_checkout",
            "place_hold",
            "cancel_hold",
            "get_patron_summary",
        ],
    },
    "ill": {
        "server_params": StdioServerParameters(
            command="python",
            args=["-m", "ill.mcp_server"],
            env={
                "DATABASE_URL": os.getenv("ILL_DB_URL", "sqlite:///./db/ill.db"),
                "PYTHONPATH": os.getenv("ILL_PYTHONPATH", "/app/services/ill/src:/app/shared/src"),
            },
        ),
        "tool_filter": [
            "approve_ill_request",
            "deny_ill_request",
            "approve_inbound_loan",
            "deny_inbound_loan",
            "get_queue_statistics",
            "query_audit_trail",
            "get_pending_outbound_queue",
            "get_pending_inbound_queue",
        ],
    },
}


class MCPConnectionManager:
    """Manages MCP toolset lifecycle with proper async context management.

    Usage:
        async with MCPConnectionManager() as manager:
            catalog_tools = await manager.get_toolset("catalog")
            # Use catalog_tools...

        # Or for specific toolsets:
        manager = MCPConnectionManager()
        async with manager.toolset_context("catalog") as toolset:
            # Use toolset...
    """

    def __init__(self):
        self._toolsets: dict[str, McpToolset] = {}
        self._active_connections: set[str] = set()
        self._initialized = False

    async def __aenter__(self) -> "MCPConnectionManager":
        """Enter async context - initialize manager."""
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - close all connections."""
        await self.close_all()

    @asynccontextmanager
    async def toolset_context(
        self, service_name: str, tool_filter: list[str] | None = None
    ) -> AsyncGenerator[McpToolset, None]:
        """Get MCP toolset with proper lifecycle management.

        Args:
            service_name: Name of the service (catalog, circulation, ill)
            tool_filter: Optional override for tool filter

        Yields:
            Configured McpToolset instance

        Raises:
            ValueError: If service_name is not configured
        """
        config = MCP_SERVICE_CONFIGS.get(service_name)
        if not config:
            raise ValueError(f"Unknown MCP service: {service_name}. Available: {list(MCP_SERVICE_CONFIGS.keys())}")

        toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=config["server_params"]
            ),
            tool_filter=tool_filter or config.get("tool_filter"),
        )

        try:
            logger.info(f"Connecting to MCP service: {service_name}")
            self._active_connections.add(service_name)
            yield toolset
        except Exception as e:
            logger.error(f"Error with MCP service {service_name}: {e}")
            raise
        finally:
            self._active_connections.discard(service_name)
            logger.info(f"Disconnected from MCP service: {service_name}")

    async def get_toolset(
        self, service_name: str, tool_filter: list[str] | None = None
    ) -> McpToolset:
        """Get or create a cached toolset for a service.

        Note: When using this method, you must manually manage the connection lifecycle
        or use the MCPConnectionManager as a context manager.

        Args:
            service_name: Name of the service
            tool_filter: Optional override for tool filter

        Returns:
            Cached or new McpToolset instance
        """
        cache_key = f"{service_name}:{','.join(tool_filter or [])}"

        if cache_key not in self._toolsets:
            config = MCP_SERVICE_CONFIGS.get(service_name)
            if not config:
                raise ValueError(f"Unknown MCP service: {service_name}")

            toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=config["server_params"]
                ),
                tool_filter=tool_filter or config.get("tool_filter"),
            )
            self._toolsets[cache_key] = toolset
            self._active_connections.add(service_name)
            logger.info(f"Created cached toolset for: {service_name}")

        return self._toolsets[cache_key]

    async def close_all(self) -> None:
        """Close all active connections and clear cache."""
        logger.info(f"Closing {len(self._toolsets)} MCP connections")
        self._toolsets.clear()
        self._active_connections.clear()
        self._initialized = False

    @property
    def active_services(self) -> set[str]:
        """Get set of currently active service names."""
        return self._active_connections.copy()

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized (in context)."""
        return self._initialized


def create_catalog_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Convenience function to create a catalog MCP toolset."""
    config = MCP_SERVICE_CONFIGS["catalog"]
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=config["server_params"]
        ),
        tool_filter=tool_filter or config.get("tool_filter"),
    )


def create_circulation_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Convenience function to create a circulation MCP toolset."""
    config = MCP_SERVICE_CONFIGS["circulation"]
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=config["server_params"]
        ),
        tool_filter=tool_filter or config.get("tool_filter"),
    )


def create_ill_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Convenience function to create an ILL MCP toolset."""
    config = MCP_SERVICE_CONFIGS["ill"]
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=config["server_params"]
        ),
        tool_filter=tool_filter or config.get("tool_filter"),
    )
