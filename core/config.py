"""
Shared configuration for Google Workspace MCP server.
This module holds configuration values that need to be shared across modules
to avoid circular imports.
"""

import os

# Server configuration
WORKSPACE_MCP_PORT = int(os.getenv("PORT", os.getenv("WORKSPACE_MCP_PORT", 8000)))
WORKSPACE_MCP_BASE_URI = os.getenv("WORKSPACE_MCP_BASE_URI", "http://localhost")
USER_GOOGLE_EMAIL = os.getenv("USER_GOOGLE_EMAIL", None)

# Transport mode (will be set by main.py)
_current_transport_mode = "stdio"  # Default to stdio


def set_transport_mode(mode: str):
    """Set the current transport mode for OAuth callback handling."""
    global _current_transport_mode
    _current_transport_mode = mode


def get_transport_mode() -> str:
    """Get the current transport mode."""
    return _current_transport_mode


def get_base_url() -> str:
    """Get base URL for constructing endpoints.

    For HTTPS URLs, we don't append the port since the ALB handles port mapping.
    For HTTP URLs (typically local development), we include the port.
    """
    # If using HTTPS, don't append the port (ALB handles 443 -> 8000 mapping)
    if WORKSPACE_MCP_BASE_URI.startswith("https://"):
        return WORKSPACE_MCP_BASE_URI
    # For HTTP (local development), include the port
    return f"{WORKSPACE_MCP_BASE_URI}:{WORKSPACE_MCP_PORT}"


def get_oauth_redirect_uri() -> str:
    """Get OAuth redirect URI based on current configuration."""
    return f"{get_base_url()}/oauth2callback"