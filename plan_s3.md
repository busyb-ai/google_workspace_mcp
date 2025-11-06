# S3 Credential Storage Implementation Plan

## Overview

Add support for storing Google OAuth credentials in AWS S3 in addition to the existing local file system storage. The implementation will detect whether the configured path is an S3 path or local path and handle operations accordingly.

## Goals

1. Support S3 storage for credentials using `s3://bucket-name/path/` format
2. Maintain backward compatibility with existing local file storage
3. Use boto3 for all S3 interactions
4. Ensure all credential operations (save, load, list, delete) work with both storage types
5. Provide clear error handling for S3 operations
6. Document configuration and setup requirements

## Architecture Changes

### 1. New Module: `auth/s3_storage.py`

Create a new module to encapsulate all S3-related operations. This keeps S3 logic isolated and maintainable.

**Functions to implement:**

```python
def is_s3_path(path: str) -> bool:
    """Check if a path is an S3 path (starts with s3://)"""

def parse_s3_path(s3_path: str) -> tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)"""

def s3_upload_json(s3_path: str, data: dict) -> None:
    """Upload JSON data to S3 path"""

def s3_download_json(s3_path: str) -> dict:
    """Download and parse JSON from S3 path"""

def s3_list_json_files(s3_dir: str) -> list[str]:
    """List all .json files in an S3 directory"""

def s3_file_exists(s3_path: str) -> bool:
    """Check if a file exists in S3"""

def s3_delete_file(s3_path: str) -> None:
    """Delete a file from S3"""

def get_s3_client():
    """Get configured boto3 S3 client (cached)"""
```

**Key implementation details:**

- Use boto3 with standard AWS credential chain (env vars, IAM roles, etc.)
- Handle S3 exceptions gracefully with meaningful error messages
- Add logging for all S3 operations
- Cache S3 client instance to avoid repeated initialization
- Set appropriate content type (application/json) for credential files
- Consider using server-side encryption (SSE) for security

### 2. Update `auth/google_auth.py`

Modify existing credential functions to support both local and S3 storage:

#### `save_credentials_to_file()` (line 125-149)

**Current behavior:** Saves to local file system

**New behavior:**
```python
def save_credentials_to_file(
    user_google_email: str,
    credentials: Credentials,
    base_dir: str = DEFAULT_CREDENTIALS_DIR,
):
    """Saves user credentials to a file or S3."""
    creds_path = _get_user_credential_path(user_google_email, base_dir)
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }

    try:
        if is_s3_path(creds_path):
            # Upload to S3
            s3_upload_json(creds_path, creds_data)
            logger.info(f"Credentials saved for user {user_google_email} to S3: {creds_path}")
        else:
            # Save to local file (existing logic)
            with open(creds_path, "w") as f:
                json.dump(creds_data, f)
            logger.info(f"Credentials saved for user {user_google_email} to {creds_path}")
    except Exception as e:
        logger.error(
            f"Error saving credentials for user {user_google_email} to {creds_path}: {e}"
        )
        raise
```

#### `load_credentials_from_file()` (line 183-228)

**Current behavior:** Loads from local file system

**New behavior:**
```python
def load_credentials_from_file(
    user_google_email: str, base_dir: str = DEFAULT_CREDENTIALS_DIR
) -> Optional[Credentials]:
    """Loads user credentials from a file or S3."""
    creds_path = _get_user_credential_path(user_google_email, base_dir)

    try:
        if is_s3_path(creds_path):
            # Check if file exists in S3
            if not s3_file_exists(creds_path):
                logger.info(
                    f"No credentials file found for user {user_google_email} in S3: {creds_path}"
                )
                return None

            # Download from S3
            creds_data = s3_download_json(creds_path)
        else:
            # Load from local file (existing logic)
            if not os.path.exists(creds_path):
                logger.info(
                    f"No credentials file found for user {user_google_email} at {creds_path}"
                )
                return None

            with open(creds_path, "r") as f:
                creds_data = json.load(f)

        # Parse expiry and create Credentials object (existing logic)
        # ...

    except Exception as e:
        logger.error(
            f"Error loading or parsing credentials for user {user_google_email} from {creds_path}: {e}"
        )
        return None
```

#### `_find_any_credentials()` (line 74-112)

**Current behavior:** Lists local directory for credential files

**New behavior:**
```python
def _find_any_credentials(
    base_dir: str = DEFAULT_CREDENTIALS_DIR,
) -> Optional[Credentials]:
    """
    Find and load any valid credentials from the credentials directory (local or S3).
    Used in single-user mode to bypass session-to-OAuth mapping.
    """
    try:
        if is_s3_path(base_dir):
            # List S3 files
            json_files = s3_list_json_files(base_dir)
            if not json_files:
                logger.info(f"[single-user] No credentials found in S3: {base_dir}")
                return None

            # Try to load each file
            for s3_key in json_files:
                try:
                    creds_data = s3_download_json(f"s3://{s3_key}")
                    credentials = Credentials(
                        token=creds_data.get("token"),
                        refresh_token=creds_data.get("refresh_token"),
                        token_uri=creds_data.get("token_uri"),
                        client_id=creds_data.get("client_id"),
                        client_secret=creds_data.get("client_secret"),
                        scopes=creds_data.get("scopes"),
                    )
                    logger.info(f"[single-user] Found credentials in S3: {s3_key}")
                    return credentials
                except Exception as e:
                    logger.warning(
                        f"[single-user] Error loading credentials from S3 {s3_key}: {e}"
                    )
                    continue
        else:
            # Existing local file logic
            # ...
    except Exception as e:
        logger.error(f"[single-user] Error finding credentials: {e}")
        return None
```

#### `_get_user_credential_path()` (line 115-122)

**Current behavior:** Creates local directory if needed

**New behavior:**
```python
def _get_user_credential_path(
    user_google_email: str, base_dir: str = DEFAULT_CREDENTIALS_DIR
) -> str:
    """Constructs the path to a user's credential file (local or S3)."""
    if is_s3_path(base_dir):
        # For S3, just append the filename (no directory creation needed)
        # Ensure base_dir ends with / for proper path joining
        if not base_dir.endswith('/'):
            base_dir += '/'
        return f"{base_dir}{user_google_email}.json"
    else:
        # Local file system - create directory if needed
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            logger.info(f"Created credentials directory: {base_dir}")
        return os.path.join(base_dir, f"{user_google_email}.json")
```

### 3. Update `auth/oauth_common_handlers.py`

The file already uses `save_credentials_to_file()` on line 210, so no changes needed. It will automatically support S3 once the function is updated.

### 4. Add boto3 Dependency

Update `pyproject.toml` to include boto3:

```toml
dependencies = [
    # ... existing dependencies ...
    "boto3>=1.34.0",
]
```

### 5. Environment Variables

Add support for AWS credentials via standard boto3 environment variables:

**Required (if not using IAM roles):**
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key

**Optional:**
- `AWS_REGION` - AWS region (default: us-east-1)
- `AWS_SESSION_TOKEN` - For temporary credentials
- `AWS_PROFILE` - Named profile from ~/.aws/credentials

**Existing variable with new behavior:**
- `GOOGLE_MCP_CREDENTIALS_DIR` - Can now be set to `s3://bucket-name/path/`

**Example configurations:**

Local storage (current behavior):
```bash
GOOGLE_MCP_CREDENTIALS_DIR=/home/user/.google_workspace_mcp/credentials
```

S3 storage (new):
```bash
GOOGLE_MCP_CREDENTIALS_DIR=s3://my-bucket/google-workspace-credentials/
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
```

Using IAM roles (EC2, ECS, Lambda):
```bash
GOOGLE_MCP_CREDENTIALS_DIR=s3://my-bucket/google-workspace-credentials/
# No AWS credentials needed - uses instance role
```

## Implementation Steps

### Phase 1: Core S3 Utilities (Day 1)

1. Create `auth/s3_storage.py` module
2. Implement path detection and parsing functions
3. Implement S3 client initialization with boto3
4. Implement S3 JSON upload/download functions
5. Implement S3 list and exists functions
6. Add comprehensive error handling and logging
7. Add unit tests for S3 utilities (optional)

**Files to create:**
- `auth/s3_storage.py`

### Phase 2: Update Credential Functions (Day 1-2)

1. Update `save_credentials_to_file()` to detect and handle S3 paths
2. Update `load_credentials_from_file()` to detect and handle S3 paths
3. Update `_find_any_credentials()` to handle S3 directories
4. Update `_get_user_credential_path()` to handle S3 paths
5. Test all credential operations with both local and S3 paths

**Files to modify:**
- `auth/google_auth.py`

### Phase 3: Dependencies and Configuration (Day 2)

1. Add boto3 to `pyproject.toml`
2. Run `uv sync` to update dependencies
3. Test that boto3 imports correctly

**Files to modify:**
- `pyproject.toml`

### Phase 4: Documentation (Day 2)

1. Update `docs/configuration.md` with S3 setup instructions
2. Update `docs/authentication.md` with S3 credential storage details
3. Update `README.md` with S3 configuration examples

**Files to modify:**
- `docs/configuration.md`
- `docs/authentication.md`
- `README.md`
- `CLAUDE.md` (if needed)

### Phase 5: Testing (Day 3)

1. Test local file storage (regression test)
2. Test S3 storage with real AWS account
3. Test path detection and switching
4. Test error scenarios (missing credentials, network errors)
5. Test OAuth 2.1 mode with S3

## Error Handling

### S3-Specific Errors to Handle

1. **NoSuchBucket**: Bucket doesn't exist
   - Error message: "S3 bucket '{bucket}' does not exist"
   - Suggestion: "Verify bucket name and ensure it exists"

2. **AccessDenied**: Insufficient permissions
   - Error message: "Access denied to S3 path '{path}'"
   - Suggestion: "Check AWS credentials and S3 bucket permissions"

3. **NoCredentialsError**: AWS credentials not found
   - Error message: "AWS credentials not configured"
   - Suggestion: "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or use IAM roles"

4. **EndpointConnectionError**: Network issues
   - Error message: "Cannot connect to S3"
   - Suggestion: "Check network connectivity and AWS region"

5. **NoSuchKey**: File doesn't exist
   - Treat as file not found (same as local storage)

### Graceful Degradation

- If S3 operations fail, log detailed error but don't crash the application
- Provide clear error messages that guide users to fix configuration
- For read operations, return None (same as file not found)
- For write operations, raise exception with actionable error message

## Security Considerations

### S3 Security Best Practices

1. **Server-Side Encryption**: Enable SSE-S3 for credential files
2. **Bucket Permissions**: Use least-privilege IAM policies
3. **Private Buckets**: Ensure credentials bucket is not public
4. **IAM Roles**: Prefer IAM roles over access keys when possible
5. **Audit Logging**: Enable S3 access logging for compliance

### Recommended IAM Policy

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
        "arn:aws:s3:::your-bucket-name/google-workspace-credentials/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

## Testing Checklist

### Local Storage (Regression)
- [ ] Save credentials to local file
- [ ] Load credentials from local file
- [ ] Find any credentials in local directory
- [ ] Single-user mode with local storage
- [ ] OAuth 2.1 with local storage

### S3 Storage (New)
- [ ] Save credentials to S3
- [ ] Load credentials from S3
- [ ] Find any credentials in S3 bucket
- [ ] Single-user mode with S3
- [ ] OAuth 2.1 with S3

### Error Scenarios
- [ ] Invalid S3 path format
- [ ] Missing AWS credentials
- [ ] Non-existent S3 bucket
- [ ] Insufficient S3 permissions
- [ ] Network connectivity issues
- [ ] Corrupted credential files

### Edge Cases
- [ ] Switch from local to S3 storage
- [ ] Switch from S3 to local storage
- [ ] Empty credential directories
- [ ] Multiple users with S3 storage
- [ ] Concurrent access to S3 credentials

## Documentation Updates

### docs/configuration.md

Add new section: "S3 Credential Storage"

```markdown
## S3 Credential Storage

The server supports storing OAuth credentials in AWS S3 instead of local file system.

### Configuration

Set the credentials directory to an S3 path:

```bash
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket/google-workspace-credentials/"
```

### AWS Credentials

Configure AWS credentials using one of these methods:

1. **Environment Variables**:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

2. **IAM Roles** (recommended for EC2/ECS/Lambda):
No credentials needed - automatically uses instance role

3. **AWS Credentials File** (~/.aws/credentials):
```ini
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
region = us-east-1
```

### S3 Bucket Setup

1. Create S3 bucket:
```bash
aws s3 mb s3://your-bucket
```

2. Enable encryption:
```bash
aws s3api put-bucket-encryption \
  --bucket your-bucket \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

3. Set bucket policy (private):
```bash
aws s3api put-public-access-block \
  --bucket your-bucket \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### Troubleshooting S3 Storage

**Error: "AWS credentials not configured"**
- Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
- Or use IAM roles for EC2/ECS/Lambda

**Error: "S3 bucket does not exist"**
- Create bucket: `aws s3 mb s3://your-bucket`
- Verify bucket name is correct

**Error: "Access denied to S3 path"**
- Check IAM permissions include s3:GetObject, s3:PutObject, s3:ListBucket
- Verify bucket policy allows access
```

### docs/authentication.md

Update "Credential Storage" section:

```markdown
## Credential Storage

### Storage Locations

Credentials can be stored in two locations:

1. **Local File System** (default):
   - Directory: `~/.google_workspace_mcp/credentials/`
   - Format: `{email}.json`
   - Permissions: 0600 (owner read/write only)

2. **AWS S3**:
   - Path: `s3://bucket-name/path/`
   - Format: `{email}.json`
   - Encryption: SSE-S3 or SSE-KMS
   - Access: IAM-controlled

### Configuring S3 Storage

To use S3 storage, set the credentials directory to an S3 path:

```bash
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket/credentials/"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

The server will automatically detect S3 paths and use boto3 for storage operations.
```

## Rollback Plan

If S3 integration causes issues:

1. **Quick Rollback**: Set `GOOGLE_MCP_CREDENTIALS_DIR` back to local path
2. **Code Rollback**: The changes are isolated in `auth/s3_storage.py` and `auth/google_auth.py`
3. **Remove boto3**: Run `uv remove boto3` if needed

## Success Criteria

- [ ] All existing functionality works with local storage (no regression)
- [ ] Credentials can be saved to and loaded from S3
- [ ] S3 path detection works correctly
- [ ] Error handling provides clear, actionable messages
- [ ] Documentation is complete and accurate
- [ ] Code follows existing patterns and style
- [ ] No security vulnerabilities introduced
- [ ] boto3 dependency added successfully

## Timeline Estimate

- **Phase 1** (Core S3 Utilities): 4-6 hours
- **Phase 2** (Update Functions): 4-6 hours
- **Phase 3** (Dependencies): 1 hour
- **Phase 4** (Documentation): 2-3 hours
- **Phase 5** (Testing): 3-4 hours

**Total Estimate**: 14-20 hours (2-3 days)

## Notes

- Keep S3 logic isolated in separate module for maintainability
- Use standard boto3 patterns and best practices
- Ensure backward compatibility is maintained
- Add comprehensive logging for troubleshooting
- Consider adding metrics/monitoring for S3 operations (future enhancement)
- Document all environment variables clearly
- Test with real AWS account before considering complete
