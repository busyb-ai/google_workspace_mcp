"""
Google Workspace RemoteAuthProvider for FastMCP v2.11.1+

This module implements OAuth 2.1 authentication for Google Workspace using FastMCP's
RemoteAuthProvider pattern. It provides:

- JWT token verification using Google's public keys
- OAuth proxy endpoints to work around CORS restrictions
- Dynamic client registration workaround
- Session bridging to Google credentials for API access

This provider is used only in streamable-http transport mode with FastMCP v2.11.1+.
For earlier versions or other transport modes, the legacy GoogleWorkspaceAuthProvider is used.
"""

import os
import logging
import aiohttp
from typing import Optional, List

from starlette.routing import Route
from pydantic import AnyHttpUrl
from google.auth.exceptions import RefreshError

try:
    from fastmcp.server.auth import RemoteAuthProvider
    from fastmcp.server.auth.providers.jwt import JWTVerifier
    REMOTEAUTHPROVIDER_AVAILABLE = True
except ImportError:
    REMOTEAUTHPROVIDER_AVAILABLE = False
    RemoteAuthProvider = object  # Fallback for type hints
    JWTVerifier = object


# Import common OAuth handlers
from auth.oauth_common_handlers import (
    handle_oauth_authorize,
    handle_proxy_token_exchange,
    handle_oauth_authorization_server,
    handle_oauth_client_config,
    handle_oauth_register
)

logger = logging.getLogger(__name__)


class GoogleRemoteAuthProvider(RemoteAuthProvider):
    """
    RemoteAuthProvider implementation for Google Workspace using FastMCP v2.11.1+.
    
    This provider extends RemoteAuthProvider to add:
    - OAuth proxy endpoints for CORS workaround
    - Dynamic client registration support
    - Enhanced session management with issuer tracking
    """
    
    def __init__(self):
        """Initialize the Google RemoteAuthProvider."""
        if not REMOTEAUTHPROVIDER_AVAILABLE:
            raise ImportError("FastMCP v2.11.1+ required for RemoteAuthProvider")
        
        # Get configuration from environment
        self.client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        self.base_url = os.getenv("WORKSPACE_MCP_BASE_URI", "http://localhost")
        self.port = int(os.getenv("PORT", os.getenv("WORKSPACE_MCP_PORT", 8000)))
        
        if not self.client_id:
            logger.error("GOOGLE_OAUTH_CLIENT_ID not set - OAuth 2.1 authentication will not work")
            raise ValueError("GOOGLE_OAUTH_CLIENT_ID environment variable is required for OAuth 2.1 authentication")
        
        # Configure JWT verifier for Google tokens
        token_verifier = JWTVerifier(
            jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
            issuer="https://accounts.google.com",
            audience=self.client_id,  # Always use actual client_id
            algorithm="RS256"
        )
        
        # Initialize RemoteAuthProvider with local server as the authorization server
        # This ensures OAuth discovery points to our proxy endpoints instead of Google directly
        # For HTTPS (production behind ALB), don't append port; for HTTP (local dev), include it
        server_url = self.base_url if self.base_url.startswith("https://") else f"{self.base_url}:{self.port}"
        super().__init__(
            token_verifier=token_verifier,
            authorization_servers=[AnyHttpUrl(server_url)],
            resource_server_url=server_url
        )
        
        logger.debug("GoogleRemoteAuthProvider initialized")
    
    async def _attempt_token_refresh(self, failed_token: str) -> Optional[str]:
        """
        Attempt to refresh a failed token by finding the user and using their refresh token.
        
        Args:
            failed_token: The token that failed verification
            
        Returns:
            New access token if refresh successful, None otherwise
        """
        try:
            from auth.oauth21_session_store import get_oauth21_session_store
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            store = get_oauth21_session_store()
            
            logger.info(f"Attempting to refresh token. Searching {len(store._sessions)} sessions...")
            
            # Try to find the user by searching all sessions for a matching token
            # Note: This is expensive but necessary when token verification fails
            # We search by exact match first, then by prefix match (tokens from same OAuth flow share prefix)
            with store._lock:
                session_count = len(store._sessions)
                logger.debug(f"Searching {session_count} sessions for matching token")
                
                # First pass: exact match (most likely scenario)
                for user_email, session_info in store._sessions.items():
                    stored_token = session_info.get("access_token")
                    if stored_token == failed_token:
                        refresh_token = session_info.get("refresh_token")
                        if refresh_token:
                            logger.debug(f"Found matching session for {user_email}, attempting refresh")
                            
                            try:
                                # Create credentials object for refresh
                                credentials = Credentials(
                                    token=None,  # Will be refreshed
                                    refresh_token=refresh_token,
                                    token_uri=session_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                                    client_id=session_info.get("client_id") or self.client_id,
                                    client_secret=session_info.get("client_secret") or self.client_secret,
                                    scopes=session_info.get("scopes", []),
                                )
                                
                                # Attempt refresh (run in executor to avoid blocking event loop)
                                import asyncio
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, credentials.refresh, Request())
                                
                                # Update the session store with new token
                                store.store_session(
                                    user_email=user_email,
                                    access_token=credentials.token,
                                    refresh_token=credentials.refresh_token,
                                    token_uri=credentials.token_uri,
                                    client_id=credentials.client_id,
                                    client_secret=credentials.client_secret,
                                    scopes=credentials.scopes,
                                    expiry=credentials.expiry,
                                    session_id=session_info.get("session_id"),
                                    mcp_session_id=session_info.get("mcp_session_id"),
                                    issuer=session_info.get("issuer", "https://accounts.google.com")
                                )
                                
                                logger.info(f"Successfully refreshed token for {user_email}")
                                return credentials.token
                                
                            except RefreshError as refresh_error:
                                logger.warning(f"RefreshError - token expired/revoked for {user_email}: {refresh_error}")
                                # Delete invalid credentials to prevent retry with bad token
                                try:
                                    from auth.google_auth import delete_credentials_file
                                    deleted = delete_credentials_file(user_email)
                                    if deleted:
                                        logger.info(f"Deleted invalid credentials for {user_email} after refresh failure")
                                except Exception as delete_error:
                                    logger.error(f"Failed to delete credentials for {user_email}: {delete_error}")
                                # Remove from session store as well
                                store.remove_session(user_email)
                                # Continue searching other sessions
                                continue
                            except Exception as refresh_error:
                                logger.warning(f"Failed to refresh token for {user_email}: {refresh_error}")
                                # Continue searching other sessions
                                continue
                
                # Second pass: prefix match (for expired tokens that might have been updated)
                # Google OAuth tokens from the same flow share a common prefix
                for user_email, session_info in store._sessions.items():
                    stored_token = session_info.get("access_token")
                    if stored_token and len(stored_token) >= 20 and len(failed_token) >= 20:
                        if stored_token[:20] == failed_token[:20]:
                            refresh_token = session_info.get("refresh_token")
                            if refresh_token:
                                logger.debug(f"Found prefix-matching session for {user_email}, attempting refresh")
                                
                                try:
                                    # Create credentials object for refresh
                                    credentials = Credentials(
                                        token=None,  # Will be refreshed
                                        refresh_token=refresh_token,
                                        token_uri=session_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                                        client_id=session_info.get("client_id") or self.client_id,
                                        client_secret=session_info.get("client_secret") or self.client_secret,
                                        scopes=session_info.get("scopes", []),
                                    )
                                    
                                    # Attempt refresh (run in executor to avoid blocking)
                                    import asyncio
                                    loop = asyncio.get_event_loop()
                                    await loop.run_in_executor(None, credentials.refresh, Request())
                                    
                                    # Update the session store with new token
                                    store.store_session(
                                        user_email=user_email,
                                        access_token=credentials.token,
                                        refresh_token=credentials.refresh_token,
                                        token_uri=credentials.token_uri,
                                        client_id=credentials.client_id,
                                        client_secret=credentials.client_secret,
                                        scopes=credentials.scopes,
                                        expiry=credentials.expiry,
                                        session_id=session_info.get("session_id"),
                                        mcp_session_id=session_info.get("mcp_session_id"),
                                        issuer=session_info.get("issuer", "https://accounts.google.com")
                                    )
                                    
                                    logger.info(f"Successfully refreshed token for {user_email} (prefix match)")
                                    return credentials.token
                                    
                                except RefreshError as refresh_error:
                                    logger.warning(f"RefreshError - token expired/revoked for {user_email} (prefix match): {refresh_error}")
                                    # Delete invalid credentials to prevent retry with bad token
                                    try:
                                        from auth.google_auth import delete_credentials_file
                                        deleted = delete_credentials_file(user_email)
                                        if deleted:
                                            logger.info(f"Deleted invalid credentials for {user_email} after refresh failure (prefix match)")
                                    except Exception as delete_error:
                                        logger.error(f"Failed to delete credentials for {user_email}: {delete_error}")
                                    # Remove from session store as well
                                    store.remove_session(user_email)
                                    # Continue searching other sessions
                                    continue
                                except Exception as refresh_error:
                                    logger.warning(f"Failed to refresh token for {user_email} (prefix match): {refresh_error}")
                                    # Continue searching other sessions
                                    continue
                
                logger.warning(f"No matching session found for token refresh after searching {session_count} sessions")
                logger.debug(f"Failed token prefix: {failed_token[:30]}...")
                return None
                
        except Exception as e:
            logger.error(f"Error attempting token refresh: {e}")
            return None
    
    def get_routes(self) -> List[Route]:
        """
        Add custom OAuth proxy endpoints to the standard protected resource routes.
        
        These endpoints work around Google's CORS restrictions and provide
        dynamic client registration support.
        """
        # Get the standard OAuth protected resource routes from RemoteAuthProvider
        routes = super().get_routes()
        
        # Log what routes we're getting from the parent
        logger.debug(f"Registered {len(routes)} OAuth routes from parent")
        
        # Add our custom proxy endpoints using common handlers
        routes.append(Route("/oauth2/authorize", handle_oauth_authorize, methods=["GET", "OPTIONS"]))
        
        routes.append(Route("/oauth2/token", handle_proxy_token_exchange, methods=["POST", "OPTIONS"]))
        
        routes.append(Route("/oauth2/register", handle_oauth_register, methods=["POST", "OPTIONS"]))
        
        routes.append(Route("/.well-known/oauth-authorization-server", handle_oauth_authorization_server, methods=["GET", "OPTIONS"]))
        
        routes.append(Route("/.well-known/oauth-client", handle_oauth_client_config, methods=["GET", "OPTIONS"]))
        
        return routes
    
    async def verify_token(self, token: str) -> Optional[object]:
        """
        Override verify_token to handle Google OAuth access tokens.
        
        Google OAuth access tokens (ya29.*) are opaque tokens that need to be
        verified using the tokeninfo endpoint, not JWT verification.
        """
        logger.info(f"verify_token called with token prefix: {token[:20]}... (length: {len(token)})")
        
        # Check if this is a Google OAuth access token (starts with ya29.)
        if token.startswith("ya29."):
            logger.debug("Detected Google OAuth access token, using tokeninfo verification")
            
            try:
                # Verify the access token using Google's tokeninfo endpoint
                async with aiohttp.ClientSession() as session:
                    url = f"https://oauth2.googleapis.com/tokeninfo?access_token={token}"
                    async with session.get(url) as response:
                        logger.debug(f"Tokeninfo response status: {response.status}, content-type: {response.content_type}")
                        if response.status != 200:
                            # Log the actual error response from Google
                            error_details = None
                            error_body = None
                            try:
                                error_body = await response.text()
                                logger.debug(f"Error response body (first 500 chars): {error_body[:500]}")
                                
                                # Try to parse as JSON if content type suggests it
                                if 'application/json' in (response.content_type or '') or (error_body and error_body.strip().startswith('{')):
                                    try:
                                        import json
                                        error_json = json.loads(error_body)
                                        error_details = error_json.get('error_description') or error_json.get('error') or error_json.get('message')
                                        logger.error(f"Token verification failed: {response.status} - Error: {error_details} | Full response: {error_json}")
                                    except (json.JSONDecodeError, ValueError) as parse_error:
                                        error_details = error_body[:200] if error_body else None
                                        logger.error(f"Token verification failed: {response.status} - {error_details} (JSON parse error: {parse_error})")
                                else:
                                    error_details = error_body[:200] if error_body else None
                                    logger.error(f"Token verification failed: {response.status} - {error_details}")
                                
                                if not error_details:
                                    logger.error(f"Token verification failed: {response.status} (no error details available, body length: {len(error_body) if error_body else 0})")
                            except Exception as e:
                                logger.error(f"Token verification failed: {response.status} (could not read error response: {e})", exc_info=True)
                            
                            # Attempt to refresh the token if we can find stored credentials
                            # Note: For "invalid_token" errors, refresh might not help, but we'll try anyway
                            logger.info(f"Attempting token refresh for invalid token (error: {error_details})")
                            refreshed_token = await self._attempt_token_refresh(token)
                            if refreshed_token:
                                logger.info("Successfully refreshed token, re-verifying new token")
                                # Recursively verify the new token
                                return await self.verify_token(refreshed_token)
                            else:
                                logger.warning("Token refresh failed or no matching session found")
                            
                            return None
                        
                        token_info = await response.json()
                        
                        # Verify the token is for our client
                        if token_info.get("aud") != self.client_id:
                            logger.error(f"Token audience mismatch: expected {self.client_id}, got {token_info.get('aud')}")
                            return None
                        
                        # Check if token is expired
                        expires_in = token_info.get("expires_in", 0)
                        if int(expires_in) <= 0:
                            logger.error("Token is expired")
                            return None
                        
                        # Create an access token object that matches the expected interface
                        from types import SimpleNamespace
                        import time
                        
                        # Calculate expires_at timestamp
                        expires_in = int(token_info.get("expires_in", 0))
                        expires_at = int(time.time()) + expires_in if expires_in > 0 else 0
                        
                        access_token = SimpleNamespace(
                            claims={
                                "email": token_info.get("email"),
                                "sub": token_info.get("sub"),
                                "aud": token_info.get("aud"),
                                "scope": token_info.get("scope", ""),
                            },
                            scopes=token_info.get("scope", "").split(),
                            token=token,
                            expires_at=expires_at,  # Add the expires_at attribute
                            client_id=self.client_id,  # Add client_id at top level
                            # Add other required fields
                            sub=token_info.get("sub", ""),
                            email=token_info.get("email", "")
                        )
                        
                        user_email = token_info.get("email")
                        if user_email:
                            from auth.oauth21_session_store import get_oauth21_session_store
                            store = get_oauth21_session_store()
                            session_id = f"google_{token_info.get('sub', 'unknown')}"
                            
                            # Try to get FastMCP session ID for binding
                            mcp_session_id = None
                            try:
                                from fastmcp.server.dependencies import get_context
                                ctx = get_context()
                                if ctx and hasattr(ctx, 'session_id'):
                                    mcp_session_id = ctx.session_id
                                    logger.debug(f"Binding MCP session {mcp_session_id} to user {user_email}")
                            except Exception:
                                pass
                            
                            # Store session with issuer information
                            store.store_session(
                                user_email=user_email,
                                access_token=token,
                                scopes=access_token.scopes,
                                session_id=session_id,
                                mcp_session_id=mcp_session_id,
                                issuer="https://accounts.google.com"
                            )
                            
                            logger.info(f"Verified OAuth token: {user_email}")
                        
                        return access_token
                        
            except Exception as e:
                logger.error(f"Error verifying Google OAuth token: {e}")
                return None
        
        else:
            # For JWT tokens, use parent's JWT verification
            logger.debug("Using JWT verification for non-OAuth token")
            access_token = await super().verify_token(token)
            
            if access_token and self.client_id:
                # Extract user information from token claims
                user_email = access_token.claims.get("email")
                if user_email:
                    from auth.oauth21_session_store import get_oauth21_session_store
                    store = get_oauth21_session_store()
                    session_id = f"google_{access_token.claims.get('sub', 'unknown')}"
                    
                    # Store session with issuer information
                    store.store_session(
                        user_email=user_email,
                        access_token=token,
                        scopes=access_token.scopes or [],
                        session_id=session_id,
                        issuer="https://accounts.google.com"
                    )
                    
                    logger.debug(f"Successfully verified JWT token for user: {user_email}")
            
            return access_token