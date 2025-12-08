import logging
import os
from typing import Optional, Union
from importlib import metadata

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from fastmcp import FastMCP

from auth.oauth21_session_store import get_oauth21_session_store, set_auth_provider
from auth.google_auth import handle_auth_callback, start_auth_flow, check_client_secrets
from auth.mcp_session_middleware import MCPSessionMiddleware
from auth.oauth_responses import create_error_response, create_success_response, create_server_error_response
from auth.auth_info_middleware import AuthInfoMiddleware
from auth.fastmcp_google_auth import GoogleWorkspaceAuthProvider
from auth.scopes import SCOPES
from core.config import (
    WORKSPACE_MCP_PORT,
    WORKSPACE_MCP_BASE_URI,
    USER_GOOGLE_EMAIL,
    get_transport_mode,
    set_transport_mode as _set_transport_mode,
    get_oauth_redirect_uri as get_oauth_redirect_uri_for_current_mode,
)

# Try to import GoogleRemoteAuthProvider for FastMCP 2.11.1+
try:
    from auth.google_remote_auth_provider import GoogleRemoteAuthProvider
    GOOGLE_REMOTE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_REMOTE_AUTH_AVAILABLE = False
    GoogleRemoteAuthProvider = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_auth_provider: Optional[Union[GoogleWorkspaceAuthProvider, GoogleRemoteAuthProvider]] = None

# --- Path Prefix Stripping ---
# When running behind ALB with path-based routing (e.g., /google-workspace/*),
# the ALB forwards the full path but our routes expect paths without the prefix.
# This middleware strips the configurable prefix from incoming requests.
PATH_PREFIX = os.getenv("MCP_PATH_PREFIX", "")  # e.g., "/google-workspace"

class PathPrefixMiddleware:
    """ASGI middleware to strip a path prefix from incoming requests."""
    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/") if prefix else ""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.prefix:
            path = scope.get("path", "")
            if path.startswith(self.prefix):
                # Strip the prefix
                scope = dict(scope)
                scope["path"] = path[len(self.prefix):] or "/"
                # Also update raw_path if present
                raw_path = scope.get("raw_path")
                if raw_path:
                    raw_path_str = raw_path.decode("latin-1")
                    if raw_path_str.startswith(self.prefix):
                        scope["raw_path"] = (raw_path_str[len(self.prefix):] or "/").encode("latin-1")
        await self.app(scope, receive, send)

# --- Middleware Definitions ---
cors_middleware = Middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.busyb.ai",
        "https://busyb.ai",
        "http://app.busyb.ai",
        "http://busyb.ai",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
session_middleware = Middleware(MCPSessionMiddleware)

# Custom FastMCP that adds CORS to streamable HTTP
class CORSEnabledFastMCP(FastMCP):
    def streamable_http_app(self) -> "Starlette":
        """Override to add CORS, session, and path prefix middleware to the app."""
        app = super().streamable_http_app()
        # Add session middleware first (to set context before other middleware)
        app.user_middleware.insert(0, session_middleware)
        # Add CORS as the second middleware
        app.user_middleware.insert(1, cors_middleware)
        # Rebuild middleware stack
        app.middleware_stack = app.build_middleware_stack()

        # Wrap with path prefix middleware if configured (must be outermost)
        if PATH_PREFIX:
            logger.info(f"Adding path prefix middleware for prefix: {PATH_PREFIX}")
            final_app = PathPrefixMiddleware(app, PATH_PREFIX)
            # Return a wrapper that behaves like Starlette but uses our middleware
            class WrappedApp(Starlette):
                def __init__(self, inner_app):
                    self._inner = inner_app
                async def __call__(self, scope, receive, send):
                    await self._inner(scope, receive, send)
            wrapped = WrappedApp(final_app)
            wrapped.routes = app.routes  # Preserve routes for introspection
            logger.info("Added session, CORS, and path prefix middleware to streamable HTTP app")
            return wrapped

        logger.info("Added session and CORS middleware to streamable HTTP app")
        return app

# --- Server Instance ---
server = CORSEnabledFastMCP(
    name="google_workspace",
    auth=None,
)

# Add the AuthInfo middleware to inject authentication into FastMCP context
auth_info_middleware = AuthInfoMiddleware()
server.add_middleware(auth_info_middleware)


def set_transport_mode(mode: str):
    """Sets the transport mode for the server."""
    _set_transport_mode(mode)
    logger.info(f"🔌 Transport: {mode}")

def configure_server_for_http():
    """
    Configures the authentication provider for HTTP transport.
    This must be called BEFORE server.run().
    """
    global _auth_provider
    transport_mode = get_transport_mode()

    if transport_mode != "streamable-http":
        return

    oauth21_enabled = os.getenv("MCP_ENABLE_OAUTH21", "false").lower() == "true"

    if oauth21_enabled:
        if not os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
            logger.warning("⚠️  OAuth 2.1 enabled but GOOGLE_OAUTH_CLIENT_ID not set")
            return

        if GOOGLE_REMOTE_AUTH_AVAILABLE:
            logger.info("🔐 OAuth 2.1 enabled")
            try:
                _auth_provider = GoogleRemoteAuthProvider()
                server.auth = _auth_provider
                set_auth_provider(_auth_provider)
                from auth.oauth21_integration import enable_oauth21
                enable_oauth21()
            except Exception as e:
                logger.error(f"Failed to initialize GoogleRemoteAuthProvider: {e}", exc_info=True)
        else:
            logger.error("OAuth 2.1 is enabled, but GoogleRemoteAuthProvider is not available.")
    else:
        logger.info("OAuth 2.1 is DISABLED. Server will use legacy tool-based authentication.")
        server.auth = None

def get_auth_provider() -> Optional[Union[GoogleWorkspaceAuthProvider, GoogleRemoteAuthProvider]]:
    """Gets the global authentication provider instance."""
    return _auth_provider

# --- Custom Routes ---
@server.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    try:
        version = metadata.version("workspace-mcp")
    except metadata.PackageNotFoundError:
        version = "dev"
    return JSONResponse({
        "status": "healthy",
        "service": "workspace-mcp",
        "version": version,
        "transport": get_transport_mode()
    })

@server.custom_route("/oauth2callback", methods=["GET"])
async def oauth2_callback(request: Request):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    # Decode state parameter to check for return_url and user_id
    return_url = None
    user_id = None
    if state:
        try:
            import base64
            import json
            state_data = json.loads(base64.urlsafe_b64decode(state).decode())
            return_url = state_data.get("return_url")
            user_id = state_data.get("user_id")
        except Exception:
            # State is not encoded, just a regular CSRF token
            pass

    if error:
        msg = f"Authentication failed: Google returned an error: {error}. State: {state}."
        logger.error(msg)
        if return_url:
            # Redirect to return_url with error
            from urllib.parse import urlencode
            error_params = urlencode({"error": error, "error_description": msg})
            return RedirectResponse(url=f"{return_url}?{error_params}")
        return create_error_response(msg)

    if not code:
        msg = "Authentication failed: No authorization code received from Google."
        logger.error(msg)
        if return_url:
            from urllib.parse import urlencode
            error_params = urlencode({"error": "no_code", "error_description": msg})
            return RedirectResponse(url=f"{return_url}?{error_params}")
        return create_error_response(msg)

    try:
        error_message = check_client_secrets()
        if error_message:
            if return_url:
                from urllib.parse import urlencode
                error_params = urlencode({"error": "config_error", "error_description": error_message})
                return RedirectResponse(url=f"{return_url}?{error_params}")
            return create_server_error_response(error_message)

        logger.info(f"OAuth callback: Received code (state: {state}).")

        verified_user_id, credentials = handle_auth_callback(
            scopes=SCOPES,
            authorization_response=str(request.url),
            redirect_uri=get_oauth_redirect_uri_for_current_mode(),
            session_id=None,
            user_id=user_id
        )

        logger.info(f"OAuth callback: Successfully authenticated user: {verified_user_id}.")

        try:
            store = get_oauth21_session_store()
            mcp_session_id = None
            if hasattr(request, 'state') and hasattr(request.state, 'session_id'):
                mcp_session_id = request.state.session_id

            store.store_session(
                user_email=verified_user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=credentials.expiry,
                session_id=f"google-{state}",
                mcp_session_id=mcp_session_id,
            )
            logger.info(f"Stored Google credentials in OAuth 2.1 session store for {verified_user_id}")
        except Exception as e:
            logger.error(f"Failed to store credentials in OAuth 2.1 store: {e}")

        # If return_url was provided, redirect back to frontend
        if return_url:
            from urllib.parse import urlencode
            success_params = urlencode({
                "success": "true",
                "email": verified_user_id
            })
            redirect_url = f"{return_url}?{success_params}"
            logger.info(f"Redirecting to return_url: {redirect_url}")
            return RedirectResponse(url=redirect_url)
        
        # Otherwise show success page
        return create_success_response(verified_user_id)
        
    except Exception as e:
        logger.error(f"Error processing OAuth callback: {str(e)}", exc_info=True)
        if return_url:
            from urllib.parse import urlencode
            error_params = urlencode({"error": "auth_failed", "error_description": str(e)})
            return RedirectResponse(url=f"{return_url}?{error_params}")
        return create_server_error_response(str(e))

@server.custom_route("/auth/status", methods=["GET", "OPTIONS"])
async def auth_status(request: Request):
    """Check authentication status for the current user."""
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
    
    try:
        # Extract bearer token from Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "authenticated": False,
                    "error": "No bearer token provided"
                },
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Verify token using auth provider if available
        auth_provider = get_auth_provider()
        user_email = None
        
        if auth_provider:
            # Try to verify the token
            try:
                access_token = await auth_provider.verify_token(token)
                if access_token:
                    user_email = getattr(access_token, 'email', None) or access_token.claims.get('email')
            except Exception as e:
                logger.debug(f"Token verification via auth provider failed: {e}")
        
        # Fallback: decode JWT without verification to extract email
        if not user_email:
            try:
                import jwt
                claims = jwt.decode(token, options={"verify_signature": False})
                user_email = claims.get('email')
            except Exception as e:
                logger.debug(f"Failed to decode JWT: {e}")
        
        # Check if we found user email and have credentials
        if user_email:
            store = get_oauth21_session_store()
            credentials = store.get_credentials(user_email)
            
            if credentials:
                # Check if credentials are valid
                is_valid = credentials.valid
                expiry = credentials.expiry.isoformat() if credentials.expiry else None
                
                return JSONResponse(
                    content={
                        "authenticated": True,
                        "email": user_email,
                        "valid": is_valid,
                        "expired": credentials.expired if hasattr(credentials, 'expired') else not is_valid,
                        "expires_at": expiry,
                        "scopes": credentials.scopes
                    },
                    headers={"Access-Control-Allow-Origin": "*"}
                )
        
        # Token provided but no valid credentials found
        return JSONResponse(
            status_code=401,
            content={
                "authenticated": False,
                "error": "Invalid or expired token"
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error(f"Error checking auth status: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "authenticated": False,
                "error": f"Internal error: {str(e)}"
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )

@server.custom_route("/auth/revoke", methods=["POST", "OPTIONS"])
async def auth_revoke(request: Request):
    """Revoke authentication and delete stored credentials."""
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
    
    try:
        # Extract bearer token from Authorization header
        auth_header = request.headers.get("authorization")
        user_email = None
        
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Try to get user email from token
            auth_provider = get_auth_provider()
            if auth_provider:
                try:
                    access_token = await auth_provider.verify_token(token)
                    if access_token:
                        user_email = getattr(access_token, 'email', None) or access_token.claims.get('email')
                except Exception as e:
                    logger.debug(f"Token verification failed: {e}")
            
            # Fallback: decode JWT without verification
            if not user_email:
                try:
                    import jwt
                    claims = jwt.decode(token, options={"verify_signature": False})
                    user_email = claims.get('email')
                except Exception:
                    pass
        
        # Also check request body for email (optional)
        if not user_email:
            try:
                body = await request.json()
                user_email = body.get('email')
            except Exception:
                pass
        
        if not user_email:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No user email found in token or request body"
                },
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        # Get credentials before revoking to call Google's revoke endpoint
        store = get_oauth21_session_store()
        credentials = store.get_credentials(user_email)
        
        # Remove session from store
        store.remove_session(user_email)
        logger.info(f"Removed OAuth session for {user_email}")

        # Delete credential file using unified delete function
        from auth.google_auth import delete_credentials_file
        credentials_deleted = delete_credentials_file(user_email)
        if credentials_deleted:
            logger.info(f"Successfully deleted credential file for {user_email}")
        else:
            logger.info(f"No credential file found or deletion failed for {user_email}")
        
        # Optionally revoke token with Google
        revoked_with_google = False
        if credentials and credentials.token:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    revoke_url = f"https://oauth2.googleapis.com/revoke?token={credentials.token}"
                    async with session.post(revoke_url) as response:
                        if response.status == 200:
                            revoked_with_google = True
                            logger.info(f"Successfully revoked token with Google for {user_email}")
                        else:
                            logger.warning(f"Google token revocation returned status {response.status}")
            except Exception as e:
                logger.warning(f"Failed to revoke token with Google: {e}")
        
        return JSONResponse(
            content={
                "success": True,
                "email": user_email,
                "revoked_with_google": revoked_with_google,
                "message": "Authentication revoked and credentials deleted"
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error(f"Error revoking auth: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Internal error: {str(e)}"
            },
            headers={"Access-Control-Allow-Origin": "*"}
        )

# --- Tools ---
@server.tool()
async def start_google_auth(service_name: str, user_google_email: str = USER_GOOGLE_EMAIL) -> str:
    if not user_google_email:
        raise ValueError("user_google_email must be provided.")

    error_message = check_client_secrets()
    if error_message:
        return f"**Authentication Error:** {error_message}"

    try:
        auth_url, _ = start_auth_flow(
            scopes=SCOPES,
            redirect_uri=get_oauth_redirect_uri_for_current_mode(),
            login_hint=user_google_email
        )
        return (
            "**Action Required: Authenticate with Google**\n\n"
            "Please visit this URL to authenticate:\n\n"
            f"**[Authenticate with Google]({auth_url})**\n\n"
            "After authenticating, retry your request."
        )
    except Exception as e:
        logger.error(f"Failed to start Google authentication flow: {e}", exc_info=True)
        return f"**Error:** An unexpected error occurred: {e}"

# OAuth 2.1 Discovery Endpoints - register manually when OAuth 2.1 is enabled but GoogleRemoteAuthProvider is not available
# These will only be registered if MCP_ENABLE_OAUTH21=true and we're in fallback mode
if os.getenv("MCP_ENABLE_OAUTH21", "false").lower() == "true" and not GOOGLE_REMOTE_AUTH_AVAILABLE:
    from auth.oauth_common_handlers import (
        handle_oauth_authorize,
        handle_proxy_token_exchange,
        handle_oauth_protected_resource,
        handle_oauth_authorization_server,
        handle_oauth_client_config,
        handle_oauth_register
    )
    
    server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])(handle_oauth_protected_resource)
    server.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])(handle_oauth_authorization_server)
    server.custom_route("/.well-known/oauth-client", methods=["GET", "OPTIONS"])(handle_oauth_client_config)
    server.custom_route("/oauth2/authorize", methods=["GET", "OPTIONS"])(handle_oauth_authorize)
    server.custom_route("/oauth2/token", methods=["POST", "OPTIONS"])(handle_proxy_token_exchange)
    server.custom_route("/oauth2/register", methods=["POST", "OPTIONS"])(handle_oauth_register)
