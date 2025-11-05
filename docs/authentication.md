# Authentication

This document details the authentication mechanisms used in the Google Workspace MCP Server.

## Table of Contents

- [Overview](#overview)
- [Legacy OAuth 2.0](#legacy-oauth-20)
- [OAuth 2.1 Multi-User](#oauth-21-multi-user)
- [Credential Management](#credential-management)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Overview

The server supports two authentication modes:

1. **Legacy OAuth 2.0**: File-based credentials, tool-based auth flow, simple single-user setup
2. **OAuth 2.1**: Bearer token authentication, multi-user sessions, browser-compatible

Both modes use Google OAuth with PKCE (Proof Key for Code Exchange) for security.

## Legacy OAuth 2.0

### Architecture

- **Credential Storage**: File-based in `.credentials/{email}.json`
- **Authentication Trigger**: Tools raise `GoogleAuthenticationError` when unauthenticated
- **Auth Initiation**: LLM calls `start_google_auth(service_name, user_google_email)` tool
- **Callback Handling**: Server processes callback at `/oauth2callback`
- **Scope Management**: All enabled tool scopes requested upfront

### Authentication Flow

```
┌──────────────────────────┐
│ 1. User calls MCP tool   │
│    (no credentials)      │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 2. @require_google_      │
│    service decorator     │
│    checks for creds      │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 3. No creds found        │
│    Raise GoogleAuth      │
│    enticationError       │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 4. LLM receives error    │
│    Calls start_google_   │
│    auth tool             │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 5. Server generates      │
│    auth URL with PKCE    │
│    Returns URL to LLM    │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 6. User visits URL       │
│    Authorizes with       │
│    Google                │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 7. Google redirects to   │
│    /oauth2callback       │
│    with code             │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 8. Server exchanges      │
│    code for tokens       │
│    Validates PKCE        │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 9. Credentials stored    │
│    to .credentials/      │
│    {email}.json          │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 10. LLM retries original │
│     tool call            │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 11. Decorator finds      │
│     credentials          │
│     Tool succeeds        │
└──────────────────────────┘
```

### Implementation Details

#### Starting Auth Flow

In `auth/google_auth.py`:

```python
def start_auth_flow(
    scopes: List[str],
    redirect_uri: str,
    login_hint: Optional[str] = None
) -> Tuple[str, str]:
    """
    Initiate OAuth flow with PKCE.

    Returns:
        Tuple of (authorization_url, state_token)
    """
    # Create flow with PKCE
    flow = Flow.from_client_config(
        client_config=get_client_config(),
        scopes=scopes,
        redirect_uri=redirect_uri
    )

    # Generate PKCE code verifier and challenge
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')

    # Store verifier for callback validation
    _store_code_verifier(state, code_verifier)

    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        login_hint=login_hint,
        prompt='consent',
        code_challenge=code_challenge,
        code_challenge_method='S256'
    )

    return authorization_url, state
```

#### Handling Callback

```python
def handle_auth_callback(
    scopes: List[str],
    authorization_response: str,
    redirect_uri: str,
    session_id: Optional[str] = None
) -> Tuple[str, Any]:
    """
    Handle OAuth callback and exchange code for tokens.

    Returns:
        Tuple of (verified_user_email, credentials)
    """
    # Extract state from response
    state = extract_state_from_url(authorization_response)

    # Retrieve and validate PKCE verifier
    code_verifier = _retrieve_code_verifier(state)
    if not code_verifier:
        raise GoogleAuthenticationError("Invalid state token")

    # Create flow and fetch token
    flow = Flow.from_client_config(
        client_config=get_client_config(),
        scopes=scopes,
        redirect_uri=redirect_uri,
        state=state
    )

    flow.fetch_token(
        authorization_response=authorization_response,
        code_verifier=code_verifier
    )

    credentials = flow.credentials

    # Verify user identity
    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        requests.Request(),
        credentials.client_id
    )
    user_email = id_info['email']

    # Store credentials
    store_credentials(user_email, credentials)

    return user_email, credentials
```

#### Credential Storage

```python
def store_credentials(user_email: str, credentials) -> None:
    """Store credentials to file."""
    creds_dir = DEFAULT_CREDENTIALS_DIR  # .credentials/
    os.makedirs(creds_dir, exist_ok=True)

    creds_path = os.path.join(creds_dir, f"{user_email}.json")

    creds_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
    }

    with open(creds_path, 'w') as f:
        json.dump(creds_data, f, indent=2)

    # Set restrictive permissions (owner only)
    os.chmod(creds_path, 0o600)
```

#### Loading Credentials

```python
def load_credentials(user_email: str) -> Optional[Credentials]:
    """Load credentials from file."""
    creds_path = os.path.join(DEFAULT_CREDENTIALS_DIR, f"{user_email}.json")

    if not os.path.exists(creds_path):
        return None

    with open(creds_path, 'r') as f:
        creds_data = json.load(f)

    credentials = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data['refresh_token'],
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    if creds_data.get('expiry'):
        credentials.expiry = datetime.fromisoformat(creds_data['expiry'])

    return credentials
```

### Token Refresh

When tokens expire, they're automatically refreshed:

```python
async def get_authenticated_google_service(
    service_name: str,
    version: str,
    tool_name: str,
    user_google_email: str,
    required_scopes: List[str],
    session_id: Optional[str] = None
) -> Tuple[Any, str]:
    """Get authenticated service with automatic token refresh."""
    credentials = load_credentials(user_google_email)

    if not credentials:
        raise GoogleAuthenticationError(
            f"No credentials found for {user_google_email}. "
            f"Please authenticate using start_google_auth tool."
        )

    # Check if token needs refresh
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            store_credentials(user_google_email, credentials)
            logger.info(f"Refreshed token for {user_google_email}")
        except RefreshError as e:
            # Token refresh failed - delete invalid credentials
            delete_credentials(user_google_email)
            raise GoogleAuthenticationError(
                f"Token refresh failed for {user_google_email}. "
                f"Please reauthenticate using start_google_auth tool."
            )

    # Build and return service
    service = build(service_name, version, credentials=credentials)
    return service, user_google_email
```

## OAuth 2.1 Multi-User

### Architecture

- **Session Storage**: In-memory thread-safe session store
- **Token Type**: Bearer tokens (JWT)
- **Authentication**: `Authorization: Bearer {token}` header
- **Multi-User**: Isolated sessions per user
- **CORS Support**: Proxy endpoints for browser clients

### Enabling OAuth 2.1

Set environment variable:
```bash
export MCP_ENABLE_OAUTH21=true
```

Or in `.env`:
```
MCP_ENABLE_OAUTH21=true
```

Server must be running in `streamable-http` mode:
```bash
uv run main.py --transport streamable-http
```

### Authentication Flow

```
┌──────────────────────────┐
│ 1. Client requests auth  │
│    GET /oauth2/authorize │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 2. Server returns Google │
│    authorization URL     │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 3. User authorizes with  │
│    Google                │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 4. Google redirects to   │
│    /oauth2callback       │
│    with code             │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 5. Client exchanges code │
│    POST /oauth2/token    │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 6. Server returns bearer │
│    token (JWT)           │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 7. Client includes token │
│    in MCP requests       │
│    Authorization: Bearer │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 8. AuthInfoMiddleware    │
│    extracts user email   │
│    from token            │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 9. Tool decorator        │
│    validates session     │
│    access                │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ 10. Tool executes with   │
│     user's Google creds  │
└──────────────────────────┘
```

### Session Store

In `auth/oauth21_session_store.py`:

```python
class SessionData:
    """Data stored for each OAuth session."""
    user_email: str
    access_token: str
    refresh_token: Optional[str]
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    expiry: Optional[datetime]
    session_id: str  # Google session ID
    mcp_session_id: Optional[str]  # MCP session ID
    created_at: datetime
    last_accessed: datetime


class OAuth21SessionStore:
    """Thread-safe session storage for OAuth 2.1."""

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._mcp_to_google_session: Dict[str, str] = {}
        self._user_email_to_sessions: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def store_session(
        self,
        user_email: str,
        access_token: str,
        refresh_token: Optional[str],
        token_uri: str,
        client_id: str,
        client_secret: str,
        scopes: List[str],
        expiry: Optional[datetime],
        session_id: str,
        mcp_session_id: Optional[str] = None
    ) -> None:
        """Store session data."""
        with self._lock:
            session_data = SessionData(
                user_email=user_email,
                access_token=access_token,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
                expiry=expiry,
                session_id=session_id,
                mcp_session_id=mcp_session_id,
                created_at=datetime.now(),
                last_accessed=datetime.now()
            )

            self._sessions[user_email] = session_data

            if mcp_session_id:
                self._mcp_to_google_session[mcp_session_id] = session_id

            if user_email not in self._user_email_to_sessions:
                self._user_email_to_sessions[user_email] = set()
            self._user_email_to_sessions[user_email].add(session_id)

    def get_credentials_with_validation(
        self,
        requested_user_email: str,
        session_id: Optional[str] = None,
        auth_token_email: Optional[str] = None,
        allow_recent_auth: bool = False
    ) -> Optional[Credentials]:
        """
        Get credentials with security validation.

        Ensures sessions can only access their own credentials.
        """
        with self._lock:
            # Validation: ensure requesting session owns the credentials
            if auth_token_email and auth_token_email != requested_user_email:
                logger.warning(
                    f"Session for {auth_token_email} attempted to access "
                    f"credentials for {requested_user_email} - DENIED"
                )
                return None

            session_data = self._sessions.get(requested_user_email)
            if not session_data:
                return None

            # Update last accessed
            session_data.last_accessed = datetime.now()

            # Build credentials object
            credentials = Credentials(
                token=session_data.access_token,
                refresh_token=session_data.refresh_token,
                token_uri=session_data.token_uri,
                client_id=session_data.client_id,
                client_secret=session_data.client_secret,
                scopes=session_data.scopes
            )

            if session_data.expiry:
                credentials.expiry = session_data.expiry

            return credentials
```

### Bearer Token Generation

The server generates JWTs for bearer tokens:

```python
import jwt
from datetime import datetime, timedelta

def generate_bearer_token(user_email: str, session_id: str) -> str:
    """Generate JWT bearer token."""
    payload = {
        'email': user_email,
        'session_id': session_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=24)
    }

    # Sign with secret key
    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm='HS256'
    )

    return token
```

### AuthInfoMiddleware

Extracts authentication info from requests:

```python
class AuthInfoMiddleware:
    """Middleware to extract auth info and inject into FastMCP context."""

    async def __call__(self, ctx: Context, next):
        """Process request and extract authentication."""
        authenticated_user = None
        auth_method = None

        # Try to get bearer token from Authorization header
        if hasattr(ctx, 'request'):
            auth_header = ctx.request.headers.get('authorization', '')

            if auth_header.lower().startswith('bearer '):
                token = auth_header[7:]  # Remove "Bearer " prefix

                try:
                    # Verify and decode JWT
                    payload = jwt.decode(
                        token,
                        SECRET_KEY,
                        algorithms=['HS256']
                    )

                    authenticated_user = payload.get('email')
                    auth_method = 'oauth21'

                    logger.debug(f"Authenticated via OAuth 2.1: {authenticated_user}")

                except jwt.ExpiredSignatureError:
                    logger.warning("Bearer token expired")
                except jwt.InvalidTokenError:
                    logger.warning("Invalid bearer token")

        # Set in context for decorator to use
        if authenticated_user:
            ctx.set_state('authenticated_user_email', authenticated_user)
            ctx.set_state('authenticated_via', auth_method)

        # Continue processing
        return await next()
```

### CORS Proxy Implementation

For browser clients, the server proxies Google OAuth endpoints:

#### Discovery Endpoint Proxy

```python
@server.custom_route("/auth/discovery/authorization-server/{server:path}", methods=["GET", "OPTIONS"])
async def proxy_auth_server_discovery(request: Request, server: str):
    """Proxy Google's authorization server discovery endpoint."""
    if request.method == "OPTIONS":
        return handle_cors_preflight()

    # Only proxy known Google servers
    if server not in ALLOWED_SERVERS:
        return JSONResponse(
            status_code=400,
            content={"error": "Unknown authorization server"}
        )

    # Fetch from Google
    google_url = f"https://{server}/.well-known/oauth-authorization-server"
    async with httpx.AsyncClient() as client:
        response = await client.get(google_url)

    # Add CORS headers
    return JSONResponse(
        content=response.json(),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )
```

#### Token Exchange Proxy

```python
@server.custom_route("/oauth2/token", methods=["POST", "OPTIONS"])
async def proxy_token_exchange(request: Request):
    """Proxy token exchange request to Google with CORS headers."""
    if request.method == "OPTIONS":
        return handle_cors_preflight()

    # Get request body
    body = await request.body()

    # Forward to Google
    google_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            google_url,
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

    # Return with CORS headers
    return JSONResponse(
        content=response.json(),
        status_code=response.status_code,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )
```

## Credential Management

### Credential Loading Priority

The server loads OAuth client credentials in this order:

1. **Environment Variables** (highest priority)
   ```bash
   export GOOGLE_OAUTH_CLIENT_ID="..."
   export GOOGLE_OAUTH_CLIENT_SECRET="..."
   ```

2. **`.env` File**
   ```
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```

3. **`client_secret.json` at Custom Path**
   ```bash
   export GOOGLE_CLIENT_SECRET_PATH="/path/to/client_secret.json"
   ```

4. **`client_secret.json` in Project Root** (lowest priority)

### Credential Storage

The server supports two storage backends for user OAuth credentials:

1. **Local File System** (default)
2. **AWS S3** (for distributed deployments)

Storage location is configured via the `GOOGLE_MCP_CREDENTIALS_DIR` environment variable.

#### Local File System Storage

**Default Path**: `.credentials/` in project root

**Configuration**:
```bash
# Use default local storage
# No configuration needed - this is the default

# Or explicitly set local path
export GOOGLE_MCP_CREDENTIALS_DIR="/path/to/credentials"
```

**File Location**: `{GOOGLE_MCP_CREDENTIALS_DIR}/{email}.json`

**Example**: `.credentials/user@gmail.com.json`

**Security**:
- File permissions set to `0o600` (owner read/write only)
- Directory permissions restricted to owner
- Credentials stored only on local machine

**Use Cases**:
- Single-server deployments
- Local development
- Desktop applications (Claude Desktop)
- Offline environments

#### AWS S3 Storage

**Path Format**: `s3://bucket-name/path/`

**Configuration**:
```bash
# Set S3 path for credential storage
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket/credentials/"

# Configure AWS credentials (one of these methods)
# Method 1: Environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"

# Method 2: IAM role (recommended for production on AWS)
# No additional configuration needed - uses instance IAM role

# Method 3: AWS credentials file
# Uses ~/.aws/credentials automatically
```

**File Location**: `s3://bucket-name/path/{email}.json`

**Example**: `s3://workspace-mcp-creds/prod/user@gmail.com.json`

**Security**:
- Server-side encryption (SSE-S3 AES256) enabled automatically
- IAM-based access control
- S3 bucket versioning (optional, recommended)
- VPC endpoints for private access (optional)
- Audit logging via CloudTrail

**Use Cases**:
- Multi-server deployments
- Container orchestration (Kubernetes, ECS)
- High availability setups
- Credential sharing across instances
- Centralized credential management

**Required IAM Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

#### Storage Type Comparison

| Feature | Local File System | AWS S3 |
|---------|------------------|---------|
| **Setup Complexity** | Simple (default) | Moderate (requires AWS setup) |
| **Multi-Server** | No | Yes |
| **High Availability** | No | Yes (S3 99.999999999% durability) |
| **Access Control** | File permissions | IAM policies |
| **Encryption** | Optional (OS-level) | Automatic (SSE-S3) |
| **Versioning** | No (unless manual backup) | Yes (S3 versioning) |
| **Audit Logging** | Manual | Automatic (CloudTrail) |
| **Cost** | Free (storage included) | ~$0.001/user/month |
| **Latency** | Very low (<1ms) | Low (~50-200ms) |
| **Best For** | Single server, development | Production, distributed systems |

#### Credential File Format

The JSON format is identical for both local and S3 storage.

**OAuth Client Configuration** (`client_secret.json`):
```json
{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "client_secret": "your-client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost:8000/oauth2callback"]
  }
}
```

**User Credentials** (stored at `{email}.json`):
```json
{
  "token": "ya29.a0AfH6SMB...",
  "refresh_token": "1//0gZ1...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "your-client-id.apps.googleusercontent.com",
  "client_secret": "your-client-secret",
  "scopes": [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
  ],
  "expiry": "2025-01-20T10:30:00"
}
```

**Note**: The server automatically detects storage type based on the `s3://` prefix in `GOOGLE_MCP_CREDENTIALS_DIR`.

### Revoking Credentials

**Legacy OAuth 2.0 - Local Storage**:
```bash
# Delete credential file from local storage
rm .credentials/user@gmail.com.json

# Optionally revoke with Google
curl -X POST "https://oauth2.googleapis.com/revoke?token={access_token}"
```

**Legacy OAuth 2.0 - S3 Storage**:
```bash
# Delete credential file from S3
aws s3 rm s3://your-bucket/credentials/user@gmail.com.json

# Optionally revoke with Google
curl -X POST "https://oauth2.googleapis.com/revoke?token={access_token}"
```

**OAuth 2.1**:
```bash
# Use revoke endpoint (works with both local and S3 storage)
curl -X POST \
  -H "Authorization: Bearer {token}" \
  http://localhost:8000/auth/revoke
```

The `/auth/revoke` endpoint automatically handles credential deletion from the configured storage backend (local or S3).

## Security Considerations

### PKCE (Proof Key for Code Exchange)

All OAuth flows use PKCE to prevent authorization code interception:

1. **Code Verifier**: Random 32-byte value
2. **Code Challenge**: SHA256 hash of verifier, base64url encoded
3. **Authorization Request**: Includes code_challenge
4. **Token Exchange**: Includes code_verifier for validation

### Token Storage Security

#### Local File System Security

- **File Permissions**: Credential files set to `0o600` (owner read/write only)
- **Directory Permissions**: `.credentials/` directory restricted to owner
- **Single Machine**: Credentials only accessible on the local machine
- **No Logging**: Tokens never logged

#### AWS S3 Storage Security

- **Encryption at Rest**: Server-side encryption (SSE-S3 AES256) enabled automatically
- **Encryption in Transit**: All S3 communication over HTTPS (TLS)
- **IAM Access Control**: Access controlled via AWS IAM policies (not file permissions)
- **Bucket Privacy**: Bucket configured as private (no public access)
- **Versioning**: Optional S3 versioning for credential recovery
- **Audit Logging**: All access logged via AWS CloudTrail
- **VPC Endpoints**: Optional VPC endpoints for private network access (no internet exposure)
- **No Logging**: Tokens never logged by application

**S3 Security Best Practices**:

1. **Use IAM Roles** instead of access keys when running on AWS infrastructure
2. **Enable MFA Delete** on S3 bucket for production environments
3. **Configure Bucket Policies** to restrict access to specific IP ranges or VPCs
4. **Enable CloudTrail** logging to audit all credential access
5. **Use KMS Encryption** (SSE-KMS) for additional key management control (optional)
6. **Set Lifecycle Policies** to delete old credential versions after retention period

**Example S3 Bucket Policy** (restrict to specific VPC):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ],
      "Condition": {
        "StringNotEquals": {
          "aws:SourceVpc": "vpc-12345678"
        }
      }
    }
  ]
}
```

#### OAuth 2.1 Session Security

- **In-Memory Storage**: OAuth 2.1 sessions stored in memory (volatile, cleared on restart)
- **File/S3 Backup**: User credentials backed up to configured storage (local or S3)
- **Session Isolation**: Enforced session-to-user credential mapping

### Session Isolation

OAuth 2.1 enforces strict session isolation:

```python
def get_credentials_with_validation(
    self,
    requested_user_email: str,
    auth_token_email: Optional[str] = None
):
    """Validate session can only access its own credentials."""
    if auth_token_email and auth_token_email != requested_user_email:
        # Block cross-user access
        logger.warning(f"Access denied: {auth_token_email} → {requested_user_email}")
        return None
    # ...
```

### Transport Security

- **Development**: `OAUTHLIB_INSECURE_TRANSPORT=1` allows http://
- **Production**: Must use HTTPS for OAuth callbacks
- **Callback URI**: Configure in Google Cloud Console

## Troubleshooting

### Invalid Grant Errors

**Symptom**: "invalid_grant" error during token exchange

**Causes**:
1. Code already used
2. Code expired (10 minutes)
3. PKCE validation failed
4. Redirect URI mismatch

**Solutions**:
1. Restart auth flow from beginning
2. Verify redirect URI matches exactly
3. Check PKCE code_verifier is correctly stored and retrieved

### Token Refresh Failures

**Symptom**: "Token refresh failed" errors

**Causes**:
1. Refresh token revoked by user
2. Refresh token expired (6 months inactivity)
3. OAuth client credentials changed

**Solutions**:

**For Local Storage**:
```bash
# Delete credential file and reauthenticate
rm .credentials/user@gmail.com.json
```

**For S3 Storage**:
```bash
# Delete credential file from S3 and reauthenticate
aws s3 rm s3://your-bucket/credentials/user@gmail.com.json
```

**Common to Both**:
1. Check OAuth client credentials are correct
2. Ensure user hasn't revoked app access in Google account settings
3. Restart server to clear service cache

### Scope Errors

**Symptom**: "insufficient scopes" or "scope mismatch" errors

**Causes**:
1. Requested scope not granted during auth
2. Tool requires scope not in original auth flow
3. Scope name typo

**Solutions**:
1. Reauthenticate with correct scopes
2. Check scope is in `SCOPES` list
3. Verify scope URLs are correct

### Session Not Found

**Symptom**: "No session found" in OAuth 2.1 mode

**Causes**:
1. Bearer token invalid or expired
2. Session expired (server restart)
3. User never authenticated

**Solutions**:
1. Check bearer token is valid JWT
2. Complete OAuth flow to create session
3. Verify token in Authorization header

### CORS Errors (Browser Clients)

**Symptom**: CORS errors in browser console

**Causes**:
1. OAuth 2.1 not enabled
2. Server not in streamable-http mode
3. Origin not in allowed list

**Solutions**:
1. Enable OAuth 2.1: `MCP_ENABLE_OAUTH21=true`
2. Use streamable-http transport
3. Check CORS middleware configuration

### S3 Storage Issues

**Symptom**: "AWS credentials not found" or "NoCredentialsError"

**Causes**:
1. AWS credentials not configured
2. IAM role not attached to instance
3. Credentials file missing or invalid

**Solutions**:
```bash
# Option 1: Set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"

# Option 2: Configure AWS credentials file
aws configure

# Option 3: Verify IAM role (on EC2/ECS)
aws sts get-caller-identity
```

---

**Symptom**: "NoSuchBucket" error

**Causes**:
1. S3 bucket doesn't exist
2. Bucket name typo in configuration
3. Wrong AWS region

**Solutions**:
```bash
# Verify bucket exists
aws s3 ls s3://your-bucket/

# Create bucket if needed
aws s3 mb s3://your-bucket --region us-east-1

# Check GOOGLE_MCP_CREDENTIALS_DIR is correct
echo $GOOGLE_MCP_CREDENTIALS_DIR
```

---

**Symptom**: "AccessDenied" or "403 Forbidden" errors

**Causes**:
1. Insufficient IAM permissions
2. Bucket policy blocking access
3. Using wrong AWS account/credentials

**Solutions**:
```bash
# Verify IAM permissions
aws s3 ls s3://your-bucket/

# Test write permission
echo "test" | aws s3 cp - s3://your-bucket/test.txt

# Check IAM policy includes required permissions:
# - s3:GetObject
# - s3:PutObject
# - s3:DeleteObject
# - s3:ListBucket
```

**Required IAM Policy** (attach to user or role):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

---

**Symptom**: "Failed to parse JSON" from S3

**Causes**:
1. Corrupted credential file in S3
2. Manual file upload with wrong encoding
3. Incomplete file write

**Solutions**:
```bash
# Download and inspect file
aws s3 cp s3://your-bucket/credentials/user@gmail.com.json - | python -m json.tool

# Delete corrupted file and reauthenticate
aws s3 rm s3://your-bucket/credentials/user@gmail.com.json

# Check S3 versioning if enabled
aws s3api list-object-versions --bucket your-bucket --prefix credentials/
```

---

**Symptom**: Slow credential loading from S3

**Causes**:
1. High network latency to S3
2. S3 bucket in wrong region
3. Not using VPC endpoints

**Solutions**:
```bash
# Use S3 bucket in same region as server
export AWS_REGION="us-east-1"  # Match server region

# Configure VPC endpoint for private S3 access (no internet latency)
# Create VPC endpoint in AWS console

# Enable service caching (30-minute TTL reduces S3 calls)
# This is enabled by default - credentials cached after first load
```

See [Configuration Guide - S3 Credential Storage](../docs/configuration.md#s3-credential-storage) for detailed S3 setup instructions.
