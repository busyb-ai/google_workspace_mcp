# Architecture

This document describes the core architecture and design patterns of the Google Workspace MCP Server.

## Table of Contents

- [Core Design Patterns](#core-design-patterns)
- [Authentication Architecture](#authentication-architecture)
- [Key Modules](#key-modules)
- [Tool Module Structure](#tool-module-structure)
- [Service Caching](#service-caching)
- [OAuth Flow Details](#oauth-flow-details)

## Core Design Patterns

### Service Decorator Pattern

The `@require_google_service()` decorator is the heart of the architecture. It automatically:
- Authenticates users via OAuth 2.0/2.1
- Injects authenticated Google API service clients
- Caches services for 30 minutes (TTL)
- Handles token refresh errors gracefully
- Manages scope resolution from string names to URLs

**How it works**:
1. Decorator intercepts function call
2. Extracts `user_google_email` from function arguments
3. Checks service cache for existing authenticated service
4. If not cached, initiates authentication flow
5. Builds Google API service client with credentials
6. Injects service as first parameter to function
7. Caches service for future calls
8. Returns function result

**Example**:
```python
from auth.service_decorator import require_google_service
from core.server import server

@server.tool()
@require_google_service("gmail", "gmail_read")
async def search_messages(service, user_google_email: str, query: str):
    """
    Search Gmail messages.

    Args:
        service: Injected by decorator (hidden from FastMCP)
        user_google_email: User's email address
        query: Gmail search query
    """
    results = service.users().messages().list(userId='me', q=query).execute()
    return results
```

The decorator modifies the function signature to hide `service` from FastMCP, so it only sees `user_google_email` and `query` as tool parameters.

### Transport-Aware OAuth

The server automatically adapts OAuth callback handling based on transport mode:

- **stdio mode**:
  - Launched via `uv run main.py` (default)
  - Automatically starts a minimal HTTP server on port 8000 for OAuth callbacks
  - Used by MCP clients (Claude Desktop, etc.)

- **streamable-http mode**:
  - Launched via `uv run main.py --transport streamable-http`
  - Uses the existing FastAPI server for OAuth callbacks
  - Used for web interfaces, debugging, and API integrations

**Both modes use `http://localhost:8000/oauth2callback` for consistency**, ensuring the same OAuth configuration works regardless of transport.

### Dual Authentication Modes

The server supports two authentication architectures:

#### 1. Legacy OAuth 2.0 (Single-User Focus)
- Tool-based authentication using `start_google_auth` tool
- File-based credential storage in `.credentials/{email}.json`
- PKCE flow for security
- Simple for single-user scenarios
- No bearer token management

#### 2. OAuth 2.1 (Multi-User)
- Remote authentication with bearer tokens
- Session management via `oauth21_session_store`
- Multi-user support with session isolation
- CORS proxy architecture for browser-based clients
- Enabled with `MCP_ENABLE_OAUTH21=true`

## Authentication Architecture

### AuthInfoMiddleware Flow

```
┌─────────────────┐
│   MCP Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  AuthInfoMiddleware     │
│  - Extract bearer token │
│  - Verify token         │
│  - Set auth context     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  FastMCP Context        │
│  authenticated_user_    │
│  email: user@email.com  │
│  authenticated_via:     │
│  oauth21 / legacy       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  @require_google_       │
│  service decorator      │
│  - Get auth from context│
│  - Load Google creds    │
│  - Build service        │
│  - Inject into function │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Tool Function          │
│  (with service injected)│
└─────────────────────────┘
```

### Credential Storage

**Legacy OAuth 2.0**:
```
.credentials/
├── user1@gmail.com.json
├── user2@gmail.com.json
└── ...
```

Each file contains Google OAuth credentials (access_token, refresh_token, scopes, expiry).

**OAuth 2.1**:
- In-memory session store (thread-safe)
- Maps session IDs to credentials
- Maps MCP session IDs to Google session IDs
- Validates session ownership before credential access

## Key Modules

### `auth/service_decorator.py`

The authentication engine containing:

- **`@require_google_service(service_type, scopes)`**: Main decorator
  - `service_type`: Service name from `SERVICE_CONFIGS` (e.g., "gmail", "drive")
  - `scopes`: Scope names or list of scope names (e.g., "gmail_read", ["gmail_read", "gmail_send"])
  - `version`: Optional version override
  - `cache_enabled`: Default True, set False to disable caching

- **`@require_multiple_services([{...}])`**: For tools needing multiple services
  - Takes list of service configs
  - Each config: `{service_type, scopes, param_name, version?}`
  - Injects multiple services with specified parameter names

- **`SERVICE_CONFIGS`**: Maps service types to API details
  ```python
  SERVICE_CONFIGS = {
      "gmail": {"service": "gmail", "version": "v1"},
      "drive": {"service": "drive", "version": "v3"},
      "calendar": {"service": "calendar", "version": "v3"},
      # ... etc
  }
  ```

- **`SCOPE_GROUPS`**: Maps friendly names to scope URLs
  ```python
  SCOPE_GROUPS = {
      "gmail_read": "https://www.googleapis.com/auth/gmail.readonly",
      "gmail_send": "https://www.googleapis.com/auth/gmail.send",
      "drive_file": "https://www.googleapis.com/auth/drive.file",
      # ... etc
  }
  ```

- **Service Cache**: `_service_cache` dictionary
  - Key: `{user_email}:{service_name}:{version}:{sorted_scopes}`
  - Value: `(service, cached_time, user_email)`
  - TTL: 30 minutes
  - Thread-safe (Python GIL)

### `auth/scopes.py`

Centralized scope management:

- **Constants**: All scope URLs defined as constants
  - `GMAIL_READONLY_SCOPE`, `DRIVE_FILE_SCOPE`, etc.
  - `BASE_SCOPES`: Required for user identification (email, profile, openid)

- **Scope Groups**: Service-specific collections
  - `GMAIL_SCOPES`, `DRIVE_SCOPES`, `CALENDAR_SCOPES`, etc.

- **`TOOL_SCOPES_MAP`**: Maps tool names to scope lists
  ```python
  TOOL_SCOPES_MAP = {
      'gmail': GMAIL_SCOPES,
      'drive': DRIVE_SCOPES,
      'calendar': CALENDAR_SCOPES,
      # ... etc
  }
  ```

- **`get_scopes_for_tools(enabled_tools)`**: Returns scopes for specific tools
  - Prevents scope sprawl
  - Only requests scopes for enabled tools
  - Always includes `BASE_SCOPES`

- **`set_enabled_tools(enabled_tools)`**: Called by `main.py`
  - Sets global `_ENABLED_TOOLS` variable
  - Used by `get_current_scopes()` for auth flows

### `core/server.py`

FastMCP server configuration and custom routes:

- **`CORSEnabledFastMCP`**: Custom FastMCP subclass
  - Adds CORS middleware to streamable-http transport
  - Adds session middleware for session tracking
  - Rebuilds middleware stack to ensure proper order

- **Server Instance**: `server = CORSEnabledFastMCP(name="google_workspace", auth=None)`
  - `auth=None` for legacy mode
  - `auth=GoogleRemoteAuthProvider()` when OAuth 2.1 enabled

- **Custom Routes**:
  - `GET /health`: Health check endpoint
  - `GET /oauth2callback`: OAuth callback handler (both modes)
  - `GET /auth/status`: Check authentication status (OAuth 2.1)
  - `POST /auth/revoke`: Revoke credentials and delete session (OAuth 2.1)

- **OAuth 2.1 Discovery Endpoints** (when enabled):
  - `GET /.well-known/oauth-protected-resource`
  - `GET /.well-known/oauth-authorization-server`
  - `GET /.well-known/oauth-client`
  - `GET /oauth2/authorize`
  - `POST /oauth2/token`
  - `POST /oauth2/register`

- **Tools**:
  - `start_google_auth(service_name, user_google_email)`: Entry point for legacy auth

### `auth/oauth21_session_store.py`

Multi-user session management:

- **`OAuth21SessionStore`**: Thread-safe session storage
  - `_sessions: Dict[str, SessionData]`: Maps session IDs to Google credentials
  - `_mcp_to_google_session: Dict[str, str]`: Maps MCP session IDs to Google session IDs
  - `_user_email_to_sessions: Dict[str, Set[str]]`: Maps user emails to their session IDs

- **Key Methods**:
  - `store_session()`: Store credentials for a session
  - `get_credentials(user_email)`: Retrieve credentials by email
  - `get_credentials_with_validation()`: Security-validated credential retrieval
  - `remove_session(user_email)`: Delete session
  - `refresh_credentials()`: Refresh expired tokens

- **Security**: Ensures sessions can only access their own credentials through validation

### `auth/google_auth.py`

Legacy OAuth implementation:

- **`get_authenticated_google_service()`**: Legacy authentication flow
  - Checks for existing credentials in `.credentials/`
  - Validates and refreshes tokens if needed
  - Returns authenticated service client

- **`start_auth_flow(scopes, redirect_uri, login_hint)`**: Initiate OAuth flow
  - Creates PKCE challenge
  - Generates state token for CSRF protection
  - Returns authorization URL

- **`handle_auth_callback()`**: Process OAuth callback
  - Validates state token
  - Exchanges authorization code for tokens
  - Stores credentials to file
  - Returns verified user email and credentials

- **File Storage**: Credentials stored as JSON in `.credentials/{email}.json`

### `core/config.py`

Shared configuration to avoid circular imports:

```python
# Server configuration
WORKSPACE_MCP_PORT = int(os.getenv("PORT", os.getenv("WORKSPACE_MCP_PORT", 8000)))
WORKSPACE_MCP_BASE_URI = os.getenv("WORKSPACE_MCP_BASE_URI", "http://localhost")
USER_GOOGLE_EMAIL = os.getenv("USER_GOOGLE_EMAIL", None)

# Transport mode management
_current_transport_mode = "stdio"  # Default

def set_transport_mode(mode: str): ...
def get_transport_mode() -> str: ...
def get_oauth_redirect_uri() -> str: ...
```

## Tool Module Structure

Each Google service has its own module in `g{service}/`:

```
gmail/
├── __init__.py
└── gmail_tools.py

gdrive/
├── __init__.py
└── drive_tools.py

gcalendar/
├── __init__.py
└── calendar_tools.py
```

### Tool Implementation Pattern

```python
# 1. Import required modules
from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors
import logging

logger = logging.getLogger(__name__)

# 2. Register tool with decorators
@server.tool()
@handle_http_errors("tool_name", is_read_only=True, service_type="service")
@require_google_service("service_type", "scope_group")
async def tool_name(service, user_google_email: str, param1: str, param2: int = 10):
    """
    Tool description.

    Args:
        service: Automatically injected Google API service client
        user_google_email: User's Google account email
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Description of return value
    """
    # 3. Use service directly
    result = service.users().method().execute()

    # 4. Process and return
    return result
```

**Important Notes**:
- `@server.tool()` must be first decorator
- `@require_google_service()` must be second (or after `@handle_http_errors()`)
- First parameter must be `service` (injected, hidden from FastMCP)
- Second parameter must be `user_google_email: str` (required for auth)
- Remaining parameters are the actual tool parameters

## Service Caching

### Cache Key Generation

```python
def _get_cache_key(user_email: str, service_name: str, version: str, scopes: List[str]) -> str:
    sorted_scopes = sorted(scopes)
    return f"{user_email}:{service_name}:{version}:{':'.join(sorted_scopes)}"
```

Example: `"user@gmail.com:gmail:v1:https://www.googleapis.com/auth/gmail.readonly"`

### Cache Lifecycle

1. **Cache Check**: Decorator checks for existing cached service
2. **Cache Hit**: Return cached service (if TTL valid)
3. **Cache Miss**: Authenticate and build new service
4. **Cache Store**: Store service with timestamp
5. **Cache Expiry**: After 30 minutes, entry is removed on next access

### Cache Management

```python
# Clear cache for specific user
clear_service_cache(user_email="user@gmail.com")

# Clear entire cache
clear_service_cache()

# Get cache statistics
stats = get_cache_stats()
# Returns: {total_entries, valid_entries, expired_entries, cache_ttl_minutes}
```

### When Cache is Cleared

- Token refresh errors (automatic)
- User revokes authentication
- Manual cache clear via `clear_service_cache()`

## OAuth Flow Details

### Legacy OAuth 2.0 Flow

```
1. User calls tool without authentication
   ↓
2. Tool decorator checks for credentials
   ↓
3. No credentials found → Raise GoogleAuthenticationError
   ↓
4. LLM calls start_google_auth(service_name, user_google_email)
   ↓
5. Server generates auth URL with PKCE challenge
   ↓
6. User visits URL and authorizes
   ↓
7. Google redirects to /oauth2callback with code
   ↓
8. Server exchanges code for tokens (validates PKCE)
   ↓
9. Credentials stored to .credentials/{email}.json
   ↓
10. LLM retries original tool call
   ↓
11. Tool decorator finds credentials → Success
```

### OAuth 2.1 Flow

```
1. Client requests authorization
   POST /oauth2/authorize → Returns auth URL
   ↓
2. User authorizes via Google
   ↓
3. Client exchanges code for tokens
   POST /oauth2/token → Returns bearer token
   ↓
4. Client includes bearer token in MCP requests
   Authorization: Bearer {token}
   ↓
5. AuthInfoMiddleware extracts authenticated user email
   ↓
6. Tool decorator validates session can access credentials
   ↓
7. Tool executes with user's Google credentials
```

### Transport Mode Handling

The server must know its transport mode before starting OAuth flows:

```python
# In main.py
set_transport_mode(args.transport)  # 'stdio' or 'streamable-http'

# OAuth callback handling adapts:
if get_transport_mode() == 'stdio':
    # Start minimal HTTP server on port 8000
    ensure_oauth_callback_available('stdio', port, base_uri)
else:
    # Use main FastAPI server
    configure_server_for_http()
```

### OAuth 2.1 CORS Proxy

The server implements an innovative CORS proxy architecture:

**Problem 1: No Dynamic Client Registration**
- Google doesn't support OAuth 2.1 dynamic client registration
- Solution: Server proxies registration requests and returns pre-configured Google OAuth credentials

**Problem 2: Missing CORS Headers**
- Google OAuth endpoints don't include CORS headers
- Blocks browser-based clients
- Solution: Server proxies token exchange and adds CORS headers

**Proxy Endpoints**:
- `/auth/discovery/authorization-server/{server}`: Proxy discovery requests
- `/oauth2/token`: Proxy token exchange with CORS headers
- `/oauth2/register`: Proxy registration (returns pre-configured credentials)

**Security**: Only proxies to known Google OAuth endpoints (`accounts.google.com`, `oauth2.googleapis.com`)
