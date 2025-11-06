# API Reference

This document provides detailed reference for the Google Workspace MCP Server APIs, decorators, and patterns.

## Table of Contents

- [Decorators](#decorators)
- [Service Configuration](#service-configuration)
- [Scope Groups](#scope-groups)
- [Tool Structure](#tool-structure)
- [HTTP Endpoints](#http-endpoints)
- [Error Handling](#error-handling)

## Decorators

### `@require_google_service`

Main decorator for authenticating and injecting Google API service clients.

#### Signature

```python
def require_google_service(
    service_type: str,
    scopes: Union[str, List[str]],
    version: Optional[str] = None,
    cache_enabled: bool = True
) -> Callable
```

#### Parameters

- **`service_type`** (str): Service type from `SERVICE_CONFIGS`
  - Examples: `"gmail"`, `"drive"`, `"calendar"`, `"docs"`, `"sheets"`

- **`scopes`** (str | List[str]): Required OAuth scopes
  - Can be scope group names (e.g., `"gmail_read"`)
  - Can be full scope URLs
  - Can be list of either

- **`version`** (str, optional): API version override
  - Default: Uses version from `SERVICE_CONFIGS`
  - Example: `"v1"`, `"v3"`, `"v4"`

- **`cache_enabled`** (bool): Enable service caching
  - Default: `True`
  - Set to `False` to disable caching for this tool

#### Usage

**Single scope**:
```python
@server.tool()
@require_google_service("gmail", "gmail_read")
async def search_messages(service, user_google_email: str, query: str):
    # service is injected automatically
    pass
```

**Multiple scopes**:
```python
@server.tool()
@require_google_service("gmail", ["gmail_read", "gmail_send"])
async def read_and_reply(service, user_google_email: str, message_id: str):
    # service has both read and send permissions
    pass
```

**Custom version**:
```python
@server.tool()
@require_google_service("sheets", "sheets_write", version="v4")
async def update_sheet(service, user_google_email: str, spreadsheet_id: str):
    # Uses Sheets API v4 explicitly
    pass
```

**Disable caching**:
```python
@server.tool()
@require_google_service("drive", "drive_file", cache_enabled=False)
async def create_sensitive_file(service, user_google_email: str, content: str):
    # Service not cached for security
    pass
```

#### Return Value

Returns a decorator that:
1. Authenticates user with specified scopes
2. Builds Google API service client
3. Injects service as first parameter
4. Caches service (if enabled)
5. Handles token refresh automatically

#### Important Notes

- **First parameter must be `service`**: This is injected and hidden from FastMCP
- **Second parameter must be `user_google_email`**: Required for authentication
- **Decorator modifies function signature**: `service` parameter is removed from the tool's visible signature

### `@require_multiple_services`

Decorator for tools that need multiple Google services.

#### Signature

```python
def require_multiple_services(
    service_configs: List[Dict[str, Any]]
) -> Callable
```

#### Parameters

- **`service_configs`** (List[Dict]): List of service configurations
  - Each config is a dictionary with:
    - `service_type` (str): Service type
    - `scopes` (str | List[str]): Required scopes
    - `param_name` (str): Parameter name for injection
    - `version` (str, optional): API version override

#### Usage

```python
from auth.service_decorator import require_multiple_services

@server.tool()
@require_multiple_services([
    {
        "service_type": "drive",
        "scopes": "drive_read",
        "param_name": "drive_service"
    },
    {
        "service_type": "docs",
        "scopes": "docs_read",
        "param_name": "docs_service"
    }
])
async def get_doc_with_metadata(
    drive_service,
    docs_service,
    user_google_email: str,
    doc_id: str
):
    """Get document with Drive metadata."""
    # Both services are injected
    metadata = drive_service.files().get(fileId=doc_id).execute()
    content = docs_service.documents().get(documentId=doc_id).execute()

    return {
        'metadata': metadata,
        'content': content
    }
```

#### Important Notes

- All specified service parameters must come first in function signature
- `user_google_email` must follow all service parameters
- Services are injected with their specified parameter names
- All services use the same caching mechanism

### `@handle_http_errors`

Decorator for standardized HTTP error handling.

#### Signature

```python
def handle_http_errors(
    tool_name: str,
    is_read_only: bool = True,
    service_type: Optional[str] = None
) -> Callable
```

#### Parameters

- **`tool_name`** (str): Name of the tool for error messages
- **`is_read_only`** (bool): Whether tool only reads data
- **`service_type`** (str, optional): Google service type

#### Usage

```python
from core.utils import handle_http_errors

@server.tool()
@handle_http_errors("create_event", is_read_only=False, service_type="calendar")
@require_google_service("calendar", "calendar_events")
async def create_event(service, user_google_email: str, summary: str):
    """Create calendar event with error handling."""
    # HttpError exceptions are caught and formatted
    event = {'summary': summary}
    return service.events().insert(calendarId='primary', body=event).execute()
```

#### Error Handling

Catches and formats:
- `HttpError` (400, 403, 404, 429, 500, etc.)
- Generic exceptions
- Provides user-friendly error messages
- Includes suggestions for resolution

## Service Configuration

### `SERVICE_CONFIGS`

Dictionary mapping service types to API details.

**Location**: `auth/service_decorator.py`

```python
SERVICE_CONFIGS = {
    "gmail": {
        "service": "gmail",
        "version": "v1"
    },
    "drive": {
        "service": "drive",
        "version": "v3"
    },
    "calendar": {
        "service": "calendar",
        "version": "v3"
    },
    "docs": {
        "service": "docs",
        "version": "v1"
    },
    "sheets": {
        "service": "sheets",
        "version": "v4"
    },
    "slides": {
        "service": "slides",
        "version": "v1"
    },
    "forms": {
        "service": "forms",
        "version": "v1"
    },
    "tasks": {
        "service": "tasks",
        "version": "v1"
    },
    "chat": {
        "service": "chat",
        "version": "v1"
    },
    "customsearch": {
        "service": "customsearch",
        "version": "v1"
    }
}
```

### Adding New Services

To add a new Google service:

```python
SERVICE_CONFIGS["newservice"] = {
    "service": "newservice",
    "version": "v1"
}
```

## Scope Groups

### `SCOPE_GROUPS`

Dictionary mapping friendly names to OAuth scope URLs.

**Location**: `auth/service_decorator.py`

```python
SCOPE_GROUPS = {
    # Gmail
    "gmail_read": "https://www.googleapis.com/auth/gmail.readonly",
    "gmail_send": "https://www.googleapis.com/auth/gmail.send",
    "gmail_compose": "https://www.googleapis.com/auth/gmail.compose",
    "gmail_modify": "https://www.googleapis.com/auth/gmail.modify",
    "gmail_labels": "https://www.googleapis.com/auth/gmail.labels",

    # Drive
    "drive_read": "https://www.googleapis.com/auth/drive.readonly",
    "drive_file": "https://www.googleapis.com/auth/drive.file",

    # Docs
    "docs_read": "https://www.googleapis.com/auth/documents.readonly",
    "docs_write": "https://www.googleapis.com/auth/documents",

    # Calendar
    "calendar_read": "https://www.googleapis.com/auth/calendar.readonly",
    "calendar_events": "https://www.googleapis.com/auth/calendar.events",

    # Sheets
    "sheets_read": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "sheets_write": "https://www.googleapis.com/auth/spreadsheets",

    # Slides
    "slides": "https://www.googleapis.com/auth/presentations",
    "slides_read": "https://www.googleapis.com/auth/presentations.readonly",

    # Forms
    "forms": "https://www.googleapis.com/auth/forms.body",
    "forms_read": "https://www.googleapis.com/auth/forms.body.readonly",
    "forms_responses_read": "https://www.googleapis.com/auth/forms.responses.readonly",

    # Tasks
    "tasks": "https://www.googleapis.com/auth/tasks",
    "tasks_read": "https://www.googleapis.com/auth/tasks.readonly",

    # Chat
    "chat_read": "https://www.googleapis.com/auth/chat.messages.readonly",
    "chat_write": "https://www.googleapis.com/auth/chat.messages",
    "chat_spaces": "https://www.googleapis.com/auth/chat.spaces",

    # Custom Search
    "customsearch": "https://www.googleapis.com/auth/cse"
}
```

### Full Scope URLs

**Location**: `auth/scopes.py`

All scope constants are defined with full URLs:

```python
# User info scopes
USERINFO_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
USERINFO_PROFILE_SCOPE = 'https://www.googleapis.com/auth/userinfo.profile'
OPENID_SCOPE = 'openid'

# Gmail scopes
GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
# ... etc
```

### Adding New Scopes

1. **Add constant** in `auth/scopes.py`:
```python
NEW_SERVICE_SCOPE = 'https://www.googleapis.com/auth/newservice'
```

2. **Add to scope group** in `auth/service_decorator.py`:
```python
SCOPE_GROUPS["newservice"] = NEW_SERVICE_SCOPE
```

3. **Add to tool-scopes mapping** in `auth/scopes.py`:
```python
TOOL_SCOPES_MAP = {
    # ... existing mappings ...
    'newservice': [NEW_SERVICE_SCOPE],
}
```

## Tool Structure

### Standard Tool Pattern

```python
"""
Module docstring describing the tools in this file.
"""
import logging
from typing import Optional, List, Dict, Any

from googleapiclient.errors import HttpError

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors

# Module-level logger
logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("tool_name", is_read_only=True, service_type="service")
@require_google_service("service", "scope_group")
async def tool_name(
    service,
    user_google_email: str,
    required_param: str,
    optional_param: Optional[int] = None
) -> Dict[str, Any]:
    """
    Brief description of what the tool does.

    More detailed description with examples and usage notes.

    Args:
        service: Automatically injected Google API service client
        user_google_email: User's Google account email address
        required_param: Description of required parameter
        optional_param: Description of optional parameter (default: None)

    Returns:
        Dictionary containing result data

    Raises:
        HttpError: If API call fails
        ValueError: If parameters are invalid
    """
    # Log tool invocation
    logger.info(f"Tool called for user: {user_google_email}")

    # Validate inputs
    if not required_param:
        raise ValueError("required_param cannot be empty")

    # Use injected service
    try:
        result = service.resource().method(param=required_param).execute()
        logger.debug(f"API call successful: {result}")
        return result
    except HttpError as e:
        logger.error(f"API error: {e}")
        raise
```

### Required Elements

1. **Decorators in order**:
   - `@server.tool()` (first)
   - `@handle_http_errors()` (optional, second)
   - `@require_google_service()` (last)

2. **Function signature**:
   - `service` as first parameter
   - `user_google_email: str` as second parameter
   - Other parameters follow
   - Async function (`async def`)

3. **Docstring**:
   - Brief description
   - Args section with all parameters
   - Returns section
   - Raises section (if applicable)

4. **Type hints**:
   - All parameters typed
   - Return type specified
   - Use `Optional[]` for optional parameters

## HTTP Endpoints

### Custom Routes

#### `GET /health`

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "workspace-mcp",
  "version": "1.2.0",
  "transport": "streamable-http"
}
```

#### `GET /oauth2callback`

OAuth callback handler.

**Query Parameters**:
- `code`: Authorization code from Google
- `state`: State token for CSRF protection
- `error`: Error code (if auth failed)

**Response**: HTML success/error page or redirect

#### `GET /auth/status`

Check authentication status (OAuth 2.1 only).

**Headers**:
- `Authorization: Bearer {token}`

**Response**:
```json
{
  "authenticated": true,
  "email": "user@gmail.com",
  "valid": true,
  "expired": false,
  "expires_at": "2025-01-20T10:30:00",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
}
```

#### `POST /auth/revoke`

Revoke authentication (OAuth 2.1 only).

**Headers**:
- `Authorization: Bearer {token}`

**Response**:
```json
{
  "success": true,
  "email": "user@gmail.com",
  "revoked_with_google": true,
  "message": "Authentication revoked and credentials deleted"
}
```

### OAuth 2.1 Discovery Endpoints

#### `GET /.well-known/oauth-protected-resource`

OAuth 2.1 protected resource metadata.

#### `GET /.well-known/oauth-authorization-server`

OAuth authorization server metadata.

#### `GET /.well-known/oauth-client`

OAuth client configuration.

#### `GET /oauth2/authorize`

OAuth authorization endpoint.

#### `POST /oauth2/token`

Token exchange endpoint.

#### `POST /oauth2/register`

Dynamic client registration endpoint.

## Error Handling

### Exception Types

#### `GoogleAuthenticationError`

Raised when authentication fails.

**Location**: `auth/google_auth.py`

**Common Causes**:
- No credentials found
- Token expired and refresh failed
- Invalid scopes
- Session validation failed

**Handling**:
```python
from auth.google_auth import GoogleAuthenticationError

try:
    service, email = await get_authenticated_google_service(...)
except GoogleAuthenticationError as e:
    # User-friendly error message
    return str(e)
```

#### `HttpError`

Google API HTTP errors.

**Location**: `googleapiclient.errors`

**Common Status Codes**:
- `400`: Bad request (invalid parameters)
- `403`: Forbidden (insufficient permissions)
- `404`: Not found (resource doesn't exist)
- `429`: Rate limit exceeded
- `500`: Internal server error

**Handling**:
```python
from googleapiclient.errors import HttpError

try:
    result = service.files().get(fileId=file_id).execute()
except HttpError as e:
    if e.resp.status == 404:
        return "File not found"
    elif e.resp.status == 403:
        return "Permission denied"
    else:
        raise
```

### Error Response Format

Standard error responses follow this format:

```json
{
  "error": {
    "code": 404,
    "message": "File not found",
    "status": "NOT_FOUND",
    "details": "The requested file does not exist or you don't have access"
  }
}
```

### Token Refresh Errors

When tokens fail to refresh:

```python
from google.auth.exceptions import RefreshError

try:
    credentials.refresh(Request())
except RefreshError as e:
    # Token refresh failed
    # Clear cache and require reauthentication
    clear_service_cache(user_email)
    raise GoogleAuthenticationError(
        f"Token refresh failed for {user_email}. "
        f"Please reauthenticate using start_google_auth tool."
    )
```

## Helper Functions

### `clear_service_cache`

Clear cached services.

```python
from auth.service_decorator import clear_service_cache

# Clear for specific user
count = clear_service_cache(user_email="user@gmail.com")

# Clear all cache
count = clear_service_cache()
```

### `get_cache_stats`

Get cache statistics.

```python
from auth.service_decorator import get_cache_stats

stats = get_cache_stats()
# {
#   "total_entries": 5,
#   "valid_entries": 4,
#   "expired_entries": 1,
#   "cache_ttl_minutes": 30
# }
```

### `get_scopes_for_tools`

Get scopes for specific tools.

```python
from auth.scopes import get_scopes_for_tools

# Get scopes for specific tools
scopes = get_scopes_for_tools(['gmail', 'drive'])

# Get all scopes
scopes = get_scopes_for_tools()
```

## MCP Protocol

### Tool Registration

Tools are automatically registered with FastMCP via the `@server.tool()` decorator.

**Schema Generation**: FastMCP automatically generates JSON schemas from function signatures and docstrings.

**Parameter Visibility**: The `@require_google_service()` decorator modifies the function signature to hide the `service` parameter from the MCP protocol.

### Tool Invocation

Tools are invoked via MCP's `tools/call` method:

```json
{
  "method": "tools/call",
  "params": {
    "name": "search_gmail_messages",
    "arguments": {
      "user_google_email": "user@gmail.com",
      "query": "subject:test"
    }
  }
}
```

### Resource Management

The server implements MCP's resource management protocol for:
- OAuth credentials
- Service instances
- Session data
