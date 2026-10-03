"""MCP server for Nigeria's NIPOST digital postcode (NDAPS)."""

from .server import Settings, create_server, main, settings_from_env

__all__ = ["Settings", "create_server", "main", "settings_from_env"]
