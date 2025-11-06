# Development Guide

This document provides guidance for developing and extending the Google Workspace MCP Server.

## Table of Contents

- [Development Setup](#development-setup)
- [Adding New Tools](#adding-new-tools)
- [Testing](#testing)
- [Debugging](#debugging)
- [Code Quality](#code-quality)
- [Publishing](#publishing)

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) for dependency management
- Google Cloud Project with OAuth 2.0 credentials

### Initial Setup

```bash
# Clone repository
git clone https://github.com/taylorwilsdon/google_workspace_mcp.git
cd google_workspace_mcp

# Install dependencies with uv
uv sync

# Create .env file for local development
cp .env.oauth21 .env

# Edit .env with your Google OAuth credentials
# GOOGLE_OAUTH_CLIENT_ID=your-client-id
# GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### Running Locally

```bash
# Stdio mode (default, for MCP clients)
uv run main.py

# HTTP mode (for debugging)
uv run main.py --transport streamable-http

# Single-user mode
uv run main.py --single-user

# Specific tools only
uv run main.py --tools gmail drive calendar

# Combination
uv run main.py --transport streamable-http --tools sheets docs --single-user
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Optional
USER_GOOGLE_EMAIL=your-email@gmail.com
OAUTHLIB_INSECURE_TRANSPORT=1  # Development only
WORKSPACE_MCP_PORT=8000
WORKSPACE_MCP_BASE_URI=http://localhost
MCP_ENABLE_OAUTH21=false  # Set to true for OAuth 2.1
MCP_SINGLE_USER_MODE=0
GOOGLE_PSE_API_KEY=your-api-key  # For Custom Search
GOOGLE_PSE_ENGINE_ID=your-engine-id
```

## Adding New Tools

### Step-by-Step Guide

#### 1. Create Tool Module

Create a new file in the appropriate service directory:

```bash
# Example: Adding a new Gmail tool
touch gmail/new_gmail_tool.py
```

#### 2. Implement Tool Function

```python
"""
Google Gmail Tools - New Feature
"""
import logging
from typing import Optional
from googleapiclient.errors import HttpError

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors

logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("my_new_tool", is_read_only=False, service_type="gmail")
@require_google_service("gmail", ["gmail_read", "gmail_send"])
async def my_new_tool(
    service,
    user_google_email: str,
    recipient: str,
    subject: str,
    body: str,
    cc: Optional[str] = None
) -> dict:
    """
    Send an email with optional CC.

    Args:
        service: Automatically injected Gmail API service client
        user_google_email: User's Google account email address
        recipient: Email address of the recipient
        subject: Email subject line
        body: Email body content
        cc: Optional CC recipient email address

    Returns:
        Dict containing sent message ID and thread ID
    """
    # Build email message
    message = {
        'to': recipient,
        'subject': subject,
        'body': body
    }

    if cc:
        message['cc'] = cc

    # Use the injected service
    result = service.users().messages().send(
        userId='me',
        body=message
    ).execute()

    logger.info(f"Sent email to {recipient} with message ID: {result['id']}")

    return {
        'message_id': result['id'],
        'thread_id': result['threadId']
    }
```

#### 3. Add New Service (If Needed)

If adding a completely new Google service, update `auth/service_decorator.py`:

```python
SERVICE_CONFIGS = {
    # ... existing services ...
    "newservice": {"service": "newservice", "version": "v1"},
}
```

#### 4. Add New Scopes (If Needed)

If adding new OAuth scopes, update `auth/scopes.py`:

```python
# Add scope constant
NEW_SERVICE_SCOPE = 'https://www.googleapis.com/auth/newservice'
NEW_SERVICE_READONLY_SCOPE = 'https://www.googleapis.com/auth/newservice.readonly'

# Add to scope groups
NEW_SERVICE_SCOPES = [
    NEW_SERVICE_SCOPE,
    NEW_SERVICE_READONLY_SCOPE
]

# Add to tool-scopes mapping
TOOL_SCOPES_MAP = {
    # ... existing mappings ...
    'newservice': NEW_SERVICE_SCOPES,
}
```

And update `auth/service_decorator.py`:

```python
SCOPE_GROUPS = {
    # ... existing groups ...
    "newservice": NEW_SERVICE_SCOPE,
    "newservice_read": NEW_SERVICE_READONLY_SCOPE,
}
```

#### 5. Import in main.py

Add the module to `tool_imports` in `main.py`:

```python
tool_imports = {
    'gmail': lambda: __import__('gmail.gmail_tools'),
    'drive': lambda: __import__('gdrive.drive_tools'),
    # ... other imports ...
    'newservice': lambda: __import__('gnewservice.newservice_tools'),
}

tool_icons = {
    'gmail': '📧',
    'drive': '📁',
    # ... other icons ...
    'newservice': '🆕',
}
```

#### 6. Test Your Tool

```bash
# Test with your specific tool enabled
uv run main.py --tools newservice

# Test in HTTP mode for easier debugging
uv run main.py --transport streamable-http --tools newservice
```

### Tool Implementation Patterns

#### Basic Read-Only Tool

```python
@server.tool()
@require_google_service("drive", "drive_read")
async def list_drive_files(service, user_google_email: str, max_results: int = 10):
    """List files in Google Drive."""
    results = service.files().list(
        pageSize=max_results,
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])
```

#### Tool with Multiple Scopes

```python
@server.tool()
@require_google_service("gmail", ["gmail_read", "gmail_send", "gmail_modify"])
async def archive_and_reply(service, user_google_email: str, message_id: str, reply_text: str):
    """Archive message and send reply."""
    # Archive
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['INBOX']}
    ).execute()

    # Reply
    reply = create_reply_message(message_id, reply_text)
    service.users().messages().send(userId='me', body=reply).execute()

    return {"status": "archived_and_replied"}
```

#### Tool with Multiple Services

```python
from auth.service_decorator import require_multiple_services

@server.tool()
@require_multiple_services([
    {"service_type": "drive", "scopes": "drive_read", "param_name": "drive_service"},
    {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"}
])
async def get_doc_with_metadata(
    drive_service,
    docs_service,
    user_google_email: str,
    doc_id: str
):
    """Get document content with Drive metadata."""
    # Get Drive metadata
    metadata = drive_service.files().get(fileId=doc_id).execute()

    # Get document content
    content = docs_service.documents().get(documentId=doc_id).execute()

    return {
        'metadata': metadata,
        'content': content
    }
```

#### Tool with Error Handling

```python
from core.utils import handle_http_errors

@server.tool()
@handle_http_errors("create_calendar_event", is_read_only=False, service_type="calendar")
@require_google_service("calendar", "calendar_events")
async def create_calendar_event(
    service,
    user_google_email: str,
    summary: str,
    start_time: str,
    end_time: str
):
    """Create a calendar event with error handling."""
    event = {
        'summary': summary,
        'start': {'dateTime': start_time},
        'end': {'dateTime': end_time}
    }

    result = service.events().insert(
        calendarId='primary',
        body=event
    ).execute()

    return result
```

## Testing

### Manual Testing

#### Test Authentication Flow

```bash
# 1. Start server in HTTP mode for easier debugging
uv run main.py --transport streamable-http --tools gmail

# 2. In another terminal, test the health endpoint
curl http://localhost:8000/health

# 3. Test authentication (use MCP client or create test script)
# The first call should fail and return an auth URL
# Visit the URL, authorize, then retry
```

#### Test with MCP Inspector

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector with your server
npx @modelcontextprotocol/inspector uv run main.py
```

#### Test OAuth Flow

```bash
# 1. Delete existing credentials
rm -rf .credentials/

# 2. Start server
uv run main.py --transport streamable-http --tools gmail

# 3. Call a tool without authentication
# Should receive auth URL

# 4. Visit auth URL and authorize

# 5. Retry tool call
# Should succeed
```

#### Test Token Refresh

```bash
# 1. Manually edit a credential file to set expired token
# .credentials/user@gmail.com.json
# Set "expiry" to a past timestamp

# 2. Call a tool
# Should automatically refresh token and succeed
```

### Automated Testing

Create tests in `tests/` directory:

```python
# tests/test_gmail_tools.py
import pytest
from unittest.mock import Mock, patch
from gmail.gmail_tools import search_gmail_messages

@pytest.mark.asyncio
async def test_search_messages():
    # Mock the service
    mock_service = Mock()
    mock_service.users().messages().list().execute.return_value = {
        'messages': [{'id': '123', 'threadId': '456'}]
    }

    # Test the function
    result = await search_gmail_messages(
        service=mock_service,
        user_google_email="test@gmail.com",
        query="subject:test"
    )

    assert len(result['messages']) == 1
    assert result['messages'][0]['id'] == '123'
```

Run tests:
```bash
pytest tests/
```

## Debugging

### Log Files

The server writes detailed logs to `mcp_server_debug.log` in the project root:

```bash
# Watch logs in real-time
tail -f mcp_server_debug.log

# Search for errors
grep "ERROR" mcp_server_debug.log

# Filter by module
grep "gmail_tools" mcp_server_debug.log
```

### Debug Logging

Add debug logging to your tools:

```python
import logging
logger = logging.getLogger(__name__)

@server.tool()
@require_google_service("gmail", "gmail_read")
async def my_tool(service, user_google_email: str, param: str):
    logger.debug(f"Tool called with param: {param}")
    logger.info(f"Processing for user: {user_google_email}")

    try:
        result = service.some_operation()
        logger.debug(f"Operation result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in my_tool: {e}", exc_info=True)
        raise
```

### Common Issues and Solutions

#### OAuth Callback 404

**Symptom**: `/oauth2callback` returns 404

**Cause**: Transport mode not set before auth flow starts

**Solution**:
```python
# In main.py, ensure set_transport_mode() is called early
set_transport_mode(args.transport)
# Before any auth operations
```

#### Scope Errors

**Symptom**: Error about missing scopes

**Cause**: Scope not in `SCOPE_GROUPS` or tool not in `TOOL_SCOPES_MAP`

**Solution**:
1. Check scope is defined in `auth/scopes.py`
2. Check scope is in `SCOPE_GROUPS` in `auth/service_decorator.py`
3. Check tool is in `TOOL_SCOPES_MAP` in `auth/scopes.py`

#### Token Refresh Errors

**Symptom**: "Token expired or revoked" errors

**Cause**: Credentials expired or user revoked access

**Solution**:
1. Delete credential file: `rm .credentials/user@gmail.com.json`
2. Reauthenticate using `start_google_auth` tool

#### Import Errors

**Symptom**: Module not found errors

**Cause**: Tool module not imported in `main.py`

**Solution**:
Add to `tool_imports` dict in `main.py`:
```python
tool_imports = {
    'mytool': lambda: __import__('gmytool.mytool_tools'),
}
```

#### Service Not Cached

**Symptom**: Reauthenticating on every request

**Cause**: Cache disabled or cache key mismatch

**Solution**:
1. Check `cache_enabled=True` in decorator (default)
2. Verify scope order is consistent
3. Check cache TTL hasn't expired (30 minutes)

### HTTP Debugging

Use curl or httpie to test HTTP endpoints:

```bash
# Health check
curl http://localhost:8000/health

# Auth status (OAuth 2.1)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/auth/status

# Revoke auth (OAuth 2.1)
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/auth/revoke
```

### Using Python Debugger

Add breakpoints to your code:

```python
import pdb

@server.tool()
@require_google_service("gmail", "gmail_read")
async def my_tool(service, user_google_email: str):
    pdb.set_trace()  # Debugger will pause here
    result = service.users().messages().list().execute()
    return result
```

Or use VS Code debugger with launch configuration:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: MCP Server",
            "type": "python",
            "request": "launch",
            "program": "main.py",
            "args": ["--transport", "streamable-http"],
            "console": "integratedTerminal",
            "env": {
                "OAUTHLIB_INSECURE_TRANSPORT": "1"
            }
        }
    ]
}
```

## Code Quality

### Linting

The project uses `ruff` for linting:

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Hints

Use type hints for all function parameters and return values:

```python
from typing import List, Dict, Optional, Any

@server.tool()
@require_google_service("gmail", "gmail_read")
async def search_messages(
    service,
    user_google_email: str,
    query: str,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Search Gmail messages.

    Args:
        service: Gmail API service client
        user_google_email: User's email address
        query: Search query string
        max_results: Maximum number of results (default: 10)

    Returns:
        List of message dictionaries
    """
    # Implementation
    pass
```

### Docstrings

Follow Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> dict:
    """
    Brief description of function.

    Longer description with more details about what the function does,
    how it works, and any important notes.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is invalid
        HttpError: When API call fails
    """
    pass
```

### Security Best Practices

1. **Never log sensitive data**:
```python
# Bad
logger.info(f"Token: {credentials.token}")

# Good
logger.info(f"Authenticated user: {user_email}")
```

2. **Validate user inputs**:
```python
def send_email(service, user_google_email: str, recipient: str, body: str):
    # Validate email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient):
        raise ValueError(f"Invalid email address: {recipient}")

    # Sanitize body content
    clean_body = sanitize_html(body)

    # Proceed with sending
    # ...
```

3. **Use scope principle of least privilege**:
```python
# Bad - requesting unnecessary scopes
@require_google_service("gmail", ["gmail_read", "gmail_send", "gmail_modify"])
async def read_messages(service, user_google_email: str):
    # Only reading, shouldn't need send/modify
    pass

# Good - only request what you need
@require_google_service("gmail", "gmail_read")
async def read_messages(service, user_google_email: str):
    pass
```

## Publishing

### Building for PyPI

```bash
# Install build dependencies
uv sync --dev

# Build distribution packages
python -m build

# Check the built packages
ls dist/
# workspace-mcp-1.2.0.tar.gz
# workspace_mcp-1.2.0-py3-none-any.whl
```

### Testing Package Locally

```bash
# Install locally
pip install -e .

# Test the CLI
workspace-mcp --help

# Test in a clean environment
uv venv test-env
source test-env/bin/activate
pip install dist/workspace_mcp-1.2.0-py3-none-any.whl
workspace-mcp --transport streamable-http
```

### Publishing to PyPI

```bash
# Install twine
uv sync --dev

# Upload to PyPI (requires PyPI credentials)
twine upload dist/*

# Or upload to Test PyPI first
twine upload --repository testpypi dist/*
```

### Building DXT (Desktop Extension)

DXT files are created for one-click Claude Desktop installation:

```bash
# Build DXT using the DXT builder tool
# (Process depends on your DXT builder setup)

# Verify DXT contains:
# - Server package
# - Dependencies
# - Manifest with configuration schema
```

### Version Management

Update version in `pyproject.toml`:

```toml
[project]
name = "workspace-mcp"
version = "1.3.0"  # Update here
```

Tag release in git:

```bash
git tag -a v1.3.0 -m "Release version 1.3.0"
git push origin v1.3.0
```
